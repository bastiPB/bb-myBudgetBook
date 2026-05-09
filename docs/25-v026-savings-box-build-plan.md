# v0.2.6 — Build Plan: Savings Box

Status: ready-to-build
Stand: 2026-05-09
Design-Entscheidungen: docs/23-v025_savings_box.md

---

## Session-Start-Protokoll

1. Diese Datei lesen (docs/25)
2. Ersten Chunk mit `[ ]` finden
3. Nur die dort genannten Dateien lesen — nicht mehr
4. Chunk ausführen — kein erklärender Zwischentext, nur Arbeit
5. `[ ]` → `[x]` setzen in dieser Datei
6. Kurzmeldung: "Chunk N erledigt. Geänderte Dateien: ..."

Ressourcen-Regel: Pro Session maximal einen Chunk abarbeiten.
Qualitäts-Regel: Ressourcen-Schonen hat keinen Einfluss auf Code-Qualität —
die Spezifikation in docs/23 ist vollständig, der Plan ist präzise genug.

---

## Fortschritt

- [x] Chunk 1 — Alembic Migration
- [x] Chunk 2 — Models + Schemas
- [x] Chunk 3 — Service: Foundation (constants, types, access)
- [x] Chunk 4 — Service: terms.py
- [x] Chunk 5 — Service: mutations.py + lifecycle.py
- [x] Chunk 6 — Service: readers.py + __init__.py
- [x] Chunk 7 — Router
- [x] Chunk 8 — Frontend: Types + API-Client
- [x] Chunk 9 — Frontend: Dashboard (SavingsBoxPage)
- [x] Chunk 10 — Frontend: Detailseite (SavingsBoxDetailPage)
- [x] Chunk 11 — Tests
- [x] Chunk 12 — CHANGELOG finalisieren

---

## Chunk 1 — Alembic Migration

**Lesen:**
- `backend/alembic/versions/` — letzten Hash ermitteln (für `down_revision`)
- `backend/app/models/base.py` — BaseModel-Spalten (id, created_at, updated_at) bestätigen

**Erstellen:** Eine neue Migrations-Datei in `backend/alembic/versions/`

### 4 neue Enums + 3 neue Tabellen

```python
def upgrade():
    # --- Enums ---
    sa.Enum("weekly", "biweekly", "monthly", name="savingsinterval").create(op.get_bind())
    sa.Enum("active", "closed", name="savingsboxstatus").create(op.get_bind())
    sa.Enum("open", "fulfilled", "missed", name="savingstermstatus").create(op.get_bind())
    sa.Enum("deposit", "penalty", "manual", name="savingsbookingtype").create(op.get_bind())

    # --- savings_boxes ---
    op.create_table(
        "savings_boxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("box_number", sa.String(100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("interval", sa.Enum("weekly", "biweekly", "monthly", name="savingsinterval"), nullable=False),
        sa.Column("min_amount_per_term", sa.Numeric(10, 2), nullable=False),
        sa.Column("penalty_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("target_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("personal_amount_per_term", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.Enum("active", "closed", name="savingsboxstatus"), nullable=False, server_default="active"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_actual_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("closing_expected_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("closing_note", sa.Text(), nullable=True),
    )

    # --- savings_terms ---
    op.create_table(
        "savings_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("savings_box_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("savings_boxes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.Enum("open", "fulfilled", "missed", name="savingstermstatus"), nullable=False, server_default="open"),
    )

    # --- savings_bookings ---
    op.create_table(
        "savings_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("savings_box_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("savings_boxes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("savings_term_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("savings_terms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("booking_type", sa.Enum("deposit", "penalty", "manual", name="savingsbookingtype"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table("savings_bookings")
    op.drop_table("savings_terms")
    op.drop_table("savings_boxes")
    sa.Enum(name="savingsbookingtype").drop(op.get_bind())
    sa.Enum(name="savingstermstatus").drop(op.get_bind())
    sa.Enum(name="savingsboxstatus").drop(op.get_bind())
    sa.Enum(name="savingsinterval").drop(op.get_bind())
```

**Done-Kriterien:**
- `alembic upgrade head` läuft ohne Fehler
- Alle 3 Tabellen + 4 Enums in der DB vorhanden
- `alembic downgrade -1` entfernt alles sauber

**CHANGELOG-Zeilen (für Chunk 12):**
```
- DB: Neue Tabellen savings_boxes, savings_terms, savings_bookings
- DB: Neue Enums SavingsInterval, SavingsBoxStatus, SavingsTermStatus, SavingsBookingType
```

---

## Chunk 2 — Models + Schemas

