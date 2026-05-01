---
doc: v020-module-system
version: 0.2.0
status: implementiert ✅
---

# v0.2.0 — Modul-System Spezifikation

## 1) Warum Module?

BB-myBudgetBook soll kein starres Produkt werden — es soll sich an den Bedarf des Nutzers anpassen.
Nicht jeder will Abos tracken. Nicht jeder braucht eine Urlaubskasse.

Mit einem **zweistufigen Modul-System** kann:
- der **Admin** entscheiden, welche Module im System überhaupt verfügbar sind
- jeder **User** aus den freigegebenen Modulen auswählen, was er in seinem Bereich sehen will

Zwei weitere Vorteile:
- Jedes Modul wird isoliert entwickelt — ein halbfertiges Modul stört andere nicht
- Neue Module können später einfach hinzugefügt werden, ohne die App-Architektur anzufassen

---

## 2) Kernkonzept: Zwei Stufen

```
Stufe 1 — Admin (System Settings unter /settings)
  "Welche Module sind im System generell verfügbar?"
  Beispiel: Sparfach JA, Haushaltsbuch NEIN (noch nicht freigegeben)

           ↓  Nur freigegebene Module erscheinen in Stufe 2

Stufe 2 — User (Profile Settings unter /profile/settings)
  "Von den verfügbaren Modulen — welche will ICH nutzen?"
  Beispiel: Sparfach JA, Urlaubskasse NEIN (brauche ich nicht)
```

**Was der User sieht = Admin hat es freigegeben UND User hat es aktiviert.**

Der Admin ist ebenfalls ein normaler User — er hat genauso seine eigenen Profile Settings
und entscheidet selbst, welche Module er in seinem Dashboard sehen möchte.
Seine Systemverwaltung (`/settings`) ist davon vollständig getrennt.

### Onboarding-Flow für neue User

Ein neuer User hat anfangs keine Module gewählt. Statt eines leeren Dashboards sieht er:

```
┌──────────────────────────────────────────────────────┐
│  Hallo Sparfuchs! 👋                                 │
│                                                      │
│  Dein Dashboard ist noch leer.                       │
│  Wähle deine Module und richte dein Dashboard ein.   │
│                                                      │
│  [Jetzt loslegen →]  (Link zu /profile/settings)    │
└──────────────────────────────────────────────────────┘
```

Sobald mindestens ein Modul aktiviert ist, verschwindet die Onboarding-Card und
das Dashboard zeigt die Inhalte der aktiven Module.

---

## 3) Datenbank-Design

### Tabelle 1: `app_settings` (systemweit, Admin-Hoheit)

Eine einzige Zeile — globale Einstellungen für die gesamte App-Instanz.

```
app_settings
├── id                    UUID (Primärschlüssel)
├── email_signup_enabled  BOOLEAN  — default: true
│                                    false = /register gesperrt, nur Admin kann User anlegen
├── modules               JSONB    — default: {"subscriptions": true}
│                                    Welche Module sind generell verfügbar?
├── created_at            TIMESTAMP
└── updated_at            TIMESTAMP
```

Beispielinhalt von `modules`:
```json
{
  "subscriptions":    true,
  "savings_box":      true,
  "vacation_fund":    false,
  "household_budget": false,
  "fund_savings":     false,
  "stock_portfolio":  false
}
```

---

### Tabelle 2: `user_settings` (pro User, User-Hoheit)

Eine Zeile pro User — persönliche Einstellungen und Modul-Auswahl.

