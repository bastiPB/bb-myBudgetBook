"""
app/services/subscriptions.py — Business-Logik für Abo-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle Funktionen prüfen: darf dieser User dieses Abo sehen / ändern?
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    BillingHistoryChangeBlockedError,
    BillingHistoryEntryNotFoundError,
    DuplicateBillingHistoryEntryError,
    ForbiddenError,
    InvalidFileError,
    InvalidSubscriptionStatusError,
    PriceEntryDeleteBlockedError,
    PriceHistoryEntryNotFoundError,
    SubscriptionNotFoundError,
)
from app.models.subscription import (
    BillingInterval,
    Subscription,
    SubscriptionBillingHistory,
    SubscriptionPauseHistory,
    SubscriptionPriceHistory,
    SubscriptionScheduledPayment,
    SubscriptionStatus,
)
from app.schemas.subscription import (
    IntervalChangeRequest,
    PriceChangeRequest,
    SubscriptionRead,
    SubscriptionCreate,
    SubscriptionDetail,
    SubscriptionUpdate,
    SuspendPayload,
)

# Umrechnungsfaktoren: wie viel eines Abo-Betrags fällt pro Monat an?
# monthly    → voller Betrag pro Monat
# quarterly  → Betrag geteilt durch 3 (Quartal = 3 Monate)
# semiannual → Betrag geteilt durch 6 (Halbjahr = 6 Monate)
# yearly     → Betrag geteilt durch 12
# biennial   → Betrag geteilt durch 24 (2 Jahre = 24 Monate)
_MONTHLY_FACTOR: dict[BillingInterval, Decimal] = {
    BillingInterval.monthly:    Decimal("1"),
    BillingInterval.quarterly:  Decimal("1") / Decimal("3"),
    BillingInterval.semiannual: Decimal("1") / Decimal("6"),
    BillingInterval.yearly:     Decimal("1") / Decimal("12"),
    BillingInterval.biennial:   Decimal("1") / Decimal("24"),
}

# Wie viele Monate stecken in einer Abrechnungsperiode?
# Wird von den Berechnungsalgorithmen genutzt um Fälligkeitsdaten zu ermitteln.
_MONTHS_PER_PERIOD: dict[BillingInterval, int] = {
    BillingInterval.monthly:    1,
    BillingInterval.quarterly:  3,
    BillingInterval.semiannual: 6,
    BillingInterval.yearly:     12,
    BillingInterval.biennial:   24,
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


def subscription_to_read(
    sub: Subscription,
    billing_history: list | None = None,
) -> SubscriptionRead:
    """
    Konvertiert ein Subscription-ORM-Objekt in SubscriptionRead mit berechnetem next_due_date.

    next_due_date ist keine DB-Spalte — ohne diese Hilfsfunktion bleibt das Feld
    immer None, weil model_validate() nur echte ORM-Attribute liest (BUG-01).

    billing_history (v0.2.4):
      Wenn übergeben, wird next_due_date aus der Billing-Historie berechnet —
      das ist korrekt auch nach Intervallwechseln (neuer Anker).
      Wenn None oder leer, Fallback auf sub.started_on + sub.interval (Snapshot-Felder).
    """
    read = SubscriptionRead.model_validate(sub)
    today = date.today()
    cached_next_due = getattr(sub, "_computed_next_due_date", None)
    if cached_next_due is not None:
        read.next_due_date = cached_next_due
    elif billing_history:
        # Billing-Historie vorhanden: Segmentrechnung berücksichtigt alle Anker und Intervalle
        read.next_due_date = compute_next_due_date_from_history(billing_history, today)
    else:
        # Fallback: snapshot-Felder nutzen (korrekt solange kein Intervallwechsel stattfand)
        read.next_due_date = compute_next_due_date(sub.started_on, _MONTHS_PER_PERIOD[sub.interval])
    return read


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurück, sortiert nach Fälligkeitsdatum.

    Gibt alle Status zurück (active, suspended, canceled) — die UI kann filtern.
    Sortierung: Billing-Historie per Bulk-Load vorladen, dann compute_next_due_date_from_history.
    Bulk-Load verhindert N+1-Abfragen (eine Query für alle Historien, nicht eine pro Abo).
    """
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    subs = list(session.execute(stmt).scalars().all())
    if not subs:
        return []

    # Billing-Historie für alle Abos auf einmal laden
    all_ids = [s.id for s in subs]
    all_bh = session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id.in_(all_ids))
    ).scalars().all()
    bh_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for e in all_bh:
        bh_by_sub[e.subscription_id].append(e)

    today = date.today()
    # Nach berechnetem Fälligkeitsdatum sortieren — nächste Fälligkeit zuerst
    for sub in subs:
        # Merken, damit die Router-Response nicht wieder auf started_on + Snapshot-Intervall
        # zurueckfaellt und Intervallwechsel in Listenansichten verliert.
        sub._computed_next_due_date = compute_next_due_date_from_history(bh_by_sub[sub.id], today)

    return sorted(
        subs,
        key=lambda s: s._computed_next_due_date,
    )


