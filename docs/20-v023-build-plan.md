# v0.2.3 — Build Plan

Status: ready-to-build
Stand: 2026-05-05
Design-Entscheidungen: docs/18-v023-subscription-redesign-discussion.md
Akzeptanz-Tests: docs/19-v023-test-scenarios.md

---

## Session-Start-Protokoll

1. Diese Datei lesen (docs/20)
2. Ersten Chunk mit `[ ]` finden
3. Nur die dort genannten Dateien lesen — nicht mehr
4. Chunk ausführen — kein erklärender Zwischentext, nur Arbeit
5. `[ ]` → `[x]` setzen in dieser Datei
6. Kurzmeldung: "Chunk N erledigt. Geänderte Dateien: ..."

Ressourcen-Regel: Pro Session maximal einen Chunk abarbeiten.
Qualitäts-Regel: Ressourcen-Schonen hat keinen Einfluss auf Code-Qualität —
die Spezifikation in docs/18+19 ist vollständig, der Plan ist präzise genug.

---

## Fortschritt

- [x] Chunk 1 — Alembic Migrations
- [x] Chunk 2 — Models + Schemas
- [x] Chunk 3 — Service: Algorithmen (reine Berechnungen)
- [x] Chunk 4 — Service: CRUD + Lifecycle
- [x] Chunk 5 — Scheduler Rewrite
- [x] Chunk 6 — Router + Neue Endpoints
- [x] Chunk 7 — Frontend: Types + API-Client
- [x] Chunk 8 — Frontend: UI
- [x] Chunk 9 — Tests
- [x] Chunk 10 — CHANGELOG finalisieren

---

## Chunk 1 — Alembic Migrations

**Lesen:**
- `backend/alembic/versions/` — letzten Hash ermitteln (für `down_revision`)
- `backend/app/models/subscription.py` — bestehende Enum-Namen bestätigen

**Erstellen:** Zwei neue Migrations-Dateien in `backend/alembic/versions/`

### Migration A: pause_history anlegen + Datenmigration

Erstellt `subscription_pause_history`, migriert bestehende `suspended_at`/`access_until`-Werte.

```python
def upgrade():
    op.create_table(
        "subscription_pause_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paused_at", sa.Date(), nullable=False),
        sa.Column("resumed_at", sa.Date(), nullable=True),
        sa.Column("access_until", sa.Date(), nullable=True),
    )

    # Datenmigration: bestehende suspended/canceled Abos → pause_history
    import uuid as _uuid
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, suspended_at, access_until FROM subscriptions "
        "WHERE status IN ('suspended', 'canceled') AND suspended_at IS NOT NULL"
    )).fetchall()
    for row in rows:
        conn.execute(sa.text(
            "INSERT INTO subscription_pause_history "
            "(id, subscription_id, paused_at, resumed_at, access_until) "
            "VALUES (:id, :sub_id, :paused_at, NULL, :access_until)"
        ), {"id": str(_uuid.uuid4()), "sub_id": str(row.id),
            "paused_at": row.suspended_at, "access_until": row.access_until})


def downgrade():
    op.drop_table("subscription_pause_history")
```

### Migration B: Spalten droppen + Enums erweitern

**Wichtig:** `ALTER TYPE ... ADD VALUE` darf nicht in einer Transaktion laufen.
Alembic-Workaround: `autocommit_block()` verwenden.

```python
def upgrade():
    # ENUM-Erweiterungen außerhalb einer Transaktion
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'paused'")
        op.execute("ALTER TYPE billinginterval ADD VALUE IF NOT EXISTS 'semiannual'")

    # Spalten droppen (kann in Transaktion)
    op.drop_column("subscriptions", "next_due_date")
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "access_until")


def downgrade():
    # ENUM-Werte können in PostgreSQL nicht entfernt werden — downgrade ist nur partiell möglich
    op.add_column("subscriptions", sa.Column("next_due_date", sa.Date(), nullable=True))
    op.add_column("subscriptions", sa.Column("suspended_at", sa.Date(), nullable=True))
    op.add_column("subscriptions", sa.Column("access_until", sa.Date(), nullable=True))
```

**Done-Kriterien:**
- `alembic upgrade head` läuft ohne Fehler durch
- `subscription_pause_history`-Tabelle existiert in der DB
- Spalten `next_due_date`, `suspended_at`, `access_until` sind weg von `subscriptions`
- Bestehende suspended/canceled-Abos haben Einträge in `subscription_pause_history`

