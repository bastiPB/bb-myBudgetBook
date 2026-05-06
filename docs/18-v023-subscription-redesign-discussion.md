# v0.2.3 Subscription Manager — Redesign-Diskussion

Status: ARBEITSDOKUMENT (wird gemeinsam überarbeitet)
Stand: 2026-05-05
Ziel: Alle Bugs + Design-Schwächen sammeln, Entscheidungen treffen, v0.2.3 vorbereiten
Akzeptanz-Szenarien (Testfälle): [docs/19-v023-test-scenarios.md](19-v023-test-scenarios.md)

---

## Implementierungsstand (2026-05-05) — Bereits umgesetzt

- Fix umgesetzt: `subscription_scheduled_payments.amount` ist nullable, damit `paused`-Perioden mit `amount = NULL` gespeichert werden koennen.
  - Migration: `backend/alembic/versions/2026-05-05-l2m3n4o5_v023_nullable_scheduled_payment_amount.py`
  - Model angepasst: `SubscriptionScheduledPayment.amount` optional/nullable
  - Schema angepasst: `ScheduledPaymentRead.amount` optional

- Fix umgesetzt: fehlende Dependency fuer `relativedelta` nachgezogen.
  - `python-dateutil` wurde in `backend/pyproject.toml` aufgenommen.

- Fix umgesetzt: Backend-Startfehler in `subscriptions` behoben.
  - Fehlender Import `dataclass` in `backend/app/services/subscriptions.py` ergaenzt.

- Fix umgesetzt: 500 auf `GET /subscriptions/{id}` behoben.
  - Ursache: `SubscriptionDetail` wurde direkt aus dem ORM-Objekt validiert, obwohl berechnete Pflichtfelder (`monatlich`, `tatsaechlich`, `intervalle`, `dieses_kalenderjahr`) zu diesem Zeitpunkt noch fehlten.
  - Loesung: zuerst Basis-Payload aus `SubscriptionRead` bauen, berechnete Felder ergaenzen, danach gegen `SubscriptionDetail` validieren.

- Fix umgesetzt: `POST /subscriptions/{id}/cancel` akzeptiert jetzt auch Requests ohne Body.
  - Router und Service wurden so angepasst, dass `payload` optional ist.
  - `access_until` wird dabei sauber auf `None` gesetzt, wenn kein Body mitgegeben wird.

- Fix umgesetzt: 500 auf `POST /subscriptions/{id}/cancel` behoben.
  - Ursache: der Endpoint hatte `response_model = SubscriptionDetail`, der Service gab aber nur ein `Subscription`-ORM-Objekt zurueck.
  - Loesung: `cancel_subscription(...)` gibt nach dem Commit jetzt `get_subscription_detail(...)` zurueck und liefert damit die vollstaendige Detail-Response mit berechneten Kennzahlen.

---

## 0) Fundament — Der Dreh- und Angelpunkt des gesamten Moduls

**Entschieden (2026-05-04):**

Der gesamte Subscription Manager baut auf genau zwei Eingaben auf:

> **"Wann hast du dieses Abo abgeschlossen?"** (Abschluss-Datum)
> **+ Abrechnungsintervall**

Das ist die menschlichste und pragmatischste Formulierung.
Kein User soll nachdenken ob er "Erste Zahlung", "Vertragsbeginn" oder "gültig ab" meint.
Er kennt das Datum an dem er auf "Abonnieren" geklickt hat — oder ungefähr, wenn er es nachträgt.

### Warum dieser Anker funktioniert

Aus `Abschluss-Datum` + `Interval` lässt sich ALLES ableiten:
- **Nächste Fälligkeit** = Abschluss-Datum + N × Interval (nächstes Datum >= heute, berechnet, nie gespeichert)
- **Tatsächlich** = Anzahl Perioden seit Abschluss × Preis (inkl. Preisänderungen, abzgl. Pausierungen)
- **Soll-Buchungen (Buchungshistorie)** = alle Fälligkeitsdaten von Abschluss bis heute im Interval-Raster

### Keine Einschränkung auf Vergangenheit oder Zukunft

Das Abschluss-Datum darf in der Vergangenheit liegen (auch 2-3 Jahre zurück — nachträgliche Erfassung)
und darf in der Zukunft liegen (z. B. "Ich bestelle Netflix ab 1. Juni").
Der User soll sich keine Gedanken darüber machen müssen.

### Wenn kein CSV-Bankimport genutzt wird

Wenn sich ein User bewusst gegen den Bankimport entscheidet (der später als separates Modul kommt),
ist `Abschluss-Datum + Interval` die einzige Quelle der Wahrheit.
Alle Berechnungen sind dann Schätzungen — und das soll transparent so kommuniziert werden.
Die Schätzung ist aber gut genug für den typischen Anwendungsfall.

### Was das für next_due_date bedeutet

`next_due_date` ist damit kein gespeichertes Feld mehr — es ist eine Berechnung.
Der User trägt es nie manuell ein. Er sieht es in der UI als berechneten Wert.
**Entscheidung: `next_due_date` wird abgeschafft als DB-Spalte und immer berechnet.**

### Umbenennung

Das Feld `started_on` wird in Concept und UI umbenannt zu:
- DB-Spalte bleibt technisch `started_on` (kein Breaking Change nötig)
- UI-Label: **"Abgeschlossen am"**
- Tooltip/Hilfetext: "Datum an dem du dieses Abo abgeschlossen hast"

---

## 0b) Die drei Kostenkennzahlen — neu definiert

### Bisheriges Modell (falsch / unvollständig)

| Kennzahl | Alte Berechnung | Problem |
|---|---|---|
| Monatlich | amount × Umrechnungsfaktor | OK für Projektion |
| Jährlich | Monatlich × 12 | Falsch: zeigt 60€ auch wenn Abo erst im Juli startete |
| Bisher Gezahlt | Segments × Preis | Buggy, 0-Fehler, Pausierungen nicht berücksichtigt |

### Neues Modell (pragmatisch, menschlich)

