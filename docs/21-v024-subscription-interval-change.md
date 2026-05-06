# v0.2.4 - Subscription Interval Change

Status: draft
Stand: 2026-05-06
Referenzen:
- v0.2.3 Redesign: [18-v023-subscription-redesign-discussion.md](18-v023-subscription-redesign-discussion.md)
- v0.2.3 Tests: [19-v023-test-scenarios.md](19-v023-test-scenarios.md)
- v0.2.3 Build Plan: [20-v023-build-plan.md](20-v023-build-plan.md)

---

## Ziel

Der Subscription Manager soll Aenderungen des Abrechnungsintervalls korrekt abbilden.

Beispiele:
- Google One wird von monatlich 1,99 EUR auf jaehrlich 19,99 EUR umgestellt.
- Ein Streaming-Abo wird von jaehrlich 59,99 EUR zurueck auf monatlich 6,99 EUR gesetzt.
- Ein Nutzer traegt die Umstellung rueckwirkend ein, weil er sie erst spaeter im Tool erfasst.

Wichtig: Eine Intervallaenderung ist fachlich fast immer auch eine Preisaenderung.
Darum darf sie nicht als einfaches `PATCH interval` umgesetzt werden.

---

## Kernentscheidung

Preis, Intervall und Faelligkeitsanker werden gemeinsam historisiert.

Bisher gibt es eine Preishistorie:

```text
subscription_price_history
- subscription_id
- amount
- valid_from
```

Fuer v0.2.4 wird daraus eine neue Historie der Abrechnungsbedingungen:

```text
subscription_billing_history
- subscription_id
- amount
- interval
- valid_from
- anchor_on
```

Entscheidung: v0.2.4 legt eine neue Tabelle `subscription_billing_history` an.
`subscription_price_history` wird nicht mit `interval` und `anchor_on` erweitert.

Begruendung:
- Die Algorithmen werden ohnehin groesser umgebaut.
- Der alte Name beschreibt das neue Konzept nicht mehr.
- Eine saubere Tabelle verhindert spaetere Verwirrung zwischen "Preis" und "Abrechnungsbedingungen".
- Die Codebase ist noch ueberschaubar genug, um den Schnitt jetzt sauber zu ziehen.

---

## Begriffe

### `amount`

Betrag pro Abrechnungsperiode.

Beispiele:
- monatlich 5,00 EUR -> `amount = 5.00`, `interval = monthly`
- jaehrlich 54,00 EUR -> `amount = 54.00`, `interval = yearly`

`amount` ist nicht "monatlich normalisiert".
Die Normalisierung passiert nur fuer Kennzahlen wie `monatlich`.

### `interval`

Abrechnungsintervall der Periode:

```text
monthly
quarterly
semiannual
yearly
biennial
```

### `valid_from`

Ab wann diese Abrechnungsbedingungen fachlich gelten.

Bei einer reinen Preisaenderung bedeutet das:

> Ab diesem Datum gilt ein anderer Preis, aber der Zahlungsrhythmus bleibt gleich.

Bei einer Intervallaenderung bedeutet das im MVP:

> Ab diesem Datum beginnt der neue Zahlungsrhythmus.

### `anchor_on`

Datum, von dem aus Faelligkeiten fuer diesen History-Eintrag berechnet werden.

Das ist der entscheidende Unterschied zwischen Preis- und Intervallaenderung:

- Reine Preisaenderung: `anchor_on` bleibt gleich.
- Intervallaenderung: `anchor_on = valid_from`.

---

## Warum `anchor_on` noetig ist

### Reine Preisaenderung

Setup:

```text
started_on: 2026-03-15
interval: monthly
amount: 5.00
price change: 7.00 ab 2026-05-01
```

Erwartete Faelligkeiten:

```text
2026-03-15  5.00
2026-04-15  5.00
2026-05-15  7.00
2026-06-15  7.00
```

Der Preis gilt ab 1. Mai, aber die Faelligkeit bleibt am 15.
Darum darf `valid_from = 2026-05-01` den Rhythmus nicht neu starten.

History:

```text
amount  interval  valid_from  anchor_on
5.00    monthly   2026-03-15  2026-03-15
7.00    monthly   2026-05-01  2026-03-15
```

### Intervallaenderung

Setup:

```text
started_on: 2026-03-15
old: monthly 5.00
new: yearly 54.00 ab 2026-07-01
```

Erwartete Faelligkeiten:

```text
2026-03-15   5.00
2026-04-15   5.00
2026-05-15   5.00
2026-06-15   5.00
2026-07-01  54.00
2027-07-01  54.00
```

Der neue Jahresrhythmus beginnt am 1. Juli.

History:

```text
amount  interval  valid_from  anchor_on
5.00    monthly   2026-03-15  2026-03-15
54.00   yearly    2026-07-01  2026-07-01
```

---

## Nicht-Ziele

