# Contributing

Danke, dass du helfen möchtest!

## Erst lesen
- MVP Scope: docs/01-mvp.md
- Roadmap: docs/05-roadmap.md
- Security baseline: docs/03-security-baseline.md

## Wie beitragen?
- Bug? -> Bug Report Issue
- Feature? -> Feature Request Issue (mit MVP Fit & Akzeptanzkriterien)
- PRs sind willkommen – bitte PR Template nutzen.

## Arbeitsablauf
1. Issue anlegen oder ein bestehendes Issue übernehmen
2. Labels für Typ, Ziel und Status setzen
3. Branch von `main` erstellen
4. Lokal prüfen
5. Pull Request gegen `main` öffnen
6. Erst mergen, wenn CI erfolgreich ist

Empfohlene Branch-Namen:
- `feature/<kurzname>`
- `fix/<kurzname>`
- `docs/<kurzname>`

Lokale Mindestprüfungen vor einem PR:
- Backend: `pytest`
- Frontend: `npm run lint` und `npm run build`

## Releases
- Releases werden nur aus `main` vorbereitet
- Versionen werden als Tag im Format `vX.Y.Z` veröffentlicht
- Vor dem Tag muss `CHANGELOG.md` einen passenden Abschnitt `## [X.Y.Z]` enthalten
- Der GitHub Release wird anschließend automatisch per GitHub Actions erzeugt

## Grundregeln
- Keine Secrets posten (weder Issues noch PRs)
- Freundlicher Ton, konstruktives Feedback
