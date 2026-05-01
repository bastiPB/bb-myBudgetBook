---
doc: ideas
status: living
---

# Ideenparkplatz & Refinement-Prozess

Diese Datei ist ein **Parkplatz für Ideen** – roh, unvollständig, ohne Druck.
Wichtig: Hier geht nichts verloren. Gleichzeitig verhindern wir, dass der MVP verwässert.

## Grundregel
- **Ideen sammeln ist billig. Umsetzung ist teuer.**
- Darum: Jede Idee durchläuft einen kurzen Check, bevor sie ""echte Arbeit"" wird.

---

# 1) Wie ich Ideen sammle

## 1.1 Quellen für Ideen
- Eigene Nutzung: ""Was nervt mich gerade?""
- Feedback: Issues/Kommentare
- Konkurrenz/Alternativen: ""Was fehlt mir bei Tool X?""
- Security/Privacy: ""Was macht es sicherer/solider?""

## 1.2 Erlaubt: Rohform
Eine Idee darf aussehen wie:
- ""Budget für Urlaub anlegen""
- ""CSV Export""
- ""Kategorien/Tags""
Das ist ok – Refinement kommt später.

---

# 2) Idee → Feature Issue (Promotion)

Sobald eine Idee ernsthaft in Betracht kommt, wird sie **als GitHub Issue (Feature Request)** erfasst.

## 2.1 Promotion-Kriterien (wann aus Idee ein Issue wird)
Mindestens 2 von 3:
- ✅ Klarer Nutzerwert
- ✅ Grobe Vorstellung von UX/Flow
- ✅ Akzeptanzkriterien formulierbar

Wenn nicht: bleibt es im Ideenparkplatz.

---

# 3) MVP-Fit & Release-Zuordnung

## 3.1 MVP-Fit Gate (v0.1)
Jede Idee muss beantworten:
- Passt es in den MVP laut docs/01-mvp.md?
- Wenn nein: v0.2 oder später

**MVP bleibt klein.** Alles, was MVP sprengt, ist automatisch v0.2+.

---

# 4) Lightweight-Checkliste für neue Features (ohne Coding)

## 4.1 Produkt
- Welches Problem löst es?
- Für welche Persona?
- Was ist der ""Happy Path""?

## 4.2 Daten
- Welche Daten werden gespeichert?
- Sind Daten sensibel?
- Muss etwas verschlüsselt oder besonders geschützt werden?

## 4.3 Security & Qualität
- Erhöht es die Angriffsfläche?
- Braucht es neue Rollen/Rechte?
- Was sind die minimalen Tests?

## 4.4 Ops
- Ändert es Backups/Migrationen?
- Ändert es die Konfiguration?

---

# 5) Ideenliste (Parkplatz)

## v0.2 Kandidaten
- Budgets (Urlaub)
- Sparpläne
- Einnahmen/Ausgaben Tracking
- Kategorien/Tags
- Export (CSV/JSON)
- **Admin-Einstellung: Selbst-Registrierung ein/aus** — aktuell ist `/auth/register` immer offen;
  ein Toggle im Admin-Bereich (Settings-Seite) soll steuern können ob neue User sich selbst registrieren
  dürfen oder nur vom Admin angelegt werden können (sinnvoll für geschlossene Familien-Instanzen)

## Later / Vielleicht
- Wiederkehrende Transaktionen (allgemeiner als Abos)
- Ziele (""Sparen für X"")
- Import/Export Integrationen
- Reports/Charts

## Security/Hardening (laufend)
- stärkere Session/Timeout Policies
- bessere Default-Konfiguration (secure by default)
- Doku: Backup/Restore + Threats

---

# 6) Refinement-Regeln (damit es effizient bleibt)

## 6.1 Kleine Schritte
- Änderungen lieber klein & häufig (PRs auch bei Doku)

## 6.2 ""Write it once""
- MVP steht in docs/01-mvp.md
- Release-Gate steht in docs/04-release-readiness-checklist.md
- Entscheidungen stehen als ADRs in docs/adr/

Wenn du etwas doppelt schreiben musst, stimmt die Struktur nicht – dann lieber Struktur verbessern.

## 6.3 KI nutzen oder selbst?
Beides ist ok:
- selbst ändern: wenn du genau weißt, was du willst
- KI nutzen: für Kürzen, Struktur, Klarheit, Konsistenz