@dataclass
class OverviewResult:
    """Zwischenergebnis für den Übersicht-Endpunkt — kein HTTP, nur Daten."""

    monthly_total: Decimal
    upcoming: list[Subscription]


@dataclass
class ComputedDue:
    """
    Eine berechnete Fälligkeit aus der Billing-Historie (v0.2.4).

    Enthält nicht nur das Datum, sondern auch Betrag, Intervall und Herkunft —
    damit der Scheduler und die Kennzahl-Funktionen keine zweite Datenbankabfrage
    brauchen um den Preis zu ermitteln.

    due_date:         Fälligkeitstag
    amount:           Betrag der zugehörigen Abrechnungsperiode
    interval:         Abrechnungsintervall der zugehörigen Periode
    billing_entry_id: ID des SubscriptionBillingHistory-Eintrags (für Tracing)
    """

    due_date: date
    amount: Decimal
    interval: BillingInterval
    billing_entry_id: uuid.UUID | None = None


def get_overview(session: Session, user_id: uuid.UUID) -> OverviewResult:
    """
    Berechnet die monatliche Gesamtsumme und die nächsten fälligen Abos.

    monthly_total: Summe aller aktiven Abo-Beträge, auf Monatsbasis normiert.
                   Abos mit started_on in der Zukunft zählen nicht (L-09).
    upcoming:      Aktive Abos, die in den nächsten 30 Tagen fällig werden.
    """
    subs = list_subscriptions(session, user_id)
    today = date.today()

    # Aktive Abos die bereits gestartet sind — Zukunfts-Abos fließen nicht in die Summe (L-09)
    active_subs = [
        s for s in subs
        if s.status == SubscriptionStatus.active and s.started_on <= today
    ]

    # Billing-Historie für alle aktiven Abos auf einmal laden (ersetzt Preishistorie).
    # Ohne Bulk-Load wäre es N+1 — eine DB-Abfrage pro Abo.
    active_ids = [s.id for s in active_subs]
    all_bh = session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id.in_(active_ids))
    ).scalars().all()
    bh_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for e in all_bh:
        bh_by_sub[e.subscription_id].append(e)

    # Monatliche Gesamtsumme: Betrag und Intervall aus den heute gültigen Billing Terms.
    # applicable_billing_terms() wählt den neuesten Eintrag mit valid_from <= today.
    monthly_total = Decimal("0")
    for s in active_subs:
        terms = applicable_billing_terms(today, bh_by_sub[s.id])
        if terms is not None:
            monthly_total += terms.amount * _MONTHLY_FACTOR[terms.interval]

    # Upcoming: aktive Abos, deren nächster Fälligkeitstag in den nächsten 30 Tagen liegt.
    cutoff = today + timedelta(days=30)
    upcoming = [
        s for s in active_subs
        if today <= compute_next_due_date_from_history(bh_by_sub[s.id], today) <= cutoff
    ]

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


def compute_due_dates(started_on: date, period_months: int, up_to: date) -> list[date]:
    """
    Gibt alle Fälligkeitsdaten von started_on bis up_to zurück (up_to inklusiv).

    Schlüssel-Eigenschaft: immer von started_on aus rechnen, nie iterativ.
    started_on + relativedelta(months=n * period_months) verhindert Ankertag-Drift.

    Beispiel: started_on=31.1., monthly
      n=0 → 31.1. | n=1 → 28.2. | n=2 → 31.3. | n=3 → 30.4.
    Der 31. wird für Feb auf 28 geklemmt, aber für März wieder auf 31 erholt.
    """
    dates, n = [], 0
    while True:
        d = started_on + relativedelta(months=n * period_months)
        if d > up_to:
            break
        dates.append(d)
        n += 1
    return dates


def compute_next_due_date(started_on: date, period_months: int) -> date:
    """
    Gibt den naechsten zukuenftigen Faelligkeitstag > heute zurueck.

    Immer von started_on aus berechnen — kein Zustand, kein Drift.
    Kann für vergangene Abos viele Iterationen brauchen, bleibt aber korrekt.
    """
    today = date.today()
    n = 0
    while True:
        d = started_on + relativedelta(months=n * period_months)
        if d > today:
            return d
        n += 1


def is_in_pause(due_date: date, pause_history: list) -> bool:
    """
    Prüft ob ein Fälligkeitsdatum in einem Pause-Intervall liegt.

    Ein Pause-Intervall geht von paused_at bis resumed_at (beide inklusiv).
    resumed_at=None bedeutet: Pause noch aktiv → alle Daten ab paused_at sind pausiert.
    """
    return any(
        p.paused_at <= due_date and (p.resumed_at is None or due_date <= p.resumed_at)
        for p in pause_history
    )


