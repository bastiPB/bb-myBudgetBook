# Changelog

All notable changes to this project will be documented in this file.
Format based on Keep a Changelog.

## [Unreleased]

## [0.2.2] - 2026-05-04

### Added

**Slice A — Abo-Lifecycle**
- Lifecycle-Status für Abos: `active`, `suspended`, `canceled`
- Neue Felder: `started_on`, `notes`, `logo_url`, `suspended_at`, `access_until`
- `POST /subscriptions/{id}/suspend` mit optionalem `access_until`
- `POST /subscriptions/{id}/resume`

**Slice B — Listen-UX**
- Suche (Name-Filter), Seitengröße 25/50/100, clientseitige Paginierung
- Status-Badge in der Abo-Tabelle
- Betragsanzeige deutsch formatiert; Eingabe akzeptiert Komma oder Punkt

**Slice C — Detailseite**
- `GET /subscriptions/{id}` mit berechneten Kostenkennzahlen (`monthly_cost_normalized`, `yearly_cost_normalized`, `total_paid_estimate`)
- Detailseite: Kostenkarten, Stammdaten, Notizen mit Inline-Bearbeitung, Suspend/Resume-Aktionen

**Slice D — Logo-Upload**
- `POST /subscriptions/{id}/logo`: Upload von JPEG/PNG/WebP bis 2 MB
- StaticFiles-Mount für `/uploads` (ADR 0010: lokales Dateisystem, relativer Pfad in DB)
- Fallback-Icon (Anfangsbuchstabe) wenn kein Logo hinterlegt
- `uploads-data` Docker-Volume für persistente Logos über Container-Neustarts

**Slice E — Preishistorie**
- `GET /subscriptions/{id}/price-history`
- Preishistorie-Karte auf Detailseite (neuester Eintrag hervorgehoben)
- `total_paid_estimate` nutzt exakte Segment-Berechnung über Preishistorie statt Schätzung
- Erster Zahlungs-Fix: +1 für die Zahlung zum Abschluss-Datum (wird nicht durch reine Monatsdifferenz erfasst)

**Slice F — Buchungs-Scheduler**
- APScheduler (BackgroundScheduler) im FastAPI-Lifespan: täglich zur konfigurierten Uhrzeit
- Neue DB-Tabelle `subscription_scheduled_payments` (UNIQUE `subscription_id + due_date` als Idempotenz-Constraint)
- Neue DB-Tabelle `user_module_configurations` (JSONB-Einstellungen pro User, ADR 0007)
- Neues Feld `scheduler_time` in `app_settings` (Format `HH:MM`, default `03:00`)
- `POST /admin/subscriptions/trigger-payments`: manueller Scheduler-Aufruf (idempotent)
- `GET /profile/module-config` + `PATCH /profile/module-config`
- ProfileSettingsPage: Abschnitt „Abo-Einstellungen" mit Toggles für Buchungshistorie und kumulierte Kosten
- SettingsPage: Abschnitt „Buchungs-Scheduler" mit manueller Auslöse-Schaltfläche

**Slice G — Buchungshistorie auf Detailseite**
- `GET /subscriptions/{id}/scheduled-payments`
- Buchungshistorie-Tabelle auf der Abo-Detailseite (nur sichtbar wenn Einträge vorhanden)
- Status-Badges: Offen (gelb), Bezahlt (grün), Verpasst (rot)

### Fixed
- `subscription_price_history.updated_at` fehlte in der Slice-A-Migration → neue Migration `h8i9j0k1` ergänzt die Spalte mit `server_default=NOW()`
- `total_paid_estimate` zeigte 0,00 € wenn Abo-Start und heutiges Datum im selben Monat lagen
- Logos gingen nach Container-Neustart verloren → `uploads-data` Named Volume in `docker-compose.yml`
- GitHub Actions CI: `PermissionError: /uploads` beim App-Import → `mkdir` + `StaticFiles`-Mount in `try/except` gewrappt

### Database Migrations
- `g7h8i9j0` — v0.2.2 Slice A: `status`, `started_on`, `notes`, `logo_url`, `suspended_at`, `access_until` zu `subscriptions`; neue Tabelle `subscription_price_history`
- `h8i9j0k1` — Slice E Fix: `updated_at` zu `subscription_price_history` nachgetragen
- `i9j0k1l2` — Slice F: neue Tabellen `subscription_scheduled_payments` + `user_module_configurations`; Spalte `scheduler_time` in `app_settings`

### ADRs
- ADR 0010: Lokales Dateisystem für User-Uploads (relativer Pfad in DB, Migrationspfad zu Object Storage offen)

## [0.2.1] - 2026-05-03

### Added
- **AppLayout-Komponente** (`AppLayout.tsx` + `AppLayout.css`): wiederverwendbare UI-Shell für alle geschützten Seiten — Header, Sidebar, Footer
- **Header**: Logo (BB-SVG), App-Name als Link, Dark/Light-Mode-Toggle, User-Dropdown (Initialen, E-Mail, Einstellungen, Abmelden)
- **Dark/Light-Mode-Toggle**: Pill-förmiger Schiebeschalter mit Mond-/Sonne-SVG-Icon (Feather Icons), Zustand persistiert in `localStorage` (`bb-theme`)
- **Sidebar**: dynamische Navigation aus `activeModules`, Admin-Bereich (Trennlinie + Sektion-Label) nur für Nutzer mit Rolle `admin`
- **Footer**: Versionsnummer
- **CSS Design-System**: CSS Custom Properties (`--color-*`, `--header-height`, `--sidebar-width`) als zentrale Theme-Basis für Light und Dark Mode
- Alle geschützten Seiten auf neues Design-System umgestellt: `LoginPage`, `RegisterPage`, `AdminPage`, `SubscriptionsPage`, `SettingsPage`, `ProfileSettingsPage`, `DashboardPage`
- ADR 0009: CSS Custom Properties als neutrales Design-System (statt Tailwind / MUI / Inline-Styles)
- Design Guide (`docs/16-design-guide.md`): lebendige Referenz für CSS-Variablen, Klassen und Do/Don't-Regeln