```
user_settings
├── id            UUID (Primärschlüssel)
├── user_id       UUID FK → users.id (UNIQUE, CASCADE DELETE)
│                 Jeder User hat genau eine Zeile — lazy angelegt beim ersten Aufruf
│                 von GET oder PATCH /profile/settings (get_or_create-Pattern in services/profile.py)
│                 NICHT beim Login — der Login-Endpoint bleibt schlank
├── display_name  VARCHAR(100) nullable
│                 Anzeigename für das Dashboard ("Hallo Sparfuchs!")
│                 Wenn leer: Teil der E-Mail vor dem @ wird verwendet
├── avatar_url    VARCHAR(500) nullable
│                 Pfad zum Profilbild — Datei-Upload kommt in v0.2.x
│                 Für v0.2.0: Feld existiert bereits in der DB, Upload-Feature folgt
├── modules       JSONB  — default: {}
│                 Welche der vom Admin freigegebenen Module will dieser User nutzen?
│                 Leer = User hat noch nichts gewählt = Onboarding-Card zeigen
├── created_at    TIMESTAMP
└── updated_at    TIMESTAMP
```

Beispielinhalt von `modules` (User hat sich Sparfach aktiviert, Abo-Manager nicht):
```json
{
  "savings_box": true,
  "subscriptions": false
}
```

### Was ist JSONB?

JSONB ist ein PostgreSQL-Datentyp für flexible Schlüssel-Wert-Paare.
Warum JSONB statt einzelner Spalten? Weil jedes neue Modul sonst eine eigene Datenbank-Migration
bräuchte (`savings_box_enabled BOOLEAN`, `vacation_fund_enabled BOOLEAN`, …).
Mit JSONB hängen wir einfach einen neuen Key ans Objekt — keine neue Migration nötig.

### Alembic-Migrationen

**Migration `e5f6g7h8`:**
- Tabelle `app_settings` anlegen
- Standard-Zeile einfügen: `email_signup_enabled=true`, `modules={"subscriptions": true}`

**Migration `f6g7h8i9`:**
- Tabelle `user_settings` anlegen
- Kein Standard-Eintrag — Zeile wird lazy beim ersten Profil-Zugriff angelegt (get_or_create)

---

## 4) Backend API

### Übersicht aller neuen Endpunkte

| Methode | Pfad | Wer darf zugreifen | Zweck |
|---|---|---|---|
| GET | `/settings` | Jeder eingeloggte User | System-Einstellungen lesen (welche Module sind verfügbar?) |
| PATCH | `/settings` | Nur Admin | System-Einstellungen ändern |
| GET | `/profile/settings` | Jeder eingeloggte User | Eigenes Profil + Modul-Auswahl lesen |
| PATCH | `/profile/settings` | Jeder eingeloggte User | Eigenes Profil + Modul-Auswahl ändern |

---

### GET `/settings`

Gibt die systemweiten Einstellungen zurück.
Jeder eingeloggte User liest diese — das Frontend braucht sie um zu wissen, was der Admin freigegeben hat.

Antwort:
```json
{
  "email_signup_enabled": true,
  "modules": {
    "subscriptions":    true,
    "savings_box":      true,
    "vacation_fund":    false,
    "household_budget": false,
    "fund_savings":     false,
    "stock_portfolio":  false
  }
}
```

---

### PATCH `/settings`

Ändert systemweite Einstellungen. Nur Admin. Partielle Updates möglich.

Beispiel — Selbst-Registrierung deaktivieren:
```json
{ "email_signup_enabled": false }
```

Beispiel — Urlaubskasse freischalten:
```json
{ "modules": { "vacation_fund": true } }
```

Antwort: Die vollständig aktualisierten System-Einstellungen (gleiche Struktur wie GET).

---

### GET `/profile/settings`

Gibt das eigene Profil und die persönlichen Modul-Einstellungen zurück.
Wird beim App-Start geladen, direkt nach den System-Einstellungen.

Antwort:
```json
{
  "display_name": "Sparfuchs",
  "avatar_url": null,
  "modules": {
    "subscriptions": true,
    "savings_box": false
  }
}
```

---

### PATCH `/profile/settings`

Ändert das eigene Profil. Partielle Updates möglich — jeder User ändert nur seinen eigenen Eintrag.

Beispiel — Anzeigenamen setzen:
```json
{ "display_name": "Sparfuchs" }
```

