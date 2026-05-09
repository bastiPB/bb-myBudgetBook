# v0.2.6 — Modul: Savings Box (Sparfach)

> Planungsdokument — Basis: Brainstorming `int/doc/brainstorming_sparfach.md`
> Stand: 2026-05-08

---

## 1. Ziel des Moduls

Das Sparfach-Modul bildet das klassische Kneipenbuch-System digital ab:
Ein externer Ort (Kneipe, Verein, Spardose) verwahrt Geld. Der Nutzer trackt seine
Einzahlungen, Intervall-Verpflichtungen und den Abschluss (Auszahlung vs. Erwartetes).

**Kernnutzen:** Nachvollziehbarkeit + Fehlbetragsschutz beim Abschluss.

---

## 2. MVP-Scope (v0.2.6)

### Im Scope
| Story | Beschreibung |
|---|---|
| S-01 | Sparfach anlegen (Name, Ort, Intervall, Betrag, Ziel, Strafgebühr optional) |
| S-02 | Automatische Spartermine generieren (Startdatum + Intervall → Term-Reihe) |
| S-03 | Einzahlung erfassen (Betrag, Datum, Notiz, editierbar) |
| S-04 | Verpasste Termine erkennen + automatische Penalty-Buchung (wenn `penalty_amount` konfiguriert) |
| S-05 | Manuelle Buchung außerhalb Termin (Typ: `deposit` / `penalty` / `manual`) |
| S-06 | Fortschritt & Ziel anzeigen (aktueller Betrag, Differenz, %-Fortschritt) |
| S-07 | Sparfach abschließen + Differenzberechnung (erwartet vs. tatsächlich ausgezahlt) |
| S-08 | Dashboard/Übersicht: alle aktiven Sparfächer, nächste Termine, Status-Zahlen |

### Explizit aus dem Scope genommen (Later)
| Feature | Warum später |
|---|---|
| Multi-User / Shared Sparfach | Braucht Einladungs-Flow, Rollen, neue Auth-Logik — eigenes Epic |
| Notifications / Reminder | Braucht Background-Scheduler (kein Infra vorhanden) |
| Strafgebühr deaktivieren/reaktivieren während Laufzeit | Nachträgliche Konfigurationsänderung — Later |
| PDF/CSV Export | Separate Infrastruktur |
| Gamification / Streaks | Nice-to-have |

---

## 3. Reuse-First Rule

Bevor neuer Code geschrieben wird, wird geprüft was wiederverwendet werden kann.

### 3.1 Direkt wiederverwendbar (kein Anpassen nötig)

| Artefakt | Datei | Wie genutzt |
|---|---|---|
| `BaseModel` | `models/base.py` | Alle 3 neuen Modelle erben davon (UUID, created_at, updated_at) |
| `EditorOrAdminUser` | `dependencies.py` | Alle Savings-Routen werden damit geschützt |
| `DatabaseSession` | `dependencies.py` | DB-Session in allen neuen Endpunkten |
| `dateutil.relativedelta` | bereits installiert via `billing.py` | Intervall-Datumsrechnung in `savings/terms.py` |
| `access.py`-Muster | `services/subscriptions/access.py` | 404/403-Checks nach gleichem Pattern bauen |
| `Numeric(10, 2)` | überall in `models/subscription.py` | Geldbeträge immer so definieren |

### 3.2 Als Vorlage nehmen (Muster übernehmen, nicht importieren)

| Vorlage | Datei | Was übernehmen |
|---|---|---|
| `BillingInterval` Enum | `models/subscription.py:12` | Gleiche `str + enum.Enum` Kombination für `SavingsInterval` |
| `SubscriptionStatus` Enum | `models/subscription.py:25` | Gleiche Struktur für `SavingsBoxStatus` + `SavingsTermStatus` |
| `_MONTHS_PER_PERIOD` Logik | `services/subscriptions/constants.py:22` | Gleiche Idee für `_DAYS_PER_SAVINGS_INTERVAL` |
| `ComputedDue` Dataclass | `services/subscriptions/types.py:19` | Vorbild für `ComputedTerm` Dataclass in `savings/types.py` |
| Service-Package-Struktur | `services/subscriptions/` | Gleiches Unterpaket-Muster für `services/savings/` |

