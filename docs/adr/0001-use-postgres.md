# ADR 0001: Use Postgres as database backend

## Status
Accepted

## Kontext
Das Projekt ist eine Web-App mit potenziell mehreren Nutzern (Privat/Paare/Familien) und benötigt zuverlässige Concurrency sowie sauberes Datenmodell.

## Entscheidung
Wir verwenden PostgreSQL als Datenbank-Backend.

## Alternativen
- SQLite (einfach, aber Concurrency/Locking bei Writes kann unter Last limitieren)
- MySQL/MariaDB (möglich, aber Postgres ist für viele OSS-Projekte ein stabiler Default)

## Konsequenzen
- Docker Compose braucht einen Postgres Service + Volume
- Migrations/Schema-Management wird wichtig (später)
