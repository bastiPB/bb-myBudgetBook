---
doc: threat-model
status: living
method: STRIDE-lite
---

# Threat Model (STRIDE-lite) — v0.1

Ziel: Ein leichtgewichtiges Threat Model, das Design-Schwächen früh sichtbar macht
und als Checkliste für spätere Features dient.

## 1) Systemüberblick (Scope)
- Frontend: SPA (Browser)
- Backend: Python API
- Datenbank: PostgreSQL
- Deployment: docker-compose (selfhosted)
- Nutzer: Privatpersonen / Paare / Familien (Multi-User möglich)

## 2) Assets (was schützen wir?)
- A1: Account-Daten (Login, Session)
- A2: Finanzdaten (Abos, Beträge, Zeiträume, Notizen)
- A3: Secrets/Keys (z.B. DB-Password, App-Encryption-Key)
- A4: Systemintegrität (Code/Images, Konfiguration)

## 3) Trust Boundaries (Vertrauensgrenzen)
- Browser ↔ Backend (Netzwerkgrenze)
- Backend ↔ Datenbank (Netzwerkgrenze)
- Host ↔ Container (Betriebsumgebung)

## 4) Data Flows (Text-DFD)
DF1: User -> Browser -> Backend: Login Request
DF2: Backend -> DB: User lookup / Session create
DF3: User -> Browser -> Backend: Abo CRUD
DF4: Backend -> DB: Abo read/write
DF5: Backend -> Browser: Übersicht / Response

## 5) STRIDE-lite Analyse (Bedrohungen & Mitigations)

### S — Spoofing (Identität vortäuschen)
- T-S1: Credential Stuffing / Brute Force auf Login
  - M: Rate limiting + Lockout/Backoff, starke Passwortregeln, optional 2FA später
- T-S2: Session Hijacking
  - M: Secure/HttpOnly/SameSite Cookies, TLS, Session rotation

### T — Tampering (Daten manipulieren)
- T-T1: Request Manipulation (IDOR, Parameter ändern)
  - M: AuthZ Checks pro Ressource (User darf nur eigene Daten), serverseitige Validierung
- T-T2: DB Tampering bei Leaks/Access
  - M: Least privilege DB user, migrations kontrolliert, Integritätschecks (optional)

### R — Repudiation (Aktionen abstreiten)
- T-R1: User bestreitet Änderungen (wer hat Abo gelöscht?)
  - M: Audit log minimal (Zeitpunkt, UserId, Aktionstyp), ohne sensitive Inhalte

### I — Information Disclosure (Datenabfluss)
- T-I1: DB-Volume/Backup wird kopiert
  - M: Sensible Felder verschlüsseln (App-Layer), Secrets nicht im Repo
- T-I2: Logs enthalten sensitive Daten
  - M: Logging scrubben (kein Klartext von Finanzdaten/Secrets), Debug nur lokal
- T-I3: Fehlermeldungen leaken Interna
  - M: sichere Error Responses, keine Stacktraces nach außen

### D — Denial of Service (Verfügbarkeit)
- T-D1: Login/Endpoints werden geflutet
  - M: Rate limiting, request size limits, timeouts
- T-D2: DB wird überlastet
  - M: Indexing später, Limits, Healthchecks

### E — Elevation of Privilege (Rechteausweitung)
- T-E1: User wird Admin durch fehlerhafte Rollenlogik
  - M: Rollenmodell minimal & getestet, Admin Aktionen extra schützen
- T-E2: SSRF/Command injection (später bei Integrationen)
  - M: Keine Shell calls, whitelists, sichere Libraries

## 6) Nicht-Ziele / Annahmen
- Wenn Host kompromittiert ist, ist das in selfhosted Settings schwer vollständig zu verhindern.
- Fokus ist: Schutz vor Datenabfluss durch DB-Kopie/Backup + typische Web-Angriffe.

## 7) Offene Punkte
- Definieren: welche Felder sind “sensibel” und werden verschlüsselt?
- Minimal Audit Logging Scope (v0.1 oder v0.2?)