**Lesen:**
- `backend/app/models/base.py`
- `backend/app/models/subscription.py` — als Strukturvorlage
- `backend/app/schemas/subscription.py` — als Strukturvorlage

**Erstellen:** `backend/app/models/savings_box.py`, `backend/app/schemas/savings_box.py`

### Models (`backend/app/models/savings_box.py`)

4 Enums + 3 Model-Klassen nach dem Muster von `subscription.py`:
- `SavingsInterval(str, enum.Enum)`: weekly, biweekly, monthly
- `SavingsBoxStatus(str, enum.Enum)`: active, closed
- `SavingsTermStatus(str, enum.Enum)`: open, fulfilled, missed
- `SavingsBookingType(str, enum.Enum)`: deposit, penalty, manual
- `SavingsBox(BaseModel)` → Tabelle `savings_boxes`
- `SavingsTerm(BaseModel)` → Tabelle `savings_terms`
- `SavingsBooking(BaseModel)` → Tabelle `savings_bookings`

Alle Spalten exakt wie in Chunk 1 definiert. `SAEnum`-Namen müssen mit den
Migrations-Enum-Namen übereinstimmen (z.B. `name="savingsinterval"`).

**Update:** `backend/app/models/__init__.py` — neue Modelle importieren

### Schemas (`backend/app/schemas/savings_box.py`)

```python
# Request-Schemas
class SavingsBoxCreate(BaseModel):
    name: str
    location: str | None = None
    box_number: str | None = None
    start_date: date
    end_date: date
    interval: SavingsInterval
    min_amount_per_term: Decimal
    penalty_amount: Decimal | None = None
    target_amount: Decimal | None = None
    personal_amount_per_term: Decimal | None = None

class SavingsBoxUpdate(BaseModel):  # alle Felder optional
    name: str | None = None
    location: str | None = None
    box_number: str | None = None
    target_amount: Decimal | None = None
    personal_amount_per_term: Decimal | None = None

class SavingsBoxCloseRequest(BaseModel):
    actual_amount: Decimal
    note: str | None = None

class SavingsBookingCreate(BaseModel):
    # deposit + penalty: Pflichtfeld (Service validiert → HTTP 422 wenn None)
    # manual: optional
    savings_term_id: uuid.UUID | None = None
    booking_type: SavingsBookingType
    amount: Decimal
    booking_date: date
    note: str | None = None

class SavingsBookingUpdate(BaseModel):  # booking_type + savings_term_id nicht änderbar
    amount: Decimal | None = None
    booking_date: date | None = None
    note: str | None = None

# Response-Schemas
class SavingsTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    due_date: date
    expected_amount: Decimal
    status: SavingsTermStatus

class SavingsBookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    savings_term_id: uuid.UUID | None
    booking_type: SavingsBookingType
    amount: Decimal
    booking_date: date
    note: str | None

class BoxSummaryRead(BaseModel):
    total_deposited: Decimal       # Summe aller deposit-Buchungen
    total_penalties: Decimal       # Summe aller penalty-Buchungen
    net_amount: Decimal            # total_deposited - total_penalties
    target_amount: Decimal | None
    personal_amount_per_term: Decimal | None
    progress_pct: Decimal | None   # net_amount / target_amount × 100, None wenn kein Ziel
    terms_open: int
    terms_fulfilled: int
    terms_missed: int

class SavingsBoxRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    location: str | None
    box_number: str | None
    start_date: date
    end_date: date
    interval: SavingsInterval
    min_amount_per_term: Decimal
    penalty_amount: Decimal | None
    status: SavingsBoxStatus
    next_open_due_date: date | None  # nächster offener Term — für Dashboard-Kachel
    summary: BoxSummaryRead          # immer befüllt — auch in der Listenansicht

class SavingsBoxDetail(SavingsBoxRead):
    terms: list[SavingsTermRead]
    bookings: list[SavingsBookingRead]
    summary: BoxSummaryRead
    closed_at: datetime | None
    closing_actual_amount: Decimal | None
    closing_expected_amount: Decimal | None
    closing_note: str | None
```

**Done-Kriterien:**
- `python -c "from app.models.savings_box import *; from app.schemas.savings_box import *"` — kein Fehler
- Alle Enum-Namen stimmen mit Migration überein

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Neu: SQLAlchemy-Modelle SavingsBox, SavingsTerm, SavingsBooking
- Neu: Pydantic-Schemas für alle Savings-Endpunkte
```

---

## Chunk 3 — Service: Foundation (constants, types, access)

**Lesen:**
- `backend/app/services/subscriptions/constants.py` — als Vorlage
- `backend/app/services/subscriptions/types.py` — als Vorlage
- `backend/app/services/subscriptions/access.py` — als Vorlage
- `backend/app/models/savings_box.py` (Chunk 2)

**Erstellen:**
- `backend/app/services/savings/__init__.py` (leer, wird in Chunk 6 befüllt)
- `backend/app/services/savings/constants.py`
- `backend/app/services/savings/types.py`
- `backend/app/services/savings/access.py`

### `constants.py`

```python
from app.models.savings_box import SavingsInterval
from datetime import timedelta