v0.2.4 soll keine automatische Buchungsbereinigung erzwingen.

Nicht Teil des MVP:
- Alte Scheduled Payments automatisch loeschen.
- Alte monatliche Buchungen automatisch in eine Jahresbuchung umwandeln.
- Banktransaktionen matchen oder korrigieren.
- Prorata-Berechnungen fuer angebrochene Perioden.
- Mehrere parallele Tarife pro Abo.

Der Fokus ist:

1. Historie korrekt speichern.
2. Kennzahlen korrekt berechnen.
3. Nutzer vor betroffenen bestehenden Buchungen warnen/blocken.

---

## Datenmodell

### Neue Tabelle

```python
class SubscriptionBillingHistory(BaseModel):
    __tablename__ = "subscription_billing_history"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, name="billinginterval"),
        nullable=False,
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    anchor_on: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("subscription_id", "valid_from", name="uq_billing_history_valid_from"),
    )
```

Hinweis fuer die Alembic-Migration:

Der PostgreSQL-Enum `billinginterval` existiert bereits durch `subscriptions.interval`.
Beim Anlegen der neuen Tabelle darf Alembic/PostgreSQL den Enum nicht erneut erzeugen.
In der Migration muss der Enum daher mit `create_type=False` wiederverwendet werden:

```python
sa.Column(
    "interval",
    sa.Enum(
        "monthly",
        "quarterly",
        "semiannual",
        "yearly",
        "biennial",
        name="billinginterval",
        create_type=False,
    ),
    nullable=False,
)
```

Im SQLAlchemy-Model selbst bleibt `SAEnum(BillingInterval, name="billinginterval")` ausreichend.

### Migration aus `subscription_price_history`

Die bestehende Preishistorie ist die Datenquelle fuer die initiale Billing-Historie.
Jeder bestehende Preiseintrag wird migriert und bekommt das aktuell gespeicherte Intervall des Abos sowie `started_on` als ersten Anker.

```python
def upgrade() -> None:
    op.create_table(...)

    import uuid as _uuid
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        """
        SELECT
            ph.subscription_id,
            ph.amount,
            ph.valid_from,
            s.interval,
            s.started_on
        FROM subscription_price_history ph
        JOIN subscriptions s ON s.id = ph.subscription_id
        """
    )).fetchall()

    for row in rows:
        conn.execute(sa.text(
            """
            INSERT INTO subscription_billing_history
                (id, subscription_id, amount, interval, valid_from, anchor_on)
            VALUES
                (:id, :subscription_id, :amount, :interval, :valid_from, :anchor_on)
            """
        ), {
            "id": str(_uuid.uuid4()),
            "subscription_id": str(row.subscription_id),
            "amount": row.amount,
            "interval": row.interval,
            "valid_from": row.valid_from,
            "anchor_on": row.started_on,
        })
```

Warum Python-UUIDs?

Das Projekt erzeugt UUIDs bewusst in Python.
Die Migration soll deshalb kein `gen_random_uuid()` verwenden, damit keine PostgreSQL-Erweiterung wie `pgcrypto` noetig wird.

Nach erfolgreicher Migration kann `subscription_price_history` entfernt werden, falls kein Rollback-Szenario sie benoetigt.
Alternativ bleibt sie fuer eine Uebergangsrelease ungenutzt bestehen und wird in einer spaeteren Migration entfernt.

### Aktuelle Cache-Felder

`subscriptions.amount` und `subscriptions.interval` bleiben vorerst erhalten.
Sie dienen als aktueller Snapshot fuer Listenansicht, einfache UI und Rueckwaertskompatibilitaet.

Die Wahrheit fuer Berechnungen ist aber die Billing-Historie.

Regel:

```text
sub.amount   = heute gueltiger amount aus billing_history
sub.interval = heute gueltiges interval aus billing_history
```

Wenn eine zukuenftige Aenderung wirksam wird, darf der Code nicht dauerhaft stale bleiben.
Lesende Funktionen muessen entweder direkt aus der Historie rechnen oder den Snapshot bei Bedarf synchronisieren.

### Cache-Sync-Regel

Jede Funktion, die einen neuen Billing-History-Eintrag schreibt oder loescht, muss danach den Snapshot pruefen.

Zentrale Hilfsfunktion:

```python
def sync_subscription_billing_snapshot(sub: Subscription, billing_history: list) -> None:
    """
    Setzt subscriptions.amount und subscriptions.interval auf die heute gueltigen Billing Terms.
    Zukuenftige Eintraege duerfen den Snapshot noch nicht veraendern.
    """
```

Regel:

```text
current = neuester Billing-History-Eintrag mit valid_from <= today
sub.amount = current.amount
sub.interval = current.interval
```

