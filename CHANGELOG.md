# Changelog

All notable changes to this project will be documented in this file.
Format based on Keep a Changelog.

## [Unreleased]

### Added
- UI-Shell-Arbeit für v0.2.1 gestartet: Header, Sidebar und Footer als neue Layout-Bausteine
- Dashboard-Initialansicht als erster strukturierter Einstieg (inkl. Empty-State-Ziel)

### Docs
- Roadmap um v0.2.1-Mini-Release-Scope ergänzt
- Release-Checklist um v0.2.1-Addendum für UI-Shell ergänzt

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