# Wie viele Tage zwischen zwei Terminen?
_DAYS_PER_INTERVAL: dict[SavingsInterval, int] = {
    SavingsInterval.weekly:   7,
    SavingsInterval.biweekly: 14,
    SavingsInterval.monthly:  0,   # Sonderfall: relativedelta statt timedelta
}
```

Hinweis: `monthly` braucht `relativedelta` (Monate haben unterschiedlich viele Tage) —
wird in `terms.py` als Sonderfall behandelt.

### `types.py`

```python
@dataclass
class BoxSummary:
    total_deposited: Decimal
    total_penalties: Decimal
    net_amount: Decimal
    target_amount: Decimal | None
    personal_amount_per_term: Decimal | None
    progress_pct: Decimal | None
    terms_open: int
    terms_fulfilled: int
    terms_missed: int
```

### `access.py`

```python
async def get_box_or_404(session, box_id, user_id) -> SavingsBox:
    """Lädt eine SavingsBox — wirft 404 wenn nicht gefunden, 403 wenn fremder Nutzer."""

def assert_box_is_open(box: SavingsBox) -> None:
    """Wirft HTTP 409 wenn status = closed. Vor jeder Schreiboperation aufrufen."""
```

**Done-Kriterien:**
- `python -c "from app.services.savings.access import *"` — kein Fehler
- `assert_box_is_open` wirft `HTTPException(409)` bei geschlossener Box

---

## Chunk 4 — Service: terms.py

**Lesen:**
- `backend/app/services/savings/constants.py` (Chunk 3)
- `backend/app/services/savings/types.py` (Chunk 3)
- `backend/app/models/savings_box.py` (Chunk 2)

**Erstellen:** `backend/app/services/savings/terms.py`

### Funktionen

```python
def generate_terms(box: SavingsBox) -> list[SavingsTerm]:
    """
    Erzeugt alle Spartermine von start_date bis end_date (inkl.).
    Jeder Term bekommt expected_amount = box.min_amount_per_term als Snapshot.
    monthly → relativedelta(months=1), weekly/biweekly → timedelta(days=7/14).
    """

async def update_term_statuses(session, box: SavingsBox) -> None:
    """
    Prüft alle open Terms der Box:
      - due_date < heute → status = missed
      - Falls penalty_amount konfiguriert und noch keine penalty-Buchung für diesen Term:
        automatisch SavingsBooking(type=penalty, amount=box.penalty_amount) anlegen.
    Idempotent: mehrfacher Aufruf erzeugt keine doppelten Penalty-Buchungen.
    """

def compute_box_summary(
    box: SavingsBox,
    terms: list[SavingsTerm],
    bookings: list[SavingsBooking],
) -> BoxSummary:
    """
    Berechnet Zusammenfassung aus Terms und Buchungen (kein DB-Zugriff).
    total_deposited = Σ amount (type=deposit)
    total_penalties = Σ amount (type=penalty)
    net_amount = total_deposited - total_penalties
    progress_pct = net_amount / target_amount × 100 wenn target_amount gesetzt, sonst None
    """
```

**Done-Kriterien:**
- `generate_terms` erzeugt für start=01.01.2026, end=31.12.2026, interval=biweekly → 27 Terme (14-Tage-Raster inkl. Start und Ende)
- `generate_terms` erzeugt für start=01.01.2026, end=31.01.2026, interval=monthly → 1 Term
- `update_term_statuses` auf offener Box mit überfälligem Term → Term = `missed`, Penalty-Buchung vorhanden
- Zweiter Aufruf → keine doppelte Penalty-Buchung

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Neu: Automatische Term-Generierung (start_date bis end_date, interval-basiert)
- Neu: Auto-Penalty bei verpassten Terminen (idempotent)
```

---

## Chunk 5 — Service: mutations.py + lifecycle.py

**Lesen:**
- `backend/app/services/savings/access.py` (Chunk 3)
- `backend/app/services/savings/terms.py` (Chunk 4)
- `backend/app/models/savings_box.py` (Chunk 2)
- `backend/app/schemas/savings_box.py` (Chunk 2)

