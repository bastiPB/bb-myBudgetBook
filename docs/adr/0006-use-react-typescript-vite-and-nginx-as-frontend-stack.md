# ADR 0006: React + TypeScript + Vite und nginx als Frontend-Stack

## Status
Accepted

## Kontext

Das Backend ist eine reine JSON-API (FastAPI, Cookie-Auth).
Ein Frontend muss diese API konsumieren und folgende Anforderungen erfüllen:

- Login / Logout mit Cookie-Session
- Admin-Bereich (User freigeben, Rollen verwalten)
- Abo-Verwaltung (CRUD + Übersicht)
- Selfhosted hinter nginx (kein externer CDN-Zwang)
- Ressourcenschonend auf der Client-Seite
- Langfristig wartbar, gut dokumentiert im Ökosystem

Da das Backend kein Server-Side Rendering anbietet (keine Jinja2-Templates),
scheidet ein HTMX/SSR-Ansatz aus — der API-Contract würde dafür grundlegend umgebaut werden müssen.

## Entscheidung

**React 18 + TypeScript + Vite** als SPA-Framework.
**nginx** serviert den statischen Build (`dist/`) und proxied API-Requests an das Backend.

## Herleitung

### Warum SPA (Single Page Application)?

Das Backend ist bewusst als JSON-API gebaut (ADR 0004).
Eine SPA konsumiert diese API direkt — keine Kopplung zwischen Darstellung und Datenschicht.
Routing, State und Rendering liegen vollständig im Browser.

### Warum React?

| Kriterium | React | Vue 3 | Alpine.js |
|---|---|---|---|
| Ökosystem | Größtes JS-Ökosystem | Sehr gut | Minimal |
| TypeScript | Erstklassig (native) | Gut | Eingeschränkt |
| Verbreitung | Industrie-Standard | Verbreitet | Nischenbereich |
| Lernkurve | Mittel (Hooks, JSX) | Etwas flacher | Sehr flach |
| Skalierbarkeit | Sehr hoch | Hoch | Niedrig |

React + TypeScript ist der De-facto-Standard für neue Projekte.
Wissen ist übertragbar, Community-Ressourcen sind abundant.

Vue 3 wäre technisch gleichwertig, hat aber ein kleineres Ökosystem und
weniger TypeScript-Reife in der Toolchain-Integration.

Alpine.js ist für eine App dieser Komplexität (Auth, Admin-Panel, CRUD-Views)
nicht geeignet — es fehlt an Komponentenstruktur und State-Management.

### Warum TypeScript?

- Typsicherheit verhindert eine ganze Klasse von Laufzeitfehlern
- API-Response-Typen können direkt aus dem Backend-Schema abgeleitet werden
- Refactoring ist sicher (IDE-Unterstützung, Compiler als Frühwarnsystem)
- Standard in React-Projekten ab mittlerer Komplexität

### Warum Vite?

- Schnellster Dev-Server der aktuellen Generation (ESM-native, kein webpack-Bundle nötig)
- Optimierter Produktions-Build via Rollup (Tree-Shaking, Code-Splitting)
- Erstklassige React + TypeScript Templates (`npm create vite`)
- Gitea selbst ist kürzlich von webpack auf Vite migriert (Referenz: go-gitea/gitea)

### Warum nginx?

- Serviert statische Dateien (`dist/`) hochperformant
- Proxy-Konfiguration: `/api/*` → Backend-Container (`backend:8000`)
- Cookie-Auth funktioniert cross-origin transparent über nginx als Reverse Proxy
- Bewährt, selbst-hostbar, passt in das bestehende Docker-Compose-Setup
- Kein separater Node.js-Prozess zur Laufzeit nötig — nach dem Build ist das Frontend pure HTML/CSS/JS

### Build- und Laufzeitstrategie (entscheidend)

- **Entwicklung (lokal):** `npm run dev` (Vite mit HMR), **kein** `npm run build` nach jeder Dateiänderung.
- **Produktion/Container:** `npm run build` läuft im **Dockerfile** (Build-Phase), nicht im Laufzeit-Container.
- **Runtime:** nginx startet nur und serviert statische Dateien aus `dist/`.

Damit gilt:

- Initialer Build: beim ersten `docker compose up --build`
- Neuer Build nach Frontend-Änderungen: erneut `docker compose up --build` (oder CI-Build)
- Kein Auto-Build-on-change im Produktionscontainer

Warum nicht `entrypoint.sh`?

- Ein Entry-Point ist Laufzeitlogik (Start des Prozesses), nicht Build-Logik.
- Builds im Entry-Point verlangsamen Starts, machen Deployments unvorhersehbar und benötigen unnötig Node.js im Runtime-Image.
- Best Practice ist ein Multi-Stage-Dockerfile: Node-Builder erzeugt `dist/`, nginx-Image enthält nur Build-Artefakte.

## Alternativen

### HTMX + Jinja2 (SSR)
- Würde Backend-Architektur grundlegend ändern (ADR 0004 konterkarieren)
- Backend würde HTML rendern statt JSON liefern — Verlust der klaren Layer-Trennung
- **Verworfen**: zu hoher Umbauaufwand, falscher Ansatz für eine JSON-API

### Vue 3 + Vite
- Technisch gleichwertig zu React
- Kleineres Ökosystem, weniger TypeScript-Reife
- **Verworfen**: React bietet bessere Langzeit-Investition für das Lernprojekt

### Alpine.js + vanilla HTML
- Kein Build-Schritt nötig
- Nicht geeignet für mehrere Ansichten mit Auth-State und Admin-Panel
- **Verworfen**: zu eingeschränkt für die geplante Komplexität

## Konsequenzen

**Positiv:**
- Klare Trennung: Backend = JSON-API, Frontend = SPA
- TypeScript auf beiden Seiten (Backend: Pydantic-Schemas → Frontend: abgeleitete Typen)
- Docker-Compose-Erweiterung: neuer `frontend`-Service (Multi-Stage Build: Node → nginx)
- nginx übernimmt API-Proxying → kein CORS-Problem, Cookie-Domain stimmt überein
- Schlankes Runtime-Image ohne Node.js, dadurch kleinere Angriffsfläche

**Negativ / Risiken:**
- Build-Schritt erforderlich (Node.js im CI/CD)
- JavaScript-Ökosystem ändert sich schnell — Abhängigkeiten müssen gepflegt werden
- Für sehr kleine Features ist React-Overhead spürbar (Hooks-Konzept, JSX)

**Offene Punkte:**
- State-Management: für MVP reicht `useState` / React Context; bei Bedarf Zustand oder TanStack Query
- Routing: React Router v6
- UI-Komponenten: bewusst offen gelassen (Tailwind CSS + headless, oder MUI, oder shadcn/ui)