**CHANGELOG-Zeilen (für Chunk 10):**
```
- DB: Neue Tabelle `subscription_pause_history` für mehrfaches Pausieren/Resumieren
- DB: Spalten `next_due_date`, `suspended_at`, `access_until` aus `subscriptions` entfernt
- DB: `PaymentStatus.paused` hinzugefügt
- DB: `BillingInterval.semiannual` (halbjährlich) hinzugefügt
```

---

## Chunk 2 — Models + Schemas

**Lesen:**
- `backend/app/models/subscription.py`
- `backend/app/schemas/subscription.py`

**Ändern:** Beide Dateien

### Models (`backend/app/models/subscription.py`)

1. `BillingInterval` Enum: `semiannual = "semiannual"` hinzufügen
2. `PaymentStatus` Enum: `paused = "paused"` hinzufügen
3. `Subscription` Model: Felder `next_due_date`, `suspended_at`, `access_until` entfernen
4. Neue Model-Klasse `SubscriptionPauseHistory` hinzufügen:

```python
class SubscriptionPauseHistory(Base):
    __tablename__ = "subscription_pause_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"))
    paused_at: Mapped[date] = mapped_column(nullable=False)
    resumed_at: Mapped[Optional[date]] = mapped_column(nullable=True)
    access_until: Mapped[Optional[date]] = mapped_column(nullable=True)
```

### Schemas (`backend/app/schemas/subscription.py`)

1. `SubscriptionCreate`:
   - `next_due_date`-Feld entfernen
   - `started_on_not_in_future`-Validator entfernen (QW-02 / L-04)
   - `semiannual` als gültiger Interval-Wert

2. `SubscriptionUpdate`:
   - `amount`-Feld entfernen (→ eigener Endpoint, RD-05)

3. `SubscriptionDetail` (Response-Schema):
   - `next_due_date` bleibt (computed, wird von Service befüllt)
   - Neue Felder hinzufügen:
     ```python
     tatsaechlich: Decimal
     intervalle: int
     dieses_kalenderjahr: Decimal
     ```

4. Neue Schema-Klassen:
   ```python
   class PriceChangeRequest(BaseModel):
       amount: Decimal
       valid_from: date

   class PauseHistoryEntry(BaseModel):
       paused_at: date
       resumed_at: Optional[date]
       access_until: Optional[date]
   ```

**Done-Kriterien:**
- `python -c "from app.models.subscription import *; from app.schemas.subscription import *"` — kein Fehler
- `SubscriptionCreate` akzeptiert kein `next_due_date` mehr
- `SubscriptionUpdate` akzeptiert kein `amount` mehr
- `BillingInterval.semiannual` und `PaymentStatus.paused` vorhanden

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Breaking: `POST /subscriptions` — Feld `next_due_date` entfernt (wird serverseitig berechnet)
- Breaking: `PATCH /subscriptions/{id}` — Feld `amount` entfernt → `POST /price-change` verwenden
```

---

## Chunk 3 — Service: Algorithmen

**Lesen:**
- `backend/app/services/subscriptions.py` — nur die Abschnitte `_MONTHLY_FACTOR` und `_compute_*`
- `docs/18-v023-subscription-redesign-discussion.md` — Abschnitt 0b (Pseudocode-Blöcke)
- `docs/19-v023-test-scenarios.md` — S-01 und S-03 (Expected Outputs als Validierung)

**Ändern:** `backend/app/services/subscriptions.py`

### Was entfernt wird:
- `_compute_total_paid_exact`
- `_compute_total_paid_estimate`

### Was hinzukommt (reine Funktionen, kein DB-Zugriff):

```python
from dateutil.relativedelta import relativedelta

_MONTHLY_FACTOR = {
    "monthly":   Decimal("1"),
    "quarterly": Decimal("1") / Decimal("3"),
    "semiannual": Decimal("1") / Decimal("6"),  # NEU
    "yearly":    Decimal("1") / Decimal("12"),
    "biennial":  Decimal("1") / Decimal("24"),
}

_MONTHS_PER_PERIOD = {
    "monthly": 1, "quarterly": 3, "semiannual": 6, "yearly": 12, "biennial": 24,
}


def compute_due_dates(started_on: date, period_months: int, up_to: date) -> list[date]:
    """Alle Fälligkeitsdaten im Raster von started_on bis up_to (inkl.)."""
    dates, n = [], 0
    while True:
        d = started_on + relativedelta(months=n * period_months)
        if d > up_to:
            break
        dates.append(d)
        n += 1
    return dates