**Kennzahl 1: Monatlich** (unverändert, bleibt Projektion)
- Was würdest du bei gleichem Preis pro Monat zahlen?
- Normalisierter Wert: monatlicher Anteil des Abo-Betrags
- Beispiel: 60€/Jahr → 5€ monatlich
- Zweck: Vergleichbarkeit verschiedener Abos auf Monatsbasis

**Kennzahl 2: Dieses Kalenderjahr** (NEU — ersetzt "Jährlich × 12") — ENTSCHIEDEN
- Was zahlst du für dieses Abo im aktuellen Kalenderjahr (1. Jan bis 31. Dez)?
- Bezug: Kalenderjahr mit Berücksichtigung des Vertragsabschlussdatums
- Berücksichtigt: Abo-Startdatum, Pausierungen, Preisänderungen (inkl. zukünftige = Vorschau)
- Beispiel: Abo startet 3. Juli, monatlich 5€
  → Dieses Jahr (Jul–Dez): 6 × 5€ = **30€**
  → Nächstes Kalenderjahr (Jan–Dez): 12 × 5€ = **60€**
- Zweck: Jahresbudgetplanung — "Was kostet mich das dieses Jahr?"
- Zukünftige Preiseinträge (valid_from > heute) werden hier als Projektion EINGERECHNET

**Algorithmus "Dieses Kalenderjahr" (Pseudocode):**
```
jan_1  = date(today.year, 1, 1)
dez_31 = date(today.year, 12, 31)

perioden = alle due_dates im Interval-Raster (started_on + N × period_months)
           die in [jan_1 .. dez_31] fallen

total = 0
für jede periode:
    wenn periode in pause_history-Intervall → überspringen
    preis = neuester Eintrag aus price_history mit valid_from <= periode
            (inkl. Zukunfts-Einträge — Ankündigungen zählen hier als Projektion)
    total += preis
```

Beispiel (L-07, zweite Meinung): Abo ab 3. Sep 2025, monatlich 5€,
Preisankündigung 7€ ab 3. Okt 2026:
- Perioden in 2026: Jan–Sep (9× 5€ = 45€) + Okt–Dez (3× 7€ = 21€) = **66€**

**Kennzahl 3: Tatsächlich** (umgebaut — das war "Bisher Gezahlt")
- Stumpfe Summe aller Zahlungen seit Abschluss bis heute
- Berücksichtigt: Preisänderungen (nach valid_from-Datum), Pausierungen (Monat pausiert = Monat fehlt)
- Klartext-Algorithmus:
  ```
  Abo abgeschlossen: 3. Jan | Heute: 4. Mai | monatlich 5€ → 5 Perioden → 25€
  
  Ab August wird es 7€ (Preisankündigung eingetragen am 1. Aug, valid_from = Nov):
  Jan–Okt: 10 × 5€ = 50€
  Nov–Dez: 2 × 7€ = 14€
  → Tatsächlich bis Dez: 64€
  
  September pausiert → September wird nicht gezählt:
  Jan–Aug: 8 × 5€ = 40€ (September: 0€)
  Okt: 1 × 5€ = 5€
  Nov–Dez: 2 × 7€ = 14€
  → Tatsächlich bis Dez: 59€
  ```
- **Wichtig:** Zukünftige Preiseinträge (valid_from > heute) werden für "Tatsächlich" IGNORIERT,
  aber für "Dieses Kalenderjahr" als Projektion eingerechnet (Vorschau-Charakter)
- UI-Kennzeichnung: "ca." oder "~" da Schätzung ohne Kontoabgleich

**Algorithmus "Tatsächlich" (Pseudocode) — ersetzt den alten Segment-Algo:**
```
perioden = alle due_dates im Interval-Raster (started_on + N × period_months)
           die <= today liegen

total = 0
für jede periode:
    wenn periode in pause_history-Intervall → überspringen  ← Pause zählt nicht
    preis = neuester Eintrag aus price_history mit valid_from <= periode
            (NUR Vergangenheits-Einträge — valid_from > today wird ignoriert)
    total += preis
```

Ergebnis: stumpfe Summe aller nicht-pausierten Perioden bis heute, mit korrektem Preis je Periode.
Kein `+1`-Hack, kein Segment-Math — Periode zählen reicht.
BUG-02 und BUG-04 lösen sich durch diesen Ansatz automatisch auf.

### Zähler als Alternative zu Buchungshistorie (NEU)

Wenn der User die Buchungshistorie nicht aktiviert hat:
- Kein Scheduler, keine scheduled_payments-Tabelle wird befüllt
- Stattdessen: einfacher Zähler auf der Detailseite
- **"X Zahlungen in [Jahr]"** — berechnet aus Abschluss-Datum + Interval
- Beispiel: Abo 3. Jan, monatlich, heute 4. Mai → "5 Zahlungen in 2026"
- Technisch: dieselbe Berechnung wie "Tatsächlich", aber nur Anzahl (keine Summe)
- Kein DB-Eintrag nötig — reine Berechnung im Service

### Die Periode-Tabelle — das Herzstück der Buchungshistorie (NEU)

**Kernidee (2026-05-04):**
Die Buchungshistorie ist keine Liste von "Ereignissen" — sie ist eine vollständige
Periode-für-Periode-Ansicht. Jede Periode im Interval-Raster erscheint als eigene Zeile,
egal ob bezahlt, pausiert oder preisgeändert.

Beispiel (Abo: 3. Jan, monatlich 5€, September pausiert, Mai Preis auf 6€):

| Periode | Fälligkeitstag | Betrag | Status |
|---|---|---|---|
| Januar | 3.1. | 5,00€ | ✓ bezahlt |
| Februar | 3.2. | 5,00€ | ✓ bezahlt |
| März | 3.3. | 5,00€ | ✓ bezahlt |
| April | 3.4. | 5,00€ | ✓ bezahlt |
| Mai | 3.5. | 6,00€ | ✓ bezahlt (Preiserhöhung) |
| Juni | 3.6. | 6,00€ | ⏳ offen |
| ... | ... | ... | ... |
| September | 3.9. | – | ⏸ pausiert |
| Oktober | 3.10. | 6,00€ | ⏳ offen |