def applicable_price(due_date: date, price_history: list, include_future: bool = False) -> Decimal:
    """
    Gibt den zum Fälligkeitstag geltenden Preis zurück.

    include_future=False (Standard, "Tatsächlich"):
      Nur Preiseinträge bis heute werden berücksichtigt.
      Angekündigte Preise (valid_from > heute) bleiben unsichtbar.

    include_future=True ("Dieses Kalenderjahr"):
      Auch zukünftige Preiseinträge fließen ein — Vorschau-Charakter.
    """
    today = date.today()
    # Nur Einträge die bis zum Fälligkeitstag bereits galten
    candidates = [p for p in price_history if p.valid_from <= due_date]
    if not include_future:
        # Zusätzlich: nur Vergangenheitspreise (keine Ankündigungen)
        candidates = [p for p in candidates if p.valid_from <= today]
    if not candidates:
        return Decimal("0")
    # Letzter Eintrag vor due_date ist der aktuelle Preis
    return max(candidates, key=lambda p: p.valid_from).amount


def applicable_billing_terms(
    due_date: date,
    billing_history: list,
    include_future: bool = False,
):
    """
    Gibt den gültigen Billing-History-Eintrag für ein Datum zurück.

    Wählt den Eintrag mit dem größten valid_from, das <= due_date liegt.

    include_future=False (Standard):
      Nur Einträge bis heute — angekündigte zukünftige Änderungen bleiben unsichtbar.
      Verwendet für: monthly_total, sub.amount-Snapshot.

    include_future=True:
      Auch zukünftige Einträge — für Vorschau (dieses Kalenderjahr, price_change Copy-forward).

    Gibt None zurück wenn keine passende Historie vorhanden ist.
    """
    today = date.today()
    candidates = [e for e in billing_history if e.valid_from <= due_date]
    if not include_future:
        # Nur Einträge die bis heute bereits wirksam sind
        candidates = [e for e in candidates if e.valid_from <= today]
    if not candidates:
        return None
    # Letzter gültiger Eintrag = höchstes valid_from <= due_date
    return max(candidates, key=lambda e: e.valid_from)


def compute_due_dates_for_billing_history(
    billing_history: list,
    up_to: date,
) -> list[ComputedDue]:
    """
    Gibt alle Fälligkeiten aus der Billing-Historie bis up_to zurück.

    Teilt die Historie in Zeitfenster:
      [entry.valid_from, next_entry.valid_from)

    Für jedes Fenster werden Fälligkeiten von entry.anchor_on aus berechnet.
    anchor_on ist der entscheidende Unterschied: bei Preisänderungen bleibt er gleich,
    bei Intervallwechseln startet er neu (= valid_from des Wechsels).

    Gibt eine nach due_date aufsteigend sortierte Liste von ComputedDue zurück.
    """
    if not billing_history:
        return []

    # Nach Wirkungsdatum aufsteigend sortieren — Segmente müssen chronologisch sein
    ordered = sorted(billing_history, key=lambda h: h.valid_from)
    result = []

    for i, entry in enumerate(ordered):
        segment_start = entry.valid_from
        # Fenster endet am Beginn des nächsten Eintrags — oder hinter up_to wenn letzter Eintrag
        segment_end = (
            ordered[i + 1].valid_from if i + 1 < len(ordered)
            else up_to + timedelta(days=1)
        )
        period_months = _MONTHS_PER_PERIOD[entry.interval]

        # Alle Fälligkeiten von anchor_on aus bis up_to berechnen
        for due in compute_due_dates(entry.anchor_on, period_months, up_to):
            # Fälligkeiten vor dem Fenster-Start: gehören zum vorigen Segment
            if due < segment_start:
                continue
            # Fälligkeiten ab dem nächsten Eintrag: gehören zum nächsten Segment
            if due >= segment_end:
                continue
            result.append(ComputedDue(
                due_date=due,
                amount=entry.amount,
                interval=entry.interval,
                billing_entry_id=entry.id,
            ))

    return sorted(result, key=lambda d: d.due_date)


def compute_next_due_date_from_history(billing_history: list, today: date) -> date:
    """
    Gibt die erste zukuenftige Faelligkeit > today zurueck.

    Berücksichtigt alle Segmente und Anker — korrekt auch nach Intervallwechseln.
    Fallback auf 9999-12-31 wenn billing_history leer ist (kein gültiger Zustand,
    schützt aber vor Absturz während der Übergangsphase in v0.2.4).
    """
    if not billing_history:
        # Leere Historie ist kein korrekter Zustand — Sentinel damit keine Exception
        return date(9999, 12, 31)

    # 3 Jahre Vorlauf reichen sicher für biennial (2-Jahres-Intervall)
    far_future = today + relativedelta(years=3)
    dues = compute_due_dates_for_billing_history(billing_history, far_future)

    for due in dues:
        if due.due_date > today:
            return due.due_date

    # Fallback: ab letztem Anker weiterrechnen (sollte mit 3 Jahren Vorlauf nie eintreten)
    ordered = sorted(billing_history, key=lambda h: h.valid_from)
    last = ordered[-1]
    period_months = _MONTHS_PER_PERIOD[last.interval]
    n = 0
    while True:
        d = last.anchor_on + relativedelta(months=n * period_months)
        if d > today:
            return d
        n += 1