def compute_next_due_date(started_on: date, period_months: int, today: date) -> date:
    """Nächster Fälligkeitstag >= today. Immer von started_on aus berechnen."""
    n = 0
    while True:
        d = started_on + relativedelta(months=n * period_months)
        if d >= today:
            return d
        n += 1


def is_in_pause(due_date: date, pause_history: list) -> bool:
    """True wenn due_date in einem Pause-Intervall liegt."""
    return any(
        p.paused_at <= due_date and (p.resumed_at is None or due_date <= p.resumed_at)
        for p in pause_history
    )


def applicable_price(due_date: date, price_history: list, include_future: bool = False) -> Decimal:
    """Aktuell gültiger Preis für diesen Tag.
    include_future=True: für Dieses-Kalenderjahr-Projektion (Ankündigungen einrechnen).
    include_future=False: für Tatsächlich (nur Vergangenheitspreise)."""
    today = date.today()
    candidates = [p for p in price_history if p.valid_from <= due_date]
    if not include_future:
        candidates = [p for p in candidates if p.valid_from <= today]
    if not candidates:
        return Decimal("0")
    return max(candidates, key=lambda p: p.valid_from).amount


def compute_tatsaechlich(
    started_on: date, period_months: int,
    price_history: list, pause_history: list, today: date
) -> Decimal:
    """Summe aller nicht-pausierten Perioden bis heute × ihren Preis."""
    total = Decimal("0")
    for due in compute_due_dates(started_on, period_months, today):
        if is_in_pause(due, pause_history):
            continue
        total += applicable_price(due, price_history, include_future=False)
    return total


def compute_intervalle(
    started_on: date, period_months: int, pause_history: list, today: date
) -> int:
    """Anzahl nicht-pausierter Perioden bis heute."""
    return sum(
        1 for due in compute_due_dates(started_on, period_months, today)
        if not is_in_pause(due, pause_history)
    )


def compute_dieses_kalenderjahr(
    started_on: date, period_months: int,
    price_history: list, pause_history: list, today: date
) -> Decimal:
    """Summe aller Perioden im aktuellen Kalenderjahr.
    Zukünftige Preiseinträge fließen als Projektion ein (Vorschau-Charakter)."""
    jan_1 = date(today.year, 1, 1)
    dez_31 = date(today.year, 12, 31)
    total = Decimal("0")
    for due in compute_due_dates(started_on, period_months, dez_31):
        if due < jan_1:
            continue
        if is_in_pause(due, pause_history):
            continue
        total += applicable_price(due, price_history, include_future=True)
    return total
```

**Done-Kriterien (manuell nachrechnen):**
- `compute_tatsaechlich(date(2026,1,31), 1, [{amount:35, valid_from:date(2026,1,31)}], [], date(2026,5,5))` → `Decimal("140.00")`
- `compute_next_due_date(date(2026,1,31), 1, date(2026,5,5))` → `date(2026,5,31)`
- `compute_tatsaechlich(date(2026,5,5), 1, [{amount:9.99, valid_from:date(2026,5,5)}], [], date(2026,5,5))` → `Decimal("9.99")` (BUG-04 behoben)

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Fix BUG-02: "Tatsächlich" — Algorithmus neu (Perioden zählen, kein Segment-Math, kein +1-Hack)
- Fix BUG-04: "Tatsächlich" = 1 Periode wenn Abo am gleichen Tag angelegt wird (war: 0)
- Neu: compute_dieses_kalenderjahr — Jahresbudget mit Preisankündigungen als Projektion
- Neu: compute_intervalle — Anzahl Zahlungsperioden seit Abschluss
- Neu: Halbjährliches Intervall (semiannual) in allen Berechnungen
```

---

## Chunk 4 — Service: CRUD + Lifecycle

**Lesen:**
- `backend/app/services/subscriptions.py` — vollständig (Chunk 3 muss abgeschlossen sein)
- `backend/app/models/subscription.py` (Chunk 2 muss abgeschlossen sein)

**Ändern:** `backend/app/services/subscriptions.py`

### Änderungen im Detail:

**`get_overview`:**
- `active_subs`-Filter: `Subscription.started_on <= date.today()` hinzufügen (L-09)
- Abos mit `started_on > today` fließen nicht in `monthly_total` ein

