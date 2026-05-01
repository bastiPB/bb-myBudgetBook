"""
alembic/env.py — Einstiegspunkt für alle Alembic-Migrationen.

Alembic ruft diese Datei auf, wenn du Befehle wie
  alembic upgrade head
  alembic revision --autogenerate -m "..."
ausführst. Hier verbinden wir Alembic mit unserer App-Konfiguration und unseren Modellen.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Unsere App-Module importieren ---
# Die Datenbank-URL kommt aus unserer config.py (nicht aus alembic.ini)
from app.config import get_settings

# Base enthält die Metadaten aller registrierten Modelle (Tabellendefinitionen)
from app.database import Base

# Alle Modelle importieren, damit sie bei Base.metadata registriert werden.
# Ohne diesen Import "sieht" Alembic die Tabellen nicht und würde sie löschen!
import app.models  # noqa: F401

# --- Alembic-Konfiguration ---
config = context.config

# Logging aus alembic.ini aktivieren
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata sagt Alembic, wie die DB aussehen SOLL (laut unseren Modellen).
# Alembic vergleicht das mit dem IST-Zustand der DB und generiert den Unterschied.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Migrationen im 'offline'-Modus ausführen.

    Offline = keine echte DB-Verbindung nötig. Alembic generiert nur SQL-Statements
    als Text. Nützlich zum Inspizieren oder für Umgebungen ohne direkten DB-Zugriff.
    """
    # URL aus unserer App-Konfiguration lesen
    url = get_settings().database_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Migrationen im 'online'-Modus ausführen (Normalfall).

    Online = echte Verbindung zur DB. Alembic führt die SQL-Änderungen direkt aus.
    """
    # Engine aus unserer Datenbank-URL erstellen
    # NullPool verhindert, dass Verbindungen nach der Migration offen bleiben
    connectable = engine_from_config(
        {"sqlalchemy.url": get_settings().database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# Alembic entscheidet selbst, welcher Modus verwendet wird
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
