# Subscriptions vNext Blueprint (Delta)

Status: draft  
Scope: v0.2.2 – v0.2.3 (Subscriptions Ausbau)  
Owner: Product + Engineering

---

## 1) Zielbild

Das bestehende Subscriptions-Modul wird von einer reinen Tabellenverwaltung zu einem kleinen Produktbereich ausgebaut:
- bessere Datenpflege (Notizen, Abschlussdatum, Suspend statt sofort loeschen)
- bessere Darstellung (Detailseite, Provider-Logo)
- bessere Nutzbarkeit (deutsche Betragseingabe, Suche, Eintragsanzahl)
- bessere Einordnung von Kosten (monatlich, jaehrlich, bisherige Gesamtkosten)

Admin-Bereich bleibt in diesem Schritt unveraendert.

---

## 2) Ist-Stand (kurz)

Backend heute:
- CRUD fuer Subscriptions
- Felder: `name`, `amount`, `next_due_date`, `interval`
- interval: monthly/quarterly/yearly/biennial
- overview: monatlich normierte Gesamtsumme + naechste Faelligkeiten

Frontend heute:
- `SubscriptionsPage` mit Liste + Inline-Edit + Delete
- keine Detailseite
- keine Suche/Pagination
- Betragseingabe aktuell per `type=number` mit Punkt

---

## 3) Delta (neu/geaendert)

### 3.1 User Features

1. Provider-Logo je Abo
- Upload eines Logos (z. B. Netflix)
- automatische Skalierung fuer:
  - Tabellenansicht (klein)
  - Detailansicht (groesser)

2. Suspend-Flow statt nur Loeschen
- Abo kann auf `suspended` gesetzt werden
- Sonderfall: Kuendigung mitten im Monat, Nutzbarkeit bis Stichtag
- Abo bleibt historisch erhalten (kein Hard Delete als Standard)

3. Neues Feld: Abschlussdatum
- `started_on` (optional)
- wenn leer: aktuelles Datum als Default
- darf in der Vergangenheit liegen

4. Detailseite pro Abo
- zentrale Ansicht fuer alle Abo-Infos
- inkl. Kostenzusammenfassung

5. Deutsche Betragseingabe
- User darf `18,00` oder `18.00` eingeben
- Speicherung in DB bleibt numerisch sauber
- Anzeige immer deutsch (`18,00`)

6. Kostenkennzahlen auf Detailseite
- monatlich
- jaehrlich
- kumuliert seit Abschluss (unter Beruecksichtigung des Intervalls)

7. Notizenfeld
- optionales Textfeld `notes`

8. Tabellen-UX
- Suche in der aktuellen Tabelle
- Seitengroesse: 25 (default), 50, 100

### 3.2 Nice-to-have (nicht in v0.2.2 / v0.2.3)

Preis-Historie:
- bei Aenderung von `amount` alten Preis mit gueltig-von/gueltig-bis speichern
- Ziel: historische Kosten nicht verfaelschen
- explizit spaeterer Slice (nach Kernfunktionen)

---

## 4) Fachliche Entscheidungen (v0.2.2)

1. Soft-Lifecycle statt sofort loeschen
- neuer Status: `active | suspended | canceled` (Vorschlag)
- Default bei neuen Abos: `active`

2. Suspend-Semantik
- Felder: `suspended_at` und optional `access_until`
- Bedeutung:
  - `suspended_at`: ab wann pausiert/gekuendigt markiert
  - `access_until`: bis wann Leistung noch verfuegbar (z. B. Monatsende)

3. Loeschen in v0.2.2
- UI-Standardaktion wird Suspend/Cancel
- Hard Delete nur als optionale Aktion (spaeter), um Historie zu bewahren

4. Geldwerte
- API akzeptiert String oder Number
- Backend normalisiert in Decimal(10,2)
- Frontend zeigt standardisiert mit Komma

5. Abschlussdatum
- `started_on` default = heute
- validierung: nicht in der Zukunft

---

## 5) Datenmodell-Delta (Backend)

Geplante neue Felder in `subscriptions`:
- `status` (enum): `active | suspended | canceled`
- `started_on` (date, not null, default today)
- `notes` (text, nullable)
- `logo_url` oder `logo_path` (string, nullable)
- `suspended_at` (date, nullable)
- `access_until` (date, nullable)

Neue Tabelle `subscription_price_history` (in Slice-A-Migration):
- `id` (uuid, pk)
- `subscription_id` (uuid, fk -> subscriptions.id, ondelete CASCADE)
- `amount` (Numeric 10,2)
- `valid_from` (date, not null)

Warum schon in Slice A?
- Preisaenderungen beginnen ab v0.2.2 automatisch aufgezeichnet zu werden
- spaeteres Nacherfassen waere lueckenhaft und nicht korrekt
- API und UI folgen erst in Slice E, die Daten laufen aber sofort mit
- `started_on <= today`
- falls `access_until` gesetzt: `access_until >= suspended_at` (wenn suspended_at gesetzt)

Hinweis Preis-Historie (Tabelle schon in Slice A, API/UI erst Slice E):
- neue Tabelle `subscription_price_history` wird in Slice-A-Migration angelegt
- Service schreibt bei jeder `amount`-Aenderung still einen Eintrag
- kein API-Endpoint, kein UI in v0.2.2
- Grund: Daten muessen ab Tag 1 laufen, sonst ist die Historie von Anfang an lueckenhaft

Implementierungsentscheidung price_history (Erkenntnisse aus Slice A):

Semantik (valid_from-only-Design):
Jeder Eintrag bedeutet "ab diesem Datum gilt Preis X".
Aufeinanderfolgende Eintraege bilden eine lueckenlose Zeitleiste:
  {9.99, started_on} → {12.99, 2026-03-01} → {14.99, 2026-05-01}
