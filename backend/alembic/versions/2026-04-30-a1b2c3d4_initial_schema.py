"""initial schema

Erstellt die initialen Tabellen: users und subscriptions.

Revision ID: a1b2c3d4
Revises: -
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = None  # Erste Migration, kein Vorgänger
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Tabellen anlegen.
    Diese Funktion wird ausgeführt wenn: alembic upgrade head
    """

    # --- Tabelle: users ---
    # Speichert alle Benutzerkonten der App
    op.create_table(
        "users",
        # Primärschlüssel als UUID — sicherer und besser skalierbar als Integer-IDs
        sa.Column("id", sa.UUID(), nullable=False),
        # E-Mail als Login-Name — muss eindeutig sein (unique=True in Index unten)
        sa.Column("email", sa.String(255), nullable=False),
        # Gehashtes Passwort (Argon2id) — niemals Klartext!
        sa.Column("password_hash", sa.String(255), nullable=False),
        # Timestamps — werden automatisch von der DB gesetzt
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index auf email für schnelle Login-Suche; unique=True verhindert doppelte E-Mails
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- Tabelle: subscriptions ---
    # Speichert alle Abos eines Benutzers
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        # Fremdschlüssel: zu welchem User gehört dieses Abo?
        # ondelete="CASCADE" = wenn der User gelöscht wird, werden seine Abos automatisch mitgelöscht
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Name des Abos (z.B. "Netflix", "Spotify")
        sa.Column("name", sa.String(255), nullable=False),
        # Betrag mit 2 Dezimalstellen (z.B. 12.99)
        # Numeric ist genauer als Float — wichtig bei Geldbeträgen!
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        # Datum der nächsten Fälligkeit
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index auf user_id für schnelle Abfragen "alle Abos eines Users"
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    """
    Tabellen entfernen (Rollback).
    Diese Funktion wird ausgeführt wenn: alembic downgrade -1
    Reihenfolge umkehren: zuerst subscriptions (wegen Fremdschlüssel), dann users.
    """
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
