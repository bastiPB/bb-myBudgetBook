---
doc: release-checklist
version: 0.1
status: living
---

# Release Readiness Checklist (v0.1)

## Funktional
- [x] docker-compose up funktioniert ohne Sonderaktionen
- [x] Erstinstallation: Admin/User Setup möglich
- [x] Login/Logout funktioniert
- [x] Registrierung erstellt Nutzer als `pending` mit Rolle `Default`
- [x] `pending` Nutzer können sich nicht einloggen
- [x] Admin-Freigabe aktiviert Login für neue Nutzer
- [x] Abos CRUD vollständig
- [x] Übersicht: monatliche Summe + nächste Fälligkeiten/Laufzeiten

## Security
- [x] Passwort-Hashing: Argon2id
- [x] Session Cookies: HttpOnly/Secure/SameSite
- [ ] Input Validation / sichere DB-Zugriffe
- [x] RBAC-Basisregeln erzwungen (`Admin`, `Viewer`, `Default`)
- [x] Rollenverwaltung nur über Admin
- [ ] `Default` sieht keine sensitiven Finanzdaten
- [ ] Keine Secrets im Repo
- [ ] Keine sensitiven Daten in Logs
- [ ] Basic Rate Limiting fürs Login

## Ops & Doku
- [ ] README Quickstart vorhanden
- [ ] Frontend-Produktionsbuild läuft reproduzierbar (Docker Multi-Stage) und nginx liefert `dist/` aus
- [ ] Backup/Restore Anleitung vorhanden
- [ ] CHANGELOG gepflegt
- [ ] Release-Tag (`vX.Y.Z`) vorbereitet und passender CHANGELOG-Abschnitt vorhanden
- [ ] Security Policy vorhanden (SECURITY.md)

## Addendum v0.2.1 (UI Shell Mini-Release) — Abgeschlossen 2026-05-03
- [x] Header ist auf allen geschützten Seiten sichtbar und konsistent
- [x] Sidebar-Navigation ist auf Desktop nutzbar
- [x] Footer ist vorhanden und überlappt keinen Inhalt
- [x] Dashboard-Initialansicht hat definierten Empty-State (kein "leerer Bildschirm")
- [ ] Sidebar/Layout auf mobilen Breiten bedienbar ← bewusst auf v0.2.x verschoben
- [ ] Layout ohne horizontales Scrollen bei mobilen Breiten ← bewusst auf v0.2.x verschoben
- [x] Frontend `npm run lint` ist grün
- [x] Frontend `npm run build` ist grün
- [x] Scope-Dokument für v0.2.1 ist aktualisiert
