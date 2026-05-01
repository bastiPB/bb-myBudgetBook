---
doc: roadmap
status: living
---

# Roadmap

## v0.1 (MVP) — Abgeschlossen ✅

Vollständig implementiert. Details: `docs/01-mvp.md`

Fertig:
- Docker-Setup (Produktion + Entwicklungsmodus)
- Auth: Login, Logout, Selbst-Registrierung
- RBAC: Rollen `admin`, `editor`, `default` + User-Lifecycle (pending/active)
- Abo-Manager: CRUD, Übersicht, monatliche Normierung, Billing-Intervalle
- Admin-Bereich: User verwalten, Rollen zuweisen

Noch offen (wird in v0.2 erledigt):
- Backup/Restore Dokumentation

---

## v0.2.0 — Modul-System Fundament + Profil — Abgeschlossen ✅

**Ziel:** Architektur schaffen auf der alle weiteren Features sauber aufgebaut werden.
Keine konkreten Module implementieren — stattdessen das Fundament und die Infrastruktur.

Vollständige Spec + Implementierungsdetails: `docs/14-v020-module-system.md`

### Was in v0.2.0 entsteht:

**Datenbank (2 neue Tabellen + 2 Migrationen):**
- `app_settings` — globale App-Einstellungen (email_signup_enabled, modules JSONB)
- `user_settings` — persönliche Einstellungen pro User (display_name, avatar_url, modules JSONB)

**Backend (2 neue API-Bereiche):**
- `GET/PATCH /settings` — System-Einstellungen (nur Admin darf schreiben)
- `GET/PATCH /profile/settings` — Persönliches Profil (jeder User für sich)

**Zwei-Stufen Modul-System:**
- Admin gibt Module systemweit frei (Stufe 1)
- User wählt aus freigegebenen Modulen seine persönliche Auswahl (Stufe 2)
- Aktiv = Admin hat freigegeben UND User hat es aktiviert

**Frontend (neue Seiten + Context):**
- Module-Registry: statisches Array aller bekannten Module
- Modules-Context: Zwei-Stufen-Logik, stellt aktive Module bereit
- Dynamische Navigation und Routen — nur aktive Module sind sichtbar
- Dashboard Onboarding-Card für neue User
- Admin Settings-Seite (`/settings`) — Module freischalten, Selbst-Registrierung
- Profile Settings-Seite (`/profile/settings`) — Eigene Module + Anzeigename

**Profil-Features:**
- `display_name` — frei wählbarer Anzeigename ("Hallo Sparfuchs!")
- `avatar_url` — Datenbankfeld bereits vorhanden, Datei-Upload folgt in v0.2.x

**Modul-Stubs (Platzhalter-Seiten) für alle geplanten Module:**
| Modul | Key | Status |
|---|---|---|
| Abo-Manager | `subscriptions` | fertig, ins Modul-System integriert ✅ |
| Sparfach | `savings_box` | Platzhalter ✅ |
| Urlaubskasse | `vacation_fund` | Platzhalter ✅ |
| Haushaltsbuch | `household_budget` | Platzhalter ✅ |
| Fondsparen | `fund_savings` | Platzhalter ✅ |
| Aktiendepot | `stock_portfolio` | Platzhalter ✅ |

**Zusätzlich implementiert:**
- Dashboard-Navigation dynamisch aus `activeModules` — keine hardcodierten Buttons mehr
- `NotFoundPage` — ersetzt blinden Login-Redirect bei unbekannten URLs (Details: Abschnitt 12 in Spec)
- `reload()` im ModulesContext — Navigation aktualisiert sich sofort nach Modul-Toggle

---

## v0.2.1 — UI Shell + Dashboard Initial — Geplant

**Ziel:** Das Frontend bekommt eine stabile Grundstruktur (Header, Sidebar, Footer) und eine erste klare Dashboard-Startansicht.

Vollständige Scope-Definition: `docs/15-v021-ui-shell-and-dashboard-initial.md`

### Scope für dieses Mini-Release

- App-Shell mit `Header`, `Sidebar`, `Footer` als wiederverwendbare Layout-Bausteine
- Grundlayout für Desktop und mobile Ansicht (responsives Verhalten)
- Erste Dashboard-Initialansicht mit klarer Struktur (Hero/Kurzstatus/Schnellzugriffe)
- Dashboard soll mit leerem Datenstand verständlich bleiben (Empty-State)

### Out of Scope (nicht Teil von v0.2.1)

- Neue Business-Logik oder neue Datenmodelle
- Neue API-Endpunkte
- Finale Detail-Visualisierung für alle Module

### Doku-Ziel in v0.2.1

- `CHANGELOG.md` pflegen (`[Unreleased]` und später `0.2.1`)
- Scope-Dokument aktuell halten
- Falls Layout-Architektur-Entscheidung dauerhaft ist: ADR ergänzen

---

## v0.2.x — Konkrete Module & Profil-Erweiterungen

Nach dem Fundament werden Module einzeln, unabhängig voneinander entwickelt.
Jedes Modul ist ein eigenständiger Entwicklungs-Sprint.

**Profil-Erweiterungen:**
- Profilbild-Upload (Avatar) — Datei-Upload, Speicherung in Docker Volume
- Passwort ändern — User kann sein eigenes Passwort ändern

**Abo-Manager Erweiterungen (erstes v0.2.x nach dem Fundament):**
- Icons für Abos (Emoji oder Dienst-Logo)
- Suspend: Abo pausieren ohne löschen
- Jahressumme pro Abo
- Gesamtsumme pro Abo ("Du hast für Netflix bisher X € gezahlt")

**Sparfach (`savings_box`):**
- Manuelle Einlagen, Verlaufsansicht
- Sparfach-Nummer / Adresse des physischen Sparfachs

**Urlaubskasse (`vacation_fund`):**
- Ziel, Datum, Sparziel, Fortschrittsanzeige
- Gemeinsam / Privat
- Manuelle Buchungen, Rückstand-Hinweis

**Haushaltsbuch (`household_budget`):**
- Monatsbudget, Partner-Einzahlungen, Ausgaben-Tracking

**Fondsparen (`fund_savings`) + Aktiendepot (`stock_portfolio`):**
- Manuelle Eingabe, Verlaufsansicht, Zielwert / Gesamtwert

**Dashboard gestalten (mittelfristig):**
- Reihenfolge der Modul-Kacheln anpassen
- Favoriten-Ansicht

---

## Weitere geplante Features (kein festes Release)

- **Kontext-Modell (Spaces)** — persönliche + geteilte Bereiche für Familien (Details: `docs/13-rbac-vision.md`)
- **Backup/Restore Dokumentation** — Doku + Testanleitung (offener Punkt aus v0.1)
- **`viewer`-Rolle** — nur lesen, kein Schreiben — im Rahmen des Kontext-Modells

---

## Langfristig / Icebox

Details in `docs/10-icebox.md`

- **EPIC 01** — Home Assistant Integration (HACS Dashboard Badges)
- **EPIC 02** — Bankanbindung / Open Banking (oder CSV Import)
- **EPIC 03** — E-Mail Benachrichtigungen (Abo-Erinnerungen, Spar-Alerts)
- **EPIC 04** — CSV Import & Reality Check (echte Buchungen mit Modulen verknüpfen)
- **EPIC 05** — Gemeinsame Bereiche (Shared Sparfach, Urlaubskasse für Paare)
