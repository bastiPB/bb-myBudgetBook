# v0.2.5 - Subscription Service Refactor

Status: draft
Stand: 2026-05-07
Referenzen:
- v0.2.4 Intervallwechsel: [21-v024-subscription-interval-change.md](21-v024-subscription-interval-change.md)
- Architekturuebersicht: [09-architecture-overview.md](09-architecture-overview.md)
- Definition of Done: [06-definition-of-done.md](06-definition-of-done.md)

---

## Ziel

`backend/app/services/subscriptions.py` ist inzwischen sehr gross und enthaelt mehrere fachlich unterschiedliche Verantwortlichkeiten:

- Zugriffsschutz und 404/403-Helfer
- Listen- und Detail-Reads
- Billing-Algorithmen
- Billing-History-Schreiblogik
- Lifecycle-Aktionen wie Pausieren, Fortsetzen, Kuendigen
- Scheduler-nahe Hilfsfunktionen
- Logo-Upload und Dateisystemlogik

v0.2.5 soll diese Datei in ein uebersichtliches Package aufteilen, ohne das Verhalten der Anwendung zu aendern.

Das Ziel ist bessere Wartbarkeit fuer Menschen und KI-Assistenten:

- kleinere Dateien
- klarere Aenderungsgruende
- weniger Kontextdruck
- stabilere Reviews
- einfachere Tests pro Fachbereich

---

## Kernentscheidung

`app.services.subscriptions` wird von einer einzelnen Datei zu einem Package.

Alt:

```text
backend/app/services/subscriptions.py
```

Neu:

```text
backend/app/services/subscriptions/
  __init__.py
  access.py
  billing.py
  constants.py
  lifecycle.py
  logos.py
  mutations.py
  readers.py
  types.py
```

Die oeffentliche Import-Oberflaeche bleibt stabil.

Router und andere Services duerfen weiterhin importieren:

```python
from app.services.subscriptions import (
    create_subscription,
    get_subscription_detail,
    price_change,
)
```

`__init__.py` re-exportiert die oeffentlichen Funktionen aus den internen Modulen.

---

## Nicht-Ziele

v0.2.5 ist ein reiner Struktur-Refactor.

Nicht Teil von v0.2.5:

- keine neue Fachlogik
- keine neuen API-Endpunkte
- keine DB-Migration
- keine UI-Aenderungen
- keine Umbenennung von Schemas oder Models
- keine Veraenderung der Fehlersemantik
- keine algorithmische Optimierung ausser dort, wo sie zwingend durch den Split noetig wird

Wenn waehrend des Refactors ein Bug auffaellt, wird er dokumentiert und separat entschieden.

---

## Zielstruktur

### `constants.py`

Enthaelt Konstanten, die von mehreren Modulen gebraucht werden.

```python
_MONTHLY_FACTOR
_MONTHS_PER_PERIOD
_ALLOWED_LOGO_TYPES
_MAX_LOGO_SIZE_BYTES
_LOGO_EXT
```

Hinweis:
- Logo-Konstanten koennen alternativ in `logos.py` bleiben, wenn sie nur dort genutzt werden.
- Billing-Konstanten gehoeren in `constants.py`, weil Scheduler und Billing-Algorithmen sie brauchen.

### `types.py`

Enthaelt kleine interne Dataclasses und reine Transporttypen.

```python
@dataclass
class OverviewResult:
    monthly_total: Decimal
    upcoming: list[Subscription]

@dataclass
class ComputedDue:
    due_date: date
    amount: Decimal
    interval: BillingInterval
    billing_entry_id: uuid.UUID | None = None
```

### `access.py`

Enthaelt gemeinsame Zugriffshilfen.

```python
def _get_subscription_or_raise(session: Session, subscription_id: uuid.UUID) -> Subscription
def _check_ownership(sub: Subscription, user_id: uuid.UUID) -> None
```

Diese Funktionen bleiben intern.

### `billing.py`

Enthaelt reine Berechnungen und Billing-History-Algorithmen.

Beispiele:

