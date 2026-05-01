# ADR 0007: Use JSONB for extensible module configuration

## Status
Accepted

## Kontext
Ab v0.2.0 unterstützt BB-myBudgetBook ein erweiterbares Modul-System mit sechs Kernmodulen
(Abo-Manager, Sparfach, Urlaubskasse, Haushaltsbuch, Fondsparen, Aktiendepot).
Neue Module sollen in Zukunft ohne Architekturanpassung hinzugefügt werden können.

Frage: Wie werden Modul-Konfigurationen in der Datenbank gespeichert?

Die Entscheidung **wer** über Modul-Sichtbarkeit entscheidet (Admin vs. User)
ist eine separate Architekturentscheidung — siehe ADR 0008.

---

## Entscheidung

Modul-Konfigurationen werden als JSONB-Felder in zwei Tabellen gespeichert:

- `app_settings.modules` (systemweit, Admin-Hoheit): Welche Module sind generell verfügbar?
- `user_settings.modules` (pro User, User-Hoheit): Welche Module will dieser User nutzen?

Beispiel `app_settings.modules`:
```json
{ "subscriptions": true, "savings_box": true, "vacation_fund": false }
```

Beispiel `user_settings.modules` (User hat nur Sparfach aktiviert):
```json
{ "savings_box": true, "subscriptions": false }
```

---

## Alternativen

### Alternative A — Boolean-Spalten pro Modul (z.B. `subscriptions_enabled BOOLEAN`)
- Pro: starke DB-seitige Typsicherheit, direkte SQL-Queries ohne JSON-Parsing
- Contra: jedes neue Modul erfordert eine Alembic-Migration für `app_settings` **und**
  `user_settings` — bei 6+ Modulen und wachsendem Katalog nicht tragbar

### Alternative B — Separate `module_config`-Tabelle (eine Zeile pro Modul pro User)
- Pro: flexibel, erweiterbar um Modul-spezifische Metadaten pro User
- Contra: viele Joins, komplexere Queries, Overhead für einfache Ein/Aus-Semantik;
  Modul-spezifische Konfiguration kann besser innerhalb des jeweiligen Moduls leben

### Alternative C — Einheitliche Tabelle statt zwei (app_settings + user_settings)
- Pro: einfacher
- Contra: vermischt Admin-Hoheit (systemweit) mit User-Hoheit (persönlich);
  Separation of Concerns und RBAC-Konformität sprechen klar dagegen

---

## Konsequenzen

**Pro:**
- Neues Modul hinzufügen = neuer Key im JSONB + neues Objekt in `MODULE_REGISTRY` —
  keine Datenbank-Migration nötig
- Admin- und User-Einstellungen leben sauber getrennt in zwei Tabellen

**Contra / Risiken:**
- JSONB bietet keine DB-seitige Typsicherheit für erlaubte Keys — ungültige Module-Keys
  werden auf Applikationsebene abgefangen: `services/profile.py` validiert in
  `PATCH /profile/settings` jeden eingehenden Key gegen `MODULE_REGISTRY` und wirft HTTP 400
  bei unbekannten oder Admin-seitig gesperrten Keys
- Für komplexe SQL-Reports über Modul-Nutzung sind JSONB-Queries aufwändiger
  (kein Index per Default — bei Bedarf GIN-Index auf beide `modules`-Felder ergänzen)

**Verwandte Entscheidung:** ADR 0008 legt fest, wie die Sichtbarkeitslogik über die
gespeicherten Werte berechnet wird.