**Erstellen:** `backend/app/services/savings/mutations.py`, `backend/app/services/savings/lifecycle.py`

### `mutations.py` — Kernregeln

**`create_box`:**
- Box anlegen → direkt `generate_terms()` aufrufen → alle Terms in gleicher Transaktion speichern

**`create_booking`:**
- `assert_box_is_open(box)`
- `booking_type == deposit`:
  - `savings_term_id` **Pflichtfeld** → HTTP 422 wenn nicht gesetzt
    (Service muss den Term laden um `expected_amount` zu kennen und den Status zu setzen)
  - `amount < term.expected_amount` → HTTP 422 ("Betrag muss mindestens X betragen")
  - Term-Status neu berechnen: hat der Term nun eine gültige Deposit-Buchung? → `fulfilled`
- `booking_type == penalty`:
  - `savings_term_id` **Pflichtfeld** → HTTP 422 wenn nicht gesetzt
- `booking_type == manual`:
  - `savings_term_id` optional — freie Buchung ohne Termin-Bezug

**`delete_booking`:**
- `assert_box_is_open(box)`
- `booking_type == penalty`:
  - Prüfen ob Deposit-Buchung für dieselbe `savings_term_id` existiert → wenn nein: HTTP 409
  - **Implementierung:** Ist `savings_term_id` der Buchung `NULL` (inkonsistente Zeile / Datenkorrektur), entfällt die Deposit-Prüfung — Löschen ist erlaubt. Normalfall über API: Penalty hat immer einen Term.
- `booking_type == deposit`:
  - Nach dem Löschen: hat der Term noch mindestens eine gültige Deposit-Buchung?
  - Wenn nein → Term zurück auf `missed`; falls `penalty_amount` konfiguriert und
    noch keine Penalty-Buchung vorhanden → Penalty-Buchung neu anlegen

**`update_booking`:**
- `assert_box_is_open(box)`
- Nur `amount`, `booking_date`, `note` änderbar
- Bei Betragsänderung: Term-Status neu berechnen

### `lifecycle.py`

**`close_savings_box`:**
```
atomare Transaktion:
1. closing_expected_amount = Σ deposit.amount - Σ penalty.amount aller Buchungen
2. closed_at = datetime.now(UTC)
3. status = closed
4. closing_actual_amount + closing_note speichern
```

**`reopen_savings_box`:**
```
status = active
closed_at = None
closing_actual_amount = None
closing_expected_amount = None
closing_note = None
```

**Done-Kriterien:**
- Deposit mit Betrag unter Mindest → HTTP 422
- Deposit auf geschlossener Box → HTTP 409
- Penalty löschen ohne Deposit → HTTP 409
- Deposit löschen → Term springt zurück auf `missed`, Penalty-Buchung neu angelegt
- close_savings_box: `closing_expected_amount` korrekt berechnet

---

## Chunk 6 — Service: readers.py + __init__.py

**Lesen:**
- `backend/app/services/savings/terms.py` (Chunk 4)
- `backend/app/services/savings/mutations.py` (Chunk 5)
- `backend/app/models/savings_box.py` (Chunk 2)

**Erstellen:** `backend/app/services/savings/readers.py`
**Ändern:** `backend/app/services/savings/__init__.py`

### `readers.py`

```python
async def list_boxes(session, user_id) -> list[tuple[SavingsBox, BoxSummary, date | None]]:
    """
    Alle Sparfächer des Users (aktiv + abgeschlossen), sortiert nach start_date desc.
    Lädt Terms + Bookings aller Boxen per Bulk (2 Queries), berechnet dann
    BoxSummary und next_open_due_date pro Box in Python — kein N+1.
    """

async def get_box_detail(session, box_id, user_id) -> tuple[SavingsBox, list[SavingsTerm], list[SavingsBooking], BoxSummary]:
    """
    Lädt Box, Terms, Bookings und ruft compute_box_summary() auf.
    Ruft vorher update_term_statuses() auf (on-demand Refresh).
    """
```

### `__init__.py` — öffentliche API

Alle Symbole re-exportieren die der Router braucht:
```python
from .mutations import create_box, update_box, create_booking, update_booking, delete_booking
from .lifecycle import close_savings_box, reopen_savings_box
from .readers import list_boxes, get_box_detail
from .terms import update_term_statuses
from .access import get_box_or_404
```

**Done-Kriterien:**
- `from app.services.savings import create_box, list_boxes, close_savings_box` — kein Fehler
- `get_box_detail` ruft `update_term_statuses` on-demand auf

---

## Chunk 7 — Router