Beispiel — Urlaubskasse für sich aktivieren (muss vom Admin freigegeben sein):
```json
{ "modules": { "vacation_fund": true } }
```

**Validierung im Backend:** Der User kann nur Module aktivieren, die der Admin in `app_settings.modules` freigegeben hat. Versucht ein User ein gesperrtes Modul zu aktivieren → HTTP 400.

---

### Neue Backend-Dateien

```
backend/app/
├── models/app_settings.py      — SQLAlchemy-Model: app_settings Tabelle
├── models/user_settings.py     — SQLAlchemy-Model: user_settings Tabelle
├── schemas/settings.py         — Pydantic-Schemas für System-Settings
├── schemas/profile.py          — Pydantic-Schemas für Profile-Settings
├── services/settings.py        — Logik: System-Settings lesen/schreiben
├── services/profile.py         — Logik: Profil lesen/schreiben, beim Login anlegen
├── routers/settings.py         — GET + PATCH /settings
└── routers/profile.py          — GET + PATCH /profile/settings
```

Beide Router werden in `main.py` eingebunden.

---

## 5) Frontend-Architektur

### 5.1 Der Typ: `ModuleDefinition`

Neue Datei `frontend/src/types/module.ts`:

```typescript
// Beschreibt ein einzelnes Modul — alles außer den Ein/Aus-Schaltern
interface ModuleDefinition {
  key: string;            // eindeutiger Name — muss mit DB-Key übereinstimmen
  label: string;          // Anzeigename, z.B. "Sparfach"
  description: string;    // kurze Beschreibung für die Settings-Seite
  route: string;          // URL-Pfad, z.B. "/savings-box"
  navLabel: string;       // Text im Navigationsmenü
}
```

### 5.2 Das Module-Registry-Array

Neue Datei `frontend/src/modules/registry.ts`:

```typescript
// MODULE_REGISTRY listet ALLE Module die im Code existieren.
// Der Admin entscheidet was verfügbar ist.
// Der User entscheidet was er davon sehen will.
// Neues Modul hinzufügen = einfach neues Objekt ans Array hängen.
const MODULE_REGISTRY: ModuleDefinition[] = [
  {
    key:         "subscriptions",
    label:       "Abo-Manager",
    description: "Verwalte wiederkehrende Abonnements (Netflix, Prime, …)",
    route:       "/subscriptions",
    navLabel:    "Abonnements",
  },
  {
    key:         "savings_box",
    label:       "Sparfach",
    description: "Traditionelles Sparfach — digitales Sparschwein",
    route:       "/savings-box",
    navLabel:    "Sparfach",
  },
  {
    key:         "vacation_fund",
    label:       "Urlaubskasse",
    description: "Plane und verfolge deinen Urlaubs-Sparplan",
    route:       "/vacation-fund",
    navLabel:    "Urlaubskasse",
  },
  {
    key:         "household_budget",
    label:       "Haushaltsbuch",
    description: "Monatsbudget, Ausgaben, Partneraufteilung",
    route:       "/household",
    navLabel:    "Haushaltsbuch",
  },
  {
    key:         "fund_savings",
    label:       "Fondsparen",
    description: "Langfristiges Sparen für Enkelkind, Patenkind oder andere",
    route:       "/fund-savings",
    navLabel:    "Fondsparen",
  },
  {
    key:         "stock_portfolio",
    label:       "Aktiendepot",
    description: "Manuelles Tracking eines Depots ohne Online-Zugang",
    route:       "/portfolio",
    navLabel:    "Aktiendepot",
  },
]
```

### 5.3 Der Modules-Context (mit Zwei-Stufen-Logik)

**Wichtig — Drei-Datei-Split** (react-refresh-Regel, siehe ADR 0006):
- `frontend/src/context/ModulesContext.ts` — Context-Objekt + `ModulesContextType`
- `frontend/src/context/ModulesProvider.tsx` — Provider-Komponente (einziger Default-Export)
- `frontend/src/context/useModules.ts` — `useModules`-Hook