**Was das technisch bedeutet:**

1. "Tatsächlich" = Summe aller Zeilen mit Status ≠ pausiert, mit valid_from <= heute
2. "Zähler" = Anzahl aller Zeilen mit Status ≠ pausiert, im Kalenderjahr
3. Pausierte Perioden erscheinen als Zeile (nicht als Lücke) → vollständige, nachvollziehbare Historie

**Warum das ein fundamentales Problem mit dem aktuellen Scheduler aufdeckt:**

Der aktuelle Scheduler generiert ein `scheduled_payment` für **HEUTE** — nicht für den
berechneten Fälligkeitstag des Abos.

Beispiel: Abo abgeschlossen am 3. Januar (monatlich).
- Korrekter Fälligkeitstag im Mai: **3. Mai**
- Was der Scheduler tut: generiert einen Eintrag für **4. Mai** (heute)

Das ist falsch. Die Tabelle würde zeigen: "Fälligkeitstag: 4. Mai" statt "Fälligkeitstag: 3. Mai".

**Scheduler-Redesign erforderlich:**
- Scheduler berechnet den Fälligkeitstag aus `started_on + N × interval`
- Generiert Eintrag NUR wenn `today >= berechneter_fälligkeitstag` für diese Periode
- `due_date` im Eintrag = berechneter Fälligkeitstag (3. Mai), NICHT today (4. Mai)
- Pausierte Perioden: Eintrag wird generiert, aber mit Status `paused` (Betrag = 0 oder regulär, Kennzeichnung: pausiert)
- UNIQUE-Constraint bleibt: `(subscription_id, due_date)` — Idempotenz gesichert

**Benötigte Status-Werte (erweitert):**
- `pending` → Periode fällig, Zahlung noch nicht bestätigt
- `paused` → Abo war in dieser Periode pausiert, keine Zahlung erwartet  ← NEU
- `matched` → Zahlung per CSV-Import bestätigt (späterer Slice)
- `missed` → Periode abgelaufen, keine Zahlung erfolgt

**Kein `canceled`-Status in der Periode-Tabelle — warum:**
Bei Kündigung schreibt der Scheduler ab dem Kündigungsdatum schlicht KEINE Einträge mehr.
Die Tabelle endet einfach. Der `canceled`-Status auf dem Abo-Objekt selbst ist das Signal —
nicht endlose "gekündigt"-Zeilen in der scheduled_payments-Tabelle.
Bei Pause ist das anders: dort soll die Lücke SICHTBAR sein ("März: pausiert, April: pausiert"),
deshalb generiert der Scheduler für pausierte Abos aktiv `paused`-Zeilen.

**Scheduler-Verhalten je Status:**
- `active` → generiert `pending`-Einträge für fällige Perioden ✓
- `suspended` → generiert `paused`-Einträge für die Pause-Perioden (Lücke sichtbar machen)
- `canceled` → generiert NICHTS — Tabelle endet bei letzter bezahlter Periode

**Zählt zur "Tatsächlich"-Summe?**
- `pending` → Ja
- `paused` → Nein
- `matched` → Ja
- `missed` → Nein

### Buchungshistorie + CSV-Import (Zukunftsbild)

Wenn der User Buchungshistorie aktiviert UND CSV-Import nutzt, wird die Tabelle angereichert:

| Periode | Fälligkeitstag | Tatsächl. Buchungstag | Betrag | Status |
|---|---|---|---|---|
| Januar 2026 | 3.1. | 11.1.26 | 5,00€ | ✓ matched |
| Februar 2026 | 3.2. | 9.2.26 | 5,00€ | ✓ matched |
| März 2026 | 3.3. | – | 5,00€ | ⏳ pending |

- "Tatsächlicher Buchungstag" = realer Bankabbuchungs-Tag (kann abweichen — 3. vs. 11.)
- Die Tage variieren — das ist normal und gewollt
- Das Datenmodell braucht dafür ein zusätzliches Feld: `matched_on` (Datum der realen Buchung)
- Fehlend heute: `matched_on`-Feld + CSV-Import-Logik (späterer Slice, nicht v0.2.3)

---

## 1) Bestätigte Bugs (aus Code-Analyse)

### BUG-01: next_due_date wird NIE automatisch fortgeschrieben

**Was passiert:**
Das Feld `next_due_date` in der DB ist ein einfaches Datumsfeld.
Es gibt keinen Code — weder im Scheduler noch im Service — der es nach Ablauf
einer Periode automatisch auf das nächste Fälligkeitsdatum vorschreibt.

**Wo im Code:**
- `scheduler_service.generate_scheduled_payments()`: erzeugt scheduled_payments für HEUTE,
  aktualisiert aber `next_due_date` auf dem Abo-Objekt niemals.
- `update_subscription()`: kein automatisches Weiterschalten.

**Konsequenz:**
Ein Abo mit next_due_date = 2026-01-01 zeigt im Mai 2026 noch immer „1. Januar".
Die Übersicht zeigt es als "überfällig" oder falsch sortiert.

**Optionen:**
- A) next_due_date automatisch hochschalten wenn das Datum überschritten ist
  (im Scheduler nach generate, oder beim Laden per computed property)
- B) next_due_date abschaffen und immer BERECHNEN aus `started_on` + `interval`
  (wäre die sauberste Lösung — kein redundantes Feld, keine Sync-Fehler)
- C) next_due_date bleibt manuell, aber UI zeigt berechneten Wert und warnt wenn abweichend

**Empfehlung zur Diskussion:** Option B

---

### BUG-02: "Bisher Gezahlt" — last-segment Bug

**Was passiert:**
Wenn eine Preisänderung HEUTE eingetragen wird, entsteht ein Preishistorie-Eintrag
mit `valid_from = date.today()`. Im `_compute_total_paid_exact`-Algorithmus:

```
segment_start = today (valid_from des neuen Eintrags)
segment_end   = today (weil is_last = True → segment_end = today)
```

Die Prüfung `if segment_end <= segment_start: continue` greift.
Der `+1`-Bonus für die laufende Zahlung feuert nicht.
Ergebnis: Die aktuell laufende Zahlung im neuen Preis fehlt in der Summe.

**Konsequenz:**
Direkt nach einer Preisänderung springt "Bisher Gezahlt" um eine Periode zurück.

**Fix-Ansatz:**
Die `+1`-Logik muss auch dann feuern wenn `segment_start == segment_end` UND es das
letzte Segment ist. Oder: das `continue` nur wenn `segment_end < segment_start` (strict).

---

### BUG-03: Preisänderungen können nicht in der Zukunft liegen

**Was passiert:**
In `update_subscription` wird `_record_price_change(session, sub, payload.amount)` ohne
`valid_from` gerufen. Das Default ist immer `date.today()`.
Es gibt kein API-Feld und keine UI um ein zukünftiges valid_from anzugeben.

**Konsequenz:**
Ankündigung "Netflix wird ab 1. Oktober teurer" kann nicht eingetragen werden.
Preisänderungen sind immer rückwirkend ab heute — auch wenn der User es schon weiß.

---

### BUG-04: "Bisher Gezahlt" = 0 wenn Abo heute angelegt wird

**Was passiert:**
Bei `create_subscription` wird `_record_price_change(..., valid_from=started_on)` gerufen.
Wenn `started_on == date.today()`:

```
segment_start = today (valid_from = started_on = today)
segment_end   = today (is_last = True)
→ if segment_end <= segment_start: continue → +1 feuert nicht → total = 0
```

**Konsequenz:**
Frisch angelegte Abos zeigen "Bisher Gezahlt: 0,00 €" obwohl die erste Zahlung am
Abschlusstag fällig ist.

---

## 2) Design-Schwächen (keine Bugs, aber schlechte UX / Logik)

### DESIGN-01: "Abgeschlossen am" — Semantik und Validierung (ENTSCHIEDEN)

**Entscheidung (aus Abschnitt 0):**
- UI-Label: **"Abgeschlossen am"**
- DB-Spalte: `started_on` (bleibt, kein Rename nötig)
- Bedeutung: Das Datum an dem der User das Abo abgeschlossen hat (Vertragsbeginn / erster Klick)
- Validierung `started_on <= today` wird **aufgehoben** — Vergangenheit UND Zukunft erlaubt

**Warum kein Datumslimit:**
1. Rückwirkende Erfassung soll reibungslos funktionieren (auch 2-3 Jahre zurück)
2. Geplante Abos in der Zukunft sollen eingetragen werden können ("Netflix ab 1. Juni")
3. User soll sich null Gedanken über Validierungsregeln machen müssen

**Auswirkung auf Berechnungen:**
- `total_paid_estimate`: wenn started_on in der Zukunft → 0 (noch nicht gezahlt) ✓ (bereits so)
- `next_due_date`: wird abgeschafft, aus started_on berechnet → kein Problem
- Scheduled Payments: werden erst ab heute generiert, nicht für die Zukunft → OK

---

### DESIGN-02: Fehlende Abrechnungsintervalle

**Fehlt: Halbjährlich (semiannual, 6 Monate)**

Aktuelle Intervalle: monthly | quarterly | yearly | biennial
Fehlend: `semiannual` (halbjährlich)

Viele Abos (Versicherungen, Sportstudio, manche Software-Lizenzen) werden halbjährlich
abgerechnet. Das ist ein echter Anwendungsfall.

`_MONTHLY_FACTOR` wäre: `Decimal("1") / Decimal("6")`
`months_per_period` wäre: `6`

---

### DESIGN-03: Keine Möglichkeit für Preisankündigungen

**Das Problem:**
Ein User liest: "Netflix wird ab 1. Oktober 2026 auf 22,99 € erhöht."
Er möchte das jetzt eintragen, damit BB-myBudgetBook ab Oktober korrekt rechnet.
Das geht aktuell nicht — `valid_from` ist immer heute.

**Was das bedeutet für die Daten-Architektur:**
Die Preishistorie erlaubt technisch schon Zukunftsdaten (kein DB-Constraint dagegen).
Der Service muss nur ermöglichen, `valid_from` beim Update mitzugeben.

**Aber: Achtung Folgeeffekte:**
- `_compute_total_paid_exact` muss future entries ignorieren (nur bis `today` rechnen)
- Die aktuelle `amount` auf dem Abo: soll sie den heutigen Preis zeigen oder den angekündigten?
  → Empfehlung: Die `amount` auf dem Abo-Objekt = aktuell gültiger Preis (max. valid_from <= today)

---

### DESIGN-03b: Abo-Lifecycle — die drei Status im Vergleich (ENTSCHIEDEN)

Der Abo-Status hat drei klar unterschiedliche Bedeutungen:

| Status | Deutsch | Bedeutung | Buchungen danach |
|---|---|---|---|
| `active` | Aktiv | Läuft normal | werden generiert |
| `suspended` | Pausiert | Vorübergehend — User ist unentschlossen | werden als `paused` markiert |
| `canceled` | Gekündigt | Endgültig — User hat entschieden | werden als `canceled` markiert |

**Semantischer Unterschied Pausiert vs. Gekündigt:**
- **Pausiert** = "Ich bin gerade unsicher, vielleicht komme ich zurück." (z.B. Sportstudio im Urlaub pausiert)
- **Gekündigt** = "Ich habe gekündigt. Das Abo ist Geschichte." (z.B. Netflix abbestellt)

**Was bei Kündigung passiert — ENTSCHIEDEN (2026-05-04):**

Der Scheduler schreibt nach dem Kündigungsdatum KEINE weiteren Einträge mehr.
Die Tabelle endet bei der letzten bezahlten Periode. Kein "✖ gekündigt" für jeden Folgemonat.
Das Abo-Objekt selbst trägt `status = canceled` — das ist Signal genug.