Wichtig:
- `price_change(...)` ruft diese Funktion nach dem neuen Eintrag auf.
- `interval_change(...)` ruft diese Funktion nach dem neuen Eintrag auf.
- Delete/Edit von Billing-History-Eintraegen ruft diese Funktion nach der Aenderung auf.
- Wenn der neue Eintrag in der Zukunft liegt, bleiben `sub.amount` und `sub.interval` unveraendert.
- Wenn ein frueher geplanter Zukunftseintrag heute wirksam wird, muessen lesende Funktionen entweder direkt aus der Historie rechnen oder den Snapshot vor der Rueckgabe synchronisieren.

Beispiel:

```text
Heute: 2026-05-06
Aktueller Snapshot: 5.00 monthly
Neuer Eintrag: 54.00 yearly valid_from=2026-07-01

Ergebnis:
sub.amount bleibt 5.00
sub.interval bleibt monthly
```

```text
Heute: 2026-05-06
Aktueller Snapshot: 5.00 monthly
Neuer Eintrag: 54.00 yearly valid_from=2026-03-01

Ergebnis:
sub.amount wird 54.00
sub.interval wird yearly
```

---

## API

### Reine Preisaenderung

Bestehender Endpoint bleibt:

```http
POST /subscriptions/{subscription_id}/price-change
```

Payload:

```json
{
  "amount": 7.99,
  "valid_from": "2026-05-01"
}
```

Semantik:
- Nur `amount` aendert sich.
- `interval` bleibt das am `valid_from` gueltige Intervall.
- `anchor_on` bleibt der am `valid_from` gueltige Anker.

### Intervallaenderung

Neuer Endpoint:

```http
POST /subscriptions/{subscription_id}/interval-change
```

Payload:

```json
{
  "amount": 54.00,
  "interval": "yearly",
  "valid_from": "2026-07-01",
  "acknowledge_existing_payments": false
}
```

Semantik:
- `amount` und `interval` werden gemeinsam geaendert.
- `anchor_on = valid_from`.
- `valid_from` ist die erste Faelligkeit des neuen Rhythmus.

Response:

```text
SubscriptionDetail
```

### Warnung bei bestehenden Buchungen

Wenn es ab `valid_from` bereits Scheduled Payments gibt, soll der Endpoint im ersten Versuch blocken:

```http
409 Conflict
```

Beispiel-Detail:

```json
{
  "detail": "Es existieren bereits 3 Buchungen ab dem 2026-03-01. Bitte bestaetige, dass die bestehende Buchungshistorie unveraendert bleiben soll."
}
```

Wenn der Nutzer bewusst bestaetigt:

```json
{
  "amount": 60.00,
  "interval": "yearly",
  "valid_from": "2026-03-01",
  "acknowledge_existing_payments": true
}
```

dann wird die neue Billing-Historie gespeichert, aber bestehende Scheduled Payments bleiben unangetastet.

---

## Schema-Aenderungen

### `SubscriptionUpdate`

`interval` wird aus `SubscriptionUpdate` entfernt.

Vorher:

```python
class SubscriptionUpdate(BaseModel):
    name: str | None = None
    interval: BillingInterval | None = None
    notes: str | None = None
```

Nachher:

```python
class SubscriptionUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
```

Begruendung:

Ein Intervallwechsel ohne Betrag, Wirkungsdatum und neuen Anker erzeugt fachlich falsche Daten.

### `IntervalChangeRequest`

```python
class IntervalChangeRequest(BaseModel):
    amount: Decimal
    interval: BillingInterval
    valid_from: date
    acknowledge_existing_payments: bool = False

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        return _normalize_amount(v)
```

### `BillingHistoryEntry`

Wird fuer `GET /subscriptions/{id}/billing-history` und die Frontend-Historientabelle benoetigt.
Das Schema gehoert in Chunk 2, der Endpoint und die Frontend-Nutzung folgen in Chunk 4/6.

```python
class BillingHistoryEntry(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    amount: Decimal
    interval: BillingInterval
    valid_from: date
    anchor_on: date
```

---

## Service-Logik

### Hilfsfunktionen

Neue zentrale Funktionen:

```python
def applicable_billing_terms(due_date: date, billing_history: list, include_future: bool = False):
    """
    Gibt den gueltigen Billing-History-Eintrag fuer ein Datum zurueck.
    """
```

```python
def billing_segments(billing_history: list, up_to: date) -> list:
    """
    Schneidet die Historie in Zeitfenster:
    [entry.valid_from, next_entry.valid_from)
    """
```

```python
def compute_due_dates_for_billing_history(billing_history: list, up_to: date) -> list:
    """
    Gibt Faelligkeiten ueber mehrere Billing-Segmente zurueck.
    Jeder Rueckgabewert enthaelt due_date, amount, interval und billing_entry.
    """
```

```python
def ensure_no_billing_history_entry_on_date(billing_history: list, valid_from: date) -> None:
    """
    Blockt price_change/interval_change, wenn fuer valid_from bereits ein Billing-History-Eintrag existiert.
    Wirft DuplicateBillingHistoryEntryError.
    """
```