Beschreibung des Providers (`ModulesProvider.tsx`):

```
Beim App-Start lädt der Context zwei Dinge parallel:
  1. GET /settings        → system_modules  (was hat Admin freigegeben?)
  2. GET /profile/settings → user_modules   (was will der User davon sehen?)

activeModules = MODULE_REGISTRY
  .filter(m => system_modules[m.key] === true)   // Stufe 1: Admin-Freigabe
  .filter(m => user_modules[m.key] === true)      // Stufe 2: User-Wunsch

Außerdem stellt der Context bereit:
  activeModules: ModuleDefinition[]    — Stufe 1 + 2 gefiltert — für Routing + Navigation
  availableModules: ModuleDefinition[] — nur Stufe 1 (Admin) — für Profile-Settings-Auswahl
  displayName: string | null          — Anzeigename aus user_settings, für Onboarding-Begrüßung
  hasChosenModules: boolean           — false = Onboarding-Card zeigen
  loading: boolean                    — true solange der initiale Fetch läuft
  reload(): void                      — neu laden nach Änderungen in Settings/ProfileSettings
                                         (z.B. Modul-Toggle → activeModules sofort aktualisieren)
```

**Was passiert wenn Admin ein Modul deaktiviert, das ein User aktiv hat?**
Das Modul verschwindet sofort aus der Navigation und den Routen des Users —
die User-Einstellung bleibt in der DB erhalten und kommt wieder wenn der Admin
das Modul erneut freigibt.

### 5.4 App.tsx — Dynamische Routen

Aus `activeModules` werden automatisch Routen und Navigations-Einträge generiert:

```typescript
// Nur aktive Module bekommen eine Route — inaktive Module sind über die URL nicht erreichbar
{activeModules.map(module => (
  <Route
    key={module.key}
    path={module.route}
    element={
      <ProtectedRoute>
        {/* Abo-Manager hat eine echte Seite, alle anderen sind Platzhalter (v0.2.0) */}
        {module.key === 'subscriptions'
          ? <SubscriptionsPage />
          : <PlaceholderPage moduleName={module.label} />
        }
      </ProtectedRoute>
    }
  />
))}
```

Navigation-Buttons auf dem Dashboard werden ebenfalls dynamisch aus `activeModules` generiert —
nur aktive Module erscheinen als Schaltfläche. Feste Buttons: "Mein Profil" (alle User),
"User verwalten" + "System-Einstellungen" (nur Admin).

Inaktive Module sind weder im Menü sichtbar noch über die URL erreichbar.

### 5.5 Neue Frontend-Dateien

```
frontend/src/
├── types/module.ts                   — ModuleDefinition Typ
├── modules/registry.ts               — MODULE_REGISTRY Array (alle 6 Module)
├── context/ModulesContext.ts          — Context-Objekt + ModulesContextType
├── context/ModulesProvider.tsx        — Provider-Komponente
├── context/useModules.ts              — useModules-Hook
├── api/settings.ts                   — fetchSystemSettings(), patchSystemSettings()
├── api/profile.ts                    — fetchProfileSettings(), patchProfileSettings()
└── pages/
    ├── SettingsPage.tsx              — Admin: System-Module freischalten
    ├── ProfileSettingsPage.tsx       — User: Eigene Module + display_name wählen
    ├── PlaceholderPage.tsx           — Wiederverwendbar: "Dieses Modul ist in Entwicklung"
    └── NotFoundPage.tsx              — 404-Seite für unbekannte URLs (siehe Abschnitt 12)
```

---

## 6) Admin Settings-Seite (`/settings`)

Geschützt durch `AdminRoute` — nur für Admins erreichbar.

**Abschnitt 1 — System-Module:**
- Liste aller Module aus MODULE_REGISTRY
- Pro Modul: Name, Beschreibung, Toggle (verfügbar / gesperrt)
- Toggle-Klick → sofort `PATCH /settings` → kein separater Speichern-Button

