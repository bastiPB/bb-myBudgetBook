"""
app/services/subscriptions.py — Business-Logik für Abo-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle Funktionen prüfen: darf dieser User dieses Abo sehen / ändern?
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, InvalidSubscriptionStatusError, SubscriptionNotFoundError
from app.models.subscription import BillingInterval, Subscription, SubscriptionPriceHistory, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SuspendPayload

# Umrechnungsfaktoren: wie viel eines Abo-Betrags fällt pro Monat an?
# monthly   → voller Betrag pro Monat
# quarterly → Betrag geteilt durch 3 (Quartal = 3 Monate)
# yearly    → Betrag geteilt durch 12
# biennial  → Betrag geteilt durch 24 (2 Jahre = 24 Monate)
_MONTHLY_FACTOR: dict[BillingInterval, Decimal] = {
    BillingInterval.monthly:   Decimal("1"),
    BillingInterval.quarterly: Decimal("1") / Decimal("3"),
    BillingInterval.yearly:    Decimal("1") / Decimal("12"),
    BillingInterval.biennial:  Decimal("1") / Decimal("24"),
}


def _get_subscription_or_raise(session: Session, subscription_id: uuid.UUID) -> Subscription:
    """
    Hilfsfunktion: Abo laden und 404 werfen wenn es nicht existiert.

    Wird von mehreren Service-Funktionen verwendet um Duplikate zu vermeiden.
    """
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()
    return sub


def _check_ownership(sub: Subscription, user_id: uuid.UUID) -> None:
    """
    Hilfsfunktion: Prüft ob das Abo dem angegebenen User gehört.

    Wirft ForbiddenError wenn nicht — so kann kein User fremde Abos bearbeiten.
    """
    if sub.user_id != user_id:
        raise ForbiddenError()


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurück, sortiert nach Fälligkeitsdatum.

    Gibt alle Status zurück (active, suspended, canceled) — die UI kann filtern.
    Wichtig: die WHERE-Klausel stellt sicher, dass ein User niemals Abos
    anderer User sehen kann — auch wenn er eine fremde ID kennt.
    """
    stmt = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.next_due_date)
    )
    return list(session.execute(stmt).scalars().all())


@dataclass
class OverviewResult:
    """Zwischenergebnis für den Übersicht-Endpunkt — kein HTTP, nur Daten."""

    monthly_total: Decimal
    upcoming: list[Subscription]


def get_overview(session: Session, user_id: uuid.UUID) -> OverviewResult:
    """
    Berechnet die monatliche Gesamtsumme und die nächsten fälligen Abos.

    monthly_total: Summe aller aktiven Abo-Beträge (suspended/canceled zählen nicht mehr).
    upcoming:      Aktive Abos, deren next_due_date innerhalb der nächsten 30 Tage liegt.
    """
    subs = list_subscriptions(session, user_id)

    # Nur aktive Abos in die Berechnung einbeziehen — suspendierte kosten nichts mehr
    active_subs = [s for s in subs if s.status == SubscriptionStatus.active]

    # Jeden Betrag auf Monatsbasis umrechnen und aufaddieren.
    # Beispiel: 89.90 € jährlich → 89.90 / 12 = 7.49 € monatlich
    monthly_total = sum(
        (s.amount * _MONTHLY_FACTOR[s.interval] for s in active_subs),
        Decimal("0"),
    )

    # Abos filtern: nur aktive, die in den nächsten 30 Tagen fällig werden
    today = date.today()
    cutoff = today + timedelta(days=30)
    upcoming = [s for s in active_subs if today <= s.next_due_date <= cutoff]

    return OverviewResult(monthly_total=monthly_total, upcoming=upcoming)