```python
def ensure_existing_payments_acknowledged_if_needed(
    session: Session,
    subscription_id: uuid.UUID,
    payload: IntervalChangeRequest,
) -> None:
    """
    Prueft bei rueckwirkenden Intervallwechseln ob Scheduled Payments ab valid_from existieren.
    Ohne acknowledge_existing_payments=True wird BillingHistoryChangeBlockedError geworfen.
    """
```

Rueckgabetyp als Dataclass:

```python
@dataclass
class ComputedDue:
    due_date: date
    amount: Decimal
    interval: BillingInterval
    billing_entry_id: uuid.UUID | None = None
```

### Pseudocode fuer Faelligkeiten

```python
def compute_due_dates_for_billing_history(history, up_to):
    ordered = sorted(history, key=lambda h: h.valid_from)
    result = []

    for i, entry in enumerate(ordered):
        segment_start = entry.valid_from
        segment_end = ordered[i + 1].valid_from if i + 1 < len(ordered) else up_to + timedelta(days=1)
        period_months = _MONTHS_PER_PERIOD[entry.interval]

        for due in compute_due_dates(entry.anchor_on, period_months, up_to):
            if due < segment_start:
                continue
            if due >= segment_end:
                continue
            result.append(ComputedDue(
                due_date=due,
                amount=entry.amount,
                interval=entry.interval,
                billing_entry_id=entry.id,
            ))

    return sorted(result, key=lambda d: d.due_date)
```

### `price_change` Copy-forward-Regel

Eine reine Preisaenderung darf keinen neuen Faelligkeitsanker erzeugen.
Darum muss `price_change(...)` beim Schreiben des neuen Billing-History-Eintrags `interval` und `anchor_on` vom bereits gueltigen Billing-Term uebernehmen.

Schrittfolge:

```python
def price_change(session, user_id, subscription_id, payload):
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    history = load_billing_history(session, subscription_id)
    ensure_no_billing_history_entry_on_date(history, payload.valid_from)

    base_terms = applicable_billing_terms(
        payload.valid_from,
        history,
        include_future=True,
    )

    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=base_terms.interval,
        anchor_on=base_terms.anchor_on,
        valid_from=payload.valid_from,
    )
    session.add(new_entry)

    sync_subscription_billing_snapshot(sub, [*history, new_entry])
    session.commit()
```

Wichtig:
- Vor dem Insert wird explizit geprueft, ob fuer `payload.valid_from` bereits ein Billing-History-Eintrag existiert. In diesem Fall wirft der Service `DuplicateBillingHistoryEntryError`.
- `base_terms` wird zum `payload.valid_from` gesucht, nicht blind zu `today`.
- `include_future=True` ist hier absichtlich: Wenn bereits eine zukuenftige Intervallaenderung geplant ist und danach eine Preisankuendigung innerhalb dieses zukuenftigen Segments eingetragen wird, muss die Preisaenderung das zukuenftige Intervall und dessen Anker kopieren.
- Falls fuer `payload.valid_from` kein gueltiger Billing-History-Eintrag existiert, ist die Historie defekt und der Service muss blocken.
- Der Snapshot wird danach nur auf die heute gueltigen Terms synchronisiert. Ein zukuenftiger Preiseintrag veraendert `sub.amount` und `sub.interval` noch nicht.

Beispiel:

```text
History:
  5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
  54.00 yearly valid_from=2026-07-01 anchor_on=2026-07-01

Neue Preisaenderung:
  59.00 valid_from=2026-10-01

Neuer Eintrag:
  59.00 yearly valid_from=2026-10-01 anchor_on=2026-07-01
```

Damit bleibt der Jahresrhythmus am 1. Juli erhalten.

### `interval_change` Insert-Regel

Auch `interval_change(...)` prueft vor dem Insert explizit auf ein Duplikat fuer `valid_from`.
Der Unique Constraint in der DB bleibt die zweite Verteidigungslinie, aber die Service-Schicht soll eine fachliche Fehlermeldung liefern.

Schrittfolge:

```python
def interval_change(session, user_id, subscription_id, payload):
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    history = load_billing_history(session, subscription_id)
    ensure_no_billing_history_entry_on_date(history, payload.valid_from)
    ensure_existing_payments_acknowledged_if_needed(session, sub.id, payload)

    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=payload.interval,
        valid_from=payload.valid_from,
        anchor_on=payload.valid_from,
    )
    session.add(new_entry)

    sync_subscription_billing_snapshot(sub, [*history, new_entry])
    session.commit()
```

Fehlerfall:

```text
Wenn bereits ein Eintrag mit subscription_id + valid_from existiert:
  -> DuplicateBillingHistoryEntryError(valid_from)
```

### `compute_next_due_date`

Alt:

```python
compute_next_due_date(sub.started_on, _MONTHS_PER_PERIOD[sub.interval])
```

Neu:

```python
compute_next_due_date_from_history(billing_history, today)
```