**`list_subscriptions`:**
- `.order_by(Subscription.next_due_date)` entfernen (L-02 — Spalte existiert nicht mehr)
- Stattdessen: nach Laden in Python sortieren via `compute_next_due_date`

**`get_subscription_detail`:**
- Pause-History aus DB laden für dieses Abo
- Price-History aus DB laden
- Response mit neuen Feldern befüllen:
  ```python
  period_months = _MONTHS_PER_PERIOD[sub.interval]
  today = date.today()
  pause_hist = session.execute(...).scalars().all()
  price_hist = session.execute(...).scalars().all()

  detail.next_due_date = compute_next_due_date(sub.started_on, period_months, today)
  detail.tatsaechlich = compute_tatsaechlich(sub.started_on, period_months, price_hist, pause_hist, today)
  detail.intervalle = compute_intervalle(sub.started_on, period_months, pause_hist, today)
  detail.dieses_kalenderjahr = compute_dieses_kalenderjahr(sub.started_on, period_months, price_hist, pause_hist, today)
  detail.monatlich = sub.amount * _MONTHLY_FACTOR[sub.interval]
  ```

**`update_subscription`:**
- `amount`-Handling entfernen (kein `_record_price_change` mehr hier)
- `next_due_date` wird nicht mehr gesetzt

**`suspend_subscription`:**
- Statt `sub.suspended_at = today`: neuen `SubscriptionPauseHistory`-Eintrag schreiben
  ```python
  pause = SubscriptionPauseHistory(subscription_id=sub.id, paused_at=today, access_until=payload.access_until)
  session.add(pause)
  ```

**`resume_subscription`:**
- Letzten offenen Pause-Eintrag laden (resumed_at IS NULL), `resumed_at = today` setzen

**`cancel_subscription` (neu):**
- `sub.status = SubscriptionStatus.canceled`
- Pause-Eintrag schreiben mit `access_until` aus Payload (optional)

**`price_change` (neu):**
- `_record_price_change(session, sub, amount, valid_from=payload.valid_from)`
- `_record_price_change` bekommt `valid_from`-Parameter (nicht mehr immer today)

**Done-Kriterien:**
- Backend startet: `uvicorn app.main:app` — kein ImportError, kein AttributeError
- `GET /subscriptions` gibt sortierte Liste zurück (Python-Sort, kein DB-Fehler)
- `GET /subscriptions/overview` gibt korrekten `monthly_total` (future-Abos ausgeschlossen)
- `GET /subscriptions/{id}` gibt `tatsaechlich`, `intervalle`, `dieses_kalenderjahr` zurück

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Fix BUG-01: next_due_date wird nicht mehr gespeichert — berechnet aus started_on + N × interval
- Fix BUG-03: Preisänderungen via eigenem Endpoint mit valid_from (Vergangenheit/heute/Zukunft)
- Neu: cancel_subscription — Abo kündigen mit optionalem access_until
- Neu: Mehrfaches Pausieren/Resumieren (subscription_pause_history)
- Neu: Abos mit started_on in der Zukunft fließen nicht in Übersichts-Gesamtsumme ein
```

---

## Chunk 5 — Scheduler Rewrite

**Lesen:**
- `backend/app/services/scheduler_service.py` — vollständig
- `docs/18-v023-subscription-redesign-discussion.md` — Abschnitt DESIGN-05 (Scheduler-Logik)

**Ändern:** `backend/app/services/scheduler_service.py`

**Vorab umgesetzt (2026-05-05):**
- `subscription_scheduled_payments.amount` ist jetzt `nullable=True`
    (inkl. Alembic-Migration + Model/Schema-Anpassung), damit `paused`-Einträge
    mit `amount = None` gespeichert werden können.

### Neue `generate_scheduled_payments`-Logik:

```python
CATCH_UP_DAYS = 60