def get_subscription(session: Session, subscription_id: uuid.UUID, user_id: uuid.UUID) -> Subscription:
    """
    Gibt ein einzelnes Abo zurück.

    Neu in v0.2.2 — wird von der Detailseite genutzt (Slice C).
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)
    return sub


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    payload: SubscriptionCreate,
) -> Subscription:
    """
    Legt ein neues Abo für den eingeloggten User an.

    Die user_id kommt aus der Session (eingeloggter User), nicht aus der Anfrage —
    so kann ein User kein Abo unter fremdem Namen anlegen.

    started_on: wenn nicht angegeben, wird das heutige Datum verwendet.
    """
    # started_on aus dem Payload nehmen, oder heute als Fallback
    started_on = payload.started_on if payload.started_on is not None else date.today()

    sub = Subscription(
        user_id=user_id,
        name=payload.name,
        amount=payload.amount,
        next_due_date=payload.next_due_date,
        interval=payload.interval,
        started_on=started_on,
        notes=payload.notes,
        # status, logo_url, suspended_at, access_until — SQLAlchemy-Defaults greifen
    )
    session.add(sub)
    session.flush()  # flush statt commit: sub.id ist jetzt verfügbar, Transaktion noch offen

    # Initialen Preis sofort in die Preishistorie schreiben.
    #
    # Warum hier und nicht erst beim ersten update?
    # Ohne diesen Eintrag ist der Startpreis nach der ersten Preisänderung unwiederbringlich verloren:
    #   Anlage:    9,99 € — kein Eintrag in history → nach Änderung auf 12,99 € unbekannt
    #   1. Änderung → {12,99, März}
    #   2. Änderung → {14,99, Mai}
    # History: [{12.99, März}, {14.99, Mai}] — Jan–Feb fehlen komplett
    #
    # Mit diesem Fix:
    # History: [{9.99, started_on}, {12.99, März}, {14.99, Mai}] → lückenlose Zeitleiste
    # valid_from = started_on (nicht heute) damit rückwirkende Abos korrekt erfasst werden.
    _record_price_change(session, sub, sub.amount, valid_from=started_on)

    session.commit()
    session.refresh(sub)
    return sub


def _record_price_change(
    session: Session,
    sub: Subscription,
    new_amount: Decimal,
    valid_from: date | None = None,
) -> None:
    """
    Schreibt einen Preishistorie-Eintrag.

    Wird von zwei Stellen gerufen:
    - create_subscription: initialer Eintrag mit valid_from = started_on
    - update_subscription: Änderungseintrag mit valid_from = heute (Standard)

    Warum valid_from als Parameter?
    Beim Anlegen eines Abos soll der Startpreis ab dem Abschlussdatum (started_on) gelten,
    nicht ab dem heutigen Tag — sonst klafft eine Lücke in der Zeitleiste für rückwirkende Abos.

    Semantik der Tabelle (valid_from-only-Design):
    Jeder Eintrag bedeutet „ab diesem Datum gilt Preis X".
    Aufeinanderfolgende Einträge bilden eine lückenlose Zeitleiste:
      {9.99, 2026-01-01} → {12.99, 2026-03-01} → {14.99, 2026-05-01}
    Slice E kann daraus den kumulierten Betrag korrekt berechnen.

    Kein API-Endpoint in v0.2.2 — die Daten laufen still mit.
    """
    entry = SubscriptionPriceHistory(
        subscription_id=sub.id,
        amount=new_amount,
        # Explizites Datum wenn übergeben (Abschluss), sonst heute (Änderung)
        valid_from=valid_from if valid_from is not None else date.today(),
    )
    session.add(entry)


def update_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SubscriptionUpdate,
) -> Subscription:
    """
    Aktualisiert ein bestehendes Abo.

    Nur Felder die im Request-Body standen (payload.model_fields_set) werden geändert.
    Wenn sich amount ändert, wird ein Eintrag in subscription_price_history geschrieben.
    notes kann damit auch explizit auf null gesetzt werden ({ "notes": null }).
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Wenn amount sich ändert: neuen Preis ab heute in der Preishistorie festhalten.
    # Semantik: jeder Eintrag sagt "ab valid_from gilt Preis X" — so entsteht eine Zeitleiste.
    # Wir prüfen: payload.amount ist gesetzt UND unterscheidet sich vom aktuellen Wert.
    if payload.amount is not None and payload.amount != sub.amount:
        _record_price_change(session, sub, payload.amount)

    # Nur die Felder aktualisieren, die der User tatsächlich mitgeschickt hat.
    #
    # Warum model_fields_set statt "if payload.x is not None"?
    # Bei Optional-Feldern bedeutet None zweierlei:
    #   - "nicht mitgeschickt" (Feld fehlt im JSON)  → soll nichts ändern
    #   - "explizit null"       ({ "notes": null })   → soll Feld leeren
    # model_fields_set enthält nur die Felder, die im Request-Body standen.
    # Damit kann man "nicht gesendet" und "auf null setzen" sauber unterscheiden.
    for field in payload.model_fields_set:
        setattr(sub, field, getattr(payload, field))

    session.commit()
    session.refresh(sub)
    return sub


def suspend_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SuspendPayload,
) -> Subscription:
    """
    Setzt ein Abo auf 'suspended'.

    Soft-Lifecycle: das Abo bleibt in der DB — keine Daten gehen verloren.
    Nur aktive Abos können suspendiert werden (409 wenn bereits suspended/canceled).

    suspended_at: wird auf heute gesetzt
    access_until: optional — bis wann ist die Leistung noch nutzbar?
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur aktive Abos können suspendiert werden
    if sub.status != SubscriptionStatus.active:
        raise InvalidSubscriptionStatusError(
            f"Nur aktive Abos können suspendiert werden. Aktueller Status: {sub.status.value}"
        )

    # Status-Wechsel durchführen
    sub.status = SubscriptionStatus.suspended
    sub.suspended_at = date.today()
    sub.access_until = payload.access_until  # kann None sein — ist OK

    session.commit()
    session.refresh(sub)
    return sub


def resume_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Subscription:
    """
    Setzt ein suspendiertes Abo wieder auf 'active'.

    Nur suspended darf zurück auf active — active oder canceled ergeben keinen Sinn.
    suspended_at und access_until werden beim Resume geleert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur suspendierte Abos können fortgesetzt werden
    if sub.status != SubscriptionStatus.suspended:
        raise InvalidSubscriptionStatusError(
            f"Nur pausierte Abos können fortgesetzt werden. Aktueller Status: {sub.status.value}"
        )

    sub.status = SubscriptionStatus.active
    # Suspend-Felder zurücksetzen — das Abo läuft wieder normal
    sub.suspended_at = None
    sub.access_until = None

    session.commit()
    session.refresh(sub)
    return sub


def delete_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """
    Löscht ein Abo unwiderruflich (Hard Delete).

    In v0.2.2 bleibt DELETE erhalten, aber die bevorzugte Aktion ist Suspend.
    Hard Delete ist nur für Abos gedacht, bei denen wirklich keine Historie benötigt wird.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    session.delete(sub)
    session.commit()