### 3.3 Nicht übernehmen / neu machen

| Was | Warum |
|---|---|
| `BillingInterval` direkt importieren und erweitern | Breaking Change — bestehende Abos nutzen diesen Enum in der DB. Neuer `SavingsInterval` ist sauberer. |
| `SubscriptionBillingHistory`-Modell | Zu abo-spezifisch (price/interval changes). Savings hat eigenes, einfacheres Buchungs-Konzept. |

---

## 4. Neue Enums

Alle neuen Enums kommen in `models/savings_box.py` (zusammen mit den Modellen, wie bei `subscription.py`).

```python
class SavingsInterval(str, enum.Enum):
    weekly    = "weekly"     # wöchentlich
    biweekly  = "biweekly"  # 2-wöchentlich
    monthly   = "monthly"   # monatlich

class SavingsBoxStatus(str, enum.Enum):
    active   = "active"    # Sparfach läuft
    closed   = "closed"    # abgeschlossen (mit Closing-Bericht)

class SavingsTermStatus(str, enum.Enum):
    open      = "open"      # noch nicht bezahlt, nicht fällig/verfallen
    fulfilled = "fulfilled" # bezahlt (pünktlich oder verspätet)
    missed    = "missed"    # Fälligkeitsdatum überschritten, keine Buchung

class SavingsBookingType(str, enum.Enum):
    deposit = "deposit"  # reguläre Einzahlung
    penalty = "penalty"  # Strafgebühr (manuell erfasst im Soft-Modus)
    manual  = "manual"   # freie Buchung außerhalb eines Termins
```

---

## 5. Datenmodell (3 neue Tabellen)

### 5.1 `SavingsBox` → Tabelle `savings_boxes`

| Spalte | Typ | Pflicht | Bemerkung |
|---|---|---|---|
| `id` | UUID | ✅ | via BaseModel |
| `user_id` | UUID FK → users | ✅ | ondelete=CASCADE |
| `name` | String(255) | ✅ | frei wählbar |
| `location` | String(255) | ❌ | Kneipe, Verein etc. |
| `box_number` | String(100) | ❌ | Sparfach-Nr. beim Wirt |
| `start_date` | Date | ✅ | erster Termin wird von hier berechnet |
| `end_date` | Date | ✅ | Laufzeitende — Sparfächer haben immer ein festes Ende, kein offener Sparplan |
| `interval` | SavingsInterval | ✅ | weekly / biweekly / monthly |
| `min_amount_per_term` | Numeric(10,2) | ✅ | Mindestsparbetrag pro Termin — vom Wirt vorgegeben, bindend |
| `penalty_amount` | Numeric(10,2) | ❌ | Strafgebühr — greift nur wenn Termin `missed` (nichts gezahlt) |
| `target_amount` | Numeric(10,2) | ❌ | **Gesamtziel** (Typ A): "Ich will am Ende €400 haben" |
| `personal_amount_per_term` | Numeric(10,2) | ❌ | **Persönliches Termziel** (Typ B): "Ich will €20 pro Termin zahlen" — nicht bindend, über Mindest hinaus |
| `status` | SavingsBoxStatus | ✅ | default: active |
| `closed_at` | DateTime(tz) | ❌ | Zeitstempel des Abschlusses — nur gesetzt wenn status = closed |
| `closing_actual_amount` | Numeric(10,2) | ❌ | vom Nutzer eingegebener tatsächlicher Auszahlungsbetrag |
| `closing_expected_amount` | Numeric(10,2) | ❌ | Snapshot zum Abschlusszeitpunkt (immutable): `Σ deposits − Σ penalties` — was der Wirt dir auszahlen sollte |
| `closing_note` | Text | ❌ | Freitext beim Abschließen |