Slice E kann daraus total_paid_estimate korrekt berechnen.

Initialer Eintrag in create_subscription (Fix):
Urspruenglicher Plan: nur bei amount-Aenderung schreiben.
Problem: ohne initialen Eintrag ist der Startpreis nach der ersten Aenderung verloren.
Beispiel ohne Fix:
  Anlage 9,99 € → kein Eintrag
  Aenderung auf 12,99 € → {12.99, Maerz}
  Aenderung auf 14,99 € → {14.99, Mai}
  History: [{12.99, Maerz}, {14.99, Mai}] — Jan/Feb komplett unbekannt
Fix: create_subscription schreibt sofort {amount, valid_from=started_on}.
Warum started_on statt heute? Damit rueckwirkende Abos korrekt erfasst werden.

_record_price_change erhaelt daher ein optionales valid_from-Argument:
- create_subscription: valid_from = started_on
- update_subscription: valid_from = date.today() (Standard)

---

## 6) API-Delta (Vorschlag)

Bestehend bleibt:
- `GET /subscriptions`
- `POST /subscriptions`
- `PATCH /subscriptions/{id}`
- `DELETE /subscriptions/{id}` (spaeter evtl. eingeschraenkt)
- `GET /subscriptions/overview`

Neu (v0.2.2):
- `GET /subscriptions/{id}` (Detail)
- `POST /subscriptions/{id}/suspend`
- `POST /subscriptions/{id}/resume`
- `POST /subscriptions/{id}/logo` (multipart upload)

Response-Erweiterungen:
- status
- started_on
- notes
- logo_url
- suspended_at
- access_until
- derived fields fuer Detailseite:
  - `monthly_cost_normalized`
  - `yearly_cost_normalized`
  - `total_paid_estimate`

---

## 7) Frontend-Delta (Vorschlag)

1. Tabellenansicht (`/subscriptions`)
- Suche (clientseitig v1)
- Seitengroesse 25/50/100
- Logo-Spalte (thumbnail)
- Status-Badge

2. Detailseite (`/subscriptions/:id`)
- Kopfbereich mit Logo, Name, Status
- Stammdaten + Notizen
- Kostenkarten (monatlich/jaehrlich/gesamt)
- Suspend/Resume Aktionen

3. Formulare
- Betragseingabe tolerant fuer `,` und `.`
- Anzeige immer deutsch formatiert

---

## 8) Vertical Slices

### Slice A (Backend zuerst, schnell nutzbar)
- DB-Migration fuer: status, started_on, notes, suspended_at, access_until
- DB-Migration fuer: `subscription_price_history` (Tabelle leer, aber bereit)
- Service: bei `amount`-Aenderung still Eintrag in price_history schreiben (kein Endpoint)
- Schema + Service + Router Update
- Suspend Endpoint
- Tests fuer Validierung + Ownership + Statuswechsel + price_history-Eintrag bei Update

Ergebnis:
- fachliche Basis steht
- kein Logo/Detailscreen noetig

### Slice B (Frontend Listen-UX)
- Suche
- Seitengroesse 25/50/100
- Status in Tabelle
- Betragsausgabe deutsch formatiert

Ergebnis:
- sofort bessere Bedienbarkeit

### Slice C (Detailseite + Kennzahlen)
- `GET /subscriptions/{id}`
- neue Detailseite
- Kostenkarten inkl. kumuliertem Wert
- Notizen anzeigen/bearbeiten

Ergebnis:
- inhaltlich vollwertige Abo-Ansicht

### Slice D (Logo Upload)
- Upload Endpoint + Speicherung
- Thumbnail/Detail-Skalierung im Frontend
- Fallback-Icon

Ergebnis:
- visuelle Verbesserung

### Slice E (spaeter, v0.2.3 oder eigener Release)
- `GET /subscriptions/{id}/price-history` Endpoint
- UI-Anzeige der Preishistorie auf Detailseite
- Daten sind ab Slice A bereits vorhanden

---

## 9) Offene Entscheidungen

1. Suspend vs Canceled
- brauchen wir beide Status direkt in v1?

2. Kumulierte Kosten-Berechnung
- einfache Naeherung aus started_on + aktuellem amount + interval
- oder exakt mit kuenftigem Preisverlauf?

3. Logo-Storage
- lokal im Backend-Dateisystem (einfach)
- oder spaeter objekt storage (skalierbar)

4. DELETE Verhalten
- fuer v1 behalten oder auf "nur admin / nur hard cleanup" verschieben?

---

## 10) Akzeptanzkriterien v0.2.2 (Minimum)

1. User kann Abo mit `started_on` und optional `notes` speichern.
2. User kann Abo auf suspended setzen, ohne Datenverlust.
3. Tabelle hat Suche + Seitengroesse 25/50/100.
4. Betragseingabe akzeptiert Komma und Punkt; Anzeige ist deutsch.
5. Detailseite zeigt alle Felder + monatlich/jaehrlich/gesamt.
6. Ownership-Checks bleiben fuer alle Endpunkte intakt.
7. Bestehende Tests bleiben gruen; neue Tests decken neue Logik ab.

---

## 11) Umsetzungstaktik (token-effizient)

1. Pro Slice ein eigener Branch (`feat/subscriptions-slice-a`, ...)
2. Pro Slice genau 1 kurze Spec-Section in PR-Beschreibung:
- Was
- Warum
- API/DB-Aenderung
- Testnachweis
3. Nur bei Querschnittsentscheidung neue ADR erstellen.
4. Keine neue lange Doku pro Mini-Schritt; diese Datei ist die zentrale Blueprint-Quelle.
