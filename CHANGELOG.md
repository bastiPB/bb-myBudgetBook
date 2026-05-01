# Changelog

All notable changes to this project will be documented in this file.
Format based on Keep a Changelog.

## [Unreleased]

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

## [0.1.0] - 2026-XX-XX
