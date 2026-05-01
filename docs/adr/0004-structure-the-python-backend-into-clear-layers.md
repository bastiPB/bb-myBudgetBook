# ADR 0004: Structure the Python backend into clear layers

## Status
Accepted

## Kontext
Ein wachsendes Backend wird schnell unübersichtlich, wenn HTTP-Endpunkte, Konfiguration, Datenbankzugriff und Business-Logik in einer einzelnen `main.py` oder wenigen Sammeldateien landen.

Das erschwert Tests, Änderungen an einzelnen Features und spätere Erweiterungen wie Budgets, Exporte oder weitere Integrationen.

## Entscheidung
Das Python-Backend wird in klar getrennte Schichten strukturiert. HTTP-Logik, Business-Logik, Datenmodelle, Schemas und Infrastruktur werden in getrennten Modulen organisiert.

Die Zielstruktur ist:

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   └── services/
├── alembic/
├── tests/
└── pyproject.toml
```

Architekturregeln:
- Router wissen nichts über DB-Details
- Services wissen nichts über HTTP
- Modelle kennen keine Business-Logik

Neue Features werden als eigener Slice ergänzt, zum Beispiel über `models/`, `schemas/`, `routers/` und `services/` desselben Fachbereichs.

## Alternativen
1) Zentrale `main.py` mit gemischter Logik
   - Pro: am Anfang schnell
   - Contra: skaliert schlecht, schwer testbar, hohe Kopplung

2) Nur grobe Trennung in wenige Dateien
   - Pro: weniger Struktur zu Beginn
   - Contra: Verantwortlichkeiten verschwimmen schnell

3) Frühzeitige komplexe Clean-Architecture mit vielen Abstraktionsschichten
   - Pro: sehr strikte Entkopplung
   - Contra: für den aktuellen Projektstand unnötig schwergewichtig

## Konsequenzen
- Pro:
  - Features bleiben lokal und verständlich erweiterbar
  - HTTP, Business-Logik und Datenmodell können getrennt getestet werden
  - Neue Fachbereiche lassen sich hinzufügen, ohne bestehende Dateien zu überladen
- Contra:
  - Es gibt mehr Dateien und etwas mehr Anfangsstruktur
  - Teamdisziplin ist nötig, damit die Schichtengrenzen nicht wieder verwischen
- Follow-ups:
  - Projektgerüst beim Start des Backends an dieser Struktur ausrichten
  - `main.py` bewusst klein halten
  - Neue Features an der Slice-Struktur messen