In der Periode-Tabelle nach Kündigung am 5. März (access_until = 31. März):

| Periode | Fälligkeitstag | Betrag | Status |
|---|---|---|---|
| Januar | 3.1. | 5,00€ | ✓ bezahlt |
| Februar | 3.2. | 5,00€ | ✓ bezahlt |
| März | 3.3. | 5,00€ | ✓ bezahlt |
| *— Abo gekündigt am 5. März, Zugang bis 31. März —* | | | |

- März gilt als bezahlt (Periode war bereits abgerechnet) — ENTSCHIEDEN
- Ab April: keine Zeilen mehr (Scheduler schweigt)
- UI zeigt unterhalb der Tabelle: "Gekündigt am 5. März 2026"
- `access_until` steuert bis wann die letzte Periode als bezahlt gilt

**Vergleich: Pause vs. Kündigung im Scheduler:**

| | Pausiert (`suspended`) | Gekündigt (`canceled`) |
|---|---|---|
| Scheduler schreibt Einträge | Ja — mit Status `paused` | Nein — Tabelle endet |
| Lücke sichtbar | Ja — jede Pause-Periode als Zeile | Nein — Tabelle hört einfach auf |
| User-Intention | "Ich komme vielleicht zurück" | "Ich bin fertig damit" |
| Wiederherstellbar | Ja (Resume-Action) | Ja (Status auf active zurücksetzen, Option B: löschen) |

**Was der User nach Kündigung tun kann:**

Option A — **Gekündigt lassen (Standard, empfohlen):**
- Abo bleibt in der DB mit Status `canceled`
- Historie bleibt vollständig sichtbar
- Nützlich für: "Was habe ich früher alles abonniert?" / Jahresrückblick

Option B — **Abo löschen (Hard Delete, auf Wunsch):**
- User entscheidet sich aktiv fürs Löschen (bewusste Aktion, kein Versehen)
- Abo + alle scheduled_payments + Preishistorie werden entfernt
- Kein Soft-Delete mehr möglich danach
- UI: deutliche Warnung + Bestätigungsdialog ("Diese Aktion kann nicht rückgängig gemacht werden")

**Was das für den bestehenden Code bedeutet:**
- `canceled`-Status ist in der DB schon vorhanden (`SubscriptionStatus.canceled`)
- Noch fehlend: ein eigener `POST /subscriptions/{id}/cancel`-Endpoint
  (aktuell gibt es nur suspend — cancel fehlt als separater Flow)
- Noch fehlend: `canceled`-Status bei scheduled_payment-Generierung berücksichtigen
  (Scheduler soll für gekündigte Abos KEINE pending-Einträge mehr generieren)
- Hard Delete: `DELETE /subscriptions/{id}` existiert schon — bleibt erhalten,
  wird aber in der UI hinter einen separaten "Abo löschen"-Button verschoben

---

### DESIGN-04: Buchungshistorie für rückwirkend eingetragene Abos — konzeptionelle Lücke

**Das Problem:**
Szenario: User hat Netflix seit Januar, trägt es im Mai nach.
- `started_on` = 2026-01-01
- Scheduler läuft täglich ab Mai → generiert Einträge ab Mai
- Für Januar bis April: KEINE scheduled_payments in der DB
- ABER: "Bisher Gezahlt" rechnet ab Januar → Inkonsistenz

**Frage: Macht Buchungshistorie für rückwirkende Abos Sinn?**

Sichtweise A (Pro Buchungshistorie rückwirkend):
- User will sehen "von Jan bis Mai habe ich X mal gezahlt"
- Rückwirkende Generierung beim Anlegen des Abos wäre konsistent

Sichtweise B (Nur ab heute vorwärts):
- Was vergangen ist, wissen wir nicht wirklich (hat er wirklich jeden Monat gezahlt?)
- Buchungshistorie = SOLL, nicht IST — rückwirkend wäre Fiktion
- "Bisher Gezahlt" als Schätzung ist ehrlicher als fake scheduled_payments

Sichtweise C (Kombination — Empfehlung zur Diskussion):
- Buchungshistorie gilt nur ab Aktivierungsdatum des Toggles (nicht ab started_on)
- "Bisher Gezahlt" = Schätzung aus started_on + Preishistorie (bleibt wie es ist)
- Beide haben unterschiedliche Aufgaben und sollten nicht vermischt werden
- Klare Trennung in der UI: "Geschätzte Gesamtkosten" vs. "Erfasste Buchungen"

---

### DESIGN-05: next_due_date — ENTSCHIEDEN (abschaffen, immer berechnen)

**Entscheidung:** `next_due_date` wird als DB-Spalte abgeschafft.
Der Wert wird immer aus `started_on + N × relativedelta(months=period_months)` berechnet.

**Technische Lösung: `dateutil.relativedelta`**

Python-Library `python-dateutil` wird verwendet. Sie behandelt Monatsgrenzen korrekt:

```
started_on = 31. Januar, monatlich:
+ relativedelta(months=1) → 28. Februar  (clamped, korrekt)
+ relativedelta(months=2) → 31. März     (Ankertag erholt sich!)
+ relativedelta(months=3) → 30. April    (clamped, korrekt)
+ relativedelta(months=4) → 31. Mai      (korrekt)
```

**Kritische Regel:** Immer von `started_on` aus berechnen (nicht von der letzten Periode weiter),
sonst geht der Ankertag (z.B. 31) dauerhaft verloren.

**Algorithmus (calculate_next_due_date):**
```
1. Berechne Anzahl vergangener Perioden seit started_on
2. Berechne: started_on + N × relativedelta(months=period_months)
   (direkt aus started_on, nicht iterativ)
3. Falls Ergebnis < today: N+1 nehmen
4. Ergebnis = nächster Fälligkeitstag
```