def generate_scheduled_payments(session: Session) -> int:
    today = date.today()
    cutoff = today - timedelta(days=CATCH_UP_DAYS)
    created_count = 0

    # Alle User mit Buchungshistorie aktiviert
    all_configs = session.execute(select(UserModuleConfiguration)).scalars().all()
    enabled_user_ids = {
        cfg.user_id for cfg in all_configs
        if (cfg.config or {}).get("subscription_booking_history", False)
    }
    if not enabled_user_ids:
        return 0

    # Alle nicht-canceled Abos dieser User
    subscriptions = session.execute(
        select(Subscription).where(
            Subscription.user_id.in_(enabled_user_ids),
            Subscription.status != SubscriptionStatus.canceled,
        )
    ).scalars().all()

    # Pause-History für alle betroffenen Abos per Bulk laden (kein N+1)
    sub_ids = [s.id for s in subscriptions]
    all_pauses = session.execute(
        select(SubscriptionPauseHistory).where(
            SubscriptionPauseHistory.subscription_id.in_(sub_ids)
        )
    ).scalars().all()
    pauses_by_sub = defaultdict(list)
    for p in all_pauses:
        pauses_by_sub[p.subscription_id].append(p)

    for sub in subscriptions:
        period_months = _MONTHS_PER_PERIOD[sub.interval]
        pause_hist = pauses_by_sub[sub.id]

        for due in compute_due_dates(sub.started_on, period_months, today):
            if due < cutoff:
                continue  # Catch-up-Fenster: nicht weiter als 60 Tage zurück

            # Existiert Eintrag schon? (erster Idempotenz-Schutz)
            existing = session.execute(
                select(SubscriptionScheduledPayment).where(
                    SubscriptionScheduledPayment.subscription_id == sub.id,
                    SubscriptionScheduledPayment.due_date == due,
                )
            ).scalar_one_or_none()
            if existing:
                continue

            if is_in_pause(due, pause_hist):
                status = PaymentStatus.paused
                amount = None
            else:
                status = PaymentStatus.pending
                amount = sub.amount

            session.add(SubscriptionScheduledPayment(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                due_date=due,
                amount=amount,
                status=status,
            ))
            created_count += 1

    if created_count > 0:
        session.commit()
    return created_count
```

**Done-Kriterien:**
- Manueller Admin-Trigger (`POST /admin/trigger-scheduler`) läuft durch, gibt count zurück
- Für active Abo: `pending`-Eintrag mit korrektem `due_date` (= berechneter Fälligkeitstag, nicht today)
- Für suspended Abo in Pause: `paused`-Eintrag
- Für canceled Abo: kein Eintrag
- Doppelter Trigger: kein Duplikat in DB

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Scheduler: period-basiert — due_date = berechneter Fälligkeitstag (nicht date.today())
- Scheduler: Catch-up-Logik — verpasste Perioden bis 60 Tage rückwirkend nachfüllen
- Scheduler: suspended → paused-Einträge (Pause in Tabelle sichtbar)
- Scheduler: canceled → keine Einträge mehr (Tabelle endet)
- Scheduler: N+1-Query eliminiert (pause_history per Bulk geladen)
```

---

## Chunk 6 — Router + Neue Endpoints

**Lesen:**
- `backend/app/routers/subscriptions.py` — vollständig
- `backend/app/schemas/subscription.py` (Chunk 2 — PriceChangeRequest, etc.)
- `backend/app/services/subscriptions.py` (Chunk 4 — neue Service-Funktionen)

**Ändern:** `backend/app/routers/subscriptions.py`

### Neue Endpoints:

```python
@router.post("/{subscription_id}/price-change", response_model=SubscriptionDetail)
async def price_change_endpoint(
    subscription_id: UUID,
    payload: PriceChangeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return price_change(session, current_user.id, subscription_id, payload)


@router.post("/{subscription_id}/cancel", response_model=SubscriptionDetail)
async def cancel_endpoint(
    subscription_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return cancel_subscription(session, current_user.id, subscription_id)
```

### Geänderte Endpoints:
- `PATCH /{id}`: Schema `SubscriptionUpdate` hat kein `amount` mehr — nichts im Router ändern,
  der Fehler kommt automatisch als 422 wenn Frontend es noch schickt

**Done-Kriterien:**
- `POST /subscriptions/{id}/price-change` mit `{"amount": 9.99, "valid_from": "2026-10-01"}` → 200
- `POST /subscriptions/{id}/cancel` → 200, Response hat `status: "canceled"`
- `GET /subscriptions/{id}` gibt `tatsaechlich`, `intervalle`, `dieses_kalenderjahr` zurück
- Ownership-Check: fremdes Abo gibt 403/404

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Neu: POST /subscriptions/{id}/price-change (amount + valid_from — Vergangenheit/heute/Zukunft)
- Neu: POST /subscriptions/{id}/cancel
```

---

## Chunk 7 — Frontend: Types + API-Client

**Lesen:**
- `frontend/src/types/subscription.ts`
- `frontend/src/api/subscriptions.ts`

**Ändern:** Beide Dateien

### Types (`frontend/src/types/subscription.ts`):

```typescript
export type BillingInterval =
  | "monthly" | "quarterly" | "semiannual" | "yearly" | "biennial"

