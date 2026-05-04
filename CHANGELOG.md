# Changelog

All notable changes to this project will be documented in this file.
Format based on Keep a Changelog.

## [Unreleased]

### Added
- Subscriptions v0.2.2 (Slice A/B, in progress): Lifecycle-Status fuer Abos (`active`, `suspended`, `canceled`)
- Subscriptions v0.2.2 (Slice A/B, in progress): Suspend-Endpoint mit optionalem `access_until`
- Subscriptions v0.2.2 (Slice A/B, in progress): neue Felder `started_on`, `notes`, `suspended_at`, `access_until`
- Subscriptions v0.2.2 (Slice A/B, in progress): Preis-Historie-Grundlage mit erster Testabdeckung (`test_subscriptions_v022.py`)
- Subscriptions v0.2.3 (Slice C, in progress): Detailansicht pro Abo mit `GET /subscriptions/{id}` als Datenbasis
- Subscriptions v0.2.3 (Slice C, in progress): Kostenkarten fuer monatlich, jaehrlich und kumuliert auf der Detailseite
- Subscriptions v0.2.3 (Slice D, in progress): Provider-Logo-Flow (Upload, Speicherung, Thumbnail in Tabelle, groessere Darstellung in Details)
- Subscriptions v0.2.3 (Slice D, in progress): Fallback-Icon wenn kein Logo hinterlegt ist

### Changed
- Subscriptions v0.2.2 (Slice B, in progress): Tabellen-UX mit Suche und Seitengroessen (25/50/100)
- Subscriptions v0.2.2 (Slice B, in progress): Betragseingabe akzeptiert Komma oder Punkt; Anzeige deutsch formatiert
- Subscriptions v0.2.3 (Slice C, in progress): Notizen und Lifecycle-Aktionen werden aus der Tabellenansicht in die Detailansicht erweitert

### Fixed
- Subscriptions v0.2.2: Resume-Flow ergaenzt (`POST /subscriptions/{id}/resume`) und `Fortsetzen`-Aktion in der Tabellenansicht fuer pausierte Abos hinzugefuegt

### Known Gaps
- Keine offenen Gaps fuer Resume in Slice B; weitere Lifecycle-Feinheiten folgen in Slice C/D
- Preis-Historie-API und History-UI bleiben bewusst fuer Slice E (nach C/D)

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
