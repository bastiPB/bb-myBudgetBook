# ADR 0003: Manage schema changes with Alembic and shared base model

## Status
Accepted

## Kontext
Das Datenmodell wird sich mit neuen Features weiterentwickeln. Ohne klare Regeln für Schemaänderungen entstehen schnell manuelle Datenbank-Anpassungen, inkonsistente Umgebungen und Modelle mit uneinheitlichen Standardfeldern.

Gleichzeitig braucht das Projekt eine robuste Grundlage für spätere Erweiterungen wie zusätzliche Tabellen, neue Spalten, Umbenennungen bestehender Felder und nachvollziehbare Datenmigrationen.

## Entscheidung
Datenbank-Schema und Datenmodell sind migrationsgetrieben. Änderungen am Schema werden ausschließlich über Alembic umgesetzt; manuelle DB-Anpassungen sind ausgeschlossen.

Alle SQLAlchemy-Modelle erben zusätzlich von einem gemeinsamen Base-Model mit folgenden Standardfeldern:
- `id` als UUID
- `created_at`
- `updated_at`

## Alternativen
1) Manuelle Schemaänderungen direkt in der Datenbank
   - Pro: schnell für Einzelfälle
   - Contra: nicht reproduzierbar, fehleranfällig, schwer reviewbar

2) Schemaänderungen ohne gemeinsames Base-Model
   - Pro: weniger Anfangsstruktur
   - Contra: inkonsistente Tabellen, duplizierte Felder, höherer Pflegeaufwand

3) Eigenes Migrationssystem statt Alembic
   - Pro: volle Kontrolle
   - Contra: unnötige Komplexität, schlechtere Integration mit SQLAlchemy

## Konsequenzen
- Pro:
  - Schemaänderungen bleiben versioniert, reviewbar und reproduzierbar
  - Lokale Umgebung, Testsysteme und Produktion lassen sich konsistent migrieren
  - Standardfelder sind in allen Tabellen einheitlich vorhanden
- Contra:
  - Jede DB-Änderung braucht bewusst eine Migration, auch kleine Anpassungen
  - Umbenennungen und Datenmigrationen müssen sorgfältig geplant und getestet werden
- Follow-ups:
  - Base-Model im Backend früh anlegen
  - Alembic von Anfang an in das Projekt-Setup aufnehmen
  - DoD und spätere Release-Checks an dieser Regel ausrichten