Semantik:
- Nimmt alle Faelligkeiten aus der Billing-Historie.
- Gibt die erste Faelligkeit `>= today` zurueck.
- Wenn das Abo erst in Zukunft beginnt, ist das die erste zukuenftige Faelligkeit.

### `compute_tatsaechlich`

Alt:

```python
for due in compute_due_dates(started_on, period_months, today):
    total += applicable_price(due, price_history)
```

Neu:

```python
for due in compute_due_dates_for_billing_history(history, today):
    if is_in_pause(due.due_date, pause_history):
        continue
    total += due.amount
```

### `compute_intervalle`

Zaehlt alle nicht pausierten Faelligkeiten aus der Billing-Historie bis heute.

```python
sum(1 for due in computed_dues if not is_in_pause(due.due_date, pause_history))
```

### `compute_dieses_kalenderjahr`

Berechnet alle Faelligkeiten im laufenden Kalenderjahr aus der Billing-Historie.

Wichtig:
- Zukuenftige Billing-History-Eintraege werden fuer diese Projektion beruecksichtigt.
- Pausen werden weiterhin uebersprungen.

---

## Verhalten bei Rueckwirkung

### Fall A: keine bestehenden Buchungen

Der Eintrag wird direkt gespeichert.

Beispiel:

```text
Heute: 2026-05-06
valid_from: 2026-03-01
Scheduled Payments ab 2026-03-01: 0
```

Ergebnis:
- Billing-Historie wird gespeichert.
- Kennzahlen werden neu berechnet.

### Fall B: bestehende Buchungen vorhanden, keine Bestaetigung

Der Endpoint blockt mit `409 Conflict`.

Beispiel:

```text
Heute: 2026-05-06
valid_from: 2026-03-01
Scheduled Payments ab 2026-03-01: 3
acknowledge_existing_payments: false
```

Ergebnis:
- Keine Aenderung.
- UI zeigt Warnung.

### Fall C: bestehende Buchungen vorhanden, bestaetigt

Der Endpoint speichert die neue Billing-Historie.

Bestehende Scheduled Payments bleiben unveraendert.

Warum?

Die Buchungshistorie kann spaeter reale Zahlungen oder Nutzerentscheidungen enthalten.
Automatisches Loeschen oder Umschreiben waere riskant.

---

## Beispiele

### S-01: monatlich zu jaehrlich, zukuenftig

Setup:

```text
today: 2026-05-06
started_on: 2026-03-15
history:
  5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
change:
  54.00 yearly valid_from=2026-07-01 anchor_on=2026-07-01
```

Faelligkeiten 2026:

```text
2026-03-15   5.00
2026-04-15   5.00
2026-05-15   5.00
2026-06-15   5.00
2026-07-01  54.00
```

Naechste Faelligkeit am 2026-05-06:

```text
2026-05-15
```

Dieses Kalenderjahr:

```text
5 + 5 + 5 + 5 + 54 = 74.00
```

### S-02: monatlich zu jaehrlich, rueckwirkend

Setup:

```text
today: 2026-05-06
old:
  5.00 monthly valid_from=2026-01-01 anchor_on=2026-01-01
change:
  60.00 yearly valid_from=2026-03-01 anchor_on=2026-03-01
```

Neue fachliche Faelligkeiten:

```text
2026-01-01   5.00
2026-02-01   5.00
2026-03-01  60.00
```

Wenn bereits Buchungen fuer Maerz, April, Mai existieren:
- erster Request: `409 Conflict`
- bestaetigter Request: Historie speichern, Buchungen unveraendert lassen

### S-03: reine Preisaenderung aendert den Anker nicht

Setup:

```text
old:
  5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
price change:
  7.00 monthly valid_from=2026-05-01 anchor_on=2026-03-15
```

Faelligkeiten:

```text
2026-03-15  5.00
2026-04-15  5.00
2026-05-15  7.00
2026-06-15  7.00
```

### S-04: jaehrlich zu monatlich

Setup:

```text
old:
  60.00 yearly valid_from=2026-01-01 anchor_on=2026-01-01
change:
  6.99 monthly valid_from=2027-01-01 anchor_on=2027-01-01
```

Faelligkeiten:

```text
2026-01-01  60.00
2027-01-01   6.99
2027-02-01   6.99
2027-03-01   6.99
```

---

## Scheduler

Der Scheduler darf nicht mehr nur `sub.interval` und `sub.amount` verwenden.

Alt:

```python
period_months = _MONTHS_PER_PERIOD[sub.interval]
for due in compute_due_dates(sub.started_on, period_months, today):
    amount = sub.amount
```

Neu:

```python
history = billing_history_by_sub[sub.id]
for due in compute_due_dates_for_billing_history(history, today):
    if due.due_date < cutoff:
        continue
    if is_in_pause(due.due_date, pause_hist):
        amount = None
        status = PaymentStatus.paused
    else:
        amount = due.amount
        status = PaymentStatus.pending
```

