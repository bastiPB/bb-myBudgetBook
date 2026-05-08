"""Billing-Algorithmen und reine bzw. ORM-Snapshot-Berechnungen."""

from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.subscription import Subscription

from .constants import _MONTHS_PER_PERIOD
from .types import ComputedDue


def compute_due_dates(started_on: date, period_months: int, up_to: date) -> list[date]:
    """
    Gibt alle Faelligkeitsdaten von started_on bis up_to zurueck (up_to inklusiv).

    Schluessel-Eigenschaft: immer von started_on aus rechnen, nie iterativ.
    started_on + relativedelta(months=n * period_months) verhindert Ankertag-Drift.

    Beispiel: started_on=31.1., monthly
      n=0 → 31.1. | n=1 → 28.2. | n=2 → 31.3. | n=3 → 30.4.
    Der 31. wird fuer Feb auf 28 geklemmt, aber fuer Maerz wieder auf 31 erholt.
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
    Kann fuer vergangene Abos viele Iterationen brauchen, bleibt aber korrekt.
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
    Prueft ob ein Faelligkeitsdatum in einem Pause-Intervall liegt.

    Ein Pause-Intervall geht von paused_at bis resumed_at (beide inklusiv).
    resumed_at=None bedeutet: Pause noch aktiv → alle Daten ab paused_at sind pausiert.
    """
    return any(
        p.paused_at <= due_date and (p.resumed_at is None or due_date <= p.resumed_at)
        for p in pause_history
    )


