"""Lesende Subscription-Service-Funktionen."""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import (
    Subscription,
    SubscriptionBillingHistory,
    SubscriptionPauseHistory,
    SubscriptionPriceHistory,
    SubscriptionScheduledPayment,
    SubscriptionStatus,
)
from app.schemas.subscription import SubscriptionDetail, SubscriptionRead

from .access import _check_ownership, _get_subscription_or_raise
from .billing import (
    applicable_billing_terms,
    compute_dieses_kalenderjahr,
    compute_intervalle,
    compute_next_due_date,
    compute_next_due_date_from_history,
    compute_tatsaechlich,
)
from .constants import _MONTHLY_FACTOR, _MONTHS_PER_PERIOD
from .types import OverviewResult


def subscription_to_read(
    sub: Subscription,
    billing_history: list | None = None,
) -> SubscriptionRead:
    """
    Konvertiert ein Subscription-ORM-Objekt in SubscriptionRead mit berechnetem next_due_date.

    next_due_date ist keine DB-Spalte — ohne diese Hilfsfunktion bleibt das Feld
    immer None, weil model_validate() nur echte ORM-Attribute liest (BUG-01).

    billing_history (v0.2.4):
      Wenn uebergeben, wird next_due_date aus der Billing-Historie berechnet —
      das ist korrekt auch nach Intervallwechseln (neuer Anker).
      Wenn None oder leer, Fallback auf sub.started_on + sub.interval (Snapshot-Felder).
    """
    read = SubscriptionRead.model_validate(sub)
    today = date.today()
    cached_next_due = getattr(sub, "_computed_next_due_date", None)
    if cached_next_due is not None:
        read.next_due_date = cached_next_due
    elif billing_history:
        # Billing-Historie vorhanden: Segmentrechnung beruecksichtigt alle Anker und Intervalle
        read.next_due_date = compute_next_due_date_from_history(billing_history, today)
    else:
        # Fallback: snapshot-Felder nutzen (korrekt solange kein Intervallwechsel stattfand)
        read.next_due_date = compute_next_due_date(sub.started_on, _MONTHS_PER_PERIOD[sub.interval])
    return read


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurueck, sortiert nach Faelligkeitsdatum.

    Gibt alle Status zurueck (active, suspended, canceled) — die UI kann filtern.
    Sortierung: Billing-Historie per Bulk-Load vorladen, dann compute_next_due_date_from_history.
    Bulk-Load verhindert N+1-Abfragen (eine Query fuer alle Historien, nicht eine pro Abo).
    """
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    subs = list(session.execute(stmt).scalars().all())
    if not subs:
        return []

    # Billing-Historie fuer alle Abos auf einmal laden
    all_ids = [s.id for s in subs]
    all_bh = session.execute(
        select(SubscriptionBillingHistory).where(SubscriptionBillingHistory.subscription_id.in_(all_ids))
    ).scalars().all()
    bh_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for e in all_bh:
        bh_by_sub[e.subscription_id].append(e)

    today = date.today()
    # Nach berechnetem Faelligkeitsdatum sortieren — naechste Faelligkeit zuerst
    for sub in subs:
        # Merken, damit die Router-Response nicht wieder auf started_on + Snapshot-Intervall
        # zurueckfaellt und Intervallwechsel in Listenansichten verliert.
        sub._computed_next_due_date = compute_next_due_date_from_history(bh_by_sub[sub.id], today)

    return sorted(
        subs,
        key=lambda s: s._computed_next_due_date,
    )


def get_overview(session: Session, user_id: uuid.UUID) -> OverviewResult:
    """
    Berechnet die monatliche Gesamtsumme und die naechsten faelligen Abos.

    monthly_total: Summe aller aktiven Abo-Betraege, auf Monatsbasis normiert.
                   Abos mit started_on in der Zukunft zaehlen nicht (L-09).
    upcoming:      Aktive Abos, die in den naechsten 30 Tagen faellig werden.
    """
    subs = list_subscriptions(session, user_id)
    today = date.today()

    # Aktive Abos die bereits gestartet sind — Zukunfts-Abos fliessen nicht in die Summe (L-09)
    active_subs = [s for s in subs if s.status == SubscriptionStatus.active and s.started_on <= today]

    # Billing-Historie fuer alle aktiven Abos auf einmal laden (ersetzt Preishistorie).
    # Ohne Bulk-Load waere es N+1 — eine DB-Abfrage pro Abo.
    active_ids = [s.id for s in active_subs]
    all_bh = session.execute(
        select(SubscriptionBillingHistory).where(SubscriptionBillingHistory.subscription_id.in_(active_ids))
    ).scalars().all()
    bh_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for e in all_bh:
        bh_by_sub[e.subscription_id].append(e)

    # Monatliche Gesamtsumme: Betrag und Intervall aus den heute gueltigen Billing Terms.
    # applicable_billing_terms() waehlt den neuesten Eintrag mit valid_from <= today.
    monthly_total = Decimal("0")
    for s in active_subs:
        terms = applicable_billing_terms(today, bh_by_sub[s.id])
        if terms is not None:
            monthly_total += terms.amount * _MONTHLY_FACTOR[terms.interval]

    # Upcoming: aktive Abos, deren naechster Faelligkeitstag in den naechsten 30 Tagen liegt.
    cutoff = today + timedelta(days=30)
    upcoming = [
        s for s in active_subs if today <= compute_next_due_date_from_history(bh_by_sub[s.id], today) <= cutoff
    ]

    return OverviewResult(monthly_total=monthly_total, upcoming=upcoming)


def get_subscription(session: Session, subscription_id: uuid.UUID, user_id: uuid.UUID) -> Subscription:
    """
    Gibt ein einzelnes Abo zurueck.

    Neu in v0.2.2 — wird von der Detailseite genutzt (Slice C).
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)
    return sub


