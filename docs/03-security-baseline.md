---
doc: security-baseline
version: 0.1
status: living
---

# Security Baseline (v0.1)

## Ziele
- Keine Secrets im Repo
- Schutz gegen triviale Angriffe (Brute force, Injection)
- Minimale Angriffsfläche (least privilege)

## Authentifizierung
- Passwörter: Argon2id Hashing (kein Klartext, keine reversible Verschlüsselung)
- Rate limiting für Login (basic)

## Autorisierung (RBAC)
- Rollen (v0.1): `admin`, `editor`, `default`
- Rollenverwaltung (anlegen/ändern/löschen) ist ausschließlich `admin` erlaubt
- Neue Nutzer starten als `pending` mit Rolle `default` — kein Datenzugriff, kein Login bis zur Admin-Freigabe
- `default` sieht nach Freigabe nur einen Wartebildschirm — bewusst kein Zugriff auf Finanzdaten (least privilege)
- `editor` darf alle Finanzdaten sehen und bearbeiten, hat aber keine administrativen Rechte (keine Benutzerverwaltung)
- `admin` hat Vollzugriff: Finanzdaten + Benutzerverwaltung
- Subscription-API (`/subscriptions/*`) ist nur für `editor` und `admin` erreichbar — `default` bekommt HTTP 403
- Erweiterte Rollen und feinere Berechtigungen (z.B. `viewer`, `restricted`) sind für v0.2+ geplant (siehe docs/13-rbac-vision.md)

## Sessions
- Cookie-basiert: HttpOnly + Secure + SameSite
- Logout invalidiert Session
- Timeouts: Idle + Absolute (später konkretisieren)

## Datenhaltung
- Postgres als DB
- Sensible Inhalte: grundsätzlich als „schutzwürdig“ behandeln
- Keine sensitiven Daten in Logs
- Backup/Restore soll dokumentiert werden

## Secrets & Konfiguration
- Secrets via env oder gemountete Datei (nicht committen)
- .env nur als Beispiel (.env.example), niemals echte Werte

## Reporting
- SECURITY.md vorhanden (responsible disclosure)