```python
compute_due_dates
compute_next_due_date
compute_next_due_date_from_history
compute_due_dates_for_billing_history
applicable_billing_terms
applicable_price
sync_subscription_billing_snapshot
compute_tatsaechlich
compute_intervalle
compute_dieses_kalenderjahr
is_in_pause
```

Regel:
- So wenig DB-Zugriff wie moeglich.
- Pure Funktionen bevorzugen.
- Gut isoliert testbar.

Hinweis zu `sync_subscription_billing_snapshot`:
Setzt `sub.amount` und `sub.interval` aus der Billing-Historie — nur **In-Memory** auf dem ORM-Objekt, **kein** `session.commit()`.
Gehoert weiterhin zu `billing.py`, weil die Auswahl der gueltigen Terms rein algorithmisch ist.

Hinweis zu `applicable_price`:
`applicable_price` wird intern von `delete_price_history_entry` in `mutations.py` benoetigt.
Das geschieht als modul-interner Import (`from .billing import applicable_price`) — kein Public-Re-Export in `__init__.py` noetig.

### `readers.py`

Enthaelt lesende Service-Funktionen, die Daten laden und Response-nahe Objekte bauen.

Beispiele:

```python
subscription_to_read
list_subscriptions
get_overview
get_subscription
get_subscription_detail
get_price_history
get_billing_history
get_scheduled_payments
```

Regel:
- Kein Commit.
- Keine Dateioperationen.
- Keine Statuswechsel.

### `mutations.py`

Enthaelt schreibende Abo- und Billing-History-Funktionen.

Beispiele:

```python
create_subscription
update_subscription
price_change
interval_change
delete_price_history_entry
delete_billing_history_entry
```

Regel:
- Transaktionen und `session.commit()` leben hier, wenn sie fachlich zu Abo/Billing-Aenderungen gehoeren.
- Cache-Sync fuer `sub.amount` und `sub.interval` passiert hier nach Billing-History-Aenderungen.

### `lifecycle.py`

Enthaelt Statuswechsel und Lebenszyklus-Aktionen.

Beispiele:

```python
suspend_subscription
resume_subscription
cancel_subscription
delete_subscription
```

Regel:
- Lifecycle ist nicht Billing-History.
- Pausen-History darf hier geschrieben werden.
- Detail-Response kann aus `readers.get_subscription_detail` kommen.

### `logos.py`

Enthaelt Dateisystemlogik fuer Logo-Uploads.

Beispiele:

```python
upload_subscription_logo
```

Regel:
- Dateisystemzugriffe sind hier isoliert.
- DB-Update fuer `logo_url` bleibt hier, weil es Teil des Upload-Flows ist.

### `__init__.py`

Re-exportiert die oeffentliche API.

Beispiel:

```python
from .billing import (
    compute_due_dates,
    compute_due_dates_for_billing_history,
    compute_next_due_date,
    compute_next_due_date_from_history,
    is_in_pause,
)
from .lifecycle import (
    cancel_subscription,
    delete_subscription,
    resume_subscription,
    suspend_subscription,
)
from .logos import upload_subscription_logo
from .mutations import (
    create_subscription,
    delete_billing_history_entry,
    delete_price_history_entry,
    interval_change,
    price_change,
    update_subscription,
)
from .readers import (
    get_billing_history,
    get_overview,
    get_price_history,
    get_scheduled_payments,
    get_subscription,
    get_subscription_detail,
    list_subscriptions,
    subscription_to_read,
)
```

---

## Import-Regeln

### Erlaubt

Interne Module duerfen gemeinsame Helfer importieren:

```python
from .access import _check_ownership, _get_subscription_or_raise
from .billing import compute_due_dates_for_billing_history
from .constants import _MONTHS_PER_PERIOD
from .types import ComputedDue
```

Router und externe Services importieren bevorzugt nur aus:

```python
app.services.subscriptions
```

### Vermeiden

Keine zyklischen Imports.

Besonders vorsichtig:

- `readers.py` darf nicht breit aus `mutations.py` importieren.
- `mutations.py` darf fuer Detail-Responses gezielt `readers.get_subscription_detail` importieren, falls noetig.
- `billing.py` sollte nicht aus `readers.py`, `mutations.py` oder `lifecycle.py` importieren.

Wenn ein zyklischer Import entsteht, ist das ein Zeichen, dass eine Funktion in ein falsches Modul gerutscht ist.

---

## Refactor-Strategie

Dieser Refactor soll in kleinen, mechanischen Schritten erfolgen.

Grundregel:

```text
Erst verschieben, dann testen.
Keine Logik gleichzeitig aendern.
```

### Schritt 1 - Package anlegen

Erstellen:

```text
backend/app/services/subscriptions/
```

Dann die alte Datei `backend/app/services/subscriptions.py` entfernen oder in das Package ueberfuehren.

Wichtig:

Python kann nicht gleichzeitig eine Datei `subscriptions.py` und ein Package `subscriptions/` mit gleichem Namen im selben Ordner sauber verwenden.

Darum muss die Umstellung in einem konsistenten Schritt passieren:

1. Inhalte in neue Package-Dateien verschieben.
2. `subscriptions.py` entfernen.
3. `subscriptions/__init__.py` mit Re-Exports erstellen.
4. Imports testen.

### Schritt 2 - Konstanten und Typen verschieben

Verschieben:

```text
constants.py
types.py
```

Keine fachliche Aenderung.

### Schritt 3 - Access-Helfer verschieben

Verschieben:

```text
access.py
```

Danach interne Imports anpassen.

### Schritt 4 - Billing-Algorithmen verschieben

Verschieben:

```text
billing.py
```

Danach Tests fuer reine Algorithmen ausfuehren.

### Schritt 5 - Reader verschieben

Verschieben:

```text
readers.py
```

Danach Router-Imports ueber `app.services.subscriptions` testen.

### Schritt 6 - Mutations verschieben

Verschieben:

```text
mutations.py
```

Danach price-change, interval-change, create/update und Delete-History-Tests ausfuehren.

### Schritt 7 - Lifecycle verschieben

Verschieben:

```text
lifecycle.py
```

Danach suspend/resume/cancel/delete testen.

### Schritt 8 - Logos verschieben

Verschieben:

```text
logos.py
```

Danach Logo-Upload-Tests oder mindestens Import-/Smoke-Test ausfuehren.

---

## Akzeptanzkriterien

### A-01: Public Imports bleiben stabil

Folgender Import muss weiterhin funktionieren:

```python
from app.services.subscriptions import create_subscription, get_subscription_detail
```

### A-02: Router muss nicht fachlich umgebaut werden

`backend/app/routers/subscriptions.py` soll nur dann angepasst werden, wenn Imports explizit auf Untermodul-Pfade zeigen.

Ziel:

```python
from app.services.subscriptions import ...
```

bleibt gueltig.

### A-03: Scheduler-Imports bleiben stabil oder werden bewusst angepasst

Wenn `scheduler_service.py` aktuell Hilfsfunktionen aus `app.services.subscriptions` importiert, sollen diese Re-Exports erhalten bleiben.

Beispiel:

```python
from app.services.subscriptions import _MONTHS_PER_PERIOD, compute_due_dates, is_in_pause
```

Langfristig besser:

```python
from app.services.subscriptions import compute_due_dates, is_in_pause
```

Konstanten koennen weiterhin re-exportiert werden, wenn das den Refactor kleiner macht.

### A-04: Keine Verhaltensaenderung

Alle bestehenden Tests laufen unveraendert.

Wenn Snapshots oder Fehlertexte sich aendern, ist das kein reiner Refactor mehr und muss separat entschieden werden.

### A-05: Neue Dateigroessen bleiben handhabbar

Orientierungswert:

```text
billing.py    darf groesser sein, aber sollte fachlich geschlossen bleiben
readers.py    < 350 Zeilen
mutations.py  < 400 Zeilen
lifecycle.py  < 250 Zeilen
logos.py      < 150 Zeilen
```