**Scheduler-Logik:**
- Läuft täglich
- Berechnet für jedes aktive/suspended Abo alle Fälligkeitsdaten im Interval-Raster
- Generiert Eintrag für alle Perioden wo `berechneter_fälligkeitstag <= today` UND noch kein Eintrag existiert (Catch-up)
- Catch-up-Fenster: maximal 60 Tage rückwirkend — so werden Perioden nach einem Scheduler-Ausfall
  nachgefüllt, ohne bei neu aktiviertem Toggle die gesamte Abo-Vergangenheit aufzurollen
- `due_date` im Eintrag = berechneter Fälligkeitstag (nicht `date.today()`)
- UNIQUE(subscription_id, due_date) sichert Idempotenz — Duplikate sind strukturell unmöglich

**Hinweis (L-01, zweite Meinung):** Abschnitt 0b hatte bereits `>=` — DESIGN-05 hatte inkonsistent `==`.
Korrigiert: `>=` mit Zeitfenster ist die kanonische Logik.

**API-Response:** `next_due_date` bleibt im Response-Schema erhalten (computed field),
damit das Frontend keine Änderung braucht. Nur die DB-Spalte fällt weg.

---

### DESIGN-06: Mehrfaches Pausieren — ENTSCHIEDEN (neue Tabelle)

**Problem:** Das aktuelle Schema speichert nur EIN Pause-Ereignis (`suspended_at`).
Bei mehrfachem Pausieren/Resumieren wird `suspended_at` überschrieben — Historiedaten gehen verloren.

**Entscheidung:** Neue Tabelle `subscription_pause_history`

```
id:               uuid (pk)
subscription_id:  uuid (fk → subscriptions.id, CASCADE)
paused_at:        date (not null) — wann wurde pausiert
resumed_at:       date (nullable) — wann wieder aktiviert, null = noch pausiert
access_until:     date (nullable) — bis wann Leistung noch nutzbar (für Cancel-Logik)
```

**Was bleibt auf `subscriptions`:**
- `status` (active / suspended / canceled) — aktueller Zustand, bleibt
- `suspended_at` — wird **abgeschafft** (redundant mit pause_history)
- `access_until` — wird **abgeschafft** (zieht in pause_history um, gilt für pause UND cancel)

**Wie der Scheduler pause_history nutzt:**
Für jede zu generierende Periode prüft der Scheduler:
- Liegt `due_date` in einem Pause-Intervall aus pause_history? (`paused_at <= due_date <= resumed_at`)
- Wenn ja → Status `paused` generieren
- Wenn nein → Status `pending` generieren

**Wie Cancel mit pause_history zusammenspielt:**
Bei Kündigung wird ein Eintrag in pause_history geschrieben mit `resumed_at = null`.
`access_until` zeigt bis wann die Leistung läuft.
Der Scheduler ignoriert `canceled`-Abos komplett (keine neuen Einträge).

---

### DESIGN-07: Preisänderungs-API — ENTSCHIEDEN (Option C: separater Endpoint)

**Entscheidung:** `amount` fliegt aus `PATCH /subscriptions/{id}` heraus.

**Neuer Endpoint:** `POST /subscriptions/{id}/price-change`

```json
Request Body:
{
  "amount": 14.99,
  "valid_from": "2026-10-01"
}
```

- `amount`: Pflichtfeld — neuer Preis
- `valid_from`: Pflichtfeld — ab wann gilt der Preis (Vergangenheit, heute, Zukunft erlaubt)

**Warum Pflichtfeld statt optional?**
Wenn `valid_from` optional wäre, müsste der User wissen dass "kein Datum = heute".
Mit Pflichtfeld ist es explizit — kein stilles Verhalten.

**Was mit `_compute_total_paid_exact` (jetzt "Tatsächlich"):**
- Nur Einträge mit `valid_from <= today` zählen zur Vergangenheits-Summe
- Einträge mit `valid_from > today` fließen in "Dieses Kalenderjahr" als Projektion ein

**Breaking Change:** `SubscriptionUpdate`-Schema verliert `amount`.
Frontend muss den Preis-Änderungs-Flow separat implementieren (eigenes Formular/Button).

---

### DESIGN-08: Tatsächlicher Abbuchungstag — ENTSCHIEDEN (kein Extra-Feld)

**Frage:** Sollte man auf dem Abo separat eintragen können, an welchem Tag die Bank wirklich abbucht
(z.B. Abo am 3. abgeschlossen, Bank zieht aber am 11. ein)?

**Entscheidung:** Kein Extra-Feld. Kein Over-Engineering.

- Ohne CSV-Import: User sieht nur den berechneten Fälligkeitstag (3.1.) — das ist genug
- Mit CSV-Import: die Tabelle zeigt automatisch beide Spalten:
  - "Fälligkeitstag" (3.1.) = berechnet aus started_on
  - "Tatsächlicher Buchungstag" (11.1.) = aus CSV-Match
- Die Abweichung zwischen erwartetem und realem Tag ist genau der Mehrwert des CSV-Imports

---

## 3) Offene Fragen (zur gemeinsamen Entscheidung)

### F-01: ~~Was ist der korrekte Name/Begriff für "started_on"?~~ ENTSCHIEDEN → "Abgeschlossen am"

### F-02: ~~Darf "Erste Zahlung" in der Zukunft liegen?~~ ENTSCHIEDEN → Ja, kein Datumslimit

### F-03: ~~Wie gehen wir mit next_due_date um?~~ ENTSCHIEDEN → Abschaffen, immer berechnen aus started_on + interval

### F-04: ~~Wie behandeln wir Preisänderungen?~~ ENTSCHIEDEN → separater Endpoint, valid_from Pflichtfeld, alles erlaubt (Vergangenheit/heute/Zukunft)

### F-05: Kennzeichnung von "Tatsächlich" — ENTSCHIEDEN

Pragmatisch: In v0.2.3 immer "ca." zeigen. Wenn CSV-Import kommt, entfällt "ca." nur
wenn alle Perioden gematcht sind. Das ist dann ein Problem von CSV-Import, nicht v0.2.3.