export type PaymentStatus = "pending" | "paused" | "matched" | "missed"

// SubscriptionCreate: next_due_date entfernen
export interface SubscriptionCreate {
  name: string
  amount: number
  interval: BillingInterval
  started_on?: string
  notes?: string
}

// SubscriptionDetail: neue Felder
export interface SubscriptionDetail {
  // ... bestehende Felder ...
  next_due_date: string       // computed, bleibt im Response
  tatsaechlich: number
  intervalle: number
  dieses_kalenderjahr: number
}

// Neu
export interface PriceChangeRequest {
  amount: number
  valid_from: string  // ISO date: "2026-10-01"
}

export interface PauseHistoryEntry {
  paused_at: string
  resumed_at: string | null
  access_until: string | null
}
```

### API-Client (`frontend/src/api/subscriptions.ts`):

```typescript
export const priceChange = (id: string, payload: PriceChangeRequest) =>
  api.post<SubscriptionDetail>(`/subscriptions/${id}/price-change`, payload)

export const cancelSubscription = (id: string) =>
  api.post<SubscriptionDetail>(`/subscriptions/${id}/cancel`)
```

`createSubscription`: `next_due_date` aus Payload entfernen.

**Done-Kriterien:**
- `npm run build` — kein TypeScript-Fehler
- `tsc --noEmit` grün

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Frontend: Halbjährliches Intervall (semiannual) als Option
- Frontend: Neue Kennzahlen tatsaechlich, intervalle, dieses_kalenderjahr in Types
```

---

## Chunk 8 — Frontend: UI

**Lesen:**
- `frontend/src/pages/SubscriptionDetailPage.tsx`
- `frontend/src/pages/SubscriptionsPage.tsx`

**Ändern:** Beide Seiten + neue Modal-Komponente

### SubscriptionDetailPage — Kennzahlen-Block:

```tsx
<div className="cost-metrics">
  <MetricRow label="Monatlich"       value={formatAmount(sub.monatlich)} />
  <MetricRow label="Dieses Jahr"     value={formatAmount(sub.dieses_kalenderjahr)} />
  <MetricRow label="Intervalle"      value={sub.intervalle}
             subtext="Seit Abo-Beginn" small italic />
  <MetricRow label="Tatsächlich"     value={`~${formatAmount(sub.tatsaechlich)}`}
             subtext="Seit Abo-Beginn" small />
</div>
```

### SubscriptionDetailPage — Preisänderung:

- Button "Preis ändern" → öffnet Formular (inline oder Modal) mit `amount` + `valid_from`
- Bei Ankündigung (valid_from > heute): Badge "Preisänderung am X: Y €" in Kopfzeile
- Abschnitt "Angekündigte Preisänderung" editierbar/löschbar

### SubscriptionDetailPage — Cancel:

- Button "Abo kündigen" → öffnet Sicherheits-Modal (Typ b)
- User muss Abo-Name eintippen, erst dann wird Button aktiv
- Dann: `cancelSubscription(id)`

### Modal-System (neue Komponente `ConfirmModal.tsx`):

```tsx
// Typ a: Einfach
<ConfirmModal
  title="Abo pausieren?"
  onConfirm={handleSuspend}
  onCancel={() => setOpen(false)}
/>

// Typ b: Sicherheits-Modal (destruktiv)
<ConfirmModal
  title="Abo löschen"
  confirmText={sub.name}   // User muss diesen Text eintippen
  dangerous
  onConfirm={handleDelete}
  onCancel={() => setOpen(false)}
/>
```

Alle `window.confirm()` im Code durch dieses Modal ersetzen.

### SubscriptionsPage:

- Interval-Dropdown: "Halbjährlich" (`semiannual`) hinzufügen

**Done-Kriterien:**
- Detailseite zeigt alle 4 Kennzahlen korrekt formatiert
- Preisänderung über UI speicherbar, erscheint in Preishistorie
- Cancel-Modal fordert Abo-Name-Eingabe, Button bleibt disabled bis Text stimmt
- Kein `window.confirm()` mehr im gesamten Frontend
- `npm run build` grün