**Lesen:**
- `backend/app/routers/subscriptions.py` — als Strukturvorlage
- `backend/app/services/savings/__init__.py` (Chunk 6)
- `backend/app/schemas/savings_box.py` (Chunk 2)
- `backend/app/main.py` — für Router-Registrierung

**Erstellen:** `backend/app/routers/savings.py`
**Ändern:** `backend/app/main.py` — Router registrieren

### Alle Endpunkte

```
POST   /savings/boxes                              → create_box → SavingsBoxDetail
GET    /savings/boxes                              → list_boxes → list[SavingsBoxRead]  (inkl. summary + next_open_due_date, kein N+1)
GET    /savings/boxes/{box_id}                     → get_box_detail → SavingsBoxDetail
PATCH  /savings/boxes/{box_id}                     → update_box → SavingsBoxRead
POST   /savings/boxes/{box_id}/close               → close_savings_box → SavingsBoxDetail
POST   /savings/boxes/{box_id}/reopen              → reopen_savings_box → SavingsBoxDetail

GET    /savings/boxes/{box_id}/terms               → aus get_box_detail → list[SavingsTermRead]
POST   /savings/boxes/{box_id}/terms/refresh       → update_term_statuses → 204

POST   /savings/boxes/{box_id}/bookings            → create_booking → SavingsBookingRead
GET    /savings/boxes/{box_id}/bookings            → aus get_box_detail → list[SavingsBookingRead]
PATCH  /savings/boxes/{box_id}/bookings/{id}       → update_booking → SavingsBookingRead
DELETE /savings/boxes/{box_id}/bookings/{id}       → delete_booking → 204
```

Alle Routen: `EditorOrAdminUser`-Dependency (wie Subscriptions).

**Done-Kriterien:**
- Backend startet ohne Fehler
- `POST /savings/boxes` mit gültigen Daten → 201, Terms in DB vorhanden
- `GET /savings/boxes/{id}` → Box + Terms + Bookings + Summary
- Ownership-Check: fremde Box → 404

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Neu: Router /savings/boxes (11 Endpunkte)
```

---

## Chunk 8 — Frontend: Types + API-Client

**Lesen:**
- `frontend/src/types/subscription.ts` — als Strukturvorlage
- `frontend/src/api/subscriptions.ts` — als Strukturvorlage

**Erstellen:**
- `frontend/src/types/savingsBox.ts`
- `frontend/src/api/savingsBox.ts`

### `types/savingsBox.ts`

```typescript
export type SavingsInterval = "weekly" | "biweekly" | "monthly"
export type SavingsBoxStatus = "active" | "closed"
export type SavingsTermStatus = "open" | "fulfilled" | "missed"
export type SavingsBookingType = "deposit" | "penalty" | "manual"

export interface BoxSummary {
  total_deposited: number
  total_penalties: number
  net_amount: number
  target_amount: number | null
  personal_amount_per_term: number | null
  progress_pct: number | null
  terms_open: number
  terms_fulfilled: number
  terms_missed: number
}

export interface SavingsTermRead { ... }
export interface SavingsBookingRead { ... }
export interface SavingsBoxRead { id, name, location, status, summary, ... }
export interface SavingsBoxDetail extends SavingsBoxRead { terms, bookings, closed_at, ... }

