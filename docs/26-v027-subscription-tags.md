---
doc: feature-spec
release: v0.2.7
status: final
---

# v0.2.7 — Subscription Tags — Feature-Katalog

Erstellt: 2026-05-13  
Status: Final (Entscheidungen abgestimmt am 2026-05-13)

---

## 1. Ziel

Abos können mit frei definierbaren Tags versehen werden (z. B. „Streaming", „KI-Abos", „Server").  
Tags helfen beim Gruppieren, Filtern und Überblicken des Abo-Portfolios.

---

## 2. Kern-Entscheidungen (ADR)

| Thema | Entscheidung | Begründung |
|---|---|---|
| Tag-Scope | User-spezifisch (nicht global) | Jeder User hat sein eigenes Abo-Portfolio |
| Farbauswahl | Vordefinierte Palette (12 Farben) | Einfacher als freier Color-Picker, konsistentes UI |
| Tag-Zuweisung | `PUT /subscriptions/{id}/tags` mit kompletter Liste | Einfachstes Frontend-Modell — keine Partial-Updates |
| Löschverhalten Tag | Cascade: Tag-Zuweisung fällt automatisch mit | Kein Waisen-Problem in der Verbindungstabelle |
| Löschverhalten Abo | Cascade: Zuweisungen fallen mit dem Abo weg | Schon durch `ondelete=CASCADE` auf subscriptions abgedeckt |

---

## 3. Datenmodell (2 neue Tabellen)

### 3.1 `subscription_tags` — Tag-Definitionen

```
id          UUID (PK, via BaseModel)
user_id     UUID FK → users.id (ondelete=CASCADE)
name        VARCHAR(50), NOT NULL
color       VARCHAR(7), NOT NULL  -- Hex-Farbe z.B. "#6366f1"
created_at  TIMESTAMP (via BaseModel)
updated_at  TIMESTAMP (via BaseModel)

UNIQUE(user_id, name)  -- kein doppelter Tag-Name pro User
```

### 3.2 `subscription_tag_assignments` — M:N-Verbindungstabelle

```
subscription_id  UUID FK → subscriptions.id (ondelete=CASCADE)
tag_id           UUID FK → subscription_tags.id (ondelete=CASCADE)

PRIMARY KEY (subscription_id, tag_id)
```

> Diese Tabelle erbt **nicht** von BaseModel — sie hat keine eigene UUID-ID, kein created_at/updated_at.  
> SQLAlchemy: wird als `Table(...)` direkt im Model definiert (Association Table Pattern).

### 3.3 Farb-Palette (12 Farben)

```
#6366f1  Indigo
#8b5cf6  Violett
#ec4899  Pink
#ef4444  Rot
#f97316  Orange
#eab308  Gelb
#22c55e  Grün
#14b8a6  Teal
#06b6d4  Cyan
#3b82f6  Blau
#64748b  Slate (neutral)
#a855f7  Lila
```

---

## 4. Backend

### 4.1 Neue Dateien

```
backend/app/
├── models/subscription_tag.py         # SubscriptionTag + Verbindungstabelle
├── schemas/subscription_tag.py        # TagRead, TagCreate, TagUpdate
├── routers/subscription_tags.py       # HTTP-Endpunkte
└── services/subscriptions/
    └── tags.py                         # Business-Logik Tags
```

`subscriptions/__init__.py` wird um die öffentlichen Symbole aus `tags.py` ergänzt.

### 4.2 API-Endpunkte

#### Tag-Verwaltung (CRUD)

| Method | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/subscriptions/tags` | Alle Tags des aktuellen Users |
| `POST` | `/subscriptions/tags` | Neuen Tag anlegen |
| `PATCH` | `/subscriptions/tags/{tag_id}` | Tag umbenennen und/oder Farbe ändern |
| `DELETE` | `/subscriptions/tags/{tag_id}` | Tag löschen (Zuweisungen fallen automatisch weg) |

#### Tag-Zuweisung (pro Abo)

| Method | Pfad | Beschreibung |
|---|---|---|
| `PUT` | `/subscriptions/{id}/tags` | Tags eines Abos komplett setzen (Liste von tag_ids) |

> `PUT` mit leerer Liste `[]` entfernt alle Tags vom Abo.  
> Das Frontend sendet immer die vollständige aktuelle Auswahl — kein Partial-Update nötig.

### 4.3 Schemas (Übersicht)

```python
# TagRead — was die API zurückgibt
class TagRead(BaseModel):
    id: UUID
    name: str
    color: str          # "#6366f1"

# TagCreate — was beim Erstellen gesendet wird
class TagCreate(BaseModel):
    name: str           # max 50 Zeichen
    color: str          # muss in der Palette sein

# TagUpdate — beim PATCH (alle Felder optional)
class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None

# TagAssignRequest — beim PUT /subscriptions/{id}/tags
class TagAssignRequest(BaseModel):
    tag_ids: list[UUID]
```

`SubscriptionRead` und `SubscriptionDetail` bekommen ein neues Feld:
```python
tags: list[TagRead] = []   # leer wenn keine Tags zugewiesen
```

### 4.4 Service-Funktionen (`services/subscriptions/tags.py`)

```
get_all_tags(user_id)                  → list[SubscriptionTag]
create_tag(user_id, name, color)       → SubscriptionTag
update_tag(tag_id, user_id, ...)       → SubscriptionTag
delete_tag(tag_id, user_id)            → None
set_subscription_tags(sub_id, tag_ids, user_id)  → list[SubscriptionTag]
```

Zugriffsschutz: jede Funktion prüft, dass `tag.user_id == aktueller_user` — analog zu `access.py`.

### 4.5 Validierungen (Backend)

- `name`: Leerzeichen am Rand werden getrimmt, Länge 1–50 Zeichen
- `color`: muss ein Hex-Wert aus der definierten Palette sein (`constants.py`)
- `UNIQUE(user_id, name)`: DB-Constraint + saubere 409-Fehlermeldung
- Tag-IDs beim PUT: müssen dem User gehören — fremde Tag-IDs → 403

---

## 5. Frontend

### 5.1 Neue Dateien

```
frontend/src/
├── api/tags.ts                         # API-Aufrufe für Tag-CRUD + Zuweisung
├── types/tag.ts                        # TagRead, TagCreate, TagUpdate, Farb-Palette
└── components/
    ├── TagBadge.tsx                    # Kleines farbiges Chip-Element
    ├── TagSelector.tsx                 # Multi-Select Dropdown für Tag-Auswahl
    └── TagManagementModal.tsx          # Modal: Tags erstellen, bearbeiten, löschen
```

### 5.2 UI-Komponenten

#### TagBadge (atomar)
- Kleines Pill/Chip: farbiger Punkt + Tag-Name
- Farbe kommt aus `tag.color`
- Wird überall verwendet: Abo-Karte, Detailansicht, Filter

#### TagSelector (für Abo-Formulare)
- Multi-Select Dropdown mit allen Tags des Users
- Bereits zugewiesene Tags vorausgewählt
- "Tags verwalten" Link öffnet das TagManagementModal
- Auswahl wird beim Speichern via `PUT /subscriptions/{id}/tags` gesendet

#### TagManagementModal
- Erreichbar: via Link im TagSelector + Einstellungen-Bereich (TBD)
- Inhalt:
  - Liste aller vorhandenen Tags mit `TagBadge` + Edit/Delete-Icons
  - Formular: "Neuen Tag erstellen" (Name-Input + Farb-Palette als Klick-Auswahl)
  - Inline-Bearbeitung: Klick auf Tag → Name + Farbe änderbar
  - Löschen: zeigt kurze Warnung ("Wird von X Abos entfernt") — kein Bestätigungs-Schritt nötig wenn 0 Abos, kurze Warnung wenn > 0

### 5.3 Integration in bestehende Seiten

| Seite / Komponente | Änderung |
|---|---|
| `SubscriptionCard.tsx` | TagBadges unterhalb des Abo-Namens anzeigen |
| `SubscriptionDetailPage.tsx` | TagBadges + TagSelector zum Bearbeiten |
| `SubscriptionCreateModal.tsx` | TagSelector einbauen (optional beim Erstellen) |
| `SubscriptionsPage.tsx` | Tag-Filter-Leiste (Slice C — optional) |

### 5.4 Types (`frontend/src/types/tag.ts`)

```typescript
export interface TagRead {
  id: string
  name: string
  color: string       // "#6366f1"
}

export interface TagCreate {
  name: string
  color: string
}

export interface TagUpdate {
  name?: string
  color?: string
}

// Vordefinierte Palette — exakt wie im Backend
export const TAG_COLORS: { hex: string; label: string }[] = [
  { hex: '#6366f1', label: 'Indigo' },
  { hex: '#8b5cf6', label: 'Violett' },
  { hex: '#ec4899', label: 'Pink' },
  { hex: '#ef4444', label: 'Rot' },
  { hex: '#f97316', label: 'Orange' },
  { hex: '#eab308', label: 'Gelb' },
  { hex: '#22c55e', label: 'Grün' },
  { hex: '#14b8a6', label: 'Teal' },
  { hex: '#06b6d4', label: 'Cyan' },
  { hex: '#3b82f6', label: 'Blau' },
  { hex: '#64748b', label: 'Slate' },
  { hex: '#a855f7', label: 'Lila' },
]
```

---

## 6. Implementierungs-Slices (Reihenfolge)

### Slice A — Datenbank-Fundament
1. `backend/app/models/subscription_tag.py` — Model + Verbindungstabelle
2. Alembic-Migration erstellen + prüfen
3. `backend/app/models/__init__.py` — neues Model registrieren

### Slice B — Backend Tag-CRUD
1. `schemas/subscription_tag.py`
2. `services/subscriptions/tags.py` (get, create, update, delete, set_tags)
3. `routers/subscription_tags.py` (alle Endpunkte)
4. Router in `main.py` registrieren
5. `SubscriptionRead` + `SubscriptionDetail` um `tags: list[TagRead]` erweitern

### Slice C — Backend Tags in Abo-Responses einbauen
1. `readers.py` anpassen: Tags beim Laden eines Abos mitladen (eager load / selectinload)
2. Manuelle Tests mit curl/httpie

### Slice D — Frontend: Tag-Typen + API
1. `frontend/src/types/tag.ts`
2. `frontend/src/api/tags.ts`

### Slice E — Frontend: TagBadge + TagManagementModal
1. `TagBadge.tsx` — atomare Komponente
2. `TagManagementModal.tsx` — CRUD-Modal
3. `TagSelector.tsx` — Multi-Select für Formulare

### Slice F — Frontend: Integration in bestehende Seiten
1. `SubscriptionCard.tsx` — Badges anzeigen
2. `SubscriptionDetailPage.tsx` — Badges + TagSelector
3. `SubscriptionCreateModal.tsx` — TagSelector (optional)

### Slice G — Frontend: Filter
1. Tag-Filter-Leiste auf `SubscriptionsPage.tsx`
2. Filterlogik: UND-Verknüpfung (Abo muss ALLE gewählten Tags haben)
3. Aktive Filter visuell hervorheben + "Filter zurücksetzen"-Button

---

## 7. Abgestimmte Entscheidungen

| # | Frage | Entscheidung |
|---|---|---|
| 1 | Soll der Tag-Filter Teil von v0.2.7 sein? | **Ja** — Filter ist Teil von v0.2.7 (Slice G) |
| 2 | Wie kommt der User zu "Tags verwalten"? | **Nur über Modal** — Link im TagSelector-Dropdown, kein Sidebar-Eintrag |
| 3 | Beim Löschen: Warnung oder Dialog? | **Inline-Warnung** — "Wird von X Abos entfernt" direkt im Modal, kein extra Klick |
| 4 | Maximale Tags pro Abo? | **Keine Grenze** — einfachste Implementierung, User entscheidet selbst |

---

## 8. Was NICHT in v0.2.7 kommt

- Tag-Sharing zwischen Usern (kein Multi-User-Scope in dieser Version)
- Freier Color-Picker (nur Palette)
- Tag-Statistiken (z.B. "Streaming kostet mich monatlich X €") — Icebox
- Sortierung/Gruppierung der Abo-Übersicht nach Tags — Icebox