Das sind keine harten Limits, sondern Warnlampen.
`readers.py` kann durch `get_subscription_detail` und den Bulk-Load in `list_subscriptions` schneller wachsen — die Detail-Logik ist typisch der Haupttreiber.

---

## Testplan

Backend:

```text
pytest
```

Gezielt:

```text
pytest backend/tests/test_subscriptions_v022.py
pytest backend/tests/test_subscriptions_v023.py
pytest backend/tests/test_subscriptions_v024.py
```

Import-Smoke-Test:

```python
from app.services.subscriptions import (
    create_subscription,
    get_subscription_detail,
    price_change,
    interval_change,
    upload_subscription_logo,
)
```

Falls es keinen v0.2.4-Test mehr gibt, entsprechend nur existierende Testdateien ausfuehren.

### `date.today`-Monkeypatch nach Package-Split

`test_subscriptions_v023.py` und `test_subscriptions_v024.py` setzen u.a. `monkeypatch.setattr("app.services.subscriptions.date", ...)`.
Im **Monolithen** wird `date.today()` ueber das eine Modul `app.services.subscriptions` aufgeloest.

Nach dem Split importiert jedes Untermodul (`billing.py`, `readers.py`, `mutations.py`, `lifecycle.py`, …) **`from datetime import date` eigenstaendig**.
Ein Patch nur auf `app.services.subscriptions.date` wirkt dann **nicht** mehr auf Code in `app.services.subscriptions.billing` usw. — die Tests koennen scheitern, obwohl die Produktionslogik unveraendert ist.

Vorgehen beim Splitten:

1. Im Package nach `date.today` suchen (z.B. `rg "date\\.today" backend/app/services/subscriptions/`).
2. Pro betroffenes Untermodul den Monkeypatch-Pfad anpassen, z.B. `app.services.subscriptions.billing.date`, oder
3. eine kleine Test-Hilfsfunktion nutzen, die dieselbe Fake-Date-Klasse auf **alle** genannten Modulstrings anwendet.

Ohne diesen Schritt widerspricht „alle Tests laufen unveraendert“ (A-04) der technischen Realitaet.

---

## Risiken

### R-01: Zirkulaere Imports

Groesstes Risiko beim Split.

Gegenmassnahmen:
- `billing.py` bleibt moeglichst pure.
- `access.py`, `constants.py`, `types.py` importieren nicht aus fachlichen Modulen.
- Re-Exports in `__init__.py` erst nach dem Split kontrollieren.

### R-02: Python-Modulkonflikt

Eine Datei `subscriptions.py` und ein Ordner `subscriptions/` mit gleichem Namen duerfen nicht parallel bestehen bleiben.

Gegenmassnahme:
- In einem Patch sauber umstellen.
- Danach Import-Smoke-Test ausfuehren.

### R-03: Tests importieren private Funktionen

Falls Tests direkt aus `app.services.subscriptions` private Helfer importieren, muessen diese entweder re-exportiert oder Tests angepasst werden.

Empfehlung:
- Re-export fuer bestehende Tests erlauben.
- Spaeter Tests gezielt auf Untermodul-Imports umstellen, wenn sinnvoll.

### R-04: Zu viele Aenderungen auf einmal

Der Refactor ist mechanisch, aber breit.

Gegenmassnahme:
- Keine Feature-Aenderungen in v0.2.5.
- Kleine Commits oder Chunks.
- Nach jedem Chunk Tests/import checks.

### R-05: Tests — `date.today`-Monkeypatch nach Split

Siehe Abschnitt **Testplan — `date.today`-Monkeypatch nach Package-Split**.
Gegenmassnahme: Patch-Ziele pro Untermodul pflegen oder zentrale Test-Hilfe; nach dem Verschieben `rg`/Review der Aufrufe.

### R-06: Bekannter Bug — falscher Fehlertyp in `delete_billing_history_entry`

`delete_billing_history_entry` wirft an zwei Stellen `PriceEntryDeleteBlockedError`
statt eines eigenen `BillingHistoryDeleteBlockedError`.

