---
doc: project-setup
status: living
---

# Projekt-Setup & Arbeitsweise

Dieses Dokument beschreibt **wie** an dem Projekt gearbeitet wird – nicht **was** gebaut wird.

---

## 1) Repos & Struktur
- GitHub ist **Single Source of Truth**
- Alle relevanten Entscheidungen sind dokumentiert
- Keine externen Wikis oder Schatten-Dokus

Wichtige Ordner:
- docs/ → Produkt, Architektur, Security
- docs/adr/ → Architekturentscheidungen
- .github/ → Projekt-Governance (Issues, PRs)

Backend-Scaffold (geplante Startstruktur):
- backend/app/main.py → App-Start, Middleware, Router registrieren
- backend/app/config.py → Settings aus .env
- backend/app/database.py → DB-Verbindung, Session
- backend/app/dependencies.py → wiederverwendbare FastAPI-Abhängigkeiten
- backend/app/exceptions.py → Fehlerklassen und globale Handler
- backend/app/models/ → SQLAlchemy-Modelle
- backend/app/schemas/ → Pydantic-Request-/Response-Schemas
- backend/app/routers/ → HTTP-Endpunkte
- backend/app/services/ → Business-Logik
- backend/alembic/ → DB-Migrations
- backend/tests/ → Tests
- backend/pyproject.toml → Python-Projektkonfiguration

---

## 2) Ideen-Workflow
1. Idee entsteht → docs/02-ideas.md
2. Idee wird konkreter → GitHub Feature Issue
3. MVP-Fit prüfen (docs/01-mvp.md)
4. Entscheidung dokumentieren (ADR oder Issue-Kommentar)

---

## 3) Änderungen & Commits
- Kleine Commits
- Aussagekräftige Commit Messages
- Auch Doku-Änderungen über Commits (keine „stillen“ Änderungen)

Beispiel:
- docs: clarify MVP success criteria
- docs: add ADR for encryption approach

---

## 4) Pull Requests (auch Solo)
Auch im Solo-Projekt:
- PRs sind Review-Momente
- PR-Template nutzen
- Check gegen DoD & Release-Checklist
- PRs gehen immer gegen `main`
- Merge erst, wenn CI grün ist

Empfohlene Branch Protection für `main`:
- Pull Request vor Merge erzwingen
- Status Checks erzwingen: `Backend tests`, `Frontend lint and build`
- Conversation Resolution erzwingen
- Linear History erzwingen
- Force Pushes und Branch Deletion verbieten

Hinweis:
- In einem Solo-Projekt sind Pflicht-Reviews optional
- Sobald mehrere Maintainer aktiv arbeiten, sollte mindestens 1 Approval verpflichtend werden

Branching-Regel:
- `main` bleibt stabil und releasbar
- Arbeit passiert in kurzen Branches: `feature/*`, `fix/*`, `docs/*`
- Keine langen Parallel-Branches ohne aktiven Grund

---

## 5) Releases
- Releases erst, wenn Release-Checklist erfüllt ist
- Changelog wird gepflegt
- Keine „halbfertigen“ Releases

CI-Mindeststandard:
- Push/Pull Request prüft Backend-Tests (`pytest`)
- Push/Pull Request prüft Frontend-Lint + Produktionsbuild (`npm run lint`, `npm run build`)

Release-Standard:
- Releases werden über Git-Tags im Format `vX.Y.Z` ausgelöst
- Vor dem Tag muss `CHANGELOG.md` einen Abschnitt `## [X.Y.Z]` enthalten
- Der Release-Workflow erstellt automatisch einen GitHub Release mit Source-Archiven (`.zip`, `.tar.gz`)

Beispiel:
- `git tag v0.1.0`
- `git push origin v0.1.0`

---

## 6) Open Source Haltung
- Transparenz ja, Chaos nein
- Sicherheit verantwortungsvoll behandeln (SECURITY.md)
- Diskussionen sachlich & respektvoll (CODE_OF_CONDUCT.md)

---

## 7) Kontinuierliche Verbesserung
- Doku ist **lebendig**
- Struktur darf sich ändern
- Wenn etwas doppelt gepflegt werden muss → Strukturproblem beheben

---

## 8) Frontend Build-Workflow (React + TS + Vite + nginx)

Grundregel:
- `npm run dev` ist nur für lokale Entwicklung (Hot Reload)
- `npm run build` ist für Produktion/Release

Automatisierung:
- Der Produktions-Build läuft im **Frontend-Dockerfile** (Multi-Stage: Node buildet, nginx serviert)
- Der Build wird automatisch ausgeführt bei `docker compose up --build` oder im CI-Image-Build

Wichtig:
- Kein `npm run build` im `entrypoint.sh`
- Entry-Points starten Prozesse zur Laufzeit, sie sind nicht für Build-Schritte gedacht
- Nach Frontend-Codeänderungen muss für die Produktionsvariante ein neues Image gebaut werden

### React Fast Refresh — Eine Exportart pro Datei

ESLint-Regel `react-refresh/only-export-components` erzwingt: Eine `.tsx`-Datei die Komponenten
exportiert, darf **nur** Komponenten exportieren.

Falsch (alles in einer Datei):
```
AuthContext.tsx → Context + Typ + Provider-Komponente + Hook
```

Richtig (aufgeteilt):
- `AuthContext.ts` — Context-Objekt und Typ (kein JSX → `.ts`)
- `AuthProvider.tsx` — nur die Provider-Komponente
- `useAuth.ts` — nur der Hook (kein JSX → `.ts`)

Gilt für alle zukünftigen Context/Hook-Kombinationen.
