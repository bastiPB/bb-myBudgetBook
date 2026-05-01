---
doc: rbac-vision
status: draft
version: 0.1
---

# RBAC-Vision: Rollen & Berechtigungen

Dieses Dokument beschreibt das gewünschte Rollenmodell für BB-myBudgetBook.
Es ist bewusst in zwei Phasen aufgeteilt: was für v0.1 gilt, und was für spätere
Versionen geplant ist — damit wir jetzt nicht zu viel bauen, aber auch nichts
verbauen.

---

## Hintergrund & Zielgruppe

Das Tool soll für Privatpersonen, Paare und Familien nutzbar sein.
Typisches Szenario: Eine technisch versierte Person ("Admin") betreibt die App,
andere Familienmitglieder nutzen sie — mit unterschiedlichen Bedürfnissen und
unterschiedlichem Technik-Know-how.

Grundprinzip: **Least Privilege** — jeder bekommt nur genau die Rechte die er
braucht. Neue Accounts starten ohne jegliche Rechte und bekommen sie explizit
zugewiesen.

---

## Phase 1 (v0.1) — Klärung des Ist-Modells

### Rollen

| Rolle    | Bedeutung |
|----------|-----------|
| `admin`  | Vollzugriff: Daten + Benutzerverwaltung + App-Einstellungen |
| `editor` | Kann alle Daten sehen und bearbeiten — aber keine Benutzerverwaltung |
| `default`| Kein Datenzugriff — reiner Wartezustand bis zur Rollenzuweisung |

> **Status:** `editor` ist im Code korrekt implementiert (Migration d4e5f6g7).

### Registrierungsfluss

```
Registrierung → Status: pending, Rolle: default
                    ↓
         Admin oder Editor gibt frei
                    ↓
         Rollenzuweisung: editor / admin / (später: weitere Rollen)
                    ↓
         Status: active → Login möglich
```

### Was darf wer? (v0.1)

| Aktion                       | default | editor | admin |
|------------------------------|---------|--------|-------|
| Einloggen (nach Freigabe)    | ✅      | ✅     | ✅    |
| Eigene Abos sehen            | ❌      | ✅     | ✅    |
| Eigene Abos anlegen/ändern   | ❌      | ✅     | ✅    |
| Übersicht / Dashboard        | ❌      | ✅     | ✅    |
| User freigeben / Rollen ändern | ❌    | ❌     | ✅    |
| User löschen                 | ❌      | ❌     | ✅    |

> **Default darf nach der Freigabe einloggen, sieht aber einen leeren Wartebildschirm**
> mit dem Hinweis: "Dein Account wurde freigeschaltet. Warte auf die Rollenzuweisung
> durch einen Admin oder Editor."

### Umgesetzte Punkte für v0.1

- Rollenprüfung in der Subscription-API: nur `editor` und `admin` haben Zugriff
  (Dependency `EditorOrAdminUser` in dependencies.py, alle Subscription-Routen abgesichert)
- `default`-User nach Login: Wartebildschirm im Dashboard (DashboardPage.tsx)

---

## Phase 2 (v0.2+) — Kontext-Modell für Familien

### Das Problem

Ein einzelner Datentopf reicht für Familien nicht aus:
- Jeder hat persönliche Finanzen (eigene Abos, eigenes Sparbuch)
- Manche Daten sind geteilt (Haushaltskasse, Urlaubskasse, gemeinsame Abos)
- Kinder sollen nur ihren eigenen Bereich sehen (z.B. Taschengeld-Sparbuch)

### Konzept: Kontexte (Spaces)

Ein **Kontext** ist ein abgegrenzter Bereich mit eigenem Datentopf.

Beispiele:
- `persönlich/sebastian` — nur Sebastian sieht das
- `persönlich/anna` — nur Anna sieht das
- `haushalt` — beide sehen und bearbeiten es
- `urlaub-2027` — alle die zugewiesen sind, sehen es
- `sparbuch/tim` — nur Tim (Kind) und die Eltern sehen es

### Geplante Rollen im Kontext-Modell

| Rolle         | Beschreibung |
|---------------|-------------|
| `admin`       | Verwaltet App + User, kann Kontexte anlegen und Rollen zuweisen |
| `editor`      | Darf alle zugewiesenen Kontexte sehen und bearbeiten |
| `viewer`      | Darf zugewiesene Kontexte nur lesen (kein Anlegen/Ändern) |
| `restricted`  | Darf nur einen einzigen, explizit zugewiesenen Kontext sehen (z.B. Kinder-Sparbuch) |
| `default`     | Kein Zugriff — Wartezustand nach Registrierung |

> `viewer` und `editor` bekommen hier eine saubere Trennung:
> Editor = lesen + schreiben, Viewer = nur lesen.

### Beispiel: Familienkonfiguration

```
Sebastian   → admin    → sieht alles, verwaltet User
Anna        → editor   → sieht und bearbeitet: haushalt, urlaub, eigene Abos
Tim (Kind)  → restricted → sieht nur: sparbuch/tim
```

### Offene Fragen für v0.2

- Wie werden Kontexte technisch abgebildet? (eigene Tabelle, Namespacing?)
- Wer darf neue Kontexte anlegen? Nur Admin oder auch Editor?
- Können Rollen pro Kontext unterschiedlich sein?
  (z.B. Anna ist Editor im Haushaltskonto, aber Viewer im Sparbuch der Kinder)
- Wie sieht die UI für die Kontext-Verwaltung aus?
- Brauchen wir benutzerdefinierte Rollen, oder reichen die vier festen?

---

## Zusammenfassung: Was jetzt, was später

| | v0.1 | v0.2+ |
|---|---|---|
| Rollen | admin, editor, default | + viewer, restricted |
| Datentrennung | jeder sieht nur seine eigenen Daten | Kontexte (persönlich + geteilt) |
| Rollenzuweisung | Admin vergibt Rollen | Admin + Kontext-Zuweisung |
| Benutzerdefinierte Rollen | nein | ggf. ja |

---

## Verwandte Dokumente

- ADR 0005 — technische Baseline-Entscheidung für RBAC
- docs/01-mvp.md — MVP-Scope (v0.1)
- docs/02-ideas.md — Ideenparkplatz für spätere Erweiterungen
