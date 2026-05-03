---
doc: icebox
status: living
scope: long-term
rules:
  - "Icebox items are NOT evaluated against MVP (docs/01-mvp.md) unless promoted."
  - "Promotion requires a concrete proposal + risks + minimal acceptance criteria."
tags:
  - target:icebox
  - type:epic
---

# Icebox (Long-term) — Ecosystem & Integrations

Diese Datei enthält **bewusst langfristige Epics**, die *nicht* in v0.1/v0.2 gehören,
aber als Vision/Optionen erhalten bleiben sollen.

## Tagging-System (für Epics)
Jeder Epic hat ein `Tags:`-Block mit festen Feldern, damit KI & Menschen konsistent arbeiten können.

**Standard-Tags**
- `target:` icebox | v0.2 | v1.x
- `type:` epic | integration | core
- `area:` ecosystem | integration | security | ux | ops
- `risk:` low | medium | high
- `privacy:` low | medium | high
- `deps:` (Liste von Abhängigkeiten)
- `decision:` open | leaning | decided

---

## Promotion-Regeln (Icebox → Roadmap/Backlog)
Ein Epic wird erst „aktiv“, wenn folgende Kriterien erfüllt sind:
1) **Konkreter Nutzen + Zielgruppe** (1–3 Sätze)
2) **Minimaler Scope** (was genau ist v1 des Epics?)
3) **Security/Privacy Impact** ist beschrieben
4) **Abhängigkeiten** sind bekannt
5) Ein GitHub Issue (Epic) wird erstellt und mit `target:vX` gelabelt

---

# EPIC 01 — Home Assistant Integration (HACS) + Dashboard Badges

## Tags
- target: icebox
- type: epic
- area: ecosystem, integration
- risk: medium
- privacy: medium
- decision: open
- deps: stable read-only API, auth for integrations, metrics/aggregation model

## Motivation / Nutzerwert
- Finanz-Overviews (z.B. monatliche Abo-Summe, nächste Fälligkeit) als Sensoren in Home Assistant sichtbar machen.
- „Financial Fitness“ als **Badges**/Ampelstatus auf Dashboards.

## Warum Ecosystem?
- HACS ist Home Assistants Community Store für **community-made integrations & UI elements** und richtet sich eher an fortgeschrittene Nutzer; es ist ein eigenes Ökosystem mit eigener Distribution.

## Scope (Minimal) — v1 des Epics
- Read-only Datenexport aus dem Finanztool:
  - `monthly_subscription_total`
  - `next_due_subscription` (Datum + Name optional)
  - `active_subscriptions_count`
  - optional: `financial_fitness_score` (einfacher Index, später verfeinerbar)

- Home Assistant Seite:
  - Custom Integration, die diese Werte als Sensoren bereitstellt
  - Installation/Distribution über HACS (Custom Integration landet unter `custom_components/`)

## Non-Goals (für v1)
- Kein Schreibzugriff aus Home Assistant (nur read-only)
- Keine „deep analytics“ im HA (Charts/Trends bleiben im Finanztool)

## Security & Privacy Notes (wichtig!)
- **Data minimization**: Home Assistant soll bevorzugt aggregierte/abgeleitete Werte bekommen (Summe, Count), nicht Rohdaten.
- Integration-Auth:
  - eigener read-only Zugriff (z.B. Integration Token / API Key) getrennt vom normalen User-Login
  - Rate limiting für den Integration Endpoint
- Logging: keine sensitiven Payloads loggen (nur Status/Fehlercodes)

## Akzeptanzkriterien (um später zu promoten)
- HA kann mindestens 2 Sensoren zuverlässig anzeigen (z.B. Summe + nächste Fälligkeit)
- Setup ist dokumentiert (HACS Install, Konfiguration, Troubleshooting)
- Kein Secret im Repo, kein Secret in Logs

## Offene Fragen
- Welche Daten sind „safe by default“ für Dashboards?
- Wie sieht ein read-only Token Modell aus, ohne den normalen Login zu belasten?

---

# EPIC 02 — Bankanbindung / Open Banking (optional) vs. CSV Import/Export

## Tags
- target: icebox
- type: epic
- area: integration, security
- risk: high
- privacy: high
- decision: open
- deps: consent/auth flow, token storage, provider choice, threat model deep-dive

## Motivation / Nutzerwert
- Automatischer Import von Umsätzen könnte den Nutzen massiv erhöhen (weniger manuell).
- Gleichzeitig ist das „privateste vom privaten“ und potenziell eine Hürde für Nutzer (und für dich persönlich).

