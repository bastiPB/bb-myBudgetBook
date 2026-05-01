---
doc: project-charter
version: 0.1
status: living
---

# Project Charter — Finanztool (aka BB-MyBudgetBook)

## Vision
Ein einfaches, sicheres, selfhosted Finanztool, das Nutzern hilft, ihre Finanzen (insbesondere Abos) im Blick zu behalten — ohne Cloud, ohne Tracking, ohne Abo-Kosten.

## Zielgruppe
Privatpersonen, Paare, ggf. Familien. Open Source / Selfhosted.

## Prinzipien
- **Selfhosted first**: Out-of-the-box über docker-compose.
- **Security baseline**: Passwörter via Argon2id; Secrets niemals im Repo; sensible Daten nicht in Logs.
- **Migrationsgetriebene Datenbank**: Schema- und Datenmodelländerungen erfolgen ausschließlich über versionierte Alembic-Migrationen; manuelle DB-Anpassungen sind ausgeschlossen. Jedes Modell erbt ein gemeinsames Base-Model mit UUID sowie Zeitstempeln für Erstellung und Aktualisierung.
- **Klare Backend-Schichten statt Monolith**: Router, Services, Modelle, Schemas und Infrastruktur sind getrennt. HTTP-Logik, Business-Logik und Datenmodell werden nicht in einer einzelnen `main.py` vermischt.
- **Quality over speed**: lieber klein, stabil, verständlich.
- **MVP strikt halten**: nur die Features, die den Kernnutzen liefern.

## Non-Goals (bewusst nicht jetzt)
- Bank-Anbindung / Konto-Import
- Automatische Kategorisierung/Scoring
- Mobile App
- ""Alles für jeden"" — Fokus bleibt klein.

## Artefakte (Single Source of Truth)
- MVP: docs/01-mvp.md
- Backlog: GitHub Issues (Feature Request Template)
- Entscheidungen: docs/adr/
- Release Gate: docs/04-release-readiness-checklist.md

## Lizenz
- AGPL-3.0 (GNU Affero General Public License v3.0)
- Begründung: Selfhosted Web-App; verhindert proprietäre Forks als SaaS ohne Quelloffenlegung.
