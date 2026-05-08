"""
tests/test_subscriptions_v024.py — Akzeptanz-Tests für v0.2.4 Algorithmen

Neue Funktionen gegenüber v0.2.3:
  - applicable_billing_terms(): gültiger Billing-Eintrag für ein Datum (inkl. include_future)
  - compute_due_dates_for_billing_history(): segmentierte Fälligkeiten aus Billing-Historie
  - compute_next_due_date_from_history(): nächste Fälligkeit korrekt nach Intervallwechsel
  - compute_tatsaechlich(), compute_intervalle(), compute_dieses_kalenderjahr() — neue Signaturen
    (billing_history statt started_on + period_months + price_history)

Szenarien:
  T-01: applicable_billing_terms — korrekter Eintrag wird für ein Datum gewählt
  T-02: applicable_billing_terms — include_future=True macht zukünftige Einträge sichtbar
  T-03: compute_due_dates_for_billing_history — einfache monatliche Historie ohne Wechsel
  T-04: compute_due_dates_for_billing_history — Preisänderung (Copy-forward-Anker)
  T-05: compute_due_dates_for_billing_history — Intervallwechsel (neuer Anker)
  T-06: compute_tatsaechlich mit Intervallwechsel
  T-07: compute_tatsaechlich — pausierte Periode wird ausgeschlossen
  T-08: compute_intervalle — mit und ohne Pause
  T-09: compute_dieses_kalenderjahr — Jahreskosten mit Intervallwechsel in der Jahresmitte
  T-10: compute_next_due_date_from_history — nächste Fälligkeit nach Intervallwechsel

Monkeypatch-Strategie: wie v0.2.3 — patch_subscriptions_service_date ersetzt date
in allen Subscription-Service-Untermodulen (siehe test_subscriptions_v023.py).

Keine DB: alle Tests testen Service-Logik isoliert (reine Python-Objekte).

Hinweis zu v0.2.3-Tests:
  compute_tatsaechlich, compute_intervalle, compute_dieses_kalenderjahr haben neue
  Signaturen in v0.2.4 erhalten. Die v0.2.3-Tests für diese Funktionen schlagen deshalb
  fehl und müssen separat aktualisiert oder deaktiviert werden.
"""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.subscription import BillingInterval
from app.services.subscriptions import (
    applicable_billing_terms,
    compute_dieses_kalenderjahr,
    compute_due_dates_for_billing_history,
    compute_intervalle,
    compute_next_due_date_from_history,
    compute_tatsaechlich,
)

_SUBSCRIPTIONS_SERVICE_DATE_MODULES = (
    "app.services.subscriptions.billing",
    "app.services.subscriptions.readers",
    "app.services.subscriptions.mutations",
    "app.services.subscriptions.lifecycle",
)


def patch_subscriptions_service_date(
    monkeypatch: pytest.MonkeyPatch,
    fake_date_cls: type[date],
) -> None:
    """Setzt dieselbe Fake-date-Klasse in allen Subscription-Service-Untermodulen."""
    for mod in _SUBSCRIPTIONS_SERVICE_DATE_MODULES:
        monkeypatch.setattr(f"{mod}.date", fake_date_cls)


# ─── Test-Hilfsobjekte ────────────────────────────────────────────────────────

def bh_entry(
    amount: str,
    interval: BillingInterval,
    valid_from: date,
    anchor_on: date | None = None,
) -> SimpleNamespace:
    """
    Minimaler Billing-History-Eintrag (SubscriptionBillingHistory-Ersatz für Tests).

    anchor_on defaults auf valid_from — entspricht dem Normalfall:
      - Neues Abo: anchor_on = started_on = valid_from
      - Intervallwechsel: anchor_on = valid_from (neuer Anker, Rhythmus startet neu)
      - Preisänderung: anchor_on wird explizit vom Vorgänger übernommen (Copy-forward).
    """
    return SimpleNamespace(
        id=uuid.uuid4(),
        amount=Decimal(amount),
        interval=interval,
        valid_from=valid_from,
        anchor_on=anchor_on if anchor_on is not None else valid_from,
    )


