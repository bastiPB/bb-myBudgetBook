# v0.2.3 — Akzeptanz-Szenarien

Status: draft  
Scope: v0.2.3 Algorithmen — compute_tatsaechlich, compute_dieses_kalenderjahr, Scheduler-Rewrite, relativedelta  
Referenz: [docs/18-v023-subscription-redesign-discussion.md](18-v023-subscription-redesign-discussion.md)

---

## Zweck

Dieses Dokument beschreibt konkrete End-to-End-Szenarien die vor dem Merge von v0.2.3 grün sein müssen.  
Jedes Szenario ist so geschrieben dass es direkt als pytest-Testfall umgesetzt werden kann.

Konventionen:
- `today` wird in jedem Test per Monkeypatch auf einen fixen Wert gesetzt — nie `date.today()` direkt im Algorithmus
- Preishistorie und Pausenhistorie sind Eingabedaten, keine DB-Calls (Service-Logik isoliert testbar)
- `relativedelta` immer von `started_on` aus — nie iterativ von Periode zu Periode

---

## S-01: Monatsgrenzen — relativedelta-Ankertag

**Was getestet wird:** Fälligkeitsdaten bei Monatsende-Startdatum.  
Der Ankertag (31.) muss sich erholen wenn der Monat es erlaubt — ohne iterative Drift.

### Setup

| Feld | Wert |
|------|------|
| started_on | 2026-01-31 |
| interval | monthly |
| amount | 35,00 € |
| price_history | [{ amount: 35.00, valid_from: 2026-01-31 }] |
| pause_history | [] |
| today (monkeypatched) | 2026-05-05 |

### Erwartete Fälligkeitsdaten

| N | Berechnung | Ergebnis | Begründung |
|---|-----------|----------|------------|
| 0 | started_on + 0 Monate | 2026-01-31 | Startdatum |
| 1 | started_on + 1 Monat  | 2026-02-28 | Feb hat 28 Tage → Klemmen |
| 2 | started_on + 2 Monate | 2026-03-31 | März hat 31 → Ankertag erholt sich |
| 3 | started_on + 3 Monate | 2026-04-30 | April hat 30 → Klemmen |
| 4 | started_on + 4 Monate | 2026-05-31 | > today → stop, das ist next_due_date |

### Erwartete Outputs

| Kennzahl | Wert |
|---------|------|
| Perioden bis heute | [2026-01-31, 2026-02-28, 2026-03-31, 2026-04-30] |
| Intervalle | 4 |
| Tatsächlich | 140,00 € (4 × 35,00 €) |
| next_due_date | 2026-05-31 |
| Dieses Kalenderjahr | 420,00 € (12 × 35,00 €) |

**Warum kein iterativer Ansatz funktioniert:**
```
Iterativ (falsch):  31.1 → 28.2 → 28.3 → 28.4 → 28.5  (Ankertag dauerhaft verloren)
Von Ankertag (richtig): 31.1+1M=28.2, 31.1+2M=31.3, 31.1+3M=30.4, 31.1+4M=31.5
```

### Pytest-Skeleton

```python
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal


def test_s01_relativedelta_anchor_recovery():
    """
    31. Januar monatlich: Feb klemmt auf 28., März erholt sich auf 31.
    Ankertag darf bei iterativer Berechnung nicht dauerhaft verloren gehen.
    """
    started_on = date(2026, 1, 31)
    period_months = 1

    expected = [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]
    actual = [started_on + relativedelta(months=n) for n in range(4)]
    assert actual == expected


def test_s01_tatsaechlich(monkeypatch):
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))
    result = compute_tatsaechlich(
        started_on=date(2026, 1, 31),
        period_months=1,
        price_history=[PriceEntry(amount=Decimal("35.00"), valid_from=date(2026, 1, 31))],
        pause_history=[],
    )
    assert result == Decimal("140.00")


def test_s01_next_due_date(monkeypatch):
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))
    assert compute_next_due_date(date(2026, 1, 31), period_months=1) == date(2026, 5, 31)


def test_s01_dieses_kalenderjahr(monkeypatch):
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))
    result = compute_dieses_kalenderjahr(
        started_on=date(2026, 1, 31),
        period_months=1,
        price_history=[PriceEntry(amount=Decimal("35.00"), valid_from=date(2026, 1, 31))],
        pause_history=[],
    )
    assert result == Decimal("420.00")
```

---

## S-02: Fiktive Buchungen — retroaktive Generierung

> **Slice:** Späterer Slice nach v0.2.3. Das Szenario beschreibt das Soll-Verhalten  
> wenn der Toggle implementiert wird.

**Was getestet wird:** Beim Aktivieren von "Buchungshistorie fiktiv" werden alle Perioden
ab started_on bis heute als `pending` generiert — stumpf, ohne Pausenberücksichtigung.

### Setup

| Feld | Wert |
|------|------|
| started_on | 2026-02-03 |
| interval | monthly |
| amount | 10,99 € |
| price_history | [{ amount: 10.99, valid_from: 2026-02-03 }] |
| pause_history | [] (wird ignoriert — fiktiv = stumpf pending) |
| today (monkeypatched) | 2026-05-05 |