export interface SavingsBoxCreate { ... }
export interface SavingsBoxUpdate { ... }
export interface SavingsBoxCloseRequest { actual_amount: number; note?: string }
export interface SavingsBookingCreate { ... }
export interface SavingsBookingUpdate { ... }
```

### `api/savingsBox.ts`

```typescript
export const listBoxes = () => api.get<SavingsBoxRead[]>("/savings/boxes")
export const getBoxDetail = (id: string) => api.get<SavingsBoxDetail>(`/savings/boxes/${id}`)
export const createBox = (data: SavingsBoxCreate) => api.post<SavingsBoxDetail>("/savings/boxes", data)
export const updateBox = (id: string, data: SavingsBoxUpdate) => api.patch<SavingsBoxRead>(...)
export const closeBox = (id: string, data: SavingsBoxCloseRequest) => api.post(...)
export const reopenBox = (id: string) => api.post(...)
export const createBooking = (boxId: string, data: SavingsBookingCreate) => api.post(...)
export const updateBooking = (boxId: string, bookingId: string, data: SavingsBookingUpdate) => api.patch(...)
export const deleteBooking = (boxId: string, bookingId: string) => api.delete(...)
export const refreshTerms = (boxId: string) => api.post(...)
```

**Done-Kriterien:**
- `npm run build` — kein TypeScript-Fehler
- `tsc --noEmit` grün

---

## Chunk 9 — Frontend: Dashboard (SavingsBoxPage)

**Lesen:**
- `frontend/src/pages/SubscriptionsPage.tsx` — Routing-Muster, Layout
- `frontend/src/api/savingsBox.ts` (Chunk 8)
- `frontend/src/types/savingsBox.ts` (Chunk 8)

**Erstellen:**
- `frontend/src/pages/SavingsBoxPage.tsx`
- `frontend/src/pages/SavingsBoxPage.css`

**Ändern:** `frontend/src/App.tsx` — zwei neue Routen eintragen (analog zu `/subscriptions/:id`):
```tsx
<Route path="/savings-box" element={<Layout><SavingsBoxPage /></Layout>} />
<Route path="/savings-box/:id" element={<Layout><SavingsBoxDetailPage /></Layout>} />
```
Nav-Link und `MODULE_KEYS` (`savings_box`) sind bereits vorhanden —
`frontend/src/modules/registry.ts` und `backend/app/services/profile.py` müssen nicht angefasst werden.

### Layout

```
SavingsBoxPage (/savings-box)
├── Header: "Sparfächer" + Button "Neues Sparfach"
├── Wenn keine Boxen: Leer-Zustand ("Noch kein Sparfach angelegt")
└── Kacheln-Grid:
    pro Box eine Kachel:
    ┌─────────────────────────────────┐
    │ Name (bold) · Ort (grau)        │
    │ Nächster Termin: DD.MM.YYYY     │  ← nächster open term
    │ ████████░░░░  €87 / €400        │  ← nur wenn target_amount gesetzt
    │ X offen · Y verpasst            │
    │ Status-Badge (aktiv / abgesch.) │
    └─────────────────────────────────┘
    Klick → /savings-box/:id
```

Formular "Neues Sparfach" → Modal oder eigene Seite `/savings-box/new`
(Felder: Name, Ort optional, Fach-Nummer optional (`box_number`), Startdatum, Enddatum,
Intervall, Mindestbetrag, Strafgebühr optional, Gesamtziel optional,
Persönliches Termziel optional)

**Done-Kriterien:**
- `/savings-box` lädt und zeigt Kacheln
- Kachel-Klick navigiert zu `/savings-box/:id`
- Formular speichert neue Box, Weiterleitung zur Detailseite
- `npm run build` grün

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Neu: /savings-box — Dashboard mit Sparfach-Kacheln
```

---

## Chunk 10 — Frontend: Detailseite (SavingsBoxDetailPage)

**Lesen:**
- `frontend/src/pages/SavingsBoxPage.tsx` (Chunk 9) — Routing-Kontext
- `frontend/src/api/savingsBox.ts` (Chunk 8)
- `frontend/src/types/savingsBox.ts` (Chunk 8)

**Erstellen:**
- `frontend/src/pages/SavingsBoxDetailPage.tsx`
- `frontend/src/pages/SavingsBoxDetailPage.css`

### Struktur: 3 Tabs

**Tab "Übersicht":**
```
Progress-Bereich (adaptiv):
  • kein Ziel → "€87 eingezahlt, €12 Strafen, €75 netto"
  • target_amount → Fortschrittsbalken €75 / €400 (progress_pct %)
  • personal_per_term → je Term: €20 geplant / €25 gezahlt ✅

Termine-Liste (gruppiert nach Status):
  ▼ Offen (N)
    [due_date] offen   [Einzahlen]-Button
  ▼ Verpasst (N)
    [due_date] ❌ verpasst   [Einzahlen]-Button   Strafe €X
  ▼ Erledigt (N)   [ausklappen]
    [due_date] ✅ erledigt   €X gezahlt
```

"Einzahlen"-Button: öffnet Modal mit Betragsfeld + Datumfeld (default: heute) + Notiz.
Bei verpasstem Term: Hinweis "Für diesen Termin wurde eine Strafgebühr erfasst."

**Tab "Buchungen":**
```
Tabelle chronologisch (neueste zuerst):
  Datum | Typ | Betrag | Termin-Bezug | Notiz | Aktionen
  Aktionen: Bearbeiten (Betrag/Datum/Notiz) | Löschen
```

Löschen Penalty ohne Deposit → Fehler-Toast anzeigen (HTTP 409)

**Tab "Einstellungen":**
```
Formular: Name, Ort, Gesamtziel, Persönliches Termziel (editierbar)
Button "Sparfach abschließen" → Zwei-Schritt:
  Schritt 1: Bestätigungs-Modal — "Bist du sicher?"
  Schritt 2: Formular — tatsächlicher Auszahlungsbetrag + Notiz
Button "Sparfach wieder öffnen" (nur wenn closed) → Bestätigungs-Modal
  Warnung: "Dein Abschlussbericht wird gelöscht."
```