> **Immutability-Regel:** Sobald `status = closed` gesetzt ist, blockt `assert_box_is_open()` alle
> folgenden Schreiboperationen mit HTTP 409:
> - `POST /bookings` — neue Buchung anlegen
> - `PATCH /bookings/{id}` — Buchung bearbeiten
> - `DELETE /bookings/{id}` — Buchung löschen
> - `POST /terms/refresh` — Term-Status aktualisieren
> - `PATCH /boxes/{id}` — Box-Metadaten ändern
>
> Einzige Ausnahme: `POST /boxes/{id}/reopen` — dieser Endpunkt darf eine geschlossene Box öffnen.
> `closing_expected_amount` wird einmalig beim `close_savings_box()`-Aufruf berechnet und danach
> nie mehr verändert.

### 5.2 `SavingsTerm` → Tabelle `savings_terms`

| Spalte | Typ | Pflicht | Bemerkung |
|---|---|---|---|
| `id` | UUID | ✅ | via BaseModel |
| `savings_box_id` | UUID FK → savings_boxes | ✅ | ondelete=CASCADE |
| `due_date` | Date | ✅ | berechnetes Fälligkeitsdatum |
| `expected_amount` | Numeric(10,2) | ✅ | Snapshot von `min_amount_per_term` zum Zeitpunkt der Term-Generierung — bleibt unveränderlich auch wenn die Box später angepasst wird |
| `status` | SavingsTermStatus | ✅ | default: open |

> **Term-Status-Logik:**
> - `deposit`-Buchung mit `amount >= expected_amount` vorhanden → `fulfilled`
> - Fälligkeitsdatum überschritten, keine Buchung → `missed` (Penalty-Buchung wird automatisch angelegt wenn konfiguriert)
> - Es gibt keine Status-Stufe "partial" — der Mindestbetrag ist starr
>
> **Zuordnung Buchung → Term:**
> Eine Buchung wird einem Term über `savings_term_id` zugeordnet. Die UI zeigt dem Nutzer
> die offenen Termine — er klickt auf einen Term und erfasst dort seine Einzahlung. Die
> `savings_term_id` wird dabei automatisch aus dem gewählten Term übernommen.
>
> **Mehrere Deposits pro Term erlaubt:**
> Ein Term kann mehrere `deposit`-Buchungen haben — z.B. weil der Nutzer 3× im Monat
> in die Kneipe geht und jedes Mal etwas einzahlt.
> Term = `fulfilled` sobald die **erste** gültige Deposit-Buchung vorhanden ist.
> Weitere Buchungen sind Bonus-Sparbeiträge und werden normal dokumentiert.
>
> **Backend-Validierung (nicht nur Frontend):**
> Jede einzelne `deposit`-Buchung muss `amount >= expected_amount` erfüllen — HTTP 422 sonst.
> Eine Buchung von €5 bei Mindest €10 wird vom Service abgelehnt, unabhängig davon was
> das Frontend schickt. Die Mindestgrenze gilt pro Buchung, nicht als Summe.

### 5.3 `SavingsBooking` → Tabelle `savings_bookings`

| Spalte | Typ | Pflicht | Bemerkung |
|---|---|---|---|
| `id` | UUID | ✅ | via BaseModel |
| `savings_box_id` | UUID FK → savings_boxes | ✅ | ondelete=CASCADE |
| `savings_term_id` | UUID FK → savings_terms | ❌ | NULL = manuelle Buchung ohne Termin-Bezug; bei `penalty`-Buchungen immer gesetzt (Pflicht) |
| `booking_type` | SavingsBookingType | ✅ | deposit / penalty / manual |
| `amount` | Numeric(10,2) | ✅ | tatsächlich eingezahlter Betrag |
| `booking_date` | Date | ✅ | Datum der Einzahlung |
| `note` | Text | ❌ | optionale Notiz |

---

## 6. Service-Package-Struktur

Nach dem gleichen Muster wie `services/subscriptions/`:

```
backend/app/services/savings/
├── __init__.py      # öffentliche API — alle Exports hier
├── access.py        # 404/403-Checks (get_box_or_404, assert_owner)
├── constants.py     # _DAYS_PER_SAVINGS_INTERVAL, etc.
├── lifecycle.py     # close_savings_box
├── mutations.py     # create_box, update_box, create_booking, delete_booking
├── readers.py       # list_boxes, get_box_detail, get_terms, get_bookings
├── terms.py         # generate_terms (Kernlogik: Startdatum + Intervall → Term-Liste)
│                    # update_term_statuses (offen → missed wenn Datum überschritten)
└── types.py         # ComputedTerm, BoxSummary (Dataclasses, kein HTTP)
```

### Modul-Aufgaben im Detail

**`terms.py`** — das Herzstück:
- `generate_terms(box)` → berechnet alle Fälligkeitsdaten ab `start_date` + `interval`
- `update_term_statuses(session, box_id)` → prüft alle `open` Terms: ist `due_date < today`? → `missed`; falls `penalty_amount` auf der Box konfiguriert ist, wird automatisch eine `penalty`-Buchung angelegt — aber nur wenn noch keine existiert (idempotent, kein doppeltes Anlegen bei mehrfachem Refresh)
- `compute_box_summary(box, terms, bookings)` → liefert aktueller Gesamtbetrag, Differenz zum Ziel, %-Fortschritt

**`lifecycle.py`**:
- `close_savings_box(session, box, actual_amount, note)` → atomare Transaktion:
  1. berechnet `closing_expected_amount` = Σ `amount` (type=`deposit`) − Σ `amount` (type=`penalty`) aller Buchungen der Box
  2. setzt `closed_at` = jetzt (UTC)
  3. setzt `status = closed`
  4. speichert `closing_actual_amount` + `closing_note`
- `assert_box_is_open(box)` → wirft HTTP 409 wenn `status = closed` — wird in `mutations.py` und `terms.py` vor jeder Schreiboperation gerufen
- `reopen_savings_box(session, box)` → setzt `status` → `active`, löscht alle vier Closing-Felder (`closed_at`, `closing_actual_amount`, `closing_expected_amount`, `closing_note`)

**`mutations.py`** — Lösch-Regeln:
- `delete_booking(session, booking)` → prüft vor dem Löschen:
  - `booking_type == penalty` → es muss mindestens eine `deposit`-Buchung mit derselben `savings_term_id` existieren — sonst HTTP 409 ("Strafe kann nur entfernt werden wenn eine Einzahlung für diesen Termin vorhanden ist")
  - `booking_type == deposit` → prüft ob nach dem Löschen der Term noch `fulfilled` bleibt; wenn nicht → Term zurück auf `missed` + Penalty-Buchung neu anlegen falls konfiguriert

**`readers.py`**:
- `list_boxes(session, user_id)` → aktive + abgeschlossene Sparfächer
- `get_box_detail(session, box_id)` → Box + Terms + Bookings + Summary

---

## 7. API-Endpunkte

Router-Datei: `routers/savings.py` — Prefix: `/savings`

### Sparfächer (Box)

| Method | Pfad | Beschreibung |
|---|---|---|
| `POST` | `/savings/boxes` | Sparfach anlegen + Terme generieren |
| `GET` | `/savings/boxes` | Alle Sparfächer des Users (aktiv + abgeschlossen) |
| `GET` | `/savings/boxes/{box_id}` | Detail: Box + Terms + Bookings + Summary |
| `PATCH` | `/savings/boxes/{box_id}` | Metadaten ändern (Name, Ort, Ziel etc.) |
| `POST` | `/savings/boxes/{box_id}/close` | Sparfach abschließen (actual_amount + note) |
| `POST` | `/savings/boxes/{box_id}/reopen` | Sparfach wieder öffnen — löscht Abschlussbericht vollständig |

### Termine (Terms)