### Erwartete generierte Einträge

```
┌────────────────────┬──────────────┬──────────┬──────────────────────────────┐
│ Periode            │ Fälligkeit   │ Betrag   │ Status                       │
├────────────────────┼──────────────┼──────────┼──────────────────────────────┤
│ Februar 2026       │ 03.02.2026   │ 10,99 €  │ pending                      │
│ März 2026          │ 03.03.2026   │ 10,99 €  │ pending                      │
│ April 2026         │ 03.04.2026   │ 10,99 €  │ pending                      │
│ Mai 2026           │ 03.05.2026   │ 10,99 €  │ pending                      │
└────────────────────┴──────────────┴──────────┴──────────────────────────────┘
  Alle Einträge retroaktiv beim Toggle-Aktivieren generiert.
  Ohne CSV-Import: Status bleibt pending — wir wissen nicht ob wirklich gezahlt wurde.
```

### Erwartete Outputs

| Kennzahl | Wert |
|---------|------|
| Generierte Einträge | 4 |
| Status aller Einträge | pending |
| Intervalle | 4 |
| Tatsächlich | ~43,96 € (4 × 10,99 €) |

**Wichtige Einschränkung:** Kein `paused`-Eintrag, auch wenn pause_history Einträge enthält.  
Fiktiv = stumpf alle pending. Pausen greifen nur ab echtem Pausierungszeitpunkt, nicht rückwirkend.

### Pytest-Skeleton

```python
def test_s02_fiktiv_generates_all_periods_as_pending(monkeypatch):
    """
    Fiktiv-Toggle aktiviert: alle Perioden ab started_on bis heute → pending.
    Pausen werden ignoriert. Kein Eintrag > today.
    """
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))

    entries = generate_fiktiv_payments(
        started_on=date(2026, 2, 3),
        period_months=1,
        price_history=[PriceEntry(amount=Decimal("10.99"), valid_from=date(2026, 2, 3))],
    )

    assert len(entries) == 4
    assert all(e.status == PaymentStatus.pending for e in entries)
    assert entries[0].due_date == date(2026, 2, 3)
    assert entries[3].due_date == date(2026, 5, 3)
    assert all(e.amount == Decimal("10.99") for e in entries)


def test_s02_fiktiv_ignores_pause_history(monkeypatch):
    """Pausen fließen in fiktiv-Modus nicht ein — alle pending."""
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))

    pause = PauseInterval(paused_at=date(2026, 3, 1), resumed_at=date(2026, 3, 31))
    entries = generate_fiktiv_payments(
        started_on=date(2026, 2, 3),
        period_months=1,
        price_history=[PriceEntry(amount=Decimal("10.99"), valid_from=date(2026, 2, 3))],
        pause_history=[pause],  # wird ignoriert
    )

    assert all(e.status == PaymentStatus.pending for e in entries)
```

---

## S-03: Pause + Preiserhöhung in derselben Periode

**Was getestet wird:** Pausierte Perioden fließen nicht in "Tatsächlich" ein.  
Eine Preiserhöhung in einer pausierten Periode hat keinen Effekt auf "Tatsächlich",
greift aber ab dem Folge-Monat in "Dieses Kalenderjahr".

### Setup

| Feld | Wert |
|------|------|
| started_on | 2026-03-03 |
| interval | monthly |
| price_history | [{ amount: 8.99, valid_from: 2026-03-03 }, { amount: 9.99, valid_from: 2026-05-03 }] |
| pause_history | [{ paused_at: 2026-04-15, resumed_at: 2026-05-30 }] |
| today (monkeypatched) | 2026-05-05 |

**Pause-Intervall:** 15. April bis 30. Mai 2026

### Scheduler-Entscheidung je Periode

| Periode | due_date | In Pause? | Status | Betrag |
|---------|----------|-----------|--------|--------|
| März 2026 | 2026-03-03 | Apr 15 > Mär 3 → Nein | pending | 8,99 € |
| April 2026 | 2026-04-03 | Apr 15 > Apr 3 → Nein | pending | 8,99 € |
| Mai 2026 | 2026-05-03 | Apr 15 ≤ Mai 3 ≤ Mai 30 → Ja | paused | – |

### Erwartete Buchungshistorie (today = 5.5.2026)

```
┌────────────────────┬──────────────┬──────────┬──────────────────────────────┐
│ Periode            │ Fälligkeit   │ Betrag   │ Status                       │
├────────────────────┼──────────────┼──────────┼──────────────────────────────┤
│ März 2026          │ 03.03.2026   │  8,99 €  │ pending                      │
│ April 2026         │ 03.04.2026   │  8,99 €  │ pending                      │
│ Mai 2026           │ 03.05.2026   │      –   │ paused                       │
└────────────────────┴──────────────┴──────────┴──────────────────────────────┘
  Pausiert: 15. April bis 30. Mai 2026
  Preiserhöhung auf 9,99 € ab 3. Mai — Mai ist pausiert, greift erst in Juni
```