**Done-Kriterien:**
- Alle 3 Tabs rendern korrekt
- Terme gruppiert nach Status (offen / verpasst / erledigt eingeklappt)
- Einzahlungs-Modal validiert Betrag (>= min_amount_per_term, sonst Fehlermeldung)
- Close-Flow: Zwei-Schritt, danach Box zeigt Status "abgeschlossen"
- Reopen-Flow: Abschlussbericht weg, Terms wieder editierbar
- `npm run build` grün

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Neu: /savings-box/:id — Detailseite mit Tabs Übersicht / Buchungen / Einstellungen
- Neu: Terme gruppiert nach Status mit Einzahlungs-Flow
- Neu: Close/Reopen-Flow mit Zwei-Schritt-Bestätigung
```

---

## Chunk 11 — Tests

**Lesen:**
- `backend/tests/test_subscriptions_v023.py` oder `test_subscriptions_v024.py` —
  die aktuellere Datei nehmen (prüfen welche Fixtures/Auth-Patterns im Repo verwendet werden)
- `backend/app/services/savings/terms.py` (Chunk 4)
- `backend/app/services/savings/mutations.py` (Chunk 5)

**Erstellen:** `backend/tests/test_savings_box_v026.py`

Keine DB — alle Tests testen Service-Logik isoliert (reine Python-Objekte via SimpleNamespace),
analog zum bestehenden Test-Muster.

### Hilfsfunktionen

```python
def make_box(**kwargs) -> SimpleNamespace:
    """Minimale SavingsBox für isolierte Tests."""
    defaults = dict(
        id=uuid.uuid4(),
        min_amount_per_term=Decimal("10.00"),
        penalty_amount=None,
        target_amount=None,
        status="active",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        interval="biweekly",
    )
    return SimpleNamespace(**{**defaults, **kwargs})

def make_term(due_date, status="open", expected_amount="10.00") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), due_date=due_date,
        status=status, expected_amount=Decimal(expected_amount),
    )

def make_booking(type, amount, term_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), booking_type=type,
        amount=Decimal(amount), savings_term_id=term_id,
        booking_date=date.today(),
    )
```

### Szenarien — terms.py

```python
def test_generate_terms_biweekly_count():
    """01.01.–31.12.2026, biweekly → 26 Terme."""

def test_generate_terms_monthly_count():
    """01.01.–31.01.2026, monthly → 1 Term."""

def test_generate_terms_weekly_count():
    """01.01.–07.01.2026, weekly → 1 Term; 01.01.–14.01.2026 → 2 Terme."""

def test_generate_terms_expected_amount_snapshot():
    """expected_amount jedes Terms = box.min_amount_per_term zum Generierungszeitpunkt."""

# update_term_statuses ist async → @pytest.mark.asyncio + pytest-asyncio verwenden
# (analog zu bestehenden async-Tests im Projekt, falls vorhanden)
@pytest.mark.asyncio
async def test_update_term_statuses_sets_missed(monkeypatch):
    """Term mit due_date gestern und status=open → nach refresh status=missed."""

@pytest.mark.asyncio
async def test_update_term_statuses_creates_penalty(monkeypatch):
    """Term missed + penalty_amount konfiguriert → Penalty-Buchung wird angelegt."""

@pytest.mark.asyncio
async def test_update_term_statuses_idempotent(monkeypatch):
    """Zweiter refresh-Aufruf erzeugt keine zweite Penalty-Buchung."""
```

### Szenarien — compute_box_summary

```python
def test_summary_net_amount():
    """net_amount = Σ deposits − Σ penalties."""

def test_summary_progress_pct_with_target():
    """progress_pct = net_amount / target_amount × 100 wenn target_amount gesetzt."""

def test_summary_progress_pct_none_without_target():
    """progress_pct = None wenn target_amount nicht gesetzt."""

def test_summary_term_counts():
    """terms_open, terms_fulfilled, terms_missed korrekt gezählt."""
```

### Szenarien — mutations.py (Business-Regeln)

```python
def test_create_booking_deposit_below_minimum_rejected():
    """Deposit mit amount < expected_amount → HTTP 422."""

def test_create_booking_deposit_at_minimum_accepted():
    """Deposit mit amount == expected_amount → kein Fehler."""

def test_create_booking_penalty_without_term_id_rejected():
    """Penalty-Buchung ohne savings_term_id → HTTP 422."""

def test_delete_penalty_without_deposit_rejected():
    """Penalty löschen wenn kein Deposit für denselben Term → HTTP 409."""