Das ist kein Refactor-Blocker — der Fehlertyp ist identisch, nur der Name ist irrefuehrend.
Nicht in v0.2.5 beheben (kein Verhaltens-Refactor), aber als Bug dokumentieren und separat entscheiden.

---

## Build Plan

### Chunk 1 - Atomarer Package-Cutover

Dateien:
- `backend/app/services/subscriptions.py` (entfaellt nach dem Cutover)
- `backend/app/services/subscriptions/__init__.py`
- `access.py`, `billing.py`, `constants.py`, `lifecycle.py`, `logos.py`, `mutations.py`, `readers.py`, `types.py`

Aufgaben:

- **Kein** Zustand mit paralleler `subscriptions.py` und leerem `subscriptions/`-Package ueber mehr als einen kurzen lokalen Zwischenschritt: Python kann nicht sinnvoll beides gleichzeitig importieren (siehe Schritt 1 unter Refactor-Strategie).
- Inhalt aus der Monolith-Datei in die Package-Module verschieben und interne Imports verdrahten; `__init__.py` re-exportiert die bisherige Public API.
- `subscriptions.py` loeschen.
- Import-Smoke-Test und erste `pytest`-Runde; Monkeypatch-Pfade in v023/v024 anpassen, sobald `date.today` in Untermodulen liegt.

### Chunk 2 - Constants, Types, Access

Dateien:
- `constants.py`
- `types.py`
- `access.py`
- alle betroffenen Imports

Aufgaben:
- Konstanten verschieben.
- Dataclasses verschieben.
- Zugriffshilfen verschieben.
- Import-Smoke-Test.

### Chunk 3 - Billing

Dateien:
- `billing.py`
- Tests fuer Abo-Algorithmen

Aufgaben:
- Reine Billing- und Datumsfunktionen verschieben.
- Existing tests laufen lassen.

### Chunk 4 - Readers

Dateien:
- `readers.py`
- `__init__.py`
- ggf. `routers/subscriptions.py`

Aufgaben:
- Lesende Service-Funktionen verschieben.
- Public Re-Exports aktualisieren.
- Router-Imports pruefen.

### Chunk 5 - Mutations

Dateien:
- `mutations.py`
- `__init__.py`

Aufgaben:
- Schreibende Funktionen verschieben.
- Billing-History-Delete und Change-Flows weiter re-exportieren.
- Tests fuer create/update/price_change/interval_change.

### Chunk 6 - Lifecycle

Dateien:
- `lifecycle.py`
- `__init__.py`

Aufgaben:
- suspend/resume/cancel/delete verschieben.
- Tests fuer Statuswechsel.

### Chunk 7 - Logos

Dateien:
- `logos.py`
- `__init__.py`

Aufgaben:
- Upload-Logik und Logo-Konstanten verschieben.
- Import- und Smoke-Test.

### Chunk 8 - Cleanup

Dateien:
- alle neuen Module
- tests

Aufgaben:
- Ungenutzte Imports entfernen.
- Re-Export-Liste in `__init__.py` finalisieren.
- `pytest` ausfuehren.
- CHANGELOG ergaenzen.

---

## CHANGELOG-Zeilen

```text
### Changed
- Subscription-Service intern in ein Package aufgeteilt (`billing`, `readers`, `mutations`, `lifecycle`, `logos`)
- Public Imports aus `app.services.subscriptions` bleiben stabil

### Internal
- `subscriptions.py` entflechtet, um Wartbarkeit und Testbarkeit zu verbessern
```

---

## Zusammenfassung

v0.2.5 ist ein reiner Struktur-Release.

Die fachliche Arbeit aus v0.2.4 bleibt unangetastet.
Der Subscription-Service wird so aufgeteilt, dass zukuenftige Aenderungen kleiner, lesbarer und risikoaermer werden.

Leitregel:

```text
Nach aussen bleibt app.services.subscriptions stabil.
Nach innen wird nach Verantwortlichkeit getrennt.
```