### Erwartete Outputs

| Kennzahl | Wert | Begründung |
|---------|------|------------|
| Intervalle | 2 | März + April (Mai pausiert) |
| Tatsächlich | 17,98 € | 2 × 8,99 € — Mai zählt nicht |
| next_due_date | 2026-06-03 | Nächste Periode nach today, Pause endet 30. Mai |
| Dieses Kalenderjahr | 87,91 € | Mär+Apr: 2×8,99 + Mai: 0 + Jun–Dez: 7×9,99 |

**Dieses Kalenderjahr — Aufschlüsselung:**
```
Mär 03:  8,99 €  (nicht pausiert, alter Preis gilt ab Mär 3)
Apr 03:  8,99 €  (nicht pausiert, Apr 3 < paused_at Apr 15)
Mai 03:  0,00 €  (pausiert → überspringen)
Jun 03:  9,99 €  (Pause endet Mai 30, Jun 3 > Mai 30 → nicht pausiert; neuer Preis)
Jul 03:  9,99 €
Aug 03:  9,99 €
Sep 03:  9,99 €
Okt 03:  9,99 €
Nov 03:  9,99 €
Dez 03:  9,99 €
──────────────────────────────────────────
         2 × 8,99 = 17,98 €
       + 7 × 9,99 = 69,93 €
       = 87,91 €
```

### Pytest-Skeleton

```python
@pytest.mark.parametrize("due_date,expected_status,expected_amount", [
    (date(2026, 3, 3), PaymentStatus.pending, Decimal("8.99")),
    (date(2026, 4, 3), PaymentStatus.pending, Decimal("8.99")),
    (date(2026, 5, 3), PaymentStatus.paused,  None),
])
def test_s03_scheduler_pause_and_price_change(due_date, expected_status, expected_amount):
    """
    April-Pause beginnt am 15. — Apr 3 liegt davor, also nicht pausiert.
    Mai liegt im Pause-Intervall [Apr 15, Mai 30] → paused.
    Preiserhöhung ab Mai 3 hat keinen Effekt auf den paused-Eintrag.
    """
    pause_history = [PauseInterval(paused_at=date(2026, 4, 15), resumed_at=date(2026, 5, 30))]
    price_history = [
        PriceEntry(amount=Decimal("8.99"), valid_from=date(2026, 3, 3)),
        PriceEntry(amount=Decimal("9.99"), valid_from=date(2026, 5, 3)),
    ]
    result = compute_period_entry(due_date, price_history, pause_history)
    assert result.status == expected_status
    assert result.amount == expected_amount


def test_s03_tatsaechlich_excludes_paused(monkeypatch):
    """Tatsächlich = nur nicht-pausierte Perioden × ihren Preis."""
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))
    result = compute_tatsaechlich(
        started_on=date(2026, 3, 3),
        period_months=1,
        price_history=[
            PriceEntry(amount=Decimal("8.99"), valid_from=date(2026, 3, 3)),
            PriceEntry(amount=Decimal("9.99"), valid_from=date(2026, 5, 3)),
        ],
        pause_history=[PauseInterval(paused_at=date(2026, 4, 15), resumed_at=date(2026, 5, 30))],
    )
    assert result == Decimal("17.98")


def test_s03_dieses_kalenderjahr_future_price_after_pause(monkeypatch):
    """
    Dieses Kalenderjahr berücksichtigt:
    - Pause (Mai übersprungen)
    - Preiserhöhung (greift ab Jun, da Mai pausiert)
    """
    monkeypatch.setattr("app.services.subscriptions.date", FakeDate(2026, 5, 5))
    result = compute_dieses_kalenderjahr(
        started_on=date(2026, 3, 3),
        period_months=1,
        price_history=[
            PriceEntry(amount=Decimal("8.99"), valid_from=date(2026, 3, 3)),
            PriceEntry(amount=Decimal("9.99"), valid_from=date(2026, 5, 3)),
        ],
        pause_history=[PauseInterval(paused_at=date(2026, 4, 15), resumed_at=date(2026, 5, 30))],
    )
    assert result == Decimal("87.91")
```

---

## Algorithmus-Referenz (Pause-Intervall-Prüfung)

```python
def is_paused(due_date: date, pause_history: list[PauseInterval]) -> bool:
    return any(
        p.paused_at <= due_date and (p.resumed_at is None or due_date <= p.resumed_at)
        for p in pause_history
    )
```

```python
def applicable_price(due_date: date, price_history: list[PriceEntry], include_future: bool = False) -> Decimal:
    candidates = [p for p in price_history if p.valid_from <= due_date]
    if not include_future:
        candidates = [p for p in candidates if p.valid_from <= date.today()]
    return max(candidates, key=lambda p: p.valid_from).amount
    # include_future=True  → für "Dieses Kalenderjahr" (Ankündigungen als Projektion)
    # include_future=False → für "Tatsächlich" (nur Vergangenheitspreise)
```
