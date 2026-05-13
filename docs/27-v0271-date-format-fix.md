---
doc: bugfix-spec
release: v0.2.71
status: released
---

# v0.2.71 — Datumseingabe: Deutsches Format (DD.MM.YYYY)

Erstellt: 2026-05-13

---

## Problem

Alle `<input type="date">`-Felder in der App zeigten das US-amerikanische Format `MM/DD/YYYY` als Platzhalter und Eingabehilfe. Das betraf:

- Erstell-Formular (Abschlussdatum bei „Neues Abo anlegen")
- Detailseite: Preisänderungs-Formular (`valid_from`-Datum)
- Detailseite: Intervallwechsel-Formular (`valid_from`-Datum)
- Sparfach-Seiten: Start- und Enddatum-Felder

Angezeigte Datumsstrings (nicht-editierbar) waren davon **nicht** betroffen — `formatDate()` gibt korrekt `DD.MM.YYYY` aus.

---

## Ursache

`frontend/index.html` hatte `<html lang="en">`. Browser richten die Darstellung von `<input type="date">` nach dem `lang`-Attribut des Dokuments. Mit `lang="en"` zeigt Chrome/Edge das US-Format.

---

## Fix

```html
<!-- vorher -->
<html lang="en">

<!-- nachher -->
<html lang="de">
```

**Datei:** `frontend/index.html`, Zeile 2.

Ein-Zeilen-Änderung. Kein JavaScript, keine Komponenten-Änderung, keine Abhängigkeiten.

---

## Auswirkung

Alle `<input type="date">`-Felder zeigen jetzt `TT.MM.JJJJ` (Chrome/Edge-Darstellung im deutschen Locale). Der interne Wert bleibt weiterhin ISO 8601 (`YYYY-MM-DD`) — das Backend erhält unverändert das korrekte Format.

Außerdem: Browser-seitige Eingabehilfen (Wochentage, Monatsnamen) werden auf Deutsch angezeigt.