**Kennzahlen-Darstellung auf der Detailseite (UX-Entscheidung):**
```
Monatlich       5,00 €
Jährlich       60,00 €   (Dieses Kalenderjahr)
Intervalle          5    [klein, kursiv: Seit Abo-Beginn]
Tatsächlich   ~25,00 €   [kleiner Text: Seit Abo-Beginn]
```
- "Intervalle" = neue Kennzahl — Anzahl Zahlungsperioden seit Abschluss
  macht "Tatsächlich" sofort nachvollziehbar: "5 × 5€ = 25€ — stimmt!"
- "Seit Abo-Beginn" direkt sichtbar (kein Tooltip nötig)
- "~" vor Tatsächlich = Schätzung, kein Kontoabgleich

### F-06: Buchungshistorie — ab wann — ENTSCHIEDEN (mit Ausblick)

**v0.2.3:** Ab Toggle-Aktivierung. Ehrlich, keine fiktiven Einträge.
"Tatsächlich" und "Buchungshistorie" beantworten bewusst verschiedene Fragen —
keine Inkonsistenz, zwei verschiedene Antworten auf zwei verschiedene Fragen.

**Ausblick — späterer Slice: Toggle "Buchungshistorie fiktiv"**
Beim Aktivieren werden alle Perioden ab started_on rückwirkend als pending generiert.
Zweck: Grundlage für CSV-Import-Matching.

Einschränkung (ENTSCHIEDEN): Fiktive Einträge ignorieren vergangene Pausen.
Rückwirkend pausieren + fiktiv + Vergangenheit = zu komplex, zu fehleranfällig.
Fiktiv = stumpf alle Perioden als pending, keine Sonderfälle.
Pausen greifen nur ab dem Zeitpunkt der echten Suspension — nicht rückwirkend.
Nicht in v0.2.3 — beim CSV-Import-Slice einplanen.

---

## 4) Entschiedene Änderungen für v0.2.3

### Prio 1 — Bugs beheben (nicht verhandelbar)

| # | Bug | Fix | Entschieden |
|---|-----|-----|---|
| BUG-01 | next_due_date bleibt stehen | Abschaffen, berechnen via relativedelta | ✓ |
| BUG-02 | "Tatsächlich" last-segment Bug | Algorithmus komplett neu schreiben (Perioden zählen statt Segmente) | ✓ |
| BUG-03 | Preisänderungen nur für heute | Separater Endpoint POST /price-change mit valid_from Pflichtfeld | ✓ |
| BUG-04 | "Tatsächlich" = 0 am ersten Tag | Folgt aus neuem Perioden-Algorithmus automatisch | ✓ |

### Prio 2 — Quick Wins

| # | Feature | Aufwand | Entschieden |
|---|---------|---------|---|
| QW-01 | Halbjährlich (semiannual) | Klein — Enum + relativedelta-Faktor | ✓ |
| QW-02 | "Abgeschlossen am" Label + kein Datumslimit | Klein — UI-Label + `started_on_not_in_future`-Validator in `backend/app/schemas/subscription.py` entfernen | ✓ |
| QW-03 | "Tatsächlich" mit "ca."-Kennzeichnung | Klein — UI-Label + Tooltip | ✓ |
| QW-04 | Cancel-Endpoint (POST /cancel) | Klein — analog zu suspend | ✓ |

### Prio 3 — Redesign (DB-Migrationen erforderlich)

| # | Feature | Komplexität | Entschieden |
|---|---------|-------------|---|
| RD-01 | next_due_date DROP COLUMN + API computed field | Mittel | ✓ |
| RD-02 | subscription_pause_history Tabelle | Mittel — neue Tabelle, suspend/resume Service anpassen | ✓ |
| RD-03 | suspended_at / access_until von Subscription entfernen | Mittel — in pause_history verschoben | ✓ |
| RD-04 | Scheduler komplett neu: period-basiert statt täglich | Groß — kompletter Rewrite. Hinweis: pause_history per Bulk-Load laden (sonst N+1-Query pro Abo) | ✓ |
| RD-05 | amount aus PATCH entfernen | Klein — breaking change Frontend | ✓ |
| RD-06 | Sortierung list_subscriptions umstellen | Klein — `.order_by(Subscription.next_due_date)` in `services/subscriptions.py` bricht nach RD-01. Ersatz: in Python nach berechnetem next_due_date sortieren | ✓ |
| RD-07 | SubscriptionCreate: next_due_date aus Request-Schema entfernen | Klein — breaking change Request-Seite. `SubscriptionCreate` in `schemas/subscription.py` verliert `next_due_date`. Frontend hört auf es zu schicken. (DESIGN-05 adressierte nur die Response-Seite) | ✓ |

### Migrationsreihenfolge (verkoppelt — muss in dieser Reihenfolge)

1. `subscription_pause_history` anlegen (RD-02) — braucht nichts Vorheriges
2. **Datenmigration** (fehlte im Ursprungsdokument): bestehende `suspended_at`/`access_until`-Werte
   für alle Abos mit `status = suspended` oder `status = canceled` in `pause_history` überführen
3. `suspended_at` + `access_until` droppen (RD-03) — erst NACH Schritt 2, sonst Datenverlust
4. `next_due_date` droppen (RD-01) — erst NACH Service-Update (RD-04, RD-06, RD-07)
5. `PaymentStatus.paused` zur PostgreSQL-ENUM hinzufügen (für RD-04 Scheduler-Rewrite)

**Hinweis Schritt 5 — PostgreSQL-ENUM:** Normale Alembic-Typ-Migration funktioniert nicht.
Stattdessen: `op.execute("ALTER TYPE paymentstatus ADD VALUE 'paused'")` direkt in der Migration.
Nicht `sa.Enum(..., name='paymentstatus')` — das würde den bestehenden Typ nicht erweitern.

### Noch offen (nicht in v0.2.3 entschieden)

Alle offenen Punkte wurden entschieden:
- OPEN-01 → F-05: "Tatsächlich" immer mit "ca." in v0.2.3 ✓
- OPEN-02 → F-06: Buchungshistorie ab Toggle-Aktivierung ✓
- Challenge A → Abschnitt 5 (L-09): `active` + skip wenn `started_on > today` ✓