def sync_subscription_billing_snapshot(
    sub: Subscription,
    billing_history: list,
) -> None:
    """
    Setzt sub.amount und sub.interval auf die heute gültigen Billing Terms.

    Wird nach jedem Schreiben oder Löschen eines Billing-History-Eintrags aufgerufen.
    Zukünftige Einträge (valid_from > heute) dürfen den Snapshot noch nicht verändern.

    Regel:
      current = neuester Eintrag mit valid_from <= today
      sub.amount   = current.amount
      sub.interval = current.interval
    """
    current = applicable_billing_terms(date.today(), billing_history, include_future=False)
    if current is not None:
        sub.amount = current.amount
        sub.interval = current.interval


def compute_tatsaechlich(
    billing_history: list,
    pause_history: list,
) -> Decimal:
    """
    Berechnet die tatsächlich entstandenen Kosten seit Abo-Beginn (v0.2.4).

    Summiert alle nicht-pausierten Fälligkeiten bis heute aus der Billing-Historie.
    Betrag und Intervall kommen direkt aus ComputedDue — kein separater Preislookup.

    Fixiert BUG-02 und BUG-04:
    - kein Segment-Mathe mit Monatsdifferenzen
    - Startperiode zählt immer (auch wenn Abo heute angelegt wurde)
    """
    today = date.today()
    total = Decimal("0")
    for due in compute_due_dates_for_billing_history(billing_history, today):
        if is_in_pause(due.due_date, pause_history):
            continue
        total += due.amount
    return total


def compute_intervalle(
    billing_history: list,
    pause_history: list,
) -> int:
    """
    Gibt die Anzahl nicht-pausierter Zahlungsperioden seit Abo-Beginn zurück (v0.2.4).

    Entspricht "wie oft hat der User dieses Abo bereits bezahlt".
    Zählt alle nicht-pausierten Fälligkeiten bis heute aus der Billing-Historie.
    """
    today = date.today()
    return sum(
        1 for due in compute_due_dates_for_billing_history(billing_history, today)
        if not is_in_pause(due.due_date, pause_history)
    )


def compute_dieses_kalenderjahr(
    billing_history: list,
    pause_history: list,
) -> Decimal:
    """
    Berechnet die Abo-Kosten im laufenden Kalenderjahr (1.1. bis 31.12.) (v0.2.4).

    Vergangene und zukünftige Billing-Einträge fließen beide ein — da alle Einträge
    (auch angekündigte Zukunfts-Intervalle) im billing_history enthalten sind, ergibt
    sich der Projektions-Charakter automatisch ohne ein separates include_future-Flag.
    Pausierte Perioden werden übersprungen.

    Gibt einen Jahresbudget-Orientierungswert zurück.
    """
    today = date.today()
    jan_1 = date(today.year, 1, 1)
    dez_31 = date(today.year, 12, 31)
    total = Decimal("0")
    for due in compute_due_dates_for_billing_history(billing_history, dez_31):
        # Perioden vor dem 1. Januar dieses Jahres überspringen
        if due.due_date < jan_1:
            continue
        if is_in_pause(due.due_date, pause_history):
            continue
        total += due.amount
    return total