Wichtig:
- Der Scheduler soll keine zukuenftigen Eintraege erzeugen.
- Catch-up bleibt bei 60 Tagen.
- Bestehende Unique Constraint `(subscription_id, due_date)` bleibt.

---

## UI

### Detailseite

Neue Aktion:

```text
Intervall aendern
```

Formularfelder:
- Neuer Betrag
- Neues Intervall
- Gilt ab / erste Faelligkeit

Label-Vorschlag:

```text
Intervallwechsel
```

Hilfetext im Formular:

```text
Das Datum ist die erste Faelligkeit im neuen Intervall.
```

### Warnung bei bestehenden Buchungen

Wenn Backend `409` wegen bestehender Buchungen liefert:

```text
Es existieren bereits Buchungen ab diesem Datum.
Die neue Aenderung wird gespeichert, aber bestehende Buchungen bleiben unveraendert.
```

Button:

```text
Trotzdem speichern
```

Der zweite Request sendet:

```json
"acknowledge_existing_payments": true
```

### Historie

Die bisherige Preishistorie wird zur Abrechnungshistorie erweitert.

Tabellenspalten:

```text
Gueltig ab | Betrag | Intervall | Anker | Aktionen
```

MVP:
- Spalte `Anker` kann in der UI verborgen bleiben, wenn sie zu technisch wirkt.
- Fuer Debugging und Vertrauen ist sie aber hilfreich.

---

## Delete/Edit von Billing-History

Der bestehende v0.2.3 Endpoint

```http
DELETE /subscriptions/{subscription_id}/price-history/{entry_id}
```

muss mit dem Umbau neu bewertet werden.

Bisher prueft der Service im Kern:
- Gibt es mindestens einen weiteren Preiseintrag?
- Gibt es Scheduled Payments im Preisfenster `[entry.valid_from, next.valid_from)`?

Nach v0.2.4 reicht das nicht mehr, weil ein Eintrag nicht nur einen Preis beschreibt.
Er beschreibt auch `interval` und `anchor_on`.

### Neue Schutzregeln

Ein Billing-History-Eintrag darf nicht geloescht werden, wenn:

- Es der einzige verbleibende Billing-History-Eintrag des Abos ist.
- Im betroffenen Zeitfenster Scheduled Payments existieren.
- Durch das Loeschen der einzige Eintrag verloren ginge, der einen bestimmten Intervallwechsel oder Faelligkeitsanker erklaert.
- Der geloeschte Eintrag heute gueltig war und danach kein gueltiger Eintrag `valid_from <= today` mehr existiert.

### Zeitfenster

Das betroffene Fenster bleibt:

```text
[entry.valid_from, next_entry.valid_from)
```

Falls kein spaeterer Eintrag existiert:

```text
[entry.valid_from, unendlich)
```

Alle Scheduled Payments in diesem Fenster blocken das Loeschen, egal ob sich "nur" der Preis, das Intervall oder der Anker aendern wuerde.

Warum so streng?

Eine vorhandene Buchung ist ein historisches Artefakt.
Wenn der Billing-History-Eintrag geloescht wird, kann die Buchung danach nicht mehr eindeutig aus der Historie hergeleitet werden.

### Anker-Beispiel

History:

```text
5.00  monthly valid_from=2026-03-15 anchor_on=2026-03-15
54.00 yearly  valid_from=2026-07-01 anchor_on=2026-07-01
```

Der zweite Eintrag ist nicht nur ein Preis von 54.00 EUR.
Er erklaert auch, warum die naechste Jahresfaelligkeit am 1. Juli liegt.

Wenn dieser Eintrag geloescht wird, faellt das Abo fachlich auf den monatlichen Rhythmus ab 15. Maerz zurueck.
Alle Buchungen ab 1. Juli waeren dann potentiell falsch.

### Cache-Sync nach Delete

Nach erfolgreichem Delete:

```python
session.delete(entry)
sync_subscription_billing_snapshot(sub, remaining_entries)
session.commit()
```

Wenn der geloeschte Eintrag nur in der Zukunft lag, bleibt der heutige Snapshot normalerweise unveraendert.
Wenn der geloeschte Eintrag heute gueltig war, faellt der Snapshot auf den vorherigen gueltigen Eintrag zurueck.

### API-Naming

Mit der neuen Tabelle wird auch das API-Naming auf Billing-History umgestellt:

```http
GET    /subscriptions/{id}/billing-history
DELETE /subscriptions/{id}/billing-history/{entry_id}
```

Der alte Pfad `/price-history` darf fuer eine Uebergangsrelease als Alias bestehen bleiben, sollte aber nicht mehr als primaerer Endpoint dokumentiert werden.

---

## Fehlerklassen

Neue Fehler:

```python
class DuplicateBillingHistoryEntryError(AppError):
    status_code = 409
```