---

## 5) Challenge Game — Ergebnisse

**Challenge 1: Monatsgrenzen / Schaltjahr** ✓ ENTSCHIEDEN
→ `dateutil.relativedelta`. Immer von `started_on` aus berechnen (nicht iterativ).
   31. Jan + 1 Monat = 28. Feb. 31. Jan + 2 Monate = 31. März (Ankertag erholt sich). ✓

**Challenge 2: Mehrfaches Pausieren** ✓ ENTSCHIEDEN
→ Neue Tabelle `subscription_pause_history`. Sauber spielen.
   `suspended_at` / `access_until` wandern in die Tabelle, fliegen von Subscription weg.

**Challenge 3: Preisänderungs-API** ✓ ENTSCHIEDEN
→ Option C: Separater Endpoint `POST /subscriptions/{id}/price-change`.
   `amount` fliegt aus PATCH raus. `valid_from` ist Pflichtfeld. Breaking change akzeptiert.

**Challenge 4 (ursprünglich "meine eigene"): Tatsächlicher Abbuchungstag** ✓ ENTSCHIEDEN
→ Kein Extra-Feld auf dem Abo. Die Tabelle zeigt Fälligkeitstag (berechnet) und
   tatsächlichen Buchungstag (aus CSV-Import) — das ist der Mehrwert des CSV-Moduls.
   Ohne CSV-Import sieht man nur den berechneten Fälligkeitstag. Das reicht.

**Noch offene Challenges:**

**Challenge A: started_on in der Zukunft** ✓ ENTSCHIEDEN (2026-05-05, L-09 zweite Meinung)

Status bleibt `active`. Kein neuer Status `scheduled` oder `pending_start` nötig.
Die Berechnungen prüfen `started_on > today` und geben 0 zurück — konsistent mit dem
was `_compute_total_paid_estimate` bereits heute tut.

Auswirkungen je Codepfad:
→ `get_overview`: Abos mit `started_on > today` fließen NICHT in monatliche Gesamtsumme ein
→ `_compute_total_paid` ("Tatsächlich"): gibt 0 zurück (keine Perioden <= today vorhanden)
→ Scheduler: generiert keine Einträge (alle due_dates liegen in der Zukunft)
→ UI: Status-Badge "Aktiv", Kennzahlen zeigen 0 — Optional: Tooltip "Startet am 1. Juni 2026"

**Challenge B: Aktueller Preis bei Preisankündigung** ✓ ENTSCHIEDEN

Abo-Karte / Übersichtsliste:
→ Zeigt immer den HEUTIGEN Preis (max valid_from <= today)
→ Badge: "Preisänderung am 1. Okt.: 14,99 €" (sichtbar, aber nicht der Hauptwert)

Detail-Ansicht:
→ Eigener Abschnitt "Angekündigte Preisänderung" mit:
   - Neuer Preis: 14,99 €
   - Gültig ab: 1. Oktober 2026
   - Editierbar (Betrag oder Datum ändern) → PATCH auf den price_history-Eintrag
   - Löschbar (Ankündigung zurückziehen) → DELETE auf den price_history-Eintrag
→ Technisch: price_history-Einträge mit valid_from > today sind "Ankündigungen"
→ Neue Endpoints nötig: PATCH + DELETE auf /subscriptions/{id}/price-history/{entry_id}

**Challenge A: Abo in der Zukunft** ✓ ENTSCHIEDEN — siehe oben

**Design-Änderungen (Notiz für später, v0.2.3 UI):**

1. Browser-native confirm() abschaffen — überall ersetzen durch eigene Modal-Overlays
   im App-Design (CSS-Variablen, gleiche Schrift, gleiche Farben wie der Rest der App)

2. Drei Modal-Typen:
   a) Bestätigungs-Modal (einfach): "Pausieren?" / "Kündigen?" → Ja / Abbrechen
   b) Sicherheits-Modal (destruktiv): Löschen → User muss Abo-Name eintippen
      Beispiel: 'Bitte trage "Netflix" ein um fortzufahren' — erst dann wird Löschen aktiv
      (Vorbild: GitHub Repository-Löschung)
   c) Erstell-Modal: "Neues Abo" öffnet ein Overlay-Formular — inkl. Logo-Upload von Anfang an,
      nicht erst auf der Detailseite nachträglich

3. Gilt auch für: Preisänderung bearbeiten/löschen, Pause einleiten, Kündigung bestätigen

---

## 6) Glossar (damit wir gemeinsam dieselben Begriffe verwenden)

| Begriff | Definition |
|---------|------------|
| started_on | "Abgeschlossen am" — Datum des Vertragsabschlusses. Kein Datumslimit. |
| next_due_date | Nächstes Fälligkeitsdatum — wird ABGESCHAFFT, immer berechnet aus started_on + N × interval |
| valid_from | Ab wann gilt ein Preis (in der Preishistorie) — darf in Vergangenheit oder Zukunft liegen |
| Tatsächlich | Summe aller bezahlten Perioden seit Abschluss — Schätzung, kein Kontoabgleich |
| Dieses Kalenderjahr | Kosten im aktuellen Kalenderjahr (1. Jan–31. Dez), bezogen auf Abschlussdatum |
| scheduled_payment | Eine Periode im Interval-Raster — Soll-Buchung mit Status (pending/paused/matched/missed). Kein canceled-Status nötig — bei Kündigung endet die Tabelle einfach. |
| Billing Interval | Abrechnungsrhythmus: monatlich / vierteljährlich / halbjährlich / jährlich / zweijährlich |
| active | Abo läuft normal |
| suspended (pausiert) | Vorübergehend pausiert — User ist unentschlossen, kommt vielleicht zurück |
| canceled (gekündigt) | Dauerhaft beendet — User hat entschieden. Historie bleibt sichtbar, Hard Delete auf Wunsch. |
| access_until | Datum bis wann die Leistung noch nutzbar ist nach Kündigung/Pause (z.B. Monatsende) |
