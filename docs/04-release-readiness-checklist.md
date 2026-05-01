---
doc: release-checklist
version: 0.1
status: living
---

# Release Readiness Checklist (v0.1)

## Funktional
- [ ] docker-compose up funktioniert ohne Sonderaktionen
- [ ] Erstinstallation: Admin/User Setup möglich
- [ ] Login/Logout funktioniert
- [ ] Registrierung erstellt Nutzer als `pending` mit Rolle `Default`
- [ ] `pending` Nutzer können sich nicht einloggen
- [ ] Admin-Freigabe aktiviert Login für neue Nutzer
- [ ] Abos CRUD vollständig
- [ ] Übersicht: monatliche Summe + nächste Fälligkeiten/Laufzeiten

## Security
- [ ] Passwort-Hashing: Argon2id
- [ ] Session Cookies: HttpOnly/Secure/SameSite
- [ ] Input Validation / sichere DB-Zugriffe
- [ ] RBAC-Basisregeln erzwungen (`Admin`, `Viewer`, `Default`)
- [ ] Rollenverwaltung nur über Admin
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