def test_delete_penalty_with_deposit_allowed():
    """Penalty löschen wenn Deposit für denselben Term vorhanden → kein Fehler."""

def test_delete_deposit_resets_term_to_missed():
    """Letztes Deposit löschen → Term zurück auf missed."""

def test_assert_box_is_open_raises_on_closed():
    """assert_box_is_open() auf geschlossener Box → HTTP 409."""
```

### Szenarien — Router (Smoke-Tests, mit DB-Fixture)

```python
def test_create_box_generates_terms(client, auth_headers):
    """POST /savings/boxes → 201; savings_terms in DB vorhanden."""

def test_get_box_detail_returns_summary(client, auth_headers):
    """GET /savings/boxes/{id} → summary.terms_open korrekt."""

def test_create_booking_below_minimum_returns_422(client, auth_headers):
    """POST /savings/boxes/{id}/bookings mit amount < min → 422."""

def test_closed_box_rejects_booking(client, auth_headers):
    """POST /savings/boxes/{id}/bookings auf geschlossener Box → 409."""
```

**Done-Kriterien:**
- `pytest backend/tests/test_savings_box_v026.py -v` — alle Tests grün
- `pytest backend/tests/` — keine Regressions

**CHANGELOG-Zeilen (für Chunk 12):**
```
- Tests: terms-Generierung, Auto-Penalty, Business-Regeln (Deposit/Delete), Router-Smoke
```

---

## Chunk 12 — CHANGELOG finalisieren

**Lesen:**
- Diese Datei (docs/25) — alle CHANGELOG-Zeilen aus Chunks 1–11 sammeln
- `CHANGELOG.md` — für Format-Konsistenz

**Ändern:** `CHANGELOG.md`

```markdown
## [0.2.6] — 2026-XX-XX

### Neues Modul: Sparfach (Savings Box)

Das Sparfach-Modul bildet das klassische Kneipenbuch-System digital ab:
externer Ort verwahrt Geld, Nutzer trackt Einzahlungen, Termine und Abschluss.

### Neue API-Endpunkte
- POST   /savings/boxes
- GET    /savings/boxes
- GET    /savings/boxes/{id}
- PATCH  /savings/boxes/{id}
- POST   /savings/boxes/{id}/close
- POST   /savings/boxes/{id}/reopen
- GET    /savings/boxes/{id}/terms
- POST   /savings/boxes/{id}/terms/refresh
- POST   /savings/boxes/{id}/bookings
- GET    /savings/boxes/{id}/bookings
- PATCH  /savings/boxes/{id}/bookings/{id}
- DELETE /savings/boxes/{id}/bookings/{id}

### Features
- Sparfach anlegen mit Mindestbetrag, Strafgebühr (optional), Gesamtziel + persönlichem Termziel
- Automatische Term-Generierung (start_date bis end_date, interval-basiert)
- Auto-Penalty-Buchung bei verpassten Terminen (idempotent)
- Mehrere Deposits pro Term erlaubt — jeder muss >= Mindestbetrag sein
- Abschluss-Flow mit Snapshot (closing_expected_amount = Σ deposits − Σ penalties)
- Reopen-Flow mit vollständigem Reset des Abschlussberichts
- Immutability: geschlossene Box blockt alle Schreiboperationen (HTTP 409)

### Datenbank
- Neue Tabellen: savings_boxes, savings_terms, savings_bookings
- Neue Enums: SavingsInterval, SavingsBoxStatus, SavingsTermStatus, SavingsBookingType

### UI
- Dashboard /savings-box mit Kacheln (Fortschrittsbalken, Status, nächster Termin)
- Detailseite /savings-box/:id mit 3 Tabs: Übersicht / Buchungen / Einstellungen
- Termine gruppiert nach Status (offen / verpasst / erledigt)
- Zwei-Schritt-Bestätigung für Close und Reopen
```

**Done-Kriterien:**
- `CHANGELOG.md` enthält v0.2.6-Eintrag
- Alle 12 Chunks in dieser Datei auf `[x]`
- Datum gesetzt

---

## Kontext-Schnellreferenz

| Was gesucht | Wo |
|---|---|
| Design-Entscheidungen + Datenmodell | `docs/23-v025_savings_box.md` |
| Bestehende Migrations | `backend/alembic/versions/` |
| Vorlage Router | `backend/app/routers/subscriptions.py` |
| Vorlage Service-Package | `backend/app/services/subscriptions/` |
| Vorlage Types/API-Client | `frontend/src/types/subscription.ts`, `frontend/src/api/subscriptions.ts` |