def get_subscription_detail(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SubscriptionDetail:
    """
    Gibt ein Abo mit allen berechneten Kostenkennzahlen zurück (v0.2.3).

    Alle vier Kennzahlen (monatlich, tatsaechlich, intervalle, dieses_kalenderjahr)
    werden frisch aus Preis- und Pausenhistorie berechnet — keine Werte aus der DB.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Billing-Historie laden (ersetzt Preishistorie ab v0.2.4)
    billing_hist = list(session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id == subscription_id)
        .order_by(SubscriptionBillingHistory.valid_from)
    ).scalars().all())

    # Pausenhistorie laden — alle Pausen dieses Abos
    pause_hist = list(session.execute(
        select(SubscriptionPauseHistory)
        .where(SubscriptionPauseHistory.subscription_id == subscription_id)
    ).scalars().all())

    today = date.today()

    # Aktuell gültige Billing Terms — für monatlich-Kennzahl
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

    # Erst Basisfelder aus dem ORM lesen, dann berechnete Pflichtfelder ergänzen
    # und als komplettes Payload gegen SubscriptionDetail validieren.
    detail_payload = SubscriptionRead.model_validate(
        sub, from_attributes=True
    ).model_dump()
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
    Gibt die Preishistorie eines Abos zurück, absteigend nach Datum (neueste zuerst).

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
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
    Gibt die Billing-Historie eines Abos zurück, absteigend nach Datum (neueste zuerst).

    Jeder Eintrag beschreibt ab wann (valid_from) welcher Betrag, welches Intervall
    und welcher Fälligkeitsanker (anchor_on) gilt.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    return list(session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id == subscription_id)
        # Neuester Eintrag zuerst — aktuelle Konditionen erscheinen oben in der UI
        .order_by(SubscriptionBillingHistory.valid_from.desc())
    ).scalars().all())


def delete_price_history_entry(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    """
    Löscht einen einzelnen Preishistorie-Eintrag — mit Sicherheitsprüfungen.

    Geblockt wenn:
    - Es der einzige verbleibende Eintrag ist (Abo ohne Preis ist ungültig).
    - Es bereits Buchungen für den Zeitraum gibt, in dem dieser Preis galt
      (historische Daten würden widersprüchlich werden).

    Präzise Bereichsprüfung:
    Nicht jede Buchung nach entry.valid_from ist betroffen — nur die im Fenster
    [entry.valid_from, nächster_eintrag.valid_from). So kann ein „mittlerer"
    Eintrag (z. B. eine falsche Zukunfts-Ankündigung ohne Buchungen) gelöscht
    werden, auch wenn spätere Einträge mit Buchungen existieren.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Gesuchten Eintrag laden und Zugehörigkeit prüfen
    entry = session.execute(
        select(SubscriptionPriceHistory).where(
            SubscriptionPriceHistory.id == entry_id,
            SubscriptionPriceHistory.subscription_id == subscription_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise PriceHistoryEntryNotFoundError()

    # Alle Einträge des Abos laden — für Einzel-Check und sub.amount-Update
    all_entries = session.execute(
        select(SubscriptionPriceHistory).where(
            SubscriptionPriceHistory.subscription_id == subscription_id
        )
    ).scalars().all()

    # Letzter Eintrag? Dann darf er nicht gelöscht werden.
    if len(all_entries) <= 1:
        raise PriceEntryDeleteBlockedError(
            "Der einzige Preiseintrag kann nicht gelöscht werden — "
            "ein Abo braucht mindestens einen Preis."
        )

    # Zeitfenster bestimmen, in dem dieser Eintrag der gültige Preis war.
    # Falls ein späterer Eintrag existiert, endet das Fenster dort.
    # Falls es der letzte Eintrag ist, geht das Fenster bis in die Zukunft.
    later = [e for e in all_entries if e.valid_from > entry.valid_from]
    next_valid_from = min(e.valid_from for e in later) if later else None

    # Buchungen im Preisfenster suchen
    stmt = select(SubscriptionScheduledPayment).where(
        SubscriptionScheduledPayment.subscription_id == subscription_id,
        SubscriptionScheduledPayment.due_date >= entry.valid_from,
    )
    if next_valid_from is not None:
        # Nur Buchungen bis zum nächsten Preiseintrag — danach gilt ein anderer Preis
        stmt = stmt.where(SubscriptionScheduledPayment.due_date < next_valid_from)

    affected = session.execute(stmt).scalar_one_or_none()
    if affected is not None:
        raise PriceEntryDeleteBlockedError(
            "Dieser Preiseintrag kann nicht gelöscht werden, da bereits Buchungen "
            "für den betroffenen Zeitraum existieren."
        )

    # Verbleibende Einträge für sub.amount-Neuberechnung vorab merken
    remaining = [e for e in all_entries if e.id != entry.id]

    session.delete(entry)

    # sub.amount korrigieren falls der gelöschte Eintrag der aktuell gültige war.
    # applicable_price() wählt anhand der verbleibenden Einträge den richtigen Preis.
    new_amount = applicable_price(date.today(), remaining)
    if new_amount != Decimal("0"):
        sub.amount = new_amount

    session.commit()


def delete_billing_history_entry(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    """
    Löscht einen einzelnen Billing-History-Eintrag — mit Sicherheitsprüfungen (v0.2.4).

    Geblockt wenn:
    - Es der einzige verbleibende Eintrag ist (Abo ohne Billing-Terms ist ungültig).
    - Es bereits Buchungen für den Zeitraum gibt, in dem dieser Eintrag galt.

    Zeitfenster-Prüfung:
    Nicht jede Buchung nach entry.valid_from ist betroffen — nur die im Fenster
    [entry.valid_from, nächster_eintrag.valid_from). Ein mittlerer Eintrag ohne
    Buchungen (z. B. falsche Ankündigung) kann so auch dann gelöscht werden,
    wenn spätere Einträge mit Buchungen existieren.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Gesuchten Eintrag laden und Zugehörigkeit prüfen
    entry = session.execute(
        select(SubscriptionBillingHistory).where(
            SubscriptionBillingHistory.id == entry_id,
            SubscriptionBillingHistory.subscription_id == subscription_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise BillingHistoryEntryNotFoundError()

    # Alle Einträge des Abos laden — für Einzel-Check und Snapshot-Update
    all_entries = list(session.execute(
        select(SubscriptionBillingHistory).where(
            SubscriptionBillingHistory.subscription_id == subscription_id
        )
    ).scalars().all())

    # Letzter Eintrag? Dann darf er nicht gelöscht werden.
    if len(all_entries) <= 1:
        raise PriceEntryDeleteBlockedError(
            "Der einzige Abrechnungseintrag kann nicht gelöscht werden — "
            "ein Abo braucht mindestens einen Eintrag."
        )

    # Zeitfenster bestimmen, in dem dieser Eintrag die gültigen Konditionen beschrieb.
    # Falls ein späterer Eintrag existiert, endet das Fenster dort.
    later = [e for e in all_entries if e.valid_from > entry.valid_from]
    next_valid_from = min(e.valid_from for e in later) if later else None

    # Buchungen im Fenster suchen — nur die sind tatsächlich von dieser Löschung betroffen
    stmt = select(SubscriptionScheduledPayment).where(
        SubscriptionScheduledPayment.subscription_id == subscription_id,
        SubscriptionScheduledPayment.due_date >= entry.valid_from,
    )
    if next_valid_from is not None:
        stmt = stmt.where(SubscriptionScheduledPayment.due_date < next_valid_from)

    affected = session.execute(stmt).scalar_one_or_none()
    if affected is not None:
        raise PriceEntryDeleteBlockedError(
            "Dieser Abrechnungseintrag kann nicht gelöscht werden, da bereits Buchungen "
            "für den betroffenen Zeitraum existieren."
        )

    remaining = [e for e in all_entries if e.id != entry.id]
    if sub.started_on <= date.today() and applicable_billing_terms(date.today(), remaining) is None:
        raise PriceEntryDeleteBlockedError(
            "Dieser Abrechnungseintrag kann nicht geloescht werden, weil danach "
            "kein aktuell gueltiger Abrechnungseintrag mehr existieren wuerde."
        )

    session.delete(entry)
    # Snapshot synchronisieren: sub.amount und sub.interval nach Löschung aktualisieren
    sync_subscription_billing_snapshot(sub, remaining)
    session.commit()


def get_scheduled_payments(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionScheduledPayment]:
    """
    Gibt alle Soll-Buchungen eines Abos zurück, absteigend nach Fälligkeitsdatum.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    stmt = (
        select(SubscriptionScheduledPayment)
        .where(SubscriptionScheduledPayment.subscription_id == subscription_id)
        # Neueste Buchung zuerst — so sieht der User die aktuellsten Einträge oben
        .order_by(SubscriptionScheduledPayment.due_date.desc())
    )
    return list(session.execute(stmt).scalars().all())


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
        interval=payload.interval,
        started_on=started_on,
        notes=payload.notes,
        # status, logo_url — SQLAlchemy-Defaults greifen
    )
    session.add(sub)
    session.flush()  # flush statt commit: sub.id ist jetzt verfügbar, Transaktion noch offen

    # Initialen Billing-History-Eintrag schreiben (v0.2.4 — ersetzt _record_price_change).
    #
    # Warum hier und nicht erst beim ersten price_change?
    # Ohne diesen Eintrag fehlt der Startpreis nach der ersten Änderung unwiederbringlich:
    #   Anlage:      9,99 € — kein Eintrag → nach Änderung auf 12,99 € unbekannt
    #   1. Änderung → {12,99, März}
    #   2. Änderung → {14,99, Mai}
    # History: [{12.99, März}, {14.99, Mai}] — Jan–Feb fehlen komplett
    #
    # Mit diesem Eintrag:
    # History: [{9.99, started_on}, {12.99, März}, {14.99, Mai}] → lückenlose Zeitleiste
    #
    # anchor_on = started_on: der Fälligkeitsrhythmus startet am Abschluss-Datum.
    # valid_from = started_on: rückwirkend angelegte Abos werden korrekt erfasst.
    initial_bh = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=sub.amount,
        interval=sub.interval,
        valid_from=started_on,
        anchor_on=started_on,
    )
    session.add(initial_bh)

    session.commit()
    session.refresh(sub)
    return sub



def update_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SubscriptionUpdate,
) -> Subscription:
    """
    Aktualisiert Name, Intervall oder Notizen eines Abos (PATCH).

    Nur Felder die im Request-Body standen (payload.model_fields_set) werden geändert.
    notes kann explizit auf null gesetzt werden ({ "notes": null }).

    Hinweis: Preisänderungen laufen über price_change() — nicht mehr über diesen Endpoint.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur die Felder aktualisieren, die der User tatsächlich mitgeschickt hat.
    #
    # Warum model_fields_set statt "if payload.x is not None"?
    # Bei Optional-Feldern bedeutet None zweierlei:
    #   - "nicht mitgeschickt" (Feld fehlt im JSON)  → soll nichts ändern
    #   - "explizit null"       ({ "notes": null })   → soll Feld leeren
    # model_fields_set enthält nur die Felder, die im Request-Body standen.
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
    Setzt ein Abo auf 'suspended' und schreibt einen Pause-Eintrag.

    Soft-Lifecycle: das Abo bleibt in der DB — keine Daten gehen verloren.
    Nur aktive Abos können suspendiert werden (409 wenn bereits suspended/canceled).
    Der Pause-Eintrag ermöglicht mehrfaches Pausieren und Resumieren (v0.2.3).
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    if sub.status != SubscriptionStatus.active:
        raise InvalidSubscriptionStatusError(
            f"Nur aktive Abos können suspendiert werden. Aktueller Status: {sub.status.value}"
        )

    today = date.today()
    sub.status = SubscriptionStatus.suspended

    # Pause-Episode in subscription_pause_history festhalten.
    # resumed_at=None bedeutet: Pause noch aktiv (wird beim Resume gesetzt).
    pause = SubscriptionPauseHistory(
        subscription_id=sub.id,
        paused_at=today,
        access_until=payload.access_until,
    )
    session.add(pause)

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
    Der letzte offene Pause-Eintrag (resumed_at IS NULL) wird auf heute geschlossen.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    if sub.status != SubscriptionStatus.suspended:
        raise InvalidSubscriptionStatusError(
            f"Nur pausierte Abos können fortgesetzt werden. Aktueller Status: {sub.status.value}"
        )

    # Letzten noch offenen Pause-Eintrag suchen und schließen.
    # "Offen" bedeutet: resumed_at ist noch NULL.
    open_pause = session.execute(
        select(SubscriptionPauseHistory)
        .where(
            SubscriptionPauseHistory.subscription_id == sub.id,
            SubscriptionPauseHistory.resumed_at.is_(None),
        )
        .order_by(SubscriptionPauseHistory.paused_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if open_pause:
        open_pause.resumed_at = date.today()

    sub.status = SubscriptionStatus.active

    session.commit()
    session.refresh(sub)
    return sub


def cancel_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SuspendPayload | None = None,
) -> SubscriptionDetail:
    """
    Kündigt ein Abo endgültig (status = 'canceled').

    Im Gegensatz zu suspend ist canceled final — ein Resumieren ist nicht vorgesehen.
    Ein Pause-Eintrag wird geschrieben damit die Buchungshistorie sauber endet
    (Scheduler erzeugt ab canceled keine weiteren Einträge mehr).
    access_until aus dem Payload: optional — bis wann ist die Leistung noch nutzbar?
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Bereits gekündigt? — doppelte Kündigung sinnlos
    if sub.status == SubscriptionStatus.canceled:
        raise InvalidSubscriptionStatusError("Das Abo ist bereits gekündigt.")

    today = date.today()
    sub.status = SubscriptionStatus.canceled

    # Pause-Eintrag schreiben — markiert den Endpunkt in der Buchungshistorie.
    # paused_at = Kündigungsdatum, resumed_at = None (endgültig).
    pause = SubscriptionPauseHistory(
        subscription_id=sub.id,
        paused_at=today,
        access_until=payload.access_until if payload is not None else None,
    )
    session.add(pause)

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)