## Warum Ecosystem?
- Eine Bankanbindung hängt fast immer von **externen APIs, OAuth/Consent, Token Handling und Drittparteien** ab.
- Viele Integrationsansätze setzen auf OAuth 2.0 Authorization Code Flow, Consent Screens, Token Refresh etc.
- Dadurch steigt die Angriffsfläche und der Security-Aufwand deutlich.

## Optionen (bewusst offen halten)
### Option A — CSV Import/Export (Core, aber später)
- Low risk / high privacy
- Keine externen Credentials
- Passt gut zu selfhosted/out-of-the-box
> Hinweis: Das ist eigentlich eher „Core“ als „Ecosystem“, aber wird hier als Alternative dokumentiert.

### Option B — Aggregator (Plaid/TrueLayer/Tink etc.)
- Schneller Start, viele Banken
- Aber: externe Abhängigkeit, oft laufende Kosten, Credentials/Consent zwingend

### Option C — Direktintegration einzelner Banken
- Max Kontrolle, aber hoher Aufwand pro Bank und starke Varianz

## Scope (Minimal) — v1 des Epics (wenn überhaupt)
- Read-only Import: **Kontoumsätze** (keine Zahlungsinitiierung)
- Normalisierung: Kategorien/Mapping optional, erstmal Rohimport + einfache Regeln
- „Privacy first“ Defaults:
  - Import ist opt-in
  - klare Consent/Scope Anzeige
  - minimale Speicherung (nur was für Features nötig ist)

## Security & Privacy Notes (kritisch)
- Token Handling:
  - Tokens dürfen nie im Repo landen
  - Tokens müssen geschützt gespeichert werden (encrypted at rest im Rahmen der App-Strategie)
- Consent/Revocation:
  - Nutzer muss Zugriff widerrufen können
- Monitoring/Rate limiting:
  - APIs werden limitiert; robustes Error Handling nötig
- API Security ist in Open Banking ein zentrales Thema (Auth, Consent, Rate limiting, Data protection).

## Non-Goals (für v1)
- Keine Zahlungsinitiierung (Payment initiation)
- Keine „always on“ Automatisierung ohne Nutzerkontrolle
- Kein Zwang zur Bankintegration für Kernnutzen

## Akzeptanzkriterien (um später zu promoten)
- Klare Entscheidung für Option A/B/C (ADR erforderlich)
- Vollständiges Threat Model Update (docs/08-threat-model.md) für Bankfluss
- Minimaler Consent/Token Lifecycle ist dokumentiert
- Nutzer kann Import sauber deaktivieren und Daten löschen (Privacy)

## Offene Fragen
- Will das Projekt überhaupt „Bankdaten live” anfassen oder bleibt es bei CSV?
- Welche Länder/Banken wären überhaupt realistisch (PSD2/Provider)?
- Wie bleibt das Setup out-of-the-box und trotzdem sicher?

---

# EPIC 03 — E-Mail Benachrichtigungen (Abo-Erinnerungen & Spar-Alerts)

## Tags
- target: icebox
- type: epic
- area: ux, integration
- risk: low
- privacy: medium
- decision: open
- deps: SMTP/E-Mail-Infrastruktur, opt-in Konfiguration pro Modul, Modul-System (v0.2.0)

## Motivation / Nutzerwert
- Abo-Manager: Nutzer erhält eine E-Mail wenn ein teures oder selten genutztes Abo fällig wird.
  Frage: “Nutzt du dieses Abo noch?” — mit Direktlink zum Suspend.
- Urlaubskasse: Nutzer erhält eine E-Mail wenn er mit dem Sparen hinterher hängt.
- Fondsparen: monatliche Erinnerung an die Sparrate.

## Scope (Minimal) — v1 des Epics
- SMTP-Konfiguration im Admin-Bereich (Server, Port, Absender-Adresse)
- Pro Modul ein opt-in Toggle: E-Mail-Erinnerungen aktivieren
- Abo-Manager: monatliche Zusammenfassung + Erinnerung 3 Tage vor Fälligkeit
- Kein fancy Template — plain text ist ok für v1

## Non-Goals (für v1)
- Push-Notifications (App, Browser)
- Komplexe Scheduling-Plattform
- Mehrere Empfänger pro Benachrichtigung

## Security & Privacy Notes
- E-Mail-Adressen und SMTP-Credentials dürfen nie im Repo landen
- Konfiguration per `.env` + Admin-UI
- Opt-in: kein Nutzer bekommt ungefragt E-Mails

