#!/bin/sh
# entrypoint.sh — Wird ausgeführt, wenn der Backend-Container startet.
#
# Reihenfolge:
#   1. Datenbankmigrationen anwenden (alembic upgrade head)
#   2. API-Server starten (uvicorn)
#
# "set -e" bedeutet: bei jedem Fehler sofort abbrechen.
# Wenn z.B. die Migration fehlschlägt, startet der Server NICHT.
set -e

echo "Wende Datenbankmigrationen an..."
alembic upgrade head

echo "Starte API-Server..."
# "exec" ersetzt diesen Shell-Prozess durch uvicorn.
# Das ist wichtig damit Docker Signale (z.B. Strg+C) korrekt weiterleitet.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
