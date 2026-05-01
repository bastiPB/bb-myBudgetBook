# Finanztool (Selfhosted Haushaltsbuch) — MVP v0.1

Ein selfhosted, Open-Source Finanztool (Web-App), das lokal via Docker läuft.
Fokus: **Datenschutz**, **Sicherheit**, **Qualität** und **Lerneffekt**.

## Warum?
- Du willst Einnahmen/Ausgaben & Abos überblicken, ohne Cloud-Abhängigkeit.
- Daten bleiben beim Nutzer: selfhosted, keine monatlichen Kosten.

## MVP (v0.1)
Siehe: docs/01-mvp.md

Highlights:
- Login (Passwort-Hashing: Argon2id)
- Userverwaltung
- Abos manuell verwalten (CRUD)
- Übersicht: monatliche Kosten + Laufzeiten/nächste Fälligkeiten
- Backend (Python API) + Postgres + SPA-Frontend

## Projektstatus
- Status: **Design & Dokumentation**
- Roadmap: docs/05-roadmap.md
- Release-Gate: docs/04-release-readiness-checklist.md

## Arbeitsworkflow

Für neue Arbeit gilt der Standardablauf:

1. Idee / Bug als GitHub Issue anlegen oder vorhandenes Issue triagieren
2. Labels setzen (`type:*`, `target:*`, `status:*`)
3. Kleinen Feature- oder Fix-Branch von `main` erstellen
4. Lokal entwickeln und prüfen
5. Pull Request gegen `main` öffnen
6. CI muss grün sein, dann mergen

Minimaler Branch-Standard:
- `feature/<kurzname>` für Features
- `fix/<kurzname>` für Fehlerbehebungen
- `docs/<kurzname>` für reine Doku-Änderungen

Die GitHub Actions CI läuft bei Push und Pull Request und prüft:
- Backend: `pytest`
- Frontend: `npm run lint` und `npm run build`

Damit ist `main` immer der stabile Integrationsstand.

Empfohlene Branch Protection für `main` in GitHub:
- Require a pull request before merging: **an**
- Require status checks to pass before merging: **an**
- Required checks: `Backend tests`, `Frontend lint and build`
- Require conversation resolution before merging: **an**
- Require linear history: **an**
- Allow force pushes: **aus**
- Allow deletions: **aus**

Hinweis für Solo-Projekte:
- Pflicht-Reviews können optional vorerst **aus** bleiben
- Sobald ein zweiter Maintainer aktiv mitarbeitet: mindestens **1 Approval** aktivieren

## Releases

Release-Standard:

1. Release-Kandidaten in `main` mergen
2. `CHANGELOG.md` um einen Abschnitt `## [X.Y.Z]` ergänzen
3. Git-Tag im Format `vX.Y.Z` erstellen
4. Tag pushen
5. GitHub Actions erstellt automatisch den Release und hängt Quellcode-Archive an

Beispiel:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Der Release-Workflow prüft vor dem Erstellen:
- Backend-Tests
- Frontend-Lint
- Frontend-Produktionsbuild
- passenden Eintrag in `CHANGELOG.md`

## Quickstart

### Voraussetzungen
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose

### Erstes Mal einrichten
```bash
git clone <repo-url>
cd BB-myBudgetBook
cp .env.example .env
# .env öffnen und Werte anpassen (Passwörter, Secret Key)
```

### Produktion (empfohlen)
Backend ist **nur über nginx** erreichbar — kein direkt exponierter Port.

Vor dem ersten Start: in der `.env` die Umgebung auf Produktion setzen:
```
ENVIRONMENT=production
```
> Ohne diesen Wert wird der Session-Cookie ohne `Secure`-Flag gesetzt — das ist
> nur für lokale Entwicklung (HTTP) gedacht, nicht für den Produktionsbetrieb.

```bash
docker compose up --build
```

App läuft unter: **http://localhost**

### Lokale Entwicklung
Backend-Port 8888 wird freigegeben, damit der Vite Dev Server den Proxy nutzen kann.

```bash
# Terminal 1 — DB + Backend (im Hintergrund)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build db backend

# Terminal 2 — Frontend mit Hot Reload
cd frontend && npm run dev
```

Frontend läuft unter: **http://localhost:5173**

---

### Befehlsübersicht

| Befehl | Was startet | Wann verwenden |
|---|---|---|
| `docker compose up --build` | DB + Backend (intern) + nginx/Frontend | Produktion — erstes Mal oder nach Codeänderung |
| `docker compose up` | DB + Backend (intern) + nginx/Frontend | Produktion — Neustart ohne Änderungen |
| `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build db backend` | DB + Backend (Port 8888 offen) | Entwicklung — erstes Mal oder nach Backend-Änderung |
| `docker compose -f docker-compose.yml -f docker-compose.dev.yml up db backend` | DB + Backend (Port 8888 offen) | Entwicklung — Neustart ohne Änderungen |
| `docker compose down` | — | Alle Container stoppen (Daten bleiben erhalten) |
| `docker compose down -v` | — | ⚠️ Alle Container + Datenbank-Daten löschen |