**CHANGELOG-Zeilen (für Chunk 10):**
```
- UI: Neue Kennzahlen-Ansicht (Monatlich / Dieses Jahr / Intervalle / Tatsächlich ~)
- UI: Preisänderungs-Flow mit Formular und Ankündigungs-Badge
- UI: Kündigungs-Flow mit Sicherheits-Modal (Abo-Name eintippen)
- UI: Modal-System ersetzt alle window.confirm()-Dialoge
- UI: "Halbjährlich" in Interval-Auswahl
```

---

## Chunk 9 — Tests

**Lesen:**
- `docs/19-v023-test-scenarios.md` — alle Szenarien vollständig
- `backend/tests/` — bestehende Tests für Kontext (Fixtures, Patterns)
- `backend/app/services/subscriptions.py` — fertige Algorithmen (Chunk 3)

**Erstellen:** `backend/tests/test_subscriptions_v023.py`

Szenarien aus docs/19 implementieren:
- S-01: `test_s01_relativedelta_anchor_recovery`, `test_s01_tatsaechlich`, `test_s01_next_due_date`, `test_s01_dieses_kalenderjahr`
- S-02: mit `@pytest.mark.skip(reason="Fiktiv-Toggle: späterer Slice")` markieren
- S-03: `test_s03_scheduler_pause_and_price_change` (parametrisiert), `test_s03_tatsaechlich_excludes_paused`, `test_s03_dieses_kalenderjahr_with_future_price`

Bestehende Tests prüfen:
- `pytest backend/tests/` — alle grün (Regressions-Check)

**Done-Kriterien:**
- `pytest backend/tests/test_subscriptions_v023.py -v` — alle Tests grün (außer S-02: skip)
- `pytest backend/tests/` — keine Regressions (bestehende Tests weiterhin grün)

**CHANGELOG-Zeilen (für Chunk 10):**
```
- Tests: S-01 (relativedelta), S-03 (Pause + Preiserhöhung) als automatisierte Tests
```

---

## Chunk 10 — CHANGELOG finalisieren

**Lesen:**
- Diese Datei (docs/20) — alle CHANGELOG-Zeilen aus den Chunks sammeln
- `CHANGELOG.md` — falls vorhanden, für Format-Konsistenz

**Erstellen/Ändern:** `CHANGELOG.md`

### v0.2.3 Eintrag (Template — aus Chunk-Zeilen zusammensetzen):

```markdown
## [0.2.3] — 2026-XX-XX

### Breaking Changes
- `POST /subscriptions`: Feld `next_due_date` entfernt (wird serverseitig aus started_on berechnet)
- `PATCH /subscriptions/{id}`: Feld `amount` entfernt → `POST /subscriptions/{id}/price-change` nutzen

### Neue API-Endpoints
- `POST /subscriptions/{id}/price-change`: Preisänderung mit valid_from (Vergangenheit/heute/Zukunft)
- `POST /subscriptions/{id}/cancel`: Abo kündigen

### Neue Features
- Halbjährliches Abrechnungsintervall (semiannual / "Halbjährlich")
- Neue Kennzahl "Intervalle": Anzahl Zahlungsperioden seit Abschluss
- Neue Kennzahl "Dieses Kalenderjahr": Jahresbudget-Ansicht inkl. Preisankündigungen
- Mehrfaches Pausieren und Resumieren (subscription_pause_history)
- Preisankündigungen: zukünftige Preise eintragenbar, Badge in Übersicht + editierbar in Detail
- Abos mit started_on in der Zukunft fließen nicht in monatliche Gesamtsumme ein

### Bugfixes
- BUG-01: next_due_date wird nicht mehr gespeichert — immer aus started_on + N × interval berechnet
- BUG-02: "Tatsächlich"-Algorithmus neu geschrieben (Perioden zählen, kein Segment-Math)
- BUG-03: Preisänderungen können in Vergangenheit und Zukunft eingetragen werden
- BUG-04: "Tatsächlich" zeigt korrekt erste Periode wenn Abo am selben Tag angelegt wird

### Scheduler
- Period-basiert: due_date = berechneter Fälligkeitstag (nicht date.today())
- Catch-up: verpasste Perioden bis 60 Tage rückwirkend automatisch nachfüllen
- suspended → paused-Einträge generiert (Pause in Buchungshistorie sichtbar)
- canceled → keine Einträge mehr (Tabelle endet sauber)

### Datenbank-Migrationen
- Neue Tabelle: subscription_pause_history
- Entfernt aus subscriptions: next_due_date, suspended_at, access_until
- Enum erweitert: PaymentStatus.paused, BillingInterval.semiannual

### UI
- Kennzahlen-Ansicht: Monatlich / Dieses Jahr / Intervalle / Tatsächlich ~
- Modal-System ersetzt alle window.confirm()-Dialoge
- Sicherheits-Modal für destruktive Aktionen (Abo-Name eintippen)
- "Halbjährlich" in Interval-Auswahl

### Tests
- S-01: relativedelta Ankertag-Verhalten
- S-03: Pause + Preiserhöhung in derselben Periode
```