```python
class BillingHistoryEntryNotFoundError(AppError):
    status_code = 404
```

```python
class BillingHistoryChangeBlockedError(AppError):
    status_code = 409
```

Bestehende `DuplicatePriceEntryError` und `PriceHistoryEntryNotFoundError` werden nicht weiterverwendet.
Die neuen Fehler sollen fachlich auf Billing-History verweisen.

---

## Akzeptanz-Szenarien

### T-01: Intervallwechsel erzeugt neuen Anker

Given:

```text
today = 2026-05-06
old = 5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
change = 54.00 yearly valid_from=2026-07-01
```

When:

```text
interval_change(...)
```

Then:

```text
new entry:
  amount = 54.00
  interval = yearly
  valid_from = 2026-07-01
  anchor_on = 2026-07-01
```

### T-02: Reine Preisaenderung behaelt alten Anker

Given:

```text
old = 5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
price change = 7.00 valid_from=2026-05-01
```

Then:

```text
new entry:
  amount = 7.00
  interval = monthly
  valid_from = 2026-05-01
  anchor_on = 2026-03-15
```

### T-03: Faelligkeiten ueber zwei Segmente

History:

```text
5.00 monthly valid_from=2026-03-15 anchor_on=2026-03-15
54.00 yearly valid_from=2026-07-01 anchor_on=2026-07-01
```

Expected dues up to 2026-12-31:

```text
2026-03-15  5.00
2026-04-15  5.00
2026-05-15  5.00
2026-06-15  5.00
2026-07-01 54.00
```

### T-04: Rueckwirkender Wechsel mit bestehenden Buchungen blockt

Given:

```text
valid_from = 2026-03-01
existing scheduled payments >= 2026-03-01: 3
acknowledge_existing_payments = false
```

Then:

```text
409 Conflict
```

### T-05: Rueckwirkender Wechsel mit Bestaetigung speichert

Given:

```text
valid_from = 2026-03-01
existing scheduled payments >= 2026-03-01: 3
acknowledge_existing_payments = true
```

Then:

```text
Billing history entry wird erstellt.
Bestehende scheduled payments bleiben unveraendert.
```

### T-06: `SubscriptionUpdate` kann Intervall nicht mehr aendern

Given:

```json
{ "interval": "yearly" }
```

Then:

```text
Request wird vom Schema ignoriert oder als 422 abgelehnt.
```

Empfehlung:
- Pydantic `extra="forbid"` fuer Update-Schemas pruefen, damit der Fehler sichtbar ist.

### T-07: Zukunftseintrag aktualisiert Snapshot nicht

Given:

```text
today = 2026-05-06
snapshot = 5.00 monthly
new billing entry = 54.00 yearly valid_from=2026-07-01 anchor_on=2026-07-01
```

Then:

```text
sub.amount bleibt 5.00
sub.interval bleibt monthly
```

### T-08: Rueckwirkender Eintrag aktualisiert Snapshot sofort

Given:

```text
today = 2026-05-06
snapshot = 5.00 monthly
new billing entry = 54.00 yearly valid_from=2026-03-01 anchor_on=2026-03-01
```

Then:

```text
sub.amount wird 54.00
sub.interval wird yearly
```

### T-09: Delete von Billing-History mit Buchungen im Fenster blockt

Given:

```text
entry = 54.00 yearly valid_from=2026-07-01 anchor_on=2026-07-01
scheduled payment exists at 2026-07-01
```

Then:

```text
DELETE billing-history/{entry_id} -> 409 Conflict
```

### T-10: Delete synchronisiert Snapshot

Given:

```text
today = 2026-05-06
history:
  5.00 monthly valid_from=2026-01-01 anchor_on=2026-01-01
  7.00 monthly valid_from=2026-03-01 anchor_on=2026-01-01
snapshot = 7.00 monthly
delete entry valid_from=2026-03-01
```

Then:

```text
sub.amount wird 5.00
sub.interval bleibt monthly
```

---

## Build Plan

### Chunk 1 - DB und Model

Dateien:
- `backend/app/models/subscription.py`
- neue Alembic Migration

Aufgaben:
- Neues Billing-History-Modell einfuehren.
- `interval` und `anchor_on` historisieren.
- Bestehende Preis-History-Eintraege migrieren.
- Unique Constraint fuer `(subscription_id, valid_from)` sicherstellen.
- In der Alembic-Migration den bestehenden PostgreSQL-Enum `billinginterval` mit `create_type=False` wiederverwenden.

### Chunk 2 - Schemas und Fehler

Dateien:
- `backend/app/schemas/subscription.py`
- `backend/app/exceptions.py`

Aufgaben:
- `IntervalChangeRequest` ergaenzen.
- `BillingHistoryEntry` als Read-Schema fuer die Historientabelle ergaenzen.
- `SubscriptionUpdate.interval` entfernen.
- Neue Fehlerklasse fuer blockierte Intervallwechsel ergaenzen.
- `DuplicateBillingHistoryEntryError` fuer doppelte `valid_from`-Eintraege ergaenzen.

