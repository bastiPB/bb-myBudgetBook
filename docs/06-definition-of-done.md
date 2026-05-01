---
doc: definition-of-done
status: living
---

# Definition of Done (DoD)

Diese Definition of Done beschreibt, **wann etwas wirklich \"fertig\" ist** – unabhängig davon, ob es sich um Code, Doku oder ein Feature handelt.

Ziel: gleichbleibende Qualität, keine Abkürzungen.

---

## 1) Allgemein (immer)
- [ ] Passt zum MVP oder zur geplanten Version (docs/01-mvp.md)
- [ ] Keine unnötige Scope-Erweiterung
- [ ] Verständlich dokumentiert (README oder docs)
- [ ] Keine TODOs ohne Issue

---

## 2) Code (wenn Code betroffen ist)
- [ ] Verständliche Namen (keine Abkürzungs-Orgie)
- [ ] Fehler sauber behandelt (keine ungefangenen Exceptions)
- [ ] Router, Services, Modelle und Schemas bleiben getrennt; keine Feature-Logik als Monolith in `main.py`
- [ ] Keine sensitiven Daten in Logs
- [ ] Linting/Formatierung eingehalten
- [ ] Minimaltests für kritische Pfade vorhanden

---

## 3) Security (wenn Daten/Auth betroffen sind)
- [ ] Passwörter: **nur Argon2id Hashing**
- [ ] Keine Secrets im Repo
- [ ] Secrets nicht in Logs
- [ ] Input validiert (keine Blindannahmen)
- [ ] Neue Angriffsfläche bewusst bewertet

---

## 4) Daten & Migrationen (wenn DB betroffen ist)
- [ ] Migration nachvollziehbar (vorwärts / rückwärts denkbar)
- [ ] Schema- und Datenmodelländerungen erfolgen nur per Alembic-Migration, nie manuell in der DB
- [ ] Neue Modelle nutzen das gemeinsame Base-Model mit UUID, created_at und updated_at
- [ ] Bestehende Daten werden nicht stillschweigend zerstört
- [ ] Backup/Restore weiterhin möglich

---

## 5) Docs & Projektpflege
- [ ] Changelog aktualisiert (falls relevant)
- [ ] ADR ergänzt, wenn Architekturentscheidung
- [ ] Release-Checklist angepasst (falls nötig)

---

## 6) Reality Check
- [ ] Würde ich das Feature **in 6 Monaten noch verstehen**?
- [ ] Würde ich es jemand Fremdem guten Gewissens zeigen?
- [ ] Würde ich es selbst nutzen?

Wenn eine dieser Fragen mit „nein“ beantwortet wird → **noch nicht done**.