| Method | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/savings/boxes/{box_id}/terms` | Alle Termine eines Sparfachs |
| `POST` | `/savings/boxes/{box_id}/terms/refresh` | Term-Status-Update anstoßen (offen → missed) |

### Buchungen (Bookings)

| Method | Pfad | Beschreibung |
|---|---|---|
| `POST` | `/savings/boxes/{box_id}/bookings` | Einzahlung / manuelle Buchung erfassen |
| `GET` | `/savings/boxes/{box_id}/bookings` | Alle Buchungen eines Sparfachs |
| `PATCH` | `/savings/boxes/{box_id}/bookings/{booking_id}` | Buchung korrigieren (Betrag, Datum, Notiz) |
| `DELETE` | `/savings/boxes/{box_id}/bookings/{booking_id}` | Buchung löschen |

### Hinweise zu den Endpunkten

- `POST /boxes` löst automatisch `generate_terms()` aus
- `POST /bookings` mit `savings_term_id` setzt den zugehörigen Term auf `fulfilled`
- `PATCH /bookings/{id}` erlaubt Korrekturen von Betrag, Datum und Notiz — `booking_type` und `savings_term_id` sind unveränderlich (sonst würden Term-Status-Übergänge inkonsistent)
- `DELETE /bookings/{id}` für `penalty`-Buchungen: nur erlaubt wenn eine `deposit`-Buchung für denselben Term existiert — HTTP 409 sonst
- `DELETE /bookings/{id}` für `deposit`-Buchungen: wenn Term danach keine gültige Einzahlung mehr hat → Term zurück auf `missed`, Penalty-Buchung wird neu angelegt falls konfiguriert
- `POST /terms/refresh` wird vom Frontend beim Öffnen eines Sparfachs aufgerufen (kein Scheduler nötig im MVP)
- Kein separater Delete-Endpunkt für Sparfächer im MVP — stattdessen `close`

---

## 8. Implementierungs-Reihenfolge

Nach CLAUDE.md Abschnitt 6 ("Reihenfolge beim Aufbau"):

| Schritt | Was | Datei(en) |
|---|---|---|
| 1 | Alembic-Migration: 3 neue Tabellen + 4 neue Enums | `alembic/versions/xxxx_add_savings_box.py` |
| 2 | SQLAlchemy-Modelle | `models/savings_box.py` |
| 3 | Pydantic-Schemas | `schemas/savings_box.py` |
| 4 | Service: `constants.py` + `types.py` | `services/savings/` |
| 5 | Service: `terms.py` (generate + refresh) | `services/savings/` |
| 6 | Service: `access.py` + `readers.py` | `services/savings/` |
| 7 | Service: `mutations.py` + `lifecycle.py` | `services/savings/` |
| 8 | Service: `__init__.py` (öffentliche API) | `services/savings/` |
| 9 | Router | `routers/savings.py` + in `main.py` registrieren |
| 10 | Frontend: Types + API-Client | `frontend/src/types/`, `frontend/src/api/` |
| 11 | Frontend: Dashboard-Seite | `frontend/src/pages/` |
| 12 | Frontend: Detailseite + Formulare | `frontend/src/pages/`, `frontend/src/components/` |

---

## 9. Offene Entscheidungen (vor Implementierung klären)

| # | Frage | Optionen | Empfehlung |
|---|---|---|---|
| ~~D-01~~ | ~~Terme bei Anlage generieren: bis end_date oder nur N Stück?~~ | — | ✅ **Gelöst:** Sparfächer haben immer ein festes Enddatum. Alle Terme werden einmalig beim Anlegen von `start_date` bis `end_date` generiert — kein Nachgenerieren, kein Hintergrundprozess. `end_date` ist Pflichtfeld. |
| ~~D-02~~ | ~~Was passiert wenn `amount_per_term` geändert wird?~~ | — | ✅ **Gelöst:** `SavingsTerm.expected_amount` friert den Mindestbetrag zum Zeitpunkt der Generierung ein. Jeder Termin ist historisch korrekt, unabhängig von späteren Box-Änderungen. |
| ~~D-03~~ | ~~Kann ein abgeschlossenes Sparfach wieder geöffnet werden?~~ | — | ✅ **Gelöst:** Option C — Zwei-Schritt-Bestätigung im Frontend (verhindert Versehen) + Reopen als Sicherheitsnetz. Reopen setzt `closing_actual_amount`, `closing_expected_amount`, `closed_at`, `closing_note` vollständig zurück und setzt `status` → `active`. Nutzer sieht Warnung: "Dein Abschlussbericht wird gelöscht." Kein halb-gültiger Bericht möglich. |
| ~~D-04~~ | ~~Strafgebühr im Closing: zählt sie zum erwarteten Betrag oder ist sie extra?~~ | — | ✅ **Gelöst:** `closing_expected_amount = Σ deposits − Σ penalties`. Der Wirt zahlt dir deinen Sparbetrag minus aufgelaufene Strafen. Die Differenz zu `closing_actual_amount` zeigt ob er sich verrechnet hat. |

---

## 10. Frontend-Skizze (grob)

```
/savings-box
  → Dashboard: Kacheln aller Sparfächer
    ┌─────────────────────────────────┐
    │ 🍺 Kneipe Zum Adler             │
    │ Nächster Termin: 01.06.2026     │
    │ ████████░░░░  €87 / €400        │
    │ 2 offen · 1 verpasst            │
    └─────────────────────────────────┘