def pause_entry(paused_at: date, resumed_at: date | None = None) -> SimpleNamespace:
    """Minimale Pausenhistorie-Zeile — nur .paused_at und .resumed_at werden gebraucht."""
    return SimpleNamespace(paused_at=paused_at, resumed_at=resumed_at)


def make_fake_date(year: int, month: int, day: int):
    """
    Gibt eine date-Unterklasse zurück deren today() das angegebene Datum liefert.

    Verwendung:
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 6))

    Identisch zur Implementierung in test_subscriptions_v023.py.
    """
    _fixed = date(year, month, day)

    class FakeDate(date):
        @classmethod
        def today(cls) -> date:
            return _fixed

    return FakeDate


# ─── T-01: applicable_billing_terms — korrekter Eintrag für ein Datum ────────

class TestT01ApplicableBillingTerms:
    """
    Zwei Billing-History-Einträge:
      - Jan 2026: 8,99 € monatlich
      - Apr 2026: 9,99 € monatlich (Preiserhöhung, same interval)

    today = 05.05.2026

    Datum vor Apr-Wechsel → erster Eintrag.
    Datum nach Apr-Wechsel → zweiter Eintrag.
    Genau auf dem Wechseldatum → zweiter Eintrag (Grenze inklusiv).
    Datum vor erstem Eintrag → None (kein gültiger Eintrag).
    """

    HISTORY = [
        bh_entry("8.99", BillingInterval.monthly, date(2026, 1, 1)),
        bh_entry("9.99", BillingInterval.monthly, date(2026, 4, 1)),
    ]

    def test_t01_before_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """due_date = Mär-01, liegt vor Apr-Wechsel → erster Eintrag (8,99 €)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2026, 3, 1), self.HISTORY)
        assert result is not None
        assert result.amount == Decimal("8.99")

    def test_t01_after_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """due_date = Mai-01, liegt nach Apr-Wechsel → zweiter Eintrag (9,99 €)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2026, 5, 1), self.HISTORY)
        assert result is not None
        assert result.amount == Decimal("9.99")

    def test_t01_on_change_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """due_date = Apr-01 (genau auf Wechseldatum) → zweiter Eintrag (Grenze inklusiv)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2026, 4, 1), self.HISTORY)
        assert result is not None
        assert result.amount == Decimal("9.99")

    def test_t01_before_history_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Datum vor dem ersten Eintrag → None (noch kein gültiger Billing-Eintrag)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2025, 12, 31), self.HISTORY)
        assert result is None


# ─── T-02: applicable_billing_terms mit include_future=True ─────────────────

class TestT02IncludeFuture:
    """
    billing_history enthält einen zukünftigen Eintrag (valid_from > today).

    today = 05.05.2026
    Aug-01 Wechsel: 9,99 € monatlich → 99,99 € jährlich (noch nicht in Kraft)

    include_future=False (Standard):
      Sep-01 liegt nach Aug-Wechsel — aber Aug-01 > today → Wechsel unsichtbar → Jan-Eintrag.
    include_future=True:
      Aug-01 wird berücksichtigt → Sep-01 bekommt 99,99 €.

    Warum wichtig? price_change() nutzt include_future=True für den Copy-forward:
    Ein neuer Preiseintrag muss das Intervall des (evtl. zukünftigen) Vorgängers erben.
    """

    HISTORY = [
        bh_entry("9.99", BillingInterval.monthly, date(2026, 1, 1)),
        bh_entry("99.99", BillingInterval.yearly, date(2026, 8, 1)),  # Zukunft
    ]

    def test_t02_future_ignored_without_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """include_future=False: Aug-Wechsel > today → unsichtbar → Sep-01 bekommt Jan-Eintrag."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2026, 9, 1), self.HISTORY, include_future=False)
        assert result is not None
        assert result.amount == Decimal("9.99")

    def test_t02_future_visible_with_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """include_future=True: Aug-Wechsel sichtbar → Sep-01 bekommt Aug-Eintrag (99,99 €)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = applicable_billing_terms(date(2026, 9, 1), self.HISTORY, include_future=True)
        assert result is not None
        assert result.amount == Decimal("99.99")
        assert result.interval == BillingInterval.yearly


# ─── T-03: compute_due_dates_for_billing_history — einfache monatliche Historie

class TestT03SimpleBillingHistory:
    """
    Ein einziger Billing-Eintrag: 9,99 € monatlich ab Jan-15-2026, Anker Jan-15.
    up_to = Mär-15-2026 → drei Fälligkeiten (15.01., 15.02., 15.03.).

    Kein Monkeypatch nötig — up_to wird explizit übergeben, date.today() nicht aufgerufen.
    """

    HISTORY = [
        bh_entry("9.99", BillingInterval.monthly, date(2026, 1, 15)),
    ]

    def test_t03_correct_due_dates(self) -> None:
        """Drei monatliche Fälligkeiten im Zeitraum."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 3, 15))
        assert [d.due_date for d in result] == [
            date(2026, 1, 15),
            date(2026, 2, 15),
            date(2026, 3, 15),
        ]

    def test_t03_amounts_all_equal(self) -> None:
        """Alle Fälligkeiten tragen den Betrag aus dem Billing-Eintrag."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 3, 15))
        assert all(d.amount == Decimal("9.99") for d in result)

    def test_t03_empty_history(self) -> None:
        """Leere Historie → leere Liste, kein Absturz."""
        result = compute_due_dates_for_billing_history([], date(2026, 3, 15))
        assert result == []


# ─── T-04: compute_due_dates_for_billing_history — Copy-forward-Anker ────────

class TestT04CopyForwardAnchor:
    """
    Preisänderung: Intervall bleibt monatlich, anchor_on wird vom Vorgänger übernommen.

    Segment 1:  9,99 € monatlich, valid_from=Jan-01, anchor_on=Jan-01
    Segment 2: 12,99 € monatlich, valid_from=Apr-01, anchor_on=Jan-01 ← Copy-forward!

    Schlüsseleigenschaft:
      Die Fälligkeiten bleiben am selben Tag des Monats (1.), weil der Anker nicht
      zurückgesetzt wurde. Das unterscheidet Preisänderung von Intervallwechsel (T-05).

    Kein Monkeypatch nötig.
    """

    HISTORY = [
        bh_entry("9.99",  BillingInterval.monthly, date(2026, 1, 1), anchor_on=date(2026, 1, 1)),
        bh_entry("12.99", BillingInterval.monthly, date(2026, 4, 1), anchor_on=date(2026, 1, 1)),
    ]

    def test_t04_dates_stay_on_first_of_month(self) -> None:
        """Alle fünf Fälligkeiten liegen am 1. des Monats — Copy-forward hält den Rhythmus."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 5, 1))
        assert [d.due_date for d in result] == [
            date(2026, 1, 1),
            date(2026, 2, 1),
            date(2026, 3, 1),
            date(2026, 4, 1),
            date(2026, 5, 1),
        ]

    def test_t04_amounts_switch_at_change_date(self) -> None:
        """Vor Apr-01: 9,99 €. Ab Apr-01 (inklusiv): 12,99 €."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 5, 1))
        amounts = [(d.due_date, d.amount) for d in result]
        assert amounts == [
            (date(2026, 1, 1), Decimal("9.99")),
            (date(2026, 2, 1), Decimal("9.99")),
            (date(2026, 3, 1), Decimal("9.99")),
            (date(2026, 4, 1), Decimal("12.99")),
            (date(2026, 5, 1), Decimal("12.99")),
        ]


# ─── T-05: compute_due_dates_for_billing_history — Intervallwechsel ──────────

class TestT05IntervalChange:
    """
    Intervallwechsel: monatlich → jährlich ab Apr-01.

    Segment 1: 9,99 € monatlich,  valid_from=Jan-01, anchor_on=Jan-01
    Segment 2: 99,99 € jährlich,  valid_from=Apr-01, anchor_on=Apr-01 ← neuer Anker!

    Schlüsseleigenschaft:
      Die Jahresfälligkeit liegt auf Apr-01 (neuem Anker), nicht auf Jan-01.
      Das ist der Kernunterschied zu Preisänderung (T-04).

    Kein Monkeypatch nötig.
    """

    HISTORY = [
        bh_entry("9.99",  BillingInterval.monthly, date(2026, 1, 1), anchor_on=date(2026, 1, 1)),
        bh_entry("99.99", BillingInterval.yearly,  date(2026, 4, 1), anchor_on=date(2026, 4, 1)),
    ]

    def test_t05_monthly_segment_jan_to_mar(self) -> None:
        """Monatliche Fälligkeiten nur Jan, Feb, Mär — Apr-01 gehört bereits zum Jahres-Segment."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 12, 31))
        monthly = [d for d in result if d.interval == BillingInterval.monthly]
        assert [d.due_date for d in monthly] == [
            date(2026, 1, 1),
            date(2026, 2, 1),
            date(2026, 3, 1),
        ]

    def test_t05_yearly_fälligkeit_on_new_anchor(self) -> None:
        """Jahresfälligkeit liegt auf Apr-01 (neuem Anker) — nicht auf Jan-01."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 12, 31))
        yearly = [d for d in result if d.interval == BillingInterval.yearly]
        assert len(yearly) == 1
        assert yearly[0].due_date == date(2026, 4, 1)
        assert yearly[0].amount == Decimal("99.99")

    def test_t05_total_four_entries(self) -> None:
        """Insgesamt 4 Einträge: 3 monatliche + 1 jährliche."""
        result = compute_due_dates_for_billing_history(self.HISTORY, date(2026, 12, 31))
        assert len(result) == 4


# ─── T-06: compute_tatsaechlich mit Intervallwechsel ─────────────────────────

class TestT06Tatsaechlich:
    """
    today = 01.07.2026

    Monatlich Jan–Mär → 3 × 9,99 € = 29,97 €
    Quartalsweise ab Apr, Anker Apr-01 → Apr-01, Jul-01 → 2 × 24,99 € = 49,98 €
    Gesamt: 79,95 €

    Jul-01 <= today = Jul-01 → inklusiv.
    """

    HISTORY = [
        bh_entry("9.99",  BillingInterval.monthly,   date(2026, 1, 1)),
        bh_entry("24.99", BillingInterval.quarterly,  date(2026, 4, 1)),
    ]

    def test_t06_combined_total(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 7, 1))
        result = compute_tatsaechlich(self.HISTORY, [])
        assert result == Decimal("79.95")


# ─── T-07: compute_tatsaechlich — pausierte Periode ausgeschlossen ────────────

class TestT07TatsaechlichWithPause:
    """
    today = 05.05.2026

    Billing: 9,99 € monatlich ab Jan-01.
    Fälligkeiten bis today (≤ Mai-05): Jan-01, Feb-01, Mär-01, Apr-01, Mai-01 (5 Stück).
    Pause: Mär-15 bis Apr-15 → Apr-01 liegt in [Mär-15, Apr-15] → pausiert.
    Nicht pausiert: Jan, Feb, Mär, Mai → 4 × 9,99 = 39,96 €.
    """

    HISTORY = [bh_entry("9.99", BillingInterval.monthly, date(2026, 1, 1))]
    PAUSES  = [pause_entry(date(2026, 3, 15), date(2026, 4, 15))]

    def test_t07_paused_period_excluded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Apr-01 in Pause → nur 4 Perioden werden summiert."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_tatsaechlich(self.HISTORY, self.PAUSES)
        assert result == Decimal("39.96")


# ─── T-08: compute_intervalle ─────────────────────────────────────────────────

class TestT08Intervalle:
    """
    today = 05.05.2026, monatlich ab Jan-01.
    Fälligkeiten: Jan, Feb, Mär, Apr, Mai-01 → 5 gesamt.
    Mit Pause [Mär-15, Apr-15]: Apr-01 ausgeschlossen → 4.
    """

    HISTORY = [bh_entry("9.99", BillingInterval.monthly, date(2026, 1, 1))]

    def test_t08_no_pause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ohne Pause: 5 Zahlungsperioden."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_intervalle(self.HISTORY, [])
        assert result == 5

    def test_t08_with_pause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Apr-01 pausiert → 4 Zahlungsperioden."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        pauses = [pause_entry(date(2026, 3, 15), date(2026, 4, 15))]
        result = compute_intervalle(self.HISTORY, pauses)
        assert result == 4


# ─── T-09: compute_dieses_kalenderjahr — mit Intervallwechsel ────────────────

class TestT09DiesesKalenderjahr:
    """
    today = 06.05.2026

    Monatlich Jan–Jun (6 Perioden × 9,99 € = 59,94 €)
    Jährlich  ab Jul-01, Anker Jul-01 (1 Periode × 99,99 € = 99,99 €)
    Dieses Jahr = 59,94 + 99,99 = 159,93 €

    Hinweis: auch zukünftige Einträge (Jul-01 > today) fließen automatisch ein,
    da compute_dieses_kalenderjahr bis Dez-31 rechnet. Das ergibt den
    Projektions-Charakter ohne ein extra include_future-Flag.
    """

    HISTORY = [
        bh_entry("9.99",  BillingInterval.monthly, date(2026, 1, 1)),
        bh_entry("99.99", BillingInterval.yearly,  date(2026, 7, 1)),
    ]

    def test_t09_jahreskosten_mit_intervallwechsel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 6))
        result = compute_dieses_kalenderjahr(self.HISTORY, [])
        assert result == Decimal("159.93")


# ─── T-10: compute_next_due_date_from_history — nach Intervallwechsel ─────────

class TestT10NextDueDateFromHistory:
    """
    today = 06.05.2026

    Segment 1: monatlich ab Jan-01 (Anker Jan-01)
    Segment 2: jährlich ab Apr-01 (Anker Apr-01 — neuer Anker durch Intervallwechsel)

    Fälligkeiten des Jahres-Segments: Apr-01-2026, Apr-01-2027, …
    Apr-01-2026 liegt vor today → nächste Fälligkeit = Apr-01-2027.

    Kein Monkeypatch nötig — today wird explizit übergeben.
    """

    HISTORY = [
        bh_entry("9.99",  BillingInterval.monthly, date(2026, 1, 1)),
        bh_entry("99.99", BillingInterval.yearly,  date(2026, 4, 1)),
    ]

    def test_t10_next_yearly_after_change(self) -> None:
        """Nächste Fälligkeit nach Apr-01-2026 (vergangen) ist Apr-01-2027."""
        result = compute_next_due_date_from_history(self.HISTORY, date(2026, 5, 6))
        assert result == date(2027, 4, 1)

    def test_t10_skips_due_today(self) -> None:
        """Wenn heute eine Faelligkeit ist, zeigt next_due_date die naechste Periode."""
        result = compute_next_due_date_from_history(self.HISTORY, date(2026, 4, 1))
        assert result == date(2027, 4, 1)

    def test_t10_skips_past_due_yesterday(self) -> None:
        """Ein Monatsabo von gestern zeigt als next_due_date den Folgemonat."""
        history = [bh_entry("9.99", BillingInterval.monthly, date(2026, 5, 6))]
        result = compute_next_due_date_from_history(history, date(2026, 5, 7))
        assert result == date(2026, 6, 6)

    def test_t10_empty_history_sentinel(self) -> None:
        """Leere Historie → Sentinel-Datum 9999-12-31 (kein Absturz, kein None)."""
        result = compute_next_due_date_from_history([], date(2026, 5, 6))
        assert result == date(9999, 12, 31)