def price_change(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    payload: PriceChangeRequest,
) -> SubscriptionDetail:
    """
    Trägt eine Preisänderung mit frei wählbarem Gültigkeitsdatum ein (v0.2.4).

    Schreibt einen Eintrag in subscription_billing_history (nicht mehr price_history).
    Copy-forward-Regel: Intervall und Anker werden vom geltenden Vorgänger-Eintrag übernommen —
    eine Preisänderung ändert nur den Betrag, der Zahlungsrhythmus bleibt gleich.

    valid_from darf in der Vergangenheit (Korrektur), heute oder Zukunft (Ankündigung) liegen.
    Gibt die vollständige SubscriptionDetail mit neu berechneten Kennzahlen zurück.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Aktuelle Billing-Historie laden — für Duplikat-Check und Copy-forward-Regel
    billing_hist = list(session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id == subscription_id)
    ).scalars().all())

    # Duplikat-Check: existiert bereits ein Eintrag für dieses Datum?
    # Kein stilles Überschreiben — der User muss den alten Eintrag erst löschen.
    if any(e.valid_from == payload.valid_from for e in billing_hist):
        raise DuplicateBillingHistoryEntryError(payload.valid_from.isoformat())

    # Copy-forward-Regel: Intervall und Anker vom geltenden Vorgänger-Eintrag übernehmen.
    # include_future=True: auch angekündigte (zukünftige) Einträge einbeziehen —
    # eine Preisänderung nach einer bereits eingetragenen Ankündigung übernimmt deren Rhythmus.
    prev = applicable_billing_terms(payload.valid_from, billing_hist, include_future=True)
    if prev is not None:
        carry_interval = prev.interval
        carry_anchor = prev.anchor_on
    else:
        # Kein Vorgänger (Preisänderung liegt vor dem initialen Eintrag): Snapshot als Fallback
        carry_interval = sub.interval
        carry_anchor = payload.valid_from

    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=carry_interval,
        valid_from=payload.valid_from,
        anchor_on=carry_anchor,
    )
    session.add(new_entry)

    # Snapshot synchronisieren: sub.amount und sub.interval auf heute gültige Terms setzen.
    # Zukünftige Einträge (valid_from > heute) ändern den Snapshot noch nicht.
    sync_subscription_billing_snapshot(sub, billing_hist + [new_entry])

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)


def interval_change(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    payload: IntervalChangeRequest,
) -> SubscriptionDetail:
    """
    Ändert Abrechnungsintervall und Betrag gemeinsam ab einem Datum (v0.2.4).

    Schlüsselregel: anchor_on = valid_from — der neue Zahlungsrhythmus startet genau hier.
    Das unterscheidet Intervallwechsel von Preisänderungen (dort bleibt anchor_on gleich).

    409-Block-Flow (rückwirkende Änderungen mit vorhandenen Buchungen):
    - acknowledge_existing_payments=False (default):
      → 409 wenn ab valid_from bereits Scheduled Payments existieren.
      → Die Fehlermeldung nennt die Anzahl der betroffenen Buchungen.
    - acknowledge_existing_payments=True:
      → Speichert trotzdem — bestehende Buchungen bleiben unverändert (bewusste User-Entscheidung).
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Aktuelle Billing-Historie laden — für Duplikat-Check
    billing_hist = list(session.execute(
        select(SubscriptionBillingHistory)
        .where(SubscriptionBillingHistory.subscription_id == subscription_id)
    ).scalars().all())

    # Duplikat-Check: existiert bereits ein Eintrag für dieses Datum?
    if any(e.valid_from == payload.valid_from for e in billing_hist):
        raise DuplicateBillingHistoryEntryError(payload.valid_from.isoformat())

    # 409-Block: rückwirkende Änderungen mit vorhandenen Buchungen erfordern explizite Bestätigung.
    # Ohne Bestätigung wird geblockt — der User soll die Konsequenzen bewusst akzeptieren.
    if not payload.acknowledge_existing_payments:
        affected = list(session.execute(
            select(SubscriptionScheduledPayment).where(
                SubscriptionScheduledPayment.subscription_id == subscription_id,
                SubscriptionScheduledPayment.due_date >= payload.valid_from,
            )
        ).scalars().all())
        if affected:
            raise BillingHistoryChangeBlockedError(
                f"Ab {payload.valid_from.isoformat()} existieren bereits "
                f"{len(affected)} Buchung(en). Bitte mit "
                "acknowledge_existing_payments=true bestätigen, um fortzufahren."
            )

    # Intervallwechsel: anchor_on = valid_from — neuer Rhythmus startet genau hier.
    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=payload.interval,
        valid_from=payload.valid_from,
        anchor_on=payload.valid_from,
    )
    session.add(new_entry)

    # Snapshot synchronisieren: sub.amount und sub.interval auf heute gültige Terms setzen.
    sync_subscription_billing_snapshot(sub, billing_hist + [new_entry])

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)