def applicable_price(due_date: date, price_history: list, include_future: bool = False) -> Decimal:
    """
    Gibt den zum Faelligkeitstag geltenden Preis zurueck.

    include_future=False (Standard, "Tatsaechlich"):
      Nur Preiseintraege bis heute werden beruecksichtigt.
      Angekuendigte Preise (valid_from > heute) bleiben unsichtbar.

    include_future=True ("Dieses Kalenderjahr"):
      Auch zukuenftige Preiseintraege fliessen ein — Vorschau-Charakter.
    """
    today = date.today()
    # Nur Eintraege die bis zum Faelligkeitstag bereits galten
    candidates = [p for p in price_history if p.valid_from <= due_date]
    if not include_future:
        # Zusaetzlich: nur Vergangenheitspreise (keine Ankuendigungen)
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
    Gibt den gueltigen Billing-History-Eintrag fuer ein Datum zurueck.

    Waehlt den Eintrag mit dem groessten valid_from, das <= due_date liegt.

    include_future=False (Standard):
      Nur Eintraege bis heute — angekuendigte zukuenftige Aenderungen bleiben unsichtbar.
      Verwendet fuer: monthly_total, sub.amount-Snapshot.

    include_future=True:
      Auch zukuenftige Eintraege — fuer Vorschau (dieses Kalenderjahr, price_change Copy-forward).

    Gibt None zurueck wenn keine passende Historie vorhanden ist.
    """
    today = date.today()
    candidates = [e for e in billing_history if e.valid_from <= due_date]
    if not include_future:
        # Nur Eintraege die bis heute bereits wirksam sind
        candidates = [e for e in candidates if e.valid_from <= today]
    if not candidates:
        return None
    # Letzter gueltiger Eintrag = hoechstes valid_from <= due_date
    return max(candidates, key=lambda e: e.valid_from)


def compute_due_dates_for_billing_history(
    billing_history: list,
    up_to: date,
) -> list[ComputedDue]:
    """
    Gibt alle Faelligkeiten aus der Billing-Historie bis up_to zurueck.

    Teilt die Historie in Zeitfenster:
      [entry.valid_from, next_entry.valid_from)

    Fuer jedes Fenster werden Faelligkeiten von entry.anchor_on aus berechnet.
    anchor_on ist der entscheidende Unterschied: bei Preisaenderungen bleibt er gleich,
    bei Intervallwechseln startet er neu (= valid_from des Wechsels).

    Gibt eine nach due_date aufsteigend sortierte Liste von ComputedDue zurueck.
    """
    if not billing_history:
        return []

    # Nach Wirkungsdatum aufsteigend sortieren — Segmente muessen chronologisch sein
    ordered = sorted(billing_history, key=lambda h: h.valid_from)
    result = []

    for i, entry in enumerate(ordered):
        segment_start = entry.valid_from
        # Fenster endet am Beginn des naechsten Eintrags — oder hinter up_to wenn letzter Eintrag
        segment_end = (
            ordered[i + 1].valid_from if i + 1 < len(ordered) else up_to + timedelta(days=1)
        )
        period_months = _MONTHS_PER_PERIOD[entry.interval]

        # Alle Faelligkeiten von anchor_on aus bis up_to berechnen
        for due in compute_due_dates(entry.anchor_on, period_months, up_to):
            # Faelligkeiten vor dem Fenster-Start: gehoeren zum vorigen Segment
            if due < segment_start:
                continue
            # Faelligkeiten ab dem naechsten Eintrag: gehoeren zum naechsten Segment
            if due >= segment_end:
                continue
            result.append(
                ComputedDue(
                    due_date=due,
                    amount=entry.amount,
                    interval=entry.interval,
                    billing_entry_id=entry.id,
                )
            )

    return sorted(result, key=lambda d: d.due_date)


def compute_next_due_date_from_history(billing_history: list, today: date) -> date:
    """
    Gibt die erste zukuenftige Faelligkeit > today zurueck.

    Beruecksichtigt alle Segmente und Anker — korrekt auch nach Intervallwechseln.
    Fallback auf 9999-12-31 wenn billing_history leer ist (kein gueltiger Zustand,
    schuetzt aber vor Absturz waehrend der Uebergangsphase in v0.2.4).
    """
    if not billing_history:
        # Leere Historie ist kein korrekter Zustand — Sentinel damit keine Exception
        return date(9999, 12, 31)

    # 3 Jahre Vorlauf reichen sicher fuer biennial (2-Jahres-Intervall)
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
    Setzt sub.amount und sub.interval auf die heute gueltigen Billing Terms.

    Wird nach jedem Schreiben oder Loeschen eines Billing-History-Eintrags aufgerufen.
    Zukuenftige Eintraege (valid_from > heute) duerfen den Snapshot noch nicht veraendern.

    Regel:
      current = neuester Eintrag mit valid_from <= today
      sub.amount   = current.amount
      sub.interval = current.interval

    Nur In-Memory auf dem ORM-Objekt, kein session.commit().
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
    Berechnet die tatsaechlich entstandenen Kosten seit Abo-Beginn (v0.2.4).

    Summiert alle nicht-pausierten Faelligkeiten bis heute aus der Billing-Historie.
    Betrag und Intervall kommen direkt aus ComputedDue — kein separater Preislookup.

    Fixiert BUG-02 und BUG-04:
    - kein Segment-Mathe mit Monatsdifferenzen
    - Startperiode zaehlt immer (auch wenn Abo heute angelegt wurde)
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
    Gibt die Anzahl nicht-pausierter Zahlungsperioden seit Abo-Beginn zurueck (v0.2.4).

    Entspricht "wie oft hat der User dieses Abo bereits bezahlt".
    Zaehlt alle nicht-pausierten Faelligkeiten bis heute aus der Billing-Historie.
    """
    today = date.today()
    return sum(
        1
        for due in compute_due_dates_for_billing_history(billing_history, today)
        if not is_in_pause(due.due_date, pause_history)
    )


def compute_dieses_kalenderjahr(
    billing_history: list,
    pause_history: list,
) -> Decimal:
    """
    Berechnet die Abo-Kosten im laufenden Kalenderjahr (1.1. bis 31.12.) (v0.2.4).

    Vergangene und zukuenftige Billing-Eintraege fliessen beide ein — da alle Eintraege
    (auch angekuendigte Zukunfts-Intervalle) im billing_history enthalten sind, ergibt
    sich der Projektions-Charakter automatisch ohne ein separates include_future-Flag.
    Pausierte Perioden werden uebersprungen.

    Gibt einen Jahresbudget-Orientierungswert zurueck.
    """
    today = date.today()
    jan_1 = date(today.year, 1, 1)
    dez_31 = date(today.year, 12, 31)
    total = Decimal("0")
    for due in compute_due_dates_for_billing_history(billing_history, dez_31):
        # Perioden vor dem 1. Januar dieses Jahres ueberspringen
        if due.due_date < jan_1:
            continue
        if is_in_pause(due.due_date, pause_history):
            continue
        total += due.amount
    return total
