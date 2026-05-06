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

from app.exceptions import DuplicatePriceEntryError, ForbiddenError, InvalidFileError, InvalidSubscriptionStatusError, PriceEntryDeleteBlockedError, PriceHistoryEntryNotFoundError, SubscriptionNotFoundError
from app.models.subscription import (
    BillingInterval,
    Subscription,
    SubscriptionPauseHistory,
    SubscriptionPriceHistory,
    SubscriptionScheduledPayment,
    SubscriptionStatus,
)
from app.schemas.subscription import (
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


def subscription_to_read(sub: Subscription) -> SubscriptionRead:
    """
    Konvertiert ein Subscription-ORM-Objekt in SubscriptionRead mit berechnetem next_due_date.

    next_due_date ist keine DB-Spalte — ohne diese Hilfsfunktion bleibt das Feld
    immer None, weil model_validate() nur echte ORM-Attribute liest (BUG-01).
    """
    read = SubscriptionRead.model_validate(sub)
    # Frisch berechnen damit die UI immer den aktuellen nächsten Fälligkeitstag sieht
    read.next_due_date = compute_next_due_date(sub.started_on, _MONTHS_PER_PERIOD[sub.interval])
    return read


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurück, sortiert nach Fälligkeitsdatum.

    Gibt alle Status zurück (active, suspended, canceled) — die UI kann filtern.
    Sortierung: in Python via compute_next_due_date, weil next_due_date nicht mehr
    als Spalte existiert (v0.2.3 / BUG-01 — Datum wird immer frisch berechnet).
    """
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    subs = list(session.execute(stmt).scalars().all())
    # Nach berechnetem Fälligkeitsdatum sortieren — nächste Fälligkeit zuerst
    return sorted(
        subs,
        key=lambda s: compute_next_due_date(s.started_on, _MONTHS_PER_PERIOD[s.interval]),
    )


@dataclass
class OverviewResult:
    """Zwischenergebnis für den Übersicht-Endpunkt — kein HTTP, nur Daten."""

    monthly_total: Decimal
    upcoming: list[Subscription]


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

    # Preishistorie für alle aktiven Abos auf einmal laden.
    # Ohne Bulk-Load wäre es N+1 — eine DB-Abfrage pro Abo.
    active_ids = [s.id for s in active_subs]
    all_price_entries = session.execute(
        select(SubscriptionPriceHistory)
        .where(SubscriptionPriceHistory.subscription_id.in_(active_ids))
    ).scalars().all()
    price_hist_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for p in all_price_entries:
        price_hist_by_sub[p.subscription_id].append(p)

    # Aktuell gültigen Preis aus Preishistorie ableiten — nicht s.amount.
    # s.amount kann stale sein wenn eine angekündigte Preisänderung wirksam wurde.
    monthly_total = sum(
        (applicable_price(today, price_hist_by_sub[s.id]) * _MONTHLY_FACTOR[s.interval]
         for s in active_subs),
        Decimal("0"),
    )

    # Upcoming: aktive Abos, deren nächster Fälligkeitstag in den nächsten 30 Tagen liegt.
    # next_due_date wird jetzt berechnet (BUG-01) — nicht mehr aus der DB gelesen.
    cutoff = today + timedelta(days=30)
    upcoming = [
        s for s in active_subs
        if today <= compute_next_due_date(s.started_on, _MONTHS_PER_PERIOD[s.interval]) <= cutoff
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
    Gibt den nächsten Fälligkeitstag >= heute zurück.

    Immer von started_on aus berechnen — kein Zustand, kein Drift.
    Kann für vergangene Abos viele Iterationen brauchen, bleibt aber korrekt.
    """
    today = date.today()
    n = 0
    while True:
        d = started_on + relativedelta(months=n * period_months)
        if d >= today:
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


def compute_tatsaechlich(
    started_on: date,
    period_months: int,
    price_history: list,
    pause_history: list,
) -> Decimal:
    """
    Berechnet die tatsächlich entstandenen Kosten seit Abo-Beginn.

    Zählt alle nicht-pausierten Perioden bis heute und multipliziert
    jede mit dem damals gültigen Preis. Fixiert BUG-02 und BUG-04:
    - kein Segment-Mathe mit Monatsdifferenzen
    - Startperiode zählt immer (auch wenn Abo heute angelegt wurde)
    """
    today = date.today()
    total = Decimal("0")
    for due in compute_due_dates(started_on, period_months, today):
        if is_in_pause(due, pause_history):
            continue
        total += applicable_price(due, price_history, include_future=False)
    return total


def compute_intervalle(
    started_on: date,
    period_months: int,
    pause_history: list,
) -> int:
    """
    Gibt die Anzahl nicht-pausierter Zahlungsperioden seit Abo-Beginn zurück.

    Entspricht "wie oft hat der User dieses Abo bereits bezahlt".
    """
    today = date.today()
    return sum(
        1 for due in compute_due_dates(started_on, period_months, today)
        if not is_in_pause(due, pause_history)
    )


def compute_dieses_kalenderjahr(
    started_on: date,
    period_months: int,
    price_history: list,
    pause_history: list,
) -> Decimal:
    """
    Berechnet die Abo-Kosten im laufenden Kalenderjahr (1.1. bis 31.12.).

    Vergangene Perioden: tatsächliche Preise.
    Zukünftige Perioden: angekündigte Preise eingerechnet (Projektion).
    Pausierte Perioden: werden übersprungen.

    Vorschau-Charakter: gibt einen Jahresbudget-Orientierungswert, der
    auch Preisankündigungen berücksichtigt die noch nicht wirksam sind.
    """
    today = date.today()
    jan_1 = date(today.year, 1, 1)
    dez_31 = date(today.year, 12, 31)
    total = Decimal("0")
    for due in compute_due_dates(started_on, period_months, dez_31):
        # Perioden vor dem 1. Januar dieses Jahres überspringen
        if due < jan_1:
            continue
        if is_in_pause(due, pause_history):
            continue
        # include_future=True: Preisankündigungen als Projektion einrechnen
        total += applicable_price(due, price_history, include_future=True)
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

    period_months = _MONTHS_PER_PERIOD[sub.interval]

    # Preishistorie laden — aufsteigend damit applicable_price korrekt arbeitet
    price_hist = list(session.execute(
        select(SubscriptionPriceHistory)
        .where(SubscriptionPriceHistory.subscription_id == subscription_id)
        .order_by(SubscriptionPriceHistory.valid_from)
    ).scalars().all())

    # Pausenhistorie laden — alle Pausen dieses Abos
    pause_hist = list(session.execute(
        select(SubscriptionPauseHistory)
        .where(SubscriptionPauseHistory.subscription_id == subscription_id)
    ).scalars().all())

    # Alle vier Kennzahlen berechnen (Algorithmen aus Chunk 3)
    today = date.today()
    # Aktuell gültiger Preis aus Preishistorie — nicht sub.amount (stale nach Preisankündigung)
    current_price = applicable_price(today, price_hist)
    monatlich = (current_price * _MONTHLY_FACTOR[sub.interval]).quantize(Decimal("0.01"))
    tatsaechlich = compute_tatsaechlich(sub.started_on, period_months, price_hist, pause_hist)
    intervalle = compute_intervalle(sub.started_on, period_months, pause_hist)
    dieses_kj = compute_dieses_kalenderjahr(sub.started_on, period_months, price_hist, pause_hist)
    next_due = compute_next_due_date(sub.started_on, period_months)

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
    - price_change:        Eintrag mit frei wählbarem valid_from (Vergangenheit/Zukunft)

    Warum valid_from als Parameter?
    Beim Anlegen soll der Startpreis ab started_on gelten, nicht ab heute.
    Beim price_change-Endpoint wählt der User selbst wann der neue Preis gilt.

    Semantik der Tabelle (valid_from-only-Design):
    Jeder Eintrag bedeutet „ab diesem Datum gilt Preis X".
    Aufeinanderfolgende Einträge bilden eine lückenlose Zeitleiste:
      {9.99, 2026-01-01} → {12.99, 2026-03-01} → {14.99, 2026-05-01}
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
    Trägt eine Preisänderung mit frei wählbarem Gültigkeitsdatum ein (v0.2.3).

    valid_from darf in der Vergangenheit (Korrektur), heute oder Zukunft (Ankündigung) liegen.
    Schreibt einen Eintrag in subscription_price_history und aktualisiert sub.amount
    wenn valid_from <= heute (der neue Preis ist bereits wirksam).
    Gibt die vollständige SubscriptionDetail mit neu berechneten Kennzahlen zurück.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Duplikat-Check: existiert bereits ein Eintrag für dieses Datum?
    # Kein stilles Überschreiben — der User muss den alten Eintrag erst löschen oder bearbeiten.
    existing = session.execute(
        select(SubscriptionPriceHistory).where(
            SubscriptionPriceHistory.subscription_id == sub.id,
            SubscriptionPriceHistory.valid_from == payload.valid_from,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicatePriceEntryError(payload.valid_from.isoformat())

    # Preishistorie-Eintrag schreiben — mit dem vom User gewählten Datum
    _record_price_change(session, sub, payload.amount, valid_from=payload.valid_from)

    # Wenn der neue Preis bereits gilt (valid_from <= heute): sub.amount aktualisieren.
    # So bleibt amount immer der aktuell gültige Preis.
    if payload.valid_from <= date.today():
        sub.amount = payload.amount

    session.commit()
    # Detail mit aktualisierten Kennzahlen zurückgeben
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