**Done-Kriterien:**
- `CHANGELOG.md` existiert und enthält v0.2.3-Eintrag
- Alle Chunks in dieser Datei auf `[x]`
- Datum in CHANGELOG auf heutiges Datum gesetzt

---

## Kontext-Schnellreferenz

| Was gesucht | Wo |
|-------------|-----|
| Design-Entscheidungen + Algorithmus-Pseudocode | `docs/18` Abschnitt 0b |
| Migrations-Reihenfolge | `docs/18` Abschnitt 4 "Migrationsreihenfolge" |
| Akzeptanz-Szenarien mit Expected Outputs | `docs/19` |
| Bestehende Migrations | `backend/alembic/versions/` |
| Bestehende Tests | `backend/tests/` |

---

## Post-Release Fixes (nach Chunk 10, 2026-05-06)

### BUG-05 — `next_due_date` fehlte in der Abo-Listenansicht

**Problem:**
`SubscriptionRead.model_validate(sub)` liest nur echte DB-Spalten aus dem ORM-Objekt.
Da `next_due_date` keine Spalte mehr ist (BUG-01-Fix), blieb das Feld in allen
List-Endpunkten immer `null` — die Spalte „Nächste Fälligkeit" zeigte überall `—`.

**Betroffen:** GET /subscriptions (Liste), POST /subscriptions (create),
POST /.../suspend, POST /.../resume, POST /.../logo, PATCH /.../{id}

**Fix:**
Neue Hilfsfunktion `subscription_to_read(sub)` in `services/subscriptions.py`:
ruft nach `model_validate` noch `compute_next_due_date()` auf und setzt das Ergebnis.
Alle 6 Router-Endpunkte verwenden jetzt `subscription_to_read()` statt
`SubscriptionRead.model_validate()`.

**Geänderte Dateien:**
- `backend/app/services/subscriptions.py` — neue Funktion `subscription_to_read`
- `backend/app/routers/subscriptions.py` — 6 Aufrufe ersetzt, Import ergänzt

---

### BUG-06 — Stale `sub.amount` nach Preisankündigung

**Problem:**
`price_change()` setzt `sub.amount` nur wenn `valid_from <= today`.
Für angekündigte Preise (valid_from in der Zukunft) bleibt `sub.amount` der alte Wert —
auch noch Tage oder Wochen nachdem der neue Preis wirksam geworden ist.

Drei Stellen haben `sub.amount` direkt gelesen:
1. `monatlich` in `get_subscription_detail` (Zeile 345)
2. `monthly_total` in `get_overview` (Zeile 140)
3. `amount`-Snapshot im Scheduler (scheduler_service.py Zeile 190)

Nur `tatsaechlich` und `dieses_kj` waren korrekt — sie nutzten schon `applicable_price()`.

**Fix:**
Alle drei Stellen leiten den aktuell gültigen Preis jetzt aus der Preishistorie ab:

- `monatlich`: `applicable_price(today, price_hist)` statt `sub.amount`
- `monthly_total`: Bulk-Load aller Preishistorien, dann `applicable_price(today, ...)` pro Abo
- Scheduler: Bulk-Load via `prices_by_sub`, dann `applicable_price(due, price_hist)` pro Fälligkeitstag

Der Scheduler-Fix hat zusätzlich einen Bonus: für Catch-up-Einträge (vergangene Fälligkeiten)
wird jetzt der Preis verwendet, der am jeweiligen Fälligkeitstag galt — nicht der heutige.

**Geänderte Dateien:**
- `backend/app/services/subscriptions.py` — `defaultdict` importiert, `get_overview` + `get_subscription_detail` geändert
- `backend/app/services/scheduler_service.py` — `SubscriptionPriceHistory` + `applicable_price` importiert, Bulk-Load ergänzt, `sub.amount` ersetzt