/savings-box/new
  → Formular: Sparfach anlegen

/savings-box/:id
  → Detailseite mit 3 Tabs:

  [ Übersicht ] [ Buchungen ] [ Einstellungen ]

  TAB: Übersicht
  ├── Progress-Bereich (adaptiv je nach gesetztem Ziel):
  │     • kein Ziel gesetzt    → nur Istzustand ("€87 eingezahlt")
  │     • target_amount        → Balken: €87 / €400
  │     • personal_per_term    → je Termin: €20 geplant, €25 gezahlt ✅
  └── Termine-Liste (gruppiert nach Status — Option B):
        ▼ Offen (1)
          01.06.2026   offen          [Einzahlen]
        ▼ Verpasst (1)
          01.05.2026   ❌ verpasst   [Einzahlen]  Strafe €2
        ▼ Erledigt (3)               [ausklappen]

  TAB: Buchungen
  └── Alle Buchungen chronologisch (Betrag, Datum, Typ, Notiz)
        Aktionen: Bearbeiten / Löschen

  TAB: Einstellungen
  └── Box bearbeiten (Name, Ort, Ziel)
      Sparfach abschließen
      Sparfach wieder öffnen
```

---

## Änderungshistorie

| Datum | Änderung |
|---|---|
| 2026-05-08 | Initiales Planungsdokument erstellt |
| 2026-05-09 | API: PATCH für Bookings ergänzt (S-03 Konsistenz) |
| 2026-05-09 | Closing: closed_at, closing_expected_amount (Snapshot) + Immutability-Regel (HTTP 409) |
| 2026-05-09 | Modell: amount_per_term → min_amount_per_term (Wirt-Minimum, starr); personal_amount_per_term + target_amount als optionale Nutzerziele (Typ A/B) |
| 2026-05-09 | SavingsTerm: expected_amount ergänzt (Snapshot bei Generierung); Term-Status-Logik + Frontend-Validierung definiert; D-02 geschlossen |
| 2026-05-09 | end_date → Pflichtfeld; D-01 geschlossen: alle Terme einmalig bei Anlage generiert |
| 2026-05-09 | D-03 geschlossen: Reopen + Zwei-Schritt-Close; POST /reopen Endpunkt + reopen_savings_box() ergänzt |
| 2026-05-09 | D-04 geschlossen: closing_expected_amount = Σ deposits − Σ penalties |
| 2026-05-09 | Penalty-Flow: auto-Buchung bei missed (idempotent), Lösch-Regel (nur mit Deposit), Deposit-Lösch-Kaskade dokumentiert |
| 2026-05-09 | Scope: Soft-Modus gestrichen, Auto-Penalty ist Teil von v0.2.6; Immutability auf alle Schreibops erweitert; Frontend-Routen auf /savings-box korrigiert |
| 2026-05-09 | Deposit-Regel: mehrere Deposits pro Term erlaubt; jede Buchung muss individuell >= expected_amount sein (HTTP 422); Term fulfilled ab erster gültiger Buchung |
| 2026-05-09 | Frontend: Dashboard mit Kacheln, Detailseite mit 3 Tabs (Übersicht / Buchungen / Einstellungen), Termine-Liste gruppiert nach Status (Option B) |