**Abschnitt 2 — Weitere System-Einstellungen:**
- Selbst-Registrierung: Toggle ein/aus
- (Spätere Einstellungen können hier ergänzt werden)

---

## 7) Profile Settings-Seite (`/profile/settings`)

Für alle eingeloggten User erreichbar — jeder sieht nur seine eigenen Daten.

**Abschnitt 1 — Persönliches Profil:**
- Anzeigename (`display_name`) — Textfeld, optional
  - Hinweis: "Wird als Begrüßung auf deinem Dashboard verwendet"
  - Wenn leer: E-Mail-Adresse (Teil vor @) wird verwendet
- Profilbild (`avatar_url`) — in v0.2.0 als Platzhalter, Upload folgt in v0.2.x

**Abschnitt 2 — Meine Module:**
- Liste aller Module die der Admin freigegeben hat
- Pro Modul: Name, Beschreibung, Toggle (aktiv / inaktiv für mich)
- Module die der Admin gesperrt hat, erscheinen hier nicht
- Toggle-Klick → sofort `PATCH /profile/settings`

---

## 8) Dashboard Onboarding-Card

Das Dashboard prüft beim Laden: hat der User mindestens ein Modul aktiviert?

**`hasChosenModules === false` → Onboarding-Card:**
```
┌──────────────────────────────────────────────────────┐
│  Hallo [display_name]! 👋                            │
│                                                      │
│  Dein Dashboard ist noch leer.                       │
│  Wähle deine Module und richte dein Dashboard ein.   │
│                                                      │
│  [Jetzt loslegen →]                                  │
└──────────────────────────────────────────────────────┘
```

**`hasChosenModules === true` → normales Dashboard** mit Inhalten der aktiven Module.

Die Onboarding-Card verschwindet automatisch sobald der User das erste Modul aktiviert und
zur Dashboard-Seite zurückkehrt.

---

## 9) Implementierungs-Plan (Reihenfolge)

### Schritt 1 — Datenbank: app_settings

Was entsteht:
- `backend/app/models/app_settings.py`
- Migration `e5f6g7h8_add_app_settings.py`

Was die Migration macht:
- Tabelle `app_settings` anlegen
- Standard-Zeile einfügen: `email_signup_enabled=true`, `modules={"subscriptions": true}`

Testbar: App startet, Tabelle existiert in DB.

---

### Schritt 2 — Datenbank: user_settings

Was entsteht:
- `backend/app/models/user_settings.py`
- Migration `f6g7h8i9_add_user_settings.py`

Was die Migration macht:
- Tabelle `user_settings` anlegen (kein Standard-Eintrag — wird lazy beim ersten Profil-Zugriff angelegt, siehe Schritt 4)

Testbar: Tabelle existiert in DB.

---

### Schritt 3 — Backend: System-Settings API

Was entsteht:
- `backend/app/schemas/settings.py`
- `backend/app/services/settings.py`
- `backend/app/routers/settings.py`
- Eintrag in `main.py`

Testbar:
- `GET /settings` gibt Standard-Einstellungen zurück
- `PATCH /settings` mit Admin-Cookie ändert Module → HTTP 200
- `PATCH /settings` ohne Admin-Cookie → HTTP 403

---

### Schritt 4 — Backend: Profile API

Was entsteht:
- `backend/app/schemas/profile.py`
- `backend/app/services/profile.py`
- `backend/app/routers/profile.py`
- Eintrag in `main.py`

**Wichtig — `user_settings` Initialisierung:**
Die Zeile für einen neuen User wird in `services/profile.py` in einer Hilfsfunktion
`get_or_create_user_settings(user_id, db)` angelegt. Diese Funktion wird aufgerufen
von `GET /profile/settings` und `PATCH /profile/settings` — nicht im Login-Endpoint.
Vorteil: der Login-Endpoint bleibt schlank; die Zeile entsteht lazy beim ersten Profil-Zugriff.