def get_subscription_detail(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SubscriptionDetail:
    """
    Gibt ein Abo mit allen berechneten Kostenkennzahlen zurueck (v0.2.3).

    Alle vier Kennzahlen (monatlich, tatsaechlich, intervalle, dieses_kalenderjahr)
    werden frisch aus Preis- und Pausenhistorie berechnet — keine Werte aus der DB.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Billing-Historie laden (ersetzt Preishistorie ab v0.2.4)
    billing_hist = list(
        session.execute(
            select(SubscriptionBillingHistory)
            .where(SubscriptionBillingHistory.subscription_id == subscription_id)
            .order_by(SubscriptionBillingHistory.valid_from)
        ).scalars().all()
    )

    # Pausenhistorie laden — alle Pausen dieses Abos
    pause_hist = list(
        session.execute(
            select(SubscriptionPauseHistory).where(SubscriptionPauseHistory.subscription_id == subscription_id)
        ).scalars().all()
    )

    today = date.today()

    # Aktuell gueltige Billing Terms — fuer monatlich-Kennzahl
    # applicable_billing_terms() liefert Betrag und Intervall zusammen
    current_terms = applicable_billing_terms(today, billing_hist)
    if current_terms is not None:
        monatlich = (current_terms.amount * _MONTHLY_FACTOR[current_terms.interval]).quantize(Decimal("0.01"))
    else:
        monatlich = Decimal("0")

    tatsaechlich = compute_tatsaechlich(billing_hist, pause_hist)
    intervalle = compute_intervalle(billing_hist, pause_hist)
    dieses_kj = compute_dieses_kalenderjahr(billing_hist, pause_hist)
    next_due = compute_next_due_date_from_history(billing_hist, today)

    # Erst Basisfelder aus dem ORM lesen, dann berechnete Pflichtfelder ergaenzen
    # und als komplettes Payload gegen SubscriptionDetail validieren.
    detail_payload = SubscriptionRead.model_validate(sub, from_attributes=True).model_dump()
    detail_payload["next_due_date"] = next_due
    detail_payload["monatlich"] = monatlich
    detail_payload["tatsaechlich"] = tatsaechlich
    detail_payload["intervalle"] = intervalle
    detail_payload["dieses_kalenderjahr"] = dieses_kj

    return SubscriptionDetail.model_validate(detail_payload)


def get_price_history(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionPriceHistory]:
    """
    Gibt die Preishistorie eines Abos zurueck, absteigend nach Datum (neueste zuerst).

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    stmt = (
        select(SubscriptionPriceHistory)
        .where(SubscriptionPriceHistory.subscription_id == subscription_id)
        # Neuester Eintrag zuerst — so erscheint der aktuelle Preis oben in der UI
        .order_by(SubscriptionPriceHistory.valid_from.desc())
    )
    return list(session.execute(stmt).scalars().all())


def get_billing_history(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionBillingHistory]:
    """
    Gibt die Billing-Historie eines Abos zurueck, absteigend nach Datum (neueste zuerst).

    Jeder Eintrag beschreibt ab wann (valid_from) welcher Betrag, welches Intervall
    und welcher Faelligkeitsanker (anchor_on) gilt.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    return list(
        session.execute(
            select(SubscriptionBillingHistory)
            .where(SubscriptionBillingHistory.subscription_id == subscription_id)
            # Neuester Eintrag zuerst — aktuelle Konditionen erscheinen oben in der UI
            .order_by(SubscriptionBillingHistory.valid_from.desc())
        ).scalars().all()
    )


def get_scheduled_payments(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionScheduledPayment]:
    """
    Gibt alle Soll-Buchungen eines Abos zurueck, absteigend nach Faelligkeitsdatum.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    stmt = (
        select(SubscriptionScheduledPayment)
        .where(SubscriptionScheduledPayment.subscription_id == subscription_id)
        # Neueste Buchung zuerst — so sieht der User die aktuellsten Eintraege oben
        .order_by(SubscriptionScheduledPayment.due_date.desc())
    )
    return list(session.execute(stmt).scalars().all())