---

### Wann brauche ich `--build`?

`--build` weist Docker an, die Images **neu zu bauen** bevor die Container starten.
Ohne `--build` verwendet Docker das zuletzt gebaute Image — Codeänderungen werden dann **nicht** übernommen.

| Situation | `--build` nötig? |
|---|---|
| Erstes Mal (noch kein Image vorhanden) | **Ja** |
| Backend-Code geändert (`app/**`) | **Ja** |
| Python-Abhängigkeiten geändert (`pyproject.toml`) | **Ja** |
| Frontend-Code geändert (`src/**`) — nur Produktion | **Ja** |
| npm-Abhängigkeiten geändert (`package.json`) | **Ja** |
| `Dockerfile` oder `nginx.conf` geändert | **Ja** |
| Nur `.env`-Werte geändert (kein Code) | Nein — `docker compose up` reicht |
| Container neu starten ohne Änderungen | Nein — `docker compose up` reicht |

**Faustformel:** Im Zweifel immer `--build`. Dauert etwas länger, ist aber immer sicher.

## HTTPS — Pflicht für den Mehrbenutzerbetrieb

> **Wichtig:** Diese App verwendet einen `Secure`-Session-Cookie.
> Browser senden diesen Cookie **nur über HTTPS** — nicht über einfaches HTTP.
>
> Konsequenz: Wer die App von einem anderen Gerät (Handy, zweiter Rechner) aufruft,
> kann sich **nicht einloggen**, solange kein HTTPS eingerichtet ist.
> Der Login scheint zu klappen, aber jede weitere Seite zeigt eine 401-Fehlermeldung.

| Adresse | Protokoll | `ENVIRONMENT` | Funktioniert? |
|---|---|---|---|
| `localhost` / `127.0.0.1` | HTTP | egal | ✅ Browser-Ausnahme |
| Heimnetz (`192.168.x.x`) | HTTP | `development` | ✅ (aber kein HTTPS — nur für Vertrauensnetzwerke) |
| Heimnetz (`192.168.x.x`) | HTTP | `production` | ❌ Cookie blockiert → Login schlägt fehl |
| Heimnetz (`192.168.x.x`) | HTTPS | `production` | ✅ |
| Eigene Domain | HTTPS | `production` | ✅ |

**Ausnahme:** Auf demselben Rechner unter `http://localhost` oder `http://127.0.0.1`
funktioniert alles — Browser behandeln `localhost` als sicheren Kontext (auch ohne HTTPS).

### HTTPS einrichten — drei Wege

#### Option 1: Caddy (empfohlen für Einsteiger)
[Caddy](https://caddyserver.com/) holt sich automatisch ein kostenloses Let's Encrypt-Zertifikat
und übernimmt die HTTPS-Terminierung — ohne manuelle Zertifikatsverwaltung.
Voraussetzung: Die App ist unter einer öffentlich erreichbaren Domain erreichbar.

Einfaches Beispiel (`Caddyfile`):
```
deinedomain.de {
    reverse_proxy localhost:80
}
```

#### Option 2: Traefik
[Traefik](https://traefik.io/) ist ein leistungsfähiger Reverse Proxy, der sich gut in
Docker-Compose-Setups integriert und ebenfalls automatisch Let's Encrypt-Zertifikate verwaltet.
Etwas mehr Konfigurationsaufwand als Caddy, dafür sehr flexibel.

#### Option 3: Nur im lokalen Netz (kein HTTPS)
Wenn die App ausschließlich auf dem **selben Rechner** läuft und du nicht von anderen
Geräten darauf zugreifen willst, kannst du mit `ENVIRONMENT=development` arbeiten —
dann ist der Cookie ohne `Secure`-Flag gesetzt und funktioniert auch über HTTP.
⚠️ Nicht für den Mehrbenutzerbetrieb oder öffentlich erreichbare Server geeignet.

## Security
Bitte keine Sicherheitslücken als öffentliche Issues posten.
Siehe: SECURITY.md

## Contributing
Siehe: CONTRIBUTING.md

## Code of Conduct
Siehe: CODE_OF_CONDUCT.md

## Ideen & Roadmap
Ideenparkplatz: docs/02-ideas.md  
Roadmap: docs/05-roadmap.md

## License
AGPL-3.0 — see [LICENSE](LICENSE) for details.
