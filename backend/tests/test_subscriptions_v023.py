"""
tests/test_subscriptions_v023.py — Akzeptanz-Tests für v0.2.3 Algorithmen

Szenarien aus docs/19-v023-test-scenarios.md:
- S-01: relativedelta-Ankertag, tatsaechlich, next_due_date, dieses_kalenderjahr
- S-02: Fiktiv-Toggle (skip — späterer Slice)
- S-03: Pause + Preiserhöhung in derselben Periode

Monkeypatch-Strategie:
  Die Service-Funktionen rufen date.today() in Untermodulen auf (v0.2.5: billing,
  readers, mutations, lifecycle). patch_subscriptions_service_date ersetzt dort
  date durch eine FakeDate-Klasse — deterministische Tests unabhängig vom System-Datum.

Keine DB: alle Tests testen Service-Logik isoliert (reine Python-Objekte).
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from dateutil.relativedelta import relativedelta

from app.models.subscription import BillingInterval
from app.services.subscriptions import (
    compute_dieses_kalenderjahr,
    compute_due_dates,
    compute_intervalle,
    compute_next_due_date,
    compute_tatsaechlich,
    is_in_pause,
)

# Nach v0.2.5 liegt date.today() in billing/readers/mutations/lifecycle — nicht im Paket-Root.
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

def billing_entry(amount: str, interval: BillingInterval, valid_from: date, anchor_on: date) -> SimpleNamespace:
    """Minimale Billing-History-Zeile im v0.2.4-Format für isolierte Service-Tests."""
    return SimpleNamespace(
        amount=Decimal(amount),
        interval=interval,
        valid_from=valid_from,
        anchor_on=anchor_on,
        id=None,
    )


def pause_entry(paused_at: date, resumed_at: date | None = None) -> SimpleNamespace:
    """Minimale Pausenhistorie-Zeile — nur .paused_at und .resumed_at werden gebraucht."""
    return SimpleNamespace(paused_at=paused_at, resumed_at=resumed_at)


def make_fake_date(year: int, month: int, day: int):
    """
    Gibt eine date-Unterklasse zurück deren today() das angegebene Datum liefert.

    Verwendung:
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))

    Die zurückgegebene Klasse kann weiterhin als Konstruktor genutzt werden:
        FakeDate(2026, 3, 1)  →  date(2026, 3, 1)
    """
    _fixed = date(year, month, day)

    class FakeDate(date):
        @classmethod
        def today(cls) -> date:
            return _fixed

    return FakeDate


# ─── S-01: Monatsgrenzen — relativedelta-Ankertag ─────────────────────────────

class TestS01RelativeDeltaAnchor:
    """
    started_on = 31.01.2026, monthly.
    Feb klemmt auf 28 — März erholt sich auf 31 (Ankertag-Recovery).
    Iterative Berechnung würde den Ankertag dauerhaft verlieren.
    """

    def test_s01_relativedelta_anchor_recovery(self) -> None:
        """31. Januar + N Monate: Feb=28, Mrz=31, Apr=30 — Ankertag erholt sich."""
        started_on = date(2026, 1, 31)
        expected = [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
        ]
        actual = [started_on + relativedelta(months=n) for n in range(4)]
        assert actual == expected

    def test_s01_due_dates_up_to_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """compute_due_dates liefert alle Fälligkeiten von Jan bis Apr (inkl.)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_due_dates(date(2026, 1, 31), period_months=1, up_to=date(2026, 5, 5))
        assert result == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
        ]

    def test_s01_next_due_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Naechster zukuenftiger Faelligkeitstag > today(5.5.2026) ist 31.05.2026."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_next_due_date(date(2026, 1, 31), period_months=1)
        assert result == date(2026, 5, 31)

    def test_s01_next_due_date_skips_due_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wenn heute ein Faelligkeitstag ist, zeigt next_due_date die naechste Periode."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 7))
        result = compute_next_due_date(date(2026, 5, 7), period_months=1)
        assert result == date(2026, 6, 7)

    def test_s01_next_due_date_skips_past_due_yesterday(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ein gestern gestartetes Monatsabo ist als naechstes im Folgemonat faellig."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 7))
        result = compute_next_due_date(date(2026, 5, 6), period_months=1)
        assert result == date(2026, 6, 6)

    def test_s01_tatsaechlich(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tatsächlich = 4 Perioden × 35,00 € = 140,00 €."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        bh = [billing_entry("35.00", BillingInterval.monthly, date(2026, 1, 31), anchor_on=date(2026, 1, 31))]
        result = compute_tatsaechlich(billing_history=bh, pause_history=[])
        assert result == Decimal("140.00")

    def test_s01_intervalle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Intervalle = 4 (Jan, Feb, Mär, Apr — alle nicht pausiert)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        bh = [billing_entry("35.00", BillingInterval.monthly, date(2026, 1, 31), anchor_on=date(2026, 1, 31))]
        result = compute_intervalle(billing_history=bh, pause_history=[])
        assert result == 4

    def test_s01_dieses_kalenderjahr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Dieses Kalenderjahr = 12 Monate × 35,00 € = 420,00 €.
        Alle Perioden Jan–Dez 2026 liegen im Kalenderjahr, kein Preiswechsel.
        """
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        bh = [billing_entry("35.00", BillingInterval.monthly, date(2026, 1, 31), anchor_on=date(2026, 1, 31))]
        result = compute_dieses_kalenderjahr(billing_history=bh, pause_history=[])
        assert result == Decimal("420.00")


# ─── S-02: Fiktive Buchungen (späterer Slice) ────────────────────────────────

@pytest.mark.skip(reason="Fiktiv-Toggle: späterer Slice nach v0.2.3")
class TestS02FiktivBookings:
    """Fiktiv-Toggle aktiviert: alle Perioden ab started_on → pending (Pausen ignoriert)."""

    def test_s02_fiktiv_generates_all_periods_as_pending(self) -> None:
        pass

    def test_s02_fiktiv_ignores_pause_history(self) -> None:
        pass


# ─── S-03: Pause + Preiserhöhung in derselben Periode ────────────────────────

class TestS03PauseAndPriceChange:
    """
    started_on = 03.03.2026, monthly.
    Pause: 15.04. bis 30.05.2026.
    Preiserhöhung: 9,99 € ab 03.05.2026.
    today = 05.05.2026.

    Apr 3 liegt vor der Pause (< 15.04.) → pending @ 8,99 €.
    Mai 3 liegt in der Pause [15.04–30.05] → paused.
    Preiserhöhung greift erst ab Jun, weil Mai pausiert ist.
    """

    STARTED_ON = date(2026, 3, 3)
    PERIOD_MONTHS = 1
    # Billing-Historie im v0.2.4-Format: Preiswechsel → anchor_on bleibt gleich wie der erste Eintrag.
    BILLING_HISTORY = [
        billing_entry("8.99", BillingInterval.monthly, date(2026, 3, 3), anchor_on=date(2026, 3, 3)),
        billing_entry("9.99", BillingInterval.monthly, date(2026, 5, 3), anchor_on=date(2026, 3, 3)),
    ]
    PAUSE_HISTORY = [
        pause_entry(paused_at=date(2026, 4, 15), resumed_at=date(2026, 5, 30)),
    ]

    @pytest.mark.parametrize("due_date,in_pause", [
        (date(2026, 3, 3), False),  # Mär — vor Pause
        (date(2026, 4, 3), False),  # Apr — Apr 3 < paused_at Apr 15 → nicht pausiert
        (date(2026, 5, 3), True),   # Mai — liegt in [Apr 15, Mai 30]
    ])
    def test_s03_is_in_pause(self, due_date: date, in_pause: bool) -> None:
        """is_in_pause erkennt korrekt welche Fälligkeiten in der Pause liegen."""
        result = is_in_pause(due_date, self.PAUSE_HISTORY)
        assert result is in_pause

    def test_s03_tatsaechlich_excludes_paused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tatsächlich = 2 × 8,99 € = 17,98 € — Mai (pausiert) zählt nicht."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_tatsaechlich(
            billing_history=self.BILLING_HISTORY,
            pause_history=self.PAUSE_HISTORY,
        )
        assert result == Decimal("17.98")

    def test_s03_intervalle_excludes_paused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Intervalle = 2 — nur Mär + Apr (Mai pausiert)."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_intervalle(
            billing_history=self.BILLING_HISTORY,
            pause_history=self.PAUSE_HISTORY,
        )
        assert result == 2

    def test_s03_dieses_kalenderjahr_with_future_price_after_pause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Dieses Kalenderjahr = 2×8,99 + 7×9,99 = 17,98 + 69,93 = 87,91 €.
        Mai pausiert → übersprungen. Preiserhöhung greift ab Jun.
        Monate: Mär(8.99) + Apr(8.99) + Mai(0) + Jun–Dez(7×9.99).
        """
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        result = compute_dieses_kalenderjahr(
            billing_history=self.BILLING_HISTORY,
            pause_history=self.PAUSE_HISTORY,
        )
        assert result == Decimal("87.91")

    def test_s03_next_due_date_after_pause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Naechste zukuenftige Faelligkeit > today(05.05.) ist 03.06.2026."""
        patch_subscriptions_service_date(monkeypatch, make_fake_date(2026, 5, 5))
        # compute_next_due_date rechnet rein aus started_on+N×period — ohne Pausenberücksichtigung.
        # Der naechste berechnete Termin > 05.05.2026 ist 03.06.2026.
        result = compute_next_due_date(self.STARTED_ON, self.PERIOD_MONTHS)
        assert result == date(2026, 6, 3)
