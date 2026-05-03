---
doc: v021-ui-shell-dashboard-initial
status: released
owner: bastiPB
---

# v0.2.1 — UI Shell + Dashboard Initial

## Ziel

Dieses Mini-Release liefert eine stabile, wiederverwendbare UI-Grundstruktur:

- Header
- Sidebar
- Footer
- erste Dashboard-Initialansicht

Schwerpunkt ist Frontend-Struktur und UX-Basis, nicht neue Business-Logik.

## Scope

### In Scope

- Gemeinsames App-Layout fuer geschuetzte Seiten
- Responsives Verhalten fuer Desktop und Mobile
- Klarer Dashboard-Einstieg mit sinnvoller Erstansicht
- Definierter Empty-State fuer fehlende Inhalte

### Out of Scope

- Neue API-Endpunkte
- Neue Datenbanktabellen oder Migrationen
- Vollausbau einzelner Finanz-Module

## Akzeptanzkriterien

- Header, Sidebar und Footer sind visuell und technisch konsistent
- Navigation bleibt bei unterschiedlichen Bildschirmbreiten benutzbar
- Dashboard zeigt bei leerem Zustand hilfreiche Orientierung
- Bestehende geschuetzte Routen funktionieren unveraendert
- Frontend Lint und Build sind erfolgreich

## Technische Leitplanken

- Keine Umgehung von ProtectedRoute/AdminRoute
- Bestehende Modul-Logik (activeModules) bleibt erhalten
- Komponentenstruktur bleibt nachvollziehbar und wartbar

## Doku-Check fuer den Release

- CHANGELOG `[Unreleased]` aktuell halten
- Roadmap-Eintrag fuer v0.2.1 gepflegt
- Release-Checklist v0.2.1-Addendum abhaken
- Falls dauerhafte Architekturentscheidung entsteht: ADR schreiben

## Release-Vorbereitung 0.2.1

- Feature-Branch erstellen (`feat/ui-shell-dashboard-initial`)
- UI-Implementierung + lokale Validierung
- PR gegen main mit kurzer Scope-Beschreibung
- CI gruen
- Changelog finalisieren und Tag `v0.2.1` setzen
