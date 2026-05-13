# Changelog

All notable changes to this project will be documented in this file.
Format based on Keep a Changelog.

## [Unreleased]

## [0.2.72] - 2026-05-13

### Modified

- **Change-Interval/Price**: Auf Detail Seite für Subscription: verschoben in Details. Auf der Übersichtsseite Text durch Icon ersetzt (Bearbeiten, Pause, Löschen)

## [0.2.71] - 2026-05-13

### Fixed

- **Datumseingabe-Format**: Alle `<input type="date">`-Felder zeigten das US-Format `MM/DD/YYYY`. Ursache war `lang="en"` in `frontend/index.html` — Browser richten die Datumsdarstellung danach. Ein-Zeilen-Fix: `lang="de"` setzt das gesamte Dokument auf deutsches Locale. Betroffen waren: Erstell-Formular (Abschlussdatum), Detailseite (Preisänderung, Intervallwechsel), Sparfach-Seiten (Start- und Enddatum). Angezeigte (nicht editierbare) Datumsstrings waren nicht betroffen — `formatDate()` gibt korrekt `DD.MM.YYYY` aus.

## [0.2.7] - 2026-05-13

### Added

**Subscription Tags** — Abos können mit eigenen Tags versehen werden (z. B. „Streaming", „KI-Abos", „Server"). Tags sind user-spezifisch mit 12 vordefinierten Farben und in beliebiger Anzahl pro Abo zuweisenbar.

- Neues CRUD-Modal zum Erstellen, Umbenennen und Löschen von Tags (mit Inline-Bestätigung)
- Tag-Zuweisung auf der Detailseite via Multi-Select-Dropdown
- Tag-Chips in der Abo-Übersicht unterhalb des Namens
- Tag-Filter in der Übersicht: AND-Verknüpfung, farbige Chips, „Filter zurücksetzen"-Button
- Backend: 2 neue Tabellen (`subscription_tags`, `subscription_tag_assignments`), 5 neue API-Endpunkte unter `/subscriptions/tags`, N+1-freies Bulk-Loading per `_computed_tags`-Pattern
- Migration `p6q7r8s9`

## [0.2.6] - 2026-05-09

### Added

**Sparfach (Savings Box)** bildet das klassische Kneipenbuch-System digital ab: Ein externer Ort verwahrt das Geld, die App trackt Einzahlungen, Termine und den Abschluss.

**Backend:** SQLAlchemy-Modelle (`SavingsBox`, `SavingsTerm`, `SavingsBooking`), Pydantic-Schemas, Service-Paket `app/services/savings/` (Terms, Buchungen, Lifecycle, Lesen ohne N+1), domain-spezifische Fehlerklassen und Router `app/routers/savings.py`.

**API-Endpunkte**
- `POST /savings/boxes`
- `GET /savings/boxes`
- `GET /savings/boxes/{id}`
- `PATCH /savings/boxes/{id}`
- `POST /savings/boxes/{id}/close`
- `POST /savings/boxes/{id}/reopen`
- `GET /savings/boxes/{id}/terms`
- `POST /savings/boxes/{id}/terms/refresh`
- `POST /savings/boxes/{id}/bookings`
- `GET /savings/boxes/{id}/bookings`
- `PATCH /savings/boxes/{id}/bookings/{id}`
- `DELETE /savings/boxes/{id}/bookings/{id}`

**Features**
- Sparfach mit Mindestbetrag pro Term, optionaler Strafgebühr, Gesamtziel und persönlichem Termziel
- Automatische Term-Generierung von `start_date` bis `end_date` (Intervall: wöchentlich, 14-tägig, monatlich)
- Auto-Penalty-Buchung bei verpassten Terminen, wenn `penalty_amount` gesetzt ist (idempotent)
- Mehrere Einzahlungen pro Term möglich — jede Einzahlung muss mindestens dem Term-`expected_amount` entsprechen
- Abschluss mit Snapshot: `closing_expected_amount` = Summe Einzahlungen − Summe Strafen
- Wieder öffnen setzt alle Abschlussfelder zurück
- Geschlossenes Sparfach blockiert Schreiboperationen (HTTP 409)

**Datenbank:** neue Tabellen `savings_boxes`, `savings_terms`, `savings_bookings`; neue Enums `savingsinterval`, `savingsboxstatus`, `savingstermstatus`, `savingsbookingtype`.

**Frontend:** Typen und API-Client (`frontend/src/types/savingsBox.ts`, `frontend/src/api/savingsBox.ts`), Dashboard `/savings-box` mit Kacheln (Fortschritt, Status, nächster Termin), Detailseite `/savings-box/:id` mit Tabs Übersicht / Buchungen / Einstellungen, Termine gruppiert nach Status, Zwei-Schritt-Bestätigung für Abschluss und Wiedereröffnung.

### Tests

- `test_savings_box_v026.py`: Term-Generierung, Kennzahlen (`compute_box_summary`), `update_term_statuses` inkl. Auto-Penalty und Idempotenz, Buchungsregeln (Mindestbetrag, Penalty-Löschen, Deposit löschen), Zugriff auf geschlossene Box; Router-Smoke über eine Mini-FastAPI-App mit SQLite (`StaticPool`) ohne Lifespan.

### Database Migrations

- `o5p6q7r8` — v0.2.6: Sparfach — PostgreSQL-Enums und Tabellen `savings_boxes`, `savings_terms`, `savings_bookings`.

## [0.2.5] - 2026-05-05

### Documentation
- [docs/21-v024-subscription-interval-change.md](docs/21-v024-subscription-interval-change.md): Spezifikation **v0.2.4** — Abwechsel von Abrechnungsintervallen (Preis + Intervall + Fälligkeitsanker in `subscription_billing_history`), segmentierte Due-Date-Algorithmen, Endpoint `POST /subscriptions/{id}/interval-change`, Migration von reiner Preishistorie, Akzeptanzkriterien und Test-Szenarien
- [docs/22-v025-subscription-service-refactor.md](docs/22-v025-subscription-service-refactor.md): Spezifikation **v0.2.5** — struktureller Refactor des Subscription-Service als Package `backend/app/services/subscriptions/` (Untermodule billing, readers, mutations, lifecycle, logos, access, constants, types), stabile Imports `from app.services.subscriptions import …`, Import-/Zyklus-Regeln, Monkeypatch-Hinweis für Tests nach dem Split, Build-Plan in Chunks

### Added
- **Intervallwechsel — kurze Abrechnungsphase**: `POST /subscriptions/{id}/interval-change` akzeptiert `acknowledge_short_segment` (default `false`). Wenn die zusammengefügte Abrechnungshistorie ein Segment kürzer als eine volle Periode des Intervalls ergeben würde (z.B. jährlich ab 01.08., nächster Eintrag schon 01.10.), antwortet die API mit **409** und Marker „Kurze Abrechnungsphase"; die Detailseite zeigt eine **zweite Bestätigungs-Checkbox** (analog zu bestehenden Buchungen).
- **Scheduler konfigurierbar (Admin)**: Systemeinstellungen enthalten jetzt `scheduler_catch_up_days` (default **60**, max **730**) für das rückwirkende Nachtragen verpasster Fälligkeiten. Zusätzlich kann die tägliche `scheduler_time` über die Systemeinstellungen geändert werden und wird **ohne App-Neustart** auf den laufenden APScheduler-Job angewendet.

### Fixed
- **BUG-08**: Kennzahl „Dieses Kalenderjahr" reagierte bei Intervallwechseln (z.B. monatlich → jährlich) fachlich falsch — der volle Jahresbetrag wurde im Fälligkeitsmonat komplett gezählt, wodurch „Dieses Jahr" bei einem Wechsel auf längere Intervalle scheinbar stark anstieg. Die Kennzahl ist jetzt **monatsbasiert anteilig** (Budget-Orientierung) und nutzt dabei die zentralen Faktoren aus `services/subscriptions/constants.py` (betrifft auch quarterly/semiannual/biennial).
- **UI**: Intervallwechsel-Formular klarer gemacht: Betrag ist **pro ausgewähltem Intervall**; zusätzlich wird ein Hinweis „entspricht ca. X € pro Jahr" angezeigt, um Verwechslungen (z.B. Jahresbetrag in Quartalsfeld) sofort sichtbar zu machen.
- **Billing-Historie**: Löschen eines Abrechnungseintrags führt nicht mehr zu HTTP 500 bei mehreren betroffenen Buchungen (`MultipleResultsFound`). Stattdessen wird die Aktion sauber mit **409** blockiert, wenn Buchungen im betroffenen Zeitraum existieren. Zusätzlich ist der **initiale Abrechnungseintrag** (Abo-Start) nicht mehr löschbar.

### Database Migrations
- `n4o5p6q7` — v0.2.5: `app_settings.scheduler_catch_up_days` (default 60) für das Catch-up-Fenster des Buchungs-Schedulers.

### Tests
- `test_settings_scheduler.py`: Validierung für `scheduler_time` (HH:MM) und `scheduler_catch_up_days` (0…730).

## [0.2.3] - 2026-05-05

### Breaking Changes
- `POST /subscriptions`: Feld `next_due_date` entfernt — wird serverseitig aus `started_on + N × interval` berechnet
- `PATCH /subscriptions/{id}`: Feld `amount` entfernt → `POST /subscriptions/{id}/price-change` verwenden

### Added

**Neue API-Endpoints**
- `POST /subscriptions/{id}/price-change`: Preisänderung mit `valid_from` (Vergangenheit/heute/Zukunft)
- `POST /subscriptions/{id}/cancel`: Abo endgültig kündigen (mit optionalem `access_until`)

**Neue Features**
- Halbjährliches Abrechnungsintervall (`semiannual` / „Halbjährlich") in allen Berechnungen und der UI
- Neue Kennzahl „Intervalle": Anzahl der bezahlten Zahlungsperioden seit Abschluss
- Neue Kennzahl „Dieses Kalenderjahr": Jahresbudget-Ansicht inkl. angekündigter Preise als Projektion
- Mehrfaches Pausieren und Resumieren über `subscription_pause_history` (beliebig oft, mit History)
- Preisankündigungen: zukünftige Preise eintragenbar; Ankündigungs-Badge in Übersicht + Detail
- Abos mit `started_on` in der Zukunft fließen nicht in die monatliche Gesamtsumme ein

**UI**
- Kennzahlen-Ansicht auf der Detailseite: Monatlich / Dieses Jahr / Intervalle / Tatsächlich ~
- Preisänderungs-Flow mit Formular und Ankündigungs-Badge
- Kündigungs-Flow mit Sicherheits-Modal (Abo-Name eintippen zur Bestätigung)
- Modal-System ersetzt alle `window.confirm()`-Dialoge
- „Halbjährlich" in der Interval-Auswahl
- `DELETE /subscriptions/{id}/price-history/{entry_id}`: Einzelnen Preishistorie-Eintrag löschen
  - Blockiert wenn es der letzte Eintrag ist (Abo braucht mindestens einen Preis)
  - Blockiert wenn Buchungen im betroffenen Preiszeitraum existieren (präzise Fensterprüfung)
  - Erlaubt das Löschen „mittlerer" Einträge (z. B. falsche Zukunfts-Ankündigung) wenn keine Buchungen betroffen sind
- `DuplicatePriceEntryError` (HTTP 409): `POST /price-change` blockiert jetzt doppelte `valid_from`-Einträge — User muss bestehenden Eintrag erst löschen oder bearbeiten
- `InfoModal`-Komponente (`frontend/src/components/InfoModal.tsx`): wiederverwendbares Info/Fehler-Overlay mit einem OK-Button, nutzt CSS-Klassen von `ConfirmModal`
- Löschen-Icon (Papierkorb) in der Preishistorie-Tabelle auf der Detailseite mit Bestätigungs-Modal und Fehler-Overlay

### Fixed
- **BUG-01**: `next_due_date` wird nicht mehr gespeichert — immer frisch aus `started_on + N × interval` berechnet (kein Drift)
- **BUG-02**: „Tatsächlich"-Algorithmus neu geschrieben — Perioden zählen statt Segment-Mathe; kein `+1`-Hack mehr
- **BUG-03**: Preisänderungen können rückwirkend und als Ankündigung eingetragen werden (`valid_from` frei wählbar)
- **BUG-04**: „Tatsächlich" zeigt korrekt 1 Periode wenn Abo am selben Tag angelegt und abgerufen wird (war: 0)
- **BUG-05**: `next_due_date` fehlte in der Abo-Listenansicht — `SubscriptionRead.model_validate()` liest nur echte DB-Spalten; neue Hilfsfunktion `subscription_to_read()` berechnet das Datum und setzt es in allen List-Endpunkten (list, create, suspend, resume, update, logo)
- **BUG-06**: Stale `sub.amount` nach Preisankündigung — `monatlich` (Detailseite), `monthly_total` (Übersicht) und Scheduler-Snapshots nutzten `sub.amount` direkt; dieser Wert wurde beim Eintragen einer Zukunfts-Preisänderung nicht automatisch aktualisiert; alle drei Stellen berechnen den Betrag jetzt über `applicable_price()` aus der Preishistorie
- **BUG-07**: Datum „Nächste Fälligkeit" in der Übersichtstabelle wurde im ISO-Format (`2026-05-15`) angezeigt — `formatDate()` war in `SubscriptionsPage.tsx` nicht importiert und nicht angewendet

### Scheduler
- Period-basiert: `due_date` = berechneter Fälligkeitstag (nicht mehr `date.today()`)
- Catch-up: verpasste Perioden bis 60 Tage rückwirkend automatisch nachfüllen
- `suspended` → `paused`-Einträge generiert (Pause in Buchungshistorie sichtbar)
- `canceled` → keine neuen Einträge mehr (Tabelle endet sauber)
- N+1-Query eliminiert: `pause_history` per Bulk-Load für alle Abos

### Database Migrations
- `j0k1l2m3` — v0.2.3 Kern: neue Tabelle `subscription_pause_history`; Spalten `next_due_date`, `suspended_at`, `access_until` aus `subscriptions` entfernt; `PaymentStatus.paused` + `BillingInterval.semiannual` ergänzt
- `l2m3n4o5` — `subscription_scheduled_payments.amount` nullable (für `paused`-Einträge ohne Betrag)

### Tests
- `test_subscriptions_v023.py`: S-01 (relativedelta Ankertag-Recovery), S-03 (Pause + Preiserhöhung in derselben Periode)
- `test_subscriptions_v022.py`: für v0.2.3 bereinigt (obsolete Felder entfernt, L-04-Aufhebung dokumentiert)

## [0.2.2] - 2026-05-04

### Added

**Slice A — Abo-Lifecycle**
- Lifecycle-Status für Abos: `active`, `suspended`, `canceled`
- Neue Felder: `started_on`, `notes`, `logo_url`, `suspended_at`, `access_until`
- `POST /subscriptions/{id}/suspend` mit optionalem `access_until`
- `POST /subscriptions/{id}/resume`

**Slice B — Listen-UX**
- Suche (Name-Filter), Seitengröße 25/50/100, clientseitige Paginierung
- Status-Badge in der Abo-Tabelle
- Betragsanzeige deutsch formatiert; Eingabe akzeptiert Komma oder Punkt

**Slice C — Detailseite**
- `GET /subscriptions/{id}` mit berechneten Kostenkennzahlen (`monthly_cost_normalized`, `yearly_cost_normalized`, `total_paid_estimate`)
- Detailseite: Kostenkarten, Stammdaten, Notizen mit Inline-Bearbeitung, Suspend/Resume-Aktionen

**Slice D — Logo-Upload**
- `POST /subscriptions/{id}/logo`: Upload von JPEG/PNG/WebP bis 2 MB
- StaticFiles-Mount für `/uploads` (ADR 0010: lokales Dateisystem, relativer Pfad in DB)
- Fallback-Icon (Anfangsbuchstabe) wenn kein Logo hinterlegt
- `uploads-data` Docker-Volume für persistente Logos über Container-Neustarts

**Slice E — Preishistorie**
- `GET /subscriptions/{id}/price-history`
- Preishistorie-Karte auf Detailseite (neuester Eintrag hervorgehoben)
- `total_paid_estimate` nutzt exakte Segment-Berechnung über Preishistorie statt Schätzung
- Erster Zahlungs-Fix: +1 für die Zahlung zum Abschluss-Datum (wird nicht durch reine Monatsdifferenz erfasst)

**Slice F — Buchungs-Scheduler**
- APScheduler (BackgroundScheduler) im FastAPI-Lifespan: täglich zur konfigurierten Uhrzeit
- Neue DB-Tabelle `subscription_scheduled_payments` (UNIQUE `subscription_id + due_date` als Idempotenz-Constraint)
- Neue DB-Tabelle `user_module_configurations` (JSONB-Einstellungen pro User, ADR 0007)
- Neues Feld `scheduler_time` in `app_settings` (Format `HH:MM`, default `03:00`)
- `POST /admin/subscriptions/trigger-payments`: manueller Scheduler-Aufruf (idempotent)
- `GET /profile/module-config` + `PATCH /profile/module-config`
- ProfileSettingsPage: Abschnitt „Abo-Einstellungen" mit Toggles für Buchungshistorie und kumulierte Kosten
- SettingsPage: Abschnitt „Buchungs-Scheduler" mit manueller Auslöse-Schaltfläche

**Slice G — Buchungshistorie auf Detailseite**
- `GET /subscriptions/{id}/scheduled-payments`
- Buchungshistorie-Tabelle auf der Abo-Detailseite (nur sichtbar wenn Einträge vorhanden)
- Status-Badges: Offen (gelb), Bezahlt (grün), Verpasst (rot)

### Fixed
- `subscription_price_history.updated_at` fehlte in der Slice-A-Migration → neue Migration `h8i9j0k1` ergänzt die Spalte mit `server_default=NOW()`
- `total_paid_estimate` zeigte 0,00 € wenn Abo-Start und heutiges Datum im selben Monat lagen
- Logos gingen nach Container-Neustart verloren → `uploads-data` Named Volume in `docker-compose.yml`
- GitHub Actions CI: `PermissionError: /uploads` beim App-Import → `mkdir` + `StaticFiles`-Mount in `try/except` gewrappt

### Database Migrations
- `g7h8i9j0` — v0.2.2 Slice A: `status`, `started_on`, `notes`, `logo_url`, `suspended_at`, `access_until` zu `subscriptions`; neue Tabelle `subscription_price_history`
- `h8i9j0k1` — Slice E Fix: `updated_at` zu `subscription_price_history` nachgetragen
- `i9j0k1l2` — Slice F: neue Tabellen `subscription_scheduled_payments` + `user_module_configurations`; Spalte `scheduler_time` in `app_settings`

### ADRs
- ADR 0010: Lokales Dateisystem für User-Uploads (relativer Pfad in DB, Migrationspfad zu Object Storage offen)

## [0.2.1] - 2026-05-03

### Added
- **AppLayout-Komponente** (`AppLayout.tsx` + `AppLayout.css`): wiederverwendbare UI-Shell für alle geschützten Seiten — Header, Sidebar, Footer
- **Header**: Logo (BB-SVG), App-Name als Link, Dark/Light-Mode-Toggle, User-Dropdown (Initialen, E-Mail, Einstellungen, Abmelden)
- **Dark/Light-Mode-Toggle**: Pill-förmiger Schiebeschalter mit Mond-/Sonne-SVG-Icon (Feather Icons), Zustand persistiert in `localStorage` (`bb-theme`)
- **Sidebar**: dynamische Navigation aus `activeModules`, Admin-Bereich (Trennlinie + Sektion-Label) nur für Nutzer mit Rolle `admin`
- **Footer**: Versionsnummer
- **CSS Design-System**: CSS Custom Properties (`--color-*`, `--header-height`, `--sidebar-width`) als zentrale Theme-Basis für Light und Dark Mode
- Alle geschützten Seiten auf neues Design-System umgestellt: `LoginPage`, `RegisterPage`, `AdminPage`, `SubscriptionsPage`, `SettingsPage`, `ProfileSettingsPage`, `DashboardPage`
- ADR 0009: CSS Custom Properties als neutrales Design-System (statt Tailwind / MUI / Inline-Styles)
- Design Guide (`docs/16-design-guide.md`): lebendige Referenz für CSS-Variablen, Klassen und Do/Don't-Regeln

### Changed
- `App.tsx`: `Layout`- und `AdminLayout`-Wrapper kombinieren `ProtectedRoute`/`AdminRoute` mit `AppLayout` — kein Code-Doppel
- `DashboardPage`: eigener Header und Logout-Button entfernt — Navigation läuft vollständig über `AppLayout`
- Alle Page-Komponenten: `useNavigate` + manuelle Dashboard-Buttons entfernt

### Fixed
- `SubscriptionsPage`: Spaltenbreiten-Verschiebung beim Aktivieren des Inline-Edit-Modus behoben (`table-layout: fixed` + explizite `th`-Breiten in %)

### Docs
- `docs/15-v021-ui-shell-and-dashboard-initial.md`: Status auf `released` gesetzt
- `docs/05-roadmap.md`: v0.2.1 als abgeschlossen markiert; Mobile-Responsiveness bewusst in v0.2.x verschoben
- `docs/04-release-readiness-checklist.md`: v0.2.1-Addendum aktualisiert

### Known Limitations
- **Mobile-Responsiveness**: bewusst auf v0.5.x verschoben — Fokus liegt auf Desktop

## [0.2.0] - 2026-05-01

### Added
- **Zwei-Stufen-Modul-Sichtbarkeit** (ADR 0007, ADR 0008): Admin gibt Module systemweit frei, User aktiviert sie individuell — nur beide aktiv = Route erreichbar
- `AppSettings`-Modell + Tabelle: systemweite Einstellungen (E-Mail-Registrierung, Modul-Freigaben als JSONB)
- `UserSettings`-Modell + Tabelle: persönliche Einstellungen pro User (Anzeigename, Avatar-URL, eigene Modul-Auswahl als JSONB)
- `GET/PATCH /settings`-Endpunkte (nur Admin): systemweite Modul-Freigabe und Registrierungs-Toggle
- `GET/PATCH /profile/settings`-Endpunkte (jeder eingeloggte User): Anzeigename, Avatar-URL, persönliche Modulauswahl
- `ModulesContext`, `ModulesProvider`, `useModules`-Hook: Frontend-State für aktive und verfügbare Module, inkl. Reload-Mechanismus
- `MODULE_REGISTRY` (frontend): zentrale Definition aller 6 Module mit Key, Label, Route und Nav-Label
- `SettingsPage`: Admin-Seite zum Freigeben/Sperren von Modulen und zum Verwalten der Registrierung
- `ProfileSettingsPage`: Nutzer-Seite für Anzeigenamen, Avatar-URL und persönliche Modulauswahl
- `DashboardPage`: Onboarding-Karte bei fehlenden Modulen, dynamische Navigations-Buttons zu aktiven Modulen
- `NotFoundPage`: smarte 404-Seite — leitet eingeloggte User zum Dashboard, ausgeloggte zum Login
- `PlaceholderPage`: Platzhalter für noch nicht implementierte Module (zeigt Modulnamen)
- Dynamische Routen in `App.tsx`: nur freigegebene + aktivierte Module sind als URL erreichbar
- Alembic-Migrationen für `app_settings` und `user_settings` (UUIDs werden in Python erzeugt, kein pgcrypto nötig)
- ADR 0007: JSONB für Modul-Konfiguration
- ADR 0008: Zwei-Stufen-Modul-Sichtbarkeitsmodell

### Changed
- `App.tsx`: Abonnement-Route ist jetzt dynamisch (aus `activeModules`), Root `/` leitet zu `/dashboard` weiter
- `main.py`: `/settings`- und `/profile/settings`-Router eingebunden

### Fixed
- Root-URL `/` landete nach Umbau auf `NotFoundPage` — `Navigate to="/dashboard"` wiederhergestellt
- Logout-Bestätigung wurde nicht angezeigt: `location.state` wurde durch `ProtectedRoute`'s `<Navigate replace />` überschrieben — Flag wird jetzt via `sessionStorage` übergeben (wird sofort nach dem ersten Lesen gelöscht)

## [0.1.0] - 2026-04-XX

### Added
- Projektstruktur und Dokumentations-Gerüst (docs/00–09, ADRs 0001–0006)
- Backend-Scaffold: FastAPI + SQLAlchemy + Alembic, Argon2id-Passwort-Hashing
- Cookie-basierte Session-Authentifizierung (itsdangerous)
- CRUD-Endpunkte für Abos mit Besitz-Prüfung und Intervall-Normalisierung
- User-Verwaltung mit Rollen (admin/editor/default) und Freigabe-Flow (pending → active)
- Frontend-Scaffold: React 19 + TypeScript + Vite + nginx (Multi-Stage Docker Build)
- SPA-Routing mit ProtectedRoute und AdminRoute
- Docker-Compose-Setup für Produktion und lokale Entwicklung (dev-Override)
- GitHub Actions CI: Backend-Tests (pytest) + Frontend-Lint und -Build
- Release-Workflow: automatischer GitHub Release bei `vX.Y.Z`-Tags

### Security
- Passwort-Hashing mit Argon2id (argon2-cffi), Rehash bei veralteten Parametern
- Session-Cookie mit Secure/HttpOnly-Flag, abhängig von ENVIRONMENT
- RBAC auf Backend-Ebene, unauthentifizierte Endpunkte sind nicht erreichbar