## Akzeptanzkriterien (um später zu promoten)
- Nutzer kann SMTP-Einstellungen im Admin-Bereich hinterlegen und testen (“Test-Mail senden”)
- Mindestens ein Modul (Abo-Manager) sendet Erinnerungen korrekt
- E-Mails können pro Modul deaktiviert werden

## Offene Fragen
- Welche E-Mail-Bibliothek? (Python: `smtplib` / `fastapi-mail` / `aiosmtplib`)
- Wie werden die Erinnerungen zeitgesteuert ausgelöst? (Cronjob im Container, APScheduler, …)

---

# EPIC 04 — CSV Import & Reality Check

## Tags
- target: icebox
- type: epic
- area: integration, core
- risk: medium
- privacy: high
- decision: open
- deps: CSV-Parser, Modul-System (v0.2.0), Abo-Manager Suspend-Funktion

## Motivation / Nutzerwert
Nutzer können einen echten Kontoauszug (CSV-Export der Bank) importieren.
Das System gleicht die realen Buchungen mit den eingetragenen Abos ab:

- **Abo-Manager Reality Check:** Wurde dieses Abo wirklich abgebucht? Oder schon nicht mehr (weil suspend gedrückt)?
- **Urlaubskasse Reality Check:** Sind die Spar-Einlagen auf dem echten Konto gelandet?
- **Haushaltsbuch:** Echte Ausgaben aus dem Kontoauszug direkt als Buchungen einspielen.

## Scope (Minimal) — v1 des Epics
- CSV-Upload im Admin-Bereich (kein automatischer Bankzugang — nur Datei-Upload)
- Normalisierung: Datum, Betrag, Verwendungszweck (spaltenbasiert, konfigurierbar)
- Matching-Logik: Welche Buchung passt zu welchem Abo? (nach Betrag + Datum-Nähe)
- Anzeige: “Gematcht”, “Nicht gefunden”, “Überschuss”

## Non-Goals (für v1)
- Kein automatischer Bankzugang (Open Banking) — das ist EPIC 02
- Keine KI-basierte Kategorisierung
- Kein Export aus dem Tool heraus

## Security & Privacy Notes
- CSV-Dateien enthalten hochsensible Finanzdaten — sie dürfen NICHT dauerhaft gespeichert werden
- Import ist ein einmaliger Vorgang: CSV einlesen → Matching → Ergebnis anzeigen → Datei wegwerfen
- Kein Logging der Buchungsinhalte

## Akzeptanzkriterien (um später zu promoten)
- Nutzer kann CSV hochladen und bekommt eine verständliche Matching-Übersicht
- Nicht gematchte Buchungen sind klar als solche gekennzeichnet
- CSV wird nach dem Import nicht gespeichert (Privacy by Design)
- Threat Model Update (docs/08-threat-model.md) für CSV-Upload-Fluss

## Offene Fragen
- Welche CSV-Formate? (Deutsche Banken exportieren unterschiedlich — DKB, Sparkasse, ING, …)
- Spalten-Mapping: fix oder konfigurierbar vom Nutzer?
- Wie viel “Fuzzy Matching” ist sinnvoll (Betrag ±X%, Datum ±Y Tage)?

---

# EPIC 05 — Gemeinsame Bereiche (Shared Contexts für Module)

## Tags
- target: icebox
- type: epic
- area: core, ux
- risk: medium
- privacy: medium
- decision: open
- deps: Modul-System (v0.2.0), Kontext-Modell (docs/13-rbac-vision.md), mind. 1 Modul implementiert

## Motivation / Nutzerwert
Manche Module sollen mehrere User gemeinsam nutzen können:
- Gemeinsames Sparfach (Familie zahlt gemeinsam ein)
- Gemeinsame Urlaubskasse (Paar spart zusammen)
- Gemeinsames Haushaltsbuch (Wer hat was bezahlt?)

Aktuell ist jedes Modul strikt pro-User (wie Abos). Dieses Epic fügt den Gedanken der **geteilten Bereiche** hinzu.

## Scope (Minimal) — v1 des Epics
- Mindestens ein Modul (z.B. Urlaubskasse) bekommt die Option “Gemeinsam”
- Gemeinsam = mehrere User sehen und bearbeiten denselben Datensatz
- Einladung: Admin fügt User einem gemeinsamen Bereich hinzu
- Berechtigungen innerhalb des gemeinsamen Bereichs: alle dürfen einzahlen, nur Admin/Owner darf löschen

## Abhängigkeit
Dieses Epic baut auf dem Kontext-Modell auf (docs/13-rbac-vision.md).
Erst wenn das Kontext-Modell entschieden ist, kann dieses Epic konkret werden.

