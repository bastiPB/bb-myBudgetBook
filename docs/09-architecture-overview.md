---
doc: architecture-overview
status: living
---

# Architektur-Überblick (v0.1)

## 1) Ziele
- Selfhosted, out-of-the-box via docker-compose
- Multi-User möglich
- Security baseline: Argon2id, sichere Sessions, keine Secrets im Repo

## 2) High-level Diagramm (Text)
[Browser / SPA]
      |
      | HTTPS (TLS)
      v
[nginx]  ──── /api/* ────► [Backend: Python API]
                                  |
                                  | DB Connection
                                  v
                            [PostgreSQL]

nginx serviert den statischen React-Build (`dist/`) direkt
und proxied API-Calls an den Backend-Container.

## 3) Komponenten
### 3.1 Frontend (SPA)
- **Stack**: React 18 + TypeScript + Vite (→ ADR 0006)
- **Hosting**: nginx serviert den statischen `dist/`-Build
- UI für Login, Registrierung, Userverwaltung, Abos (CRUD), Übersicht
- Kommuniziert ausschließlich über die JSON-API des Backends
- Cookie-Auth: nginx und Backend teilen dieselbe Domain → kein CORS-Problem

```text
frontend/
├── src/
│   ├── main.tsx           # Entry Point
│   ├── App.tsx            # Root-Komponente, Routing
│   ├── pages/             # LoginPage, RegisterPage, DashboardPage, AdminPage, SubscriptionsPage
│   ├── components/        # ProtectedRoute, AdminRoute (Routen-Schutz)
│   ├── api/               # Fetch-Wrapper gegen das Backend (auth, admin, subscriptions)
│   └── types/             # TypeScript-Interfaces (UserRead, SubscriptionRead, …)
├── index.html
├── vite.config.ts
└── package.json
```

### 3.2 Backend (Python API)
- Auth (Passwort-Hashing: Argon2id)
- Session Handling (Cookies)
- Business Logik (Abos)
- Optional: App-Layer Verschlüsselung für sensible Felder (ADR 0002)
- RBAC + User Lifecycle (Rollen: `admin`, `editor`, `default`):
      - **Weg 1 — Selbst-Registrierung**: User registriert sich → Status `pending`, Rolle `default`
        → Admin gibt frei (Status → `active`) und weist Rolle zu
      - **Weg 2 — Admin legt User an**: Admin erstellt User direkt mit Passwort + Rolle
        → User ist sofort `active`, kein Freigabe-Schritt nötig
      - `default` nach Login: Wartebildschirm — kein Zugriff auf Finanzdaten (HTTP 403 auf `/subscriptions/*`)
      - `editor`: Finanzdaten lesen und bearbeiten, keine Benutzerverwaltung
      - `admin`: Vollzugriff — Finanzdaten + Benutzerverwaltung
      - Rollenverwaltung ist ausschließlich über Admin-Endpunkte erlaubt

Empfohlene Struktur:

```text
backend/
├── app/
│   ├── main.py            # Nur: App-Start, Middleware, Router registrieren
│   ├── config.py          # Settings aus .env
│   ├── database.py        # DB-Verbindung, Session
│   ├── dependencies.py    # Wiederverwendbare FastAPI-Abhängigkeiten
│   ├── exceptions.py      # Eigene Fehlerklassen + globale Error-Handler
│   ├── models/            # SQLAlchemy-Modelle
│   ├── schemas/           # Pydantic-Schemas für Request/Response
│   ├── routers/           # HTTP-Endpunkte
│   └── services/          # Business-Logik
├── alembic/               # DB-Migrations
├── tests/
└── pyproject.toml
```

Architekturregeln:
- Router wissen nichts über DB-Details
- Services wissen nichts über HTTP
- Modelle kennen keine Business-Logik

Neue Features sollen als eigener vertikaler Slice ergänzt werden, z.B. `models/budget.py`, `schemas/budget.py`, `routers/budget.py`, `services/budget.py`, ohne bestehende Kernstrukturen unnötig anzufassen.

Hinweis zur Erweiterbarkeit:
- Zusätzliche Rollen sind möglich und werden später explizit Domänenkontexten zugeordnet (z.B. Haushaltsbuch, Sparbuch).
- Feingranulare Berechtigungen werden schrittweise ergänzt, nicht ad hoc.

### 3.3 Datenbank (PostgreSQL)
- Persistenz für Users, Abos, etc.
- DB user mit least privilege (später konkretisieren)

## 4) Konfiguration & Secrets
- Secrets per env oder gemountete Datei
- .env.* nicht ins Repo (siehe .gitignore)

## 5) Doku-Navigation
- MVP: docs/01-mvp.md
- Ideas/Refinement: docs/02-ideas.md
- Security Baseline: docs/03-security-baseline.md
- Release Checklist: docs/04-release-readiness-checklist.md
- Threat Model: docs/08-threat-model.md
- ADRs: docs/adr/
