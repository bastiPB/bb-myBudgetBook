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
- Will das Projekt überhaupt „Bankdaten live“ anfassen oder bleibt es bei CSV?
- Welche Länder/Banken wären überhaupt realistisch (PSD2/Provider)?
- Wie bleibt das Setup out-of-the-box und trotzdem sicher?