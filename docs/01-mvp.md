---
doc: mvp
version: 0.1
status: frozen
---

# MVP (v0.1) — Scope & Ziele

## Problem / Zielgruppe
- Zielgruppe: Privatpersonen, Paare, ggf. Familien (Selfhosted, OpenSource)
- Problem: Überblick über Abos und (später) Einnahmen/Ausgaben ohne Cloud

## Wertversprechen
- Lokal per Docker, keine Sorgen um ""wo liegen meine Finanzdaten?""
- Keine monatlichen Kosten, volle Datenhoheit

## Must-Haves (v0.1)
1) Login mit sicherem Passwort (Passwort-Hashing: Argon2id)
2) Rollen & Berechtigungen (Mindestmodell): `admin`, `editor`, `default`
	- **Selbst-Registrierung**: User registriert sich über `/register` → landet als `pending` mit Rolle `default`
	- **Admin legt User direkt an**: Admin erstellt User mit Passwort und Rolle → User ist sofort `active`
	- `pending` Nutzer können sich nicht einloggen, bis ein Admin freigibt (Status → `active`)
	- `default` darf sich nach Freigabe einloggen, sieht aber einen Wartebildschirm — kein Zugriff auf Finanzdaten
	- `editor` darf alle Finanzdaten sehen und bearbeiten, aber keine Benutzerverwaltung
	- `admin` darf alles: Finanzdaten + Benutzerverwaltung (Rollen anlegen, ändern, User löschen)
3) Abos manuell anlegen/ändern/löschen (Netflix, Prime, Audible, …)
4) Übersicht: monatliche Abo-Kosten + Laufzeit / nächste Fälligkeiten
5) Backend (Python API) + Postgres DB + modernes SPA-Frontend (keine Page Reloads)

## Out of Scope (v0.2+)
- Budgets (Urlaub)
- Sparpläne
- Financial Fitness (Scoring)
- Bankimport / automatischer Import
- Mobile App
- Feingranulare Permission-Matrix pro Aktion
- Freie, komplexe Rollen-Policies über mehrere Haushaltskontexte hinweg

## Erfolgskriterien (v0.1)
- docker-compose: Start in wenigen Minuten
- User kann innerhalb von 2 Minuten erstes Abo anlegen
- Doku vorhanden: Setup + Backup/Restore + Security Hinweise

## Offene Fragen (Tracking)
- Datenverschlüsselung: Applikationsseitige Feldverschlüsselung (später ADR)
- Minimaler Backup/Restore Prozess (später ADR)
- Rollen-Zuordnung zu separaten Kontexten (z.B. Haushaltsbuch, Sparbuch) im Detail
