"""add app_settings table

Erstellt die Tabelle app_settings für systemweite Einstellungen.
Legt die einzige Standard-Zeile an:
  - email_signup_enabled = true  (Selbstregistrierung erlaubt)
  - modules = {"subscriptions": true}  (nur Abo-Manager ist standardmäßig aktiv)

Weitere Module schaltet der Admin später bewusst frei (ADR 0007, ADR 0008).

Revision ID: e5f6g7h8
Revises: d4e5f6g7
Create Date: 2026-05-01

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "e5f6g7h8"
down_revision: Union[str, Sequence[str], None] = "d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Tabelle app_settings anlegen und Standard-Zeile einfügen.
    Diese Funktion wird ausgeführt wenn: alembic upgrade head
    """

    # --- Tabelle: app_settings ---
    # Systemweite Einstellungen — immer genau eine Zeile, nie mehr.
    # Neue Module brauchen keine neue Spalte, nur einen neuen Key im JSONB-Feld (ADR 0007).
    op.create_table(
        "app_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        # Selbstregistrierung: True = jeder kann sich selbst einen Account erstellen
        sa.Column(
            "email_signup_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Systemweite Modul-Freigabe: Stufe 1 des Zwei-Stufen-Modells (ADR 0008)
        # JSONB = binäres JSON in PostgreSQL, ::jsonb = expliziter Cast zum richtigen Typ
        sa.Column(
            "modules",
            JSONB(),
            nullable=False,
            server_default=sa.text("""'{"subscriptions": true}'::jsonb"""),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Standard-Zeile einfügen — die App erwartet genau eine Zeile in dieser Tabelle.
    # UUID wird in Python erzeugt statt mit gen_random_uuid() in SQL —
    # gen_random_uuid() ist erst ab PostgreSQL 13 ohne pgcrypto-Extension verfügbar.
    op.execute(
        sa.text(
            """
            INSERT INTO app_settings (id, email_signup_enabled, modules)
            VALUES (:id, true, '{"subscriptions": true}')
            """
        ).bindparams(id=str(uuid.uuid4()))
    )


def downgrade() -> None:
    """
    Tabelle app_settings entfernen (Rollback).
    Diese Funktion wird ausgeführt wenn: alembic downgrade -1
    Die Standard-Zeile wird automatisch mitgelöscht, wenn die Tabelle fällt.
    """
    op.drop_table("app_settings")