### Chunk 3 - Service-Algorithmen

Dateien:
- `backend/app/services/subscriptions.py`

Aufgaben:
- `applicable_billing_terms`
- `compute_due_dates_for_billing_history`
- `compute_next_due_date_from_history`
- `sync_subscription_billing_snapshot`
- Kennzahlen auf Billing-History umstellen.

### Chunk 4 - Endpoints

Dateien:
- `backend/app/services/subscriptions.py`
- `backend/app/routers/subscriptions.py`

Aufgaben:
- `POST /subscriptions/{id}/interval-change`
- Bestehenden `price-change` intern auf Billing-History umstellen.
- In `price_change` und `interval_change` vor dem Insert explizit auf doppeltes `valid_from` pruefen.
- Delete-Endpoint fuer Billing-History anpassen: `interval`, `anchor_on`, betroffene Scheduled Payments und Cache-Sync beruecksichtigen.

### Chunk 5 - Scheduler

Dateien:
- `backend/app/services/scheduler_service.py`

Aufgaben:
- Faelligkeiten aus Billing-History statt `sub.interval` erzeugen.
- Billing-History fuer alle betroffenen Abos per Bulk-Load vorladen und als `billing_history_by_sub` gruppieren, analog zu `pause_history`.
- Amount pro Faelligkeit aus ComputedDue verwenden.

### Chunk 6 - Frontend

Dateien:
- `frontend/src/types/subscription.ts`
- `frontend/src/api/subscriptions.ts`
- `frontend/src/pages/SubscriptionsPage.tsx`
- `frontend/src/pages/SubscriptionDetailPage.tsx`

Aufgaben:
- Typen fuer `IntervalChangeRequest`.
- `SubscriptionUpdate` ohne `interval` nachziehen.
- API-Client-Funktion `intervalChange`.
- Interval-Selector aus dem Inline-Edit der Uebersichtsseite entfernen.
- In der Uebersichtsseite optional einen Hinweis/Link anzeigen: "Intervall ueber Detailseite aendern".
- Formular "Intervall wechseln".
- 409-Warnung mit Bestaetigungsflow.

### Chunk 7 - Tests

Dateien:
- `backend/tests/test_subscriptions_v024.py`

Aufgaben:
- Akzeptanz-Szenarien T-01 bis T-10 abdecken.
- Reine Algorithmus-Tests ohne DB bevorzugen.
- Service-Tests fuer Block/Confirm-Verhalten mit Mock-Session.

---

## Offene Entscheidungen

### O-01: Tabelle umbenennen oder erweitern?

Entscheidung: neue Tabelle `subscription_billing_history`.

`subscription_price_history` wird nicht erweitert.

Begruendung:
- v0.2.4 ist ohnehin ein grosser Refactor der Subscription-Algorithmen.
- `subscription_price_history` mit `interval` und `anchor_on` waere fachlich irrefuehrend.
- Eine explizite Billing-History bildet das neue Konzept sauber ab.
- Spaetere Features wie Edit/Delete, Intervallwechsel-Anzeige und Scheduler-Debugging werden verstaendlicher.

Migrationsstrategie:
- Neue Tabelle `subscription_billing_history` anlegen.
- Bestehende `subscription_price_history`-Eintraege in Billing-History migrieren.
- Bestehende Service-/Router-/Frontend-Namen von Price-History auf Billing-History umbauen.
- Optional: `/price-history` fuer eine Uebergangsrelease als Alias behalten.

Status: entschieden.

### O-02: Soll `valid_from` beim Intervallwechsel immer erste Faelligkeit sein?

Empfehlung: Ja.

Das ist fuer Nutzer am klarsten:

> "Ab wann zahlst du im neuen Intervall?"

### O-03: Was passiert mit historischen Scheduled Payments?

Empfehlung fuer v0.2.4:

Nicht automatisch veraendern.
Nur warnen/blocken und bewusste Bestaetigung verlangen.

Spaeter kann ein eigener Reparatur-Dialog kommen:

```text
Bestehende Buchungen im Zeitraum neu generieren
```

Das ist aber ein eigener Slice.

---

## Zusammenfassung

v0.2.4 fuehrt eine Historie der Abrechnungsbedingungen ein.

Damit koennen Preis und Intervall gemeinsam ab einem Datum geaendert werden, ohne historische Berechnungen zu verfaelschen.

Die wichtigste fachliche Regel:

```text
Preisaenderung:
  amount neu, interval gleich, anchor_on gleich

Intervallaenderung:
  amount neu, interval neu, anchor_on = valid_from
```

Bestehende Buchungen werden nicht automatisch umgeschrieben.
Rueckwirkende Aenderungen mit vorhandenen Buchungen brauchen eine bewusste Bestaetigung.