Testbar:
- Nach Login: `GET /profile/settings` gibt leere Module + null für display_name zurück
- `PATCH /profile/settings` mit `{"display_name": "Test"}` → gespeichert
- `PATCH /profile/settings` mit gesperrtem Modul → HTTP 400
- Jeder User sieht nur seine eigenen Daten

---

### Schritt 5 — Frontend: Module-Registry + Context

Was entsteht:
- `frontend/src/types/module.ts`
- `frontend/src/modules/registry.ts` (alle 6 Module)
- `frontend/src/context/ModulesContext.ts` — Context-Objekt + Typ
- `frontend/src/context/ModulesProvider.tsx` — Provider-Komponente
- `frontend/src/context/useModules.ts` — Hook
- `frontend/src/api/settings.ts`
- `frontend/src/api/profile.ts`
- `frontend/src/pages/PlaceholderPage.tsx`
- Änderung `frontend/src/App.tsx` — dynamische Routen
- Änderung `frontend/src/main.tsx` — ModulesProvider einbinden

Testbar:
- App startet ohne Fehler
- Abo-Manager erscheint in der Navigation (system aktiviert + user noch leer → Onboarding)

---

### Schritt 6 — Frontend: Dashboard Onboarding-Card

Was entsteht:
- Onboarding-Komponente in `DashboardPage.tsx`

Testbar:
- Neuer User sieht Onboarding-Card mit Begrüßung
- Link führt zu `/profile/settings`
- Nach Aktivierung eines Moduls: Card verschwindet

---

### Schritt 7 — Frontend: Admin Settings-Seite

Was entsteht:
- `frontend/src/pages/SettingsPage.tsx`
- Route `/settings` in `App.tsx` (Admin-geschützt)

Testbar:
- Admin sieht alle 6 Module mit Toggle
- Modul aktivieren → erscheint in Profile Settings anderer User
- Modul deaktivieren → verschwindet sofort überall

---

### Schritt 8 — Frontend: Profile Settings-Seite

Was entsteht:
- `frontend/src/pages/ProfileSettingsPage.tsx`
- Route `/profile/settings` in `App.tsx` (für alle eingeloggten User)

Testbar (vollständiger Funktionstest):
- User öffnet `/profile/settings` → sieht nur vom Admin freigegebene Module
- User aktiviert Modul → erscheint in seiner Navigation
- User deaktiviert Modul → verschwindet aus seiner Navigation
- display_name setzen → Begrüßung auf Dashboard aktualisiert sich
- Admin kann dieselbe Seite benutzen (für sein eigenes Profil)

---

## 10) Modul-Katalog

### Modul 1: Abo-Manager (`subscriptions`)
**Status in v0.2.0:** bereits vollständig implementiert, wird ins Modul-System integriert

Vorhanden: CRUD, Übersicht, monatliche Normierung, Intervalle (monatlich/vierteljährlich/jährlich/alle 2 Jahre)

Mittelfristig (v0.2.x):
- Icons für Abos
- Suspend: Abo pausieren ohne löschen
- Jahressumme + Gesamtsumme ("Du hast für Netflix bisher X € gezahlt")

Langfristig (Icebox):
- E-Mail-Ping: "Nutzt du dieses Abo noch?"
- CSV Reality Check: wurde das Abo wirklich abgebucht?

---

### Modul 2: Sparfach (`savings_box`)
**Status in v0.2.0:** Platzhalter-Seite ("In Entwicklung")

Geplant: Manuelle Einlagen, Verlauf, Sparfach-Nummer/Adresse
Mittelfristig: Gemeinsames Sparfach (mehrere User)

---

### Modul 3: Urlaubskasse (`vacation_fund`)
**Status in v0.2.0:** Platzhalter-Seite ("In Entwicklung")

