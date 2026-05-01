# ADR 0005: Introduce RBAC baseline and admin approval flow

## Status
Accepted

## Kontext
Mit wachsender Nutzerzahl braucht das Projekt ein klares und sicheres Rollenmodell. Ohne feste Basis drohen überprivilegierte Accounts, unkontrollierte Einsicht in sensitive Finanzdaten und inkonsistente Freigabeprozesse.

Zusätzlich soll die Plattform künftig erweiterbar bleiben, z.B. für Familienkonten oder getrennte Domänen wie Haushaltsbuch und Sparbuch.

## Entscheidung
Wir führen ein RBAC-Mindestmodell mit drei Rollen ein:
- `admin`
- `editor` (ursprünglich als `viewer` geplant, in v0.1 umbenannt — siehe unten)
- `default`

Verbindliche Regeln:
- Neue Nutzer registrieren mit Rolle `default` und Status `pending`
- `pending` Nutzer dürfen sich nicht einloggen, bis ein `admin` freigibt
- Rollenverwaltung (anlegen, ändern, löschen) ist ausschließlich `admin` erlaubt
- `default` bleibt bewusst eingeschränkt: nach Login nur Wartebildschirm, kein Zugriff auf Finanzdaten
- `editor` darf alle Finanzdaten sehen und bearbeiten, aber keine Benutzerverwaltung
- `admin` hat Vollzugriff: Finanzdaten + Benutzerverwaltung

Erweiterbarkeit:
- Zusätzliche Rollen sind erlaubt
- Rollen können später explizit Domänenkontexten zugeordnet werden (z.B. Haushaltsbuch, Sparbuch)
- Feingranulare Permission-Modelle werden später versioniert ergänzt

## Alternativen
1) Nur zwei Rollen (Admin/User)
   - Pro: einfacher Start
   - Contra: fehlende Abstufung, zu grobe Rechtevergabe

2) Volles Policy-System (ABAC/komplizierte Permission-Matrix) von Anfang an
   - Pro: maximal flexibel
   - Contra: hoher Implementierungs- und Testaufwand für frühen Projektstand

3) Registrierung ohne Freigabeprozess
   - Pro: niedrige Einstiegshürde
   - Contra: unnötiges Risiko bei Mehrnutzerbetrieb und sensitiven Daten

## Konsequenzen
- Pro:
  - Klare Sicherheitsbasis für Mehrnutzerbetrieb
  - Least-Privilege von Anfang an umsetzbar
  - Erweiterbarkeit für zukünftige Domänen/Rollen bleibt erhalten
- Contra:
  - Mehr Verwaltungsaufwand durch Admin-Freigabe
  - Zusätzliche UI/API-Flows für Rollen- und Statusverwaltung nötig

## Umsetzung (v0.1)

Alle Follow-ups wurden umgesetzt:

- User-Modell: Felder `role` (Enum: admin/editor/default) und `status` (Enum: pending/active)
- Login-Service: prüft explizit auf `status == active`, sonst HTTP 403
- `default`-User nach Login: Wartebildschirm im Frontend, Subscription-API gibt HTTP 403
- Admin-Endpunkte: Freigabe (`POST /admin/users/{id}/approve`), Rollenvergabe (`PATCH /admin/users/{id}/role`), Löschen (`DELETE /admin/users/{id}`)

**Erweiterung gegenüber ursprünglicher Planung — zwei Wege zur User-Erstellung:**
1. **Selbst-Registrierung** (`POST /auth/register`): User registriert sich selbst → `pending/default` → Admin-Freigabe nötig
2. **Admin-Erstellung** (`POST /admin/users`): Admin legt User direkt an → sofort `active`, Rolle frei wählbar

**Umbenennung `viewer` → `editor`:**
Die Rolle hieß im ersten Entwurf `viewer`, was "nur lesen" impliziert. Da `editor` in v0.1 aber
lesen *und* schreiben darf, wurde sie in `editor` umbenannt (Alembic-Migration `d4e5f6g7`).
`viewer` als reine Lese-Rolle ist für v0.2+ im Kontext-Modell geplant (siehe docs/13-rbac-vision.md).