# Erlaubte Bild-Typen für Logo-Uploads (ADR 0010)
_ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
# Dateiendung pro Content-Type — UUID-Dateiname verhindert Kollisionen und Path-Traversal
_LOGO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def upload_subscription_logo(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    content_type: str,
    file_content: bytes,
    upload_dir: str,
) -> Subscription:
    """
    Speichert ein Logo für ein Abo auf dem Dateisystem (ADR 0010: lokales Dateisystem).

    Validiert Dateityp (JPEG/PNG/WebP) und Größe (max. 2 MB).
    Löscht das alte Logo wenn vorhanden, schreibt das neue.
    Speichert den relativen Pfad ("logos/<uuid>.ext") in der DB — nicht die absolute URL.
    Der relative Pfad ist der entscheidende Entwurfsaspekt aus ADR 0010:
    bei späterer Migration zu Object Storage ändert sich nur dieser Service-Code.
    """
    # Dateityp prüfen — nur bekannte Bild-Formate akzeptieren
    if content_type not in _ALLOWED_LOGO_TYPES:
        raise InvalidFileError("Ungültiger Dateityp. Erlaubt: JPEG, PNG, WebP.")

    # Dateigröße prüfen — zu große Bilder würden die Festplatte belasten
    if len(file_content) > _MAX_LOGO_SIZE_BYTES:
        raise InvalidFileError("Datei zu groß. Maximum: 2 MB.")

    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Altes Logo löschen wenn vorhanden — Festplatte sauber halten
    if sub.logo_url:
        old_file = Path(upload_dir) / sub.logo_url
        # missing_ok=True: kein Fehler wenn die Datei schon fehlt (z. B. manuell gelöscht)
        old_file.unlink(missing_ok=True)

    # Neuen Dateinamen mit UUID generieren — verhindert Kollisionen und Path-Traversal-Angriffe.
    # Niemals den vom Client gelieferten Dateinamen verwenden!
    ext = _LOGO_EXT[content_type]
    relative_path = f"logos/{uuid.uuid4()}{ext}"
    dest = Path(upload_dir) / relative_path
    # Verzeichnis anlegen falls es noch nicht existiert (z. B. erster Upload überhaupt)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_content)

    # Nur den relativen Pfad in der DB speichern (ADR 0010: kein absoluter Pfad, keine URL)
    sub.logo_url = relative_path
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