## Akzeptanzkriterien (um später zu promoten)
- Klare Entscheidung: Wie hängen Kontext-Modell und geteilte Module zusammen? (ADR erforderlich)
- Mindestens ein Modul mit “Gemeinsam”-Funktion vollständig implementiert und getestet

---

# EPIC 06 — Backup-Anleitung & Datensicherung

## Tags
- target: icebox
- type: epic
- area: ops
- risk: high
- privacy: high
- decision: leaning
- deps: ADR 0010 (lokales Dateisystem für User-Uploads)

## Motivation / Nutzerwert
Ab v0.2.2 speichert die App Dateien außerhalb der Datenbank (Logos unter `/uploads/`).
Ein reines `pg_dump` erfasst diese Dateien nicht. Nutzer, die nur die Datenbank sichern,
verlieren beim Wiederherstellen alle hochgeladenen Logos — ohne Fehlermeldung.

Dieses Epic adressiert das Risiko mit Dokumentation und optional einem einfachen Backup-Skript.

## Optionen (bewusst offen halten)

### Option A — Backup-Anleitung in der Dokumentation
- Erklärt welche Volumes gesichert werden müssen: PostgreSQL-Daten + `/uploads`-Volume
- Zeigt ein konkretes Beispiel mit `pg_dump` + `tar` für das Upload-Verzeichnis
- Low risk, sofort umsetzbar

### Option B — Backup-Skript im Repo
- Shell-Skript (`scripts/backup.sh`) das `pg_dump` + Upload-Volume-Archiv kombiniert
- Kann per Cronjob auf dem Server geplant werden
- Ergebnis: eine einzige `.tar.gz`-Datei pro Tag

### Option C — Backup-Service im docker-compose
- Zusätzlicher Container (z.B. `offen/docker-volume-backup`) der automatisch sichert
- Neue externe Abhängigkeit, aber vollständig automatisiert

## Scope (Minimal) — v1 des Epics
- Mindestens Option A umsetzen (Dokumentation)
- Option B (Skript) als sinnvolle Erweiterung

## Non-Goals (für v1)
- Kein Off-Site-Backup (S3, SFTP) — das ist bewusste Eigenverantwortung des Selfhosters
- Keine Backup-Überwachung / Alerting

## Security & Privacy Notes
- Backup-Dateien enthalten Finanzdaten und sind hochsensibel
- Backup-Zielverzeichnis sollte außerhalb des Web-Roots liegen
- Dokumentation muss Dateiberechtigungen und Verschlüsselungsempfehlung (z.B. `gpg`) erwähnen

## Akzeptanzkriterien (um später zu promoten)
- Dokumentation erklärt alle zu sichernden Daten vollständig
- Nutzer kann Backup erstellen und eine leere Instanz daraus wiederherstellen
- Backup-Anleitung ist Teil der offiziellen Setup-Dokumentation

---

# EPIC 07 — Bank Transactions + Subscription Matching Flow (CSV-first)

## Tags
- target: icebox
- type: epic
- area: integration, core
- risk: high
- privacy: high
- decision: open
- deps: EPIC 04 (CSV Import), Slice F (`subscription_scheduled_payments`), Modul-Konfiguration pro User

## Motivation / Nutzerwert
Das Budget Book soll nicht nur Planwerte zeigen, sondern reale Kontobewegungen gegen den Abo-Manager prüfen.
Dadurch wird sichtbar:
- wurde ein aktives Abo tatsächlich abgebucht?
- fehlt eine erwartete Abbuchung?
- wurde trotz gekündigtem/inaktivem Abo trotzdem gebucht?

## Kontext (Gedanke in einem Satz)
Soll-Buchungen kommen aus dem Abo-Kontext (planbar), Ist-Buchungen aus CSV-Import (real), und ein Matching verbindet beides nachvollziehbar.

## Datenmodell (Vorschlag, detailliert)

### 1) bank_transactions
Zweck: persistierte, normalisierte Ist-Buchungen aus CSV-Import.

Pflichtfelder (MVP-nahe):
- `id` (uuid, pk)
- `user_id` (uuid, fk -> users.id)
- `transaction_date` (date, not null)
- `amount` (numeric(10,2), not null)
- `currency` (varchar(3), default EUR)
- `description_raw` (text, not null)

Sinnvolle Zusatzfelder:
- `booking_date` (date, nullable)
- `counterparty` (varchar(255), nullable)
- `iban_masked` (varchar(34), nullable)
- `reference_raw` (text, nullable)
- `import_batch_id` (uuid, fk -> import_batches.id)
- `matched_payment_id` (uuid, fk -> subscription_scheduled_payments.id, nullable)
- `match_confidence` (numeric(5,2), nullable)
- `created_at`, `updated_at`