### Changed
- `App.tsx`: `Layout`- und `AdminLayout`-Wrapper kombinieren `ProtectedRoute`/`AdminRoute` mit `AppLayout` — kein Code-Doppel
- `DashboardPage`: eigener Header und Logout-Button entfernt — Navigation läuft vollständig über `AppLayout`
- Alle Page-Komponenten: `useNavigate` + manuelle Dashboard-Buttons entfernt

### Fixed
- `SubscriptionsPage`: Spaltenbreiten-Verschiebung beim Aktivieren des Inline-Edit-Modus behoben (`table-layout: fixed` + explizite `th`-Breiten in %)

### Docs
- `docs/15-v021-ui-shell-and-dashboard-initial.md`: Status auf `released` gesetzt
- `docs/05-roadmap.md`: v0.2.1 als abgeschlossen markiert; Mobile-Responsiveness bewusst in v0.2.x verschoben
- `docs/04-release-readiness-checklist.md`: v0.2.1-Addendum aktualisiert

### Known Limitations
- **Mobile-Responsiveness**: bewusst auf v0.5.x verschoben — Fokus liegt auf Desktop

## [0.2.0] - 2026-05-01

### Added
- **Zwei-Stufen-Modul-Sichtbarkeit** (ADR 0007, ADR 0008): Admin gibt Module systemweit frei, User aktiviert sie individuell — nur beide aktiv = Route erreichbar
- `AppSettings`-Modell + Tabelle: systemweite Einstellungen (E-Mail-Registrierung, Modul-Freigaben als JSONB)
- `UserSettings`-Modell + Tabelle: persönliche Einstellungen pro User (Anzeigename, Avatar-URL, eigene Modul-Auswahl als JSONB)
- `GET/PATCH /settings`-Endpunkte (nur Admin): systemweite Modul-Freigabe und Registrierungs-Toggle
- `GET/PATCH /profile/settings`-Endpunkte (jeder eingeloggte User): Anzeigename, Avatar-URL, persönliche Modulauswahl
- `ModulesContext`, `ModulesProvider`, `useModules`-Hook: Frontend-State für aktive und verfügbare Module, inkl. Reload-Mechanismus
- `MODULE_REGISTRY` (frontend): zentrale Definition aller 6 Module mit Key, Label, Route und Nav-Label
- `SettingsPage`: Admin-Seite zum Freigeben/Sperren von Modulen und zum Verwalten der Registrierung
- `ProfileSettingsPage`: Nutzer-Seite für Anzeigenamen, Avatar-URL und persönliche Modulauswahl
- `DashboardPage`: Onboarding-Karte bei fehlenden Modulen, dynamische Navigations-Buttons zu aktiven Modulen
- `NotFoundPage`: smarte 404-Seite — leitet eingeloggte User zum Dashboard, ausgeloggte zum Login
- `PlaceholderPage`: Platzhalter für noch nicht implementierte Module (zeigt Modulnamen)
- Dynamische Routen in `App.tsx`: nur freigegebene + aktivierte Module sind als URL erreichbar
- Alembic-Migrationen für `app_settings` und `user_settings` (UUIDs werden in Python erzeugt, kein pgcrypto nötig)
- ADR 0007: JSONB für Modul-Konfiguration
- ADR 0008: Zwei-Stufen-Modul-Sichtbarkeitsmodell

### Changed
- `App.tsx`: Abonnement-Route ist jetzt dynamisch (aus `activeModules`), Root `/` leitet zu `/dashboard` weiter
- `main.py`: `/settings`- und `/profile/settings`-Router eingebunden

### Fixed
- Root-URL `/` landete nach Umbau auf `NotFoundPage` — `Navigate to="/dashboard"` wiederhergestellt
- Logout-Bestätigung wurde nicht angezeigt: `location.state` wurde durch `ProtectedRoute`'s `<Navigate replace />` überschrieben — Flag wird jetzt via `sessionStorage` übergeben (wird sofort nach dem ersten Lesen gelöscht)

## [0.1.0] - 2026-04-XX

### Added
- Projektstruktur und Dokumentations-Gerüst (docs/00–09, ADRs 0001–0006)
- Backend-Scaffold: FastAPI + SQLAlchemy + Alembic, Argon2id-Passwort-Hashing
- Cookie-basierte Session-Authentifizierung (itsdangerous)
- CRUD-Endpunkte für Abos mit Besitz-Prüfung und Intervall-Normalisierung
- User-Verwaltung mit Rollen (admin/editor/default) und Freigabe-Flow (pending → active)
- Frontend-Scaffold: React 19 + TypeScript + Vite + nginx (Multi-Stage Docker Build)
- SPA-Routing mit ProtectedRoute und AdminRoute
- Docker-Compose-Setup für Produktion und lokale Entwicklung (dev-Override)
- GitHub Actions CI: Backend-Tests (pytest) + Frontend-Lint und -Build
- Release-Workflow: automatischer GitHub Release bei `vX.Y.Z`-Tags

### Security
- Passwort-Hashing mit Argon2id (argon2-cffi), Rehash bei veralteten Parametern
- Session-Cookie mit Secure/HttpOnly-Flag, abhängig von ENVIRONMENT
- RBAC auf Backend-Ebene, unauthentifizierte Endpunkte sind nicht erreichbar