Geplant: Ziel, Datum, Sparziel, Fortschrittsanzeige, manuelle Buchungen
Mittelfristig: Gemeinsam/Privat, Rückstand-Notifizierung
Langfristig: CSV Reality Check

---

### Modul 4: Haushaltsbuch (`household_budget`)
**Status in v0.2.0:** Platzhalter-Seite ("In Entwicklung")

Geplant: Monatsbudget, Partner-Einzahlungen, Ausgaben-Tracking, Restanzeige
Offen: Kontext-Modell (docs/13-rbac-vision.md) entscheidet Details

---

### Modul 5: Fondsparen (`fund_savings`)
**Status in v0.2.0:** Platzhalter-Seite ("In Entwicklung")

Geplant: Begünstigte Person, Sparplan, Zielwert, Fortschrittsanzeige

---

### Modul 6: Aktiendepot (`stock_portfolio`)
**Status in v0.2.0:** Platzhalter-Seite ("In Entwicklung")

Geplant: Depot-Name/Bank, Positionen (manuell), Gesamtwert, Gewinn/Verlust
Offen: Kurs-Aktualisierung manuell oder später optional per API?

---

## 11) Was NICHT in v0.2.0 rein kommt

| Feature | Warum verschoben |
|---|---|
| Profilbild Upload (Avatar) | Braucht Datei-Upload-Infrastruktur (Volume, Serving) — v0.2.x |
| Echte Implementierung der Module | Jedes Modul = eigenständiger Sprint nach v0.2.0 |
| Dashboard-Layout anpassen | Mittelfristig — erst Module füllen, dann Layout |
| E-Mail Benachrichtigungen | Eigenes Epic (docs/10-icebox.md EPIC 03) |
| CSV Import | Sehr komplex — eigenes Epic (docs/10-icebox.md EPIC 04) |
| Passwort ändern | Eigenständiges Feature, kein Bezug zum Modul-System |
| Kontext-Modell / Spaces | Eigenständiges Feature (docs/13-rbac-vision.md) |
| Backup/Restore Doku | Wird parallel abgehakt, kein Bezug zum Modul-System |

---

## 12) 404-Behandlung und Navigation

### Problem

Der ursprüngliche Catch-all `<Route path="*" element={<Navigate to="/login" />} />` hat
jeden unbekannten URL blind zum Login umgeleitet — auch für bereits eingeloggte User.
Das sieht aus wie ein Systemfehler (z.B. `/profile` statt `/profile/settings` → Login-Seite).

### Lösung: NotFoundPage

Neue Datei `frontend/src/pages/NotFoundPage.tsx` ersetzt den blindem Redirect:

```
Unbekannte URL → NotFoundPage ("404 — Seite nicht gefunden")
  ├── User eingeloggt   → Button "Zum Dashboard"
  └── User ausgeloggt   → Button "Zum Login"
```

Die `NotFoundPage` verwendet `useAuth()` um den Login-Status zu prüfen und zeigt den
passenden Button an. So sieht der User immer einen klaren Hinweis statt einer
verwirrenden Weiterleitung.

### Dashboard-Navigation

Die Schaltflächen auf dem Dashboard sind dynamisch — sie werden aus `activeModules` generiert.
Nur Module die für diesen User aktiv sind, erscheinen als Button.

Fest verdrahtete Buttons (immer sichtbar):
- **Mein Profil** → `/profile/settings` — für alle eingeloggten User
- **User verwalten** → `/admin` — nur Admin
- **System-Einstellungen** → `/settings` — nur Admin

---

## 13) Verknüpfte Dokumente

- `docs/05-roadmap.md` — Gesamtroadmap
- `docs/09-architecture-overview.md` — Architekturregeln (vertikale Slices)
- `docs/10-icebox.md` — Langfristige Erweiterungen (E-Mail, CSV, gemeinsame Bereiche)
- `docs/13-rbac-vision.md` — RBAC / Kontext-Modell (separat von Modulen)