Index-Ideen:
- `(user_id, transaction_date)`
- `(user_id, amount)`
- `(matched_payment_id)`

Privacy-Hinweis:
- nur nötige Rohdaten speichern
- keine CSV-Datei als Dateiobjekt dauerhaft halten
- sensible Felder ggf. maskieren/reduzieren

### 2) subscription_scheduled_payments (Abhängigkeit aus Slice F)
Zweck: Soll-Buchungen zum Stichtag, robust und idempotent erzeugt.

Wesentliche Felder:
- `id` (uuid, pk)
- `subscription_id` (uuid, fk)
- `user_id` (uuid, fk)
- `due_date` (date, not null)
- `expected_amount` (numeric(10,2), not null)
- `currency` (varchar(3), default EUR)
- `status` (zunächst: `pending | matched | missed`)
- `bank_transaction_id` (uuid, fk -> bank_transactions.id, nullable)
- `matched_at` (timestamptz, nullable)
- `created_at`, `updated_at`

Harte Doppelbuchungsbremse:
- eindeutiger Constraint auf `(subscription_id, due_date)`
- Scheduler und manueller Trigger müssen per upsert/no-op arbeiten

## Matching-Flow (CSV-first)

1. CSV importieren und in `bank_transactions` normalisieren.
2. Offene Soll-Buchungen (`status = pending`) für den User laden.
3. Kandidaten je Soll-Buchung suchen:
- Betrag exakt oder in enger Toleranz
- Datum innerhalb definierter Fensterlogik
- Text-Hinweise (`name`/Provider vs. `description_raw`)
4. Bei eindeutigem Treffer:
- Soll-Buchung auf `matched`
- Verknüpfung in beide Richtungen setzen
5. Bei ausbleibendem Treffer nach Frist:
- Soll-Buchung auf `missed`
6. Sonderfall: Treffer für Abo mit Status `canceled` oder `suspended`:
- als Warnfall markieren (später eigenes Event/Status möglich)

## Notification-Idee (Warnfall)
Vorschlagstext für später:
"Unerwartete Abbuchung erkannt: Für dein inaktives Abo wurde eine Kontobewegung gefunden. Bitte prüfe, ob das Abo noch aktiv ist oder ob die Buchung ignoriert werden soll."

## Konfigurationsgedanke pro User (Modul-Ebene)
Für Abo-Manager sollen kombinierbar sein:
- `subscription_cumulative_calculation` (an/aus)
- `subscription_booking_history` (an/aus)
Beide können gleichzeitig aktiv sein.

Namensregel (verbindlich):
- Modul-spezifische JSONB-Flags bekommen immer ein Modul-Prefix (`<modul>_<feature_flag>`)
- Hintergrund: verhindert Key-Kollisionen zwischen Modulen in derselben `config`-Struktur

Implikation fuer UI/Backend:
- Profile Settings des Users muessen die namespaceten Keys explizit anbieten und persistieren
- Service-Validierung soll nur bekannte Keys pro Modul akzeptieren (Whitelist statt freier String-Keys)

## Offene Architekturfragen (bewusst notiert)
- Wie streng ist Betrag-/Datums-Toleranz im ersten Wurf?
- Ab wann gilt eine Soll-Buchung als `missed` (z. B. +3/+5/+7 Tage)?
- Braucht es früh ein manuelles Rematching im UI?
- Wie gehen wir mit Sammelbuchungen um (ein Betrag für mehrere Services)?

## Originalfragen als Gedächtnisspeicher (bewusst persönlich)
- "Welche Komponente sorgt dafür, dass zum Abrechnungsstichtag auch wirklich ein Wert geschrieben wird?"
- "Was passiert, wenn CSVs zeitlich verspätet importiert werden?"
- "Welchen Status zeigen wir, wenn noch keine Kontobuchung gefunden wurde?"
- "Wie reagieren wir, wenn trotz inaktivem/gekündigtem Abo eine echte Buchung eingeht?"

## Akzeptanzkriterien (um später zu promoten)
- Datenmodell für `bank_transactions` ist per ADR oder Schema-Skizze festgelegt
- Matching-Status und Fristen sind fachlich entschieden
- Privacy-Entscheidung ist dokumentiert (Speicherdauer, Maskierung, Logging)
- End-to-End Testfall ist beschreibbar: CSV rein -> Match/No-Match -> nachvollziehbarer Status