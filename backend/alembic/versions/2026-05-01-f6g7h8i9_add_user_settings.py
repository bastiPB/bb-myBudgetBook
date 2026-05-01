"""add user_settings table

Erstellt die Tabelle user_settings für persönliche User-Einstellungen
(display_name, avatar_url, aktive Module).

Kein Standard-Eintrag — die Zeile wird lazy beim ersten Profil-Zugriff angelegt
(get_or_create-Pattern in services/profile.py, Schritt 4).

Revision ID: f6g7h8i9
Revises: e5f6g7h8
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "f6g7h8i9"
down_revision: Union[str, Sequence[str], None] = "e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Tabelle user_settings anlegen.
    Diese Funktion wird ausgeführt wenn: alembic upgrade head
    """

    # --- Tabelle: user_settings ---
    # Persönliche Einstellungen — maximal eine Zeile pro User (UNIQUE auf user_id).
    # Wird nicht beim Login befüllt, sondern lazy beim ersten GET/PATCH /profile/settings.
    op.create_table(
        "user_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        # Fremdschlüssel auf users.id — UNIQUE = ein User, eine Zeile.
        # ondelete="CASCADE" = wenn der User gelöscht wird, fallen seine Einstellungen automatisch mit.
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Optionaler Anzeigename — Fallback im Frontend: E-Mail vor dem @
        sa.Column("display_name", sa.String(100), nullable=True),
        # Platzhalter für Profilbild-URL — Upload-Feature folgt in v0.2.x
        sa.Column("avatar_url", sa.String(500), nullable=True),
        # Persönliche Modul-Auswahl: Stufe 2 des Zwei-Stufen-Modells (ADR 0008)
        # {} = noch keine Module gewählt → Dashboard zeigt Onboarding-Card
        sa.Column(
            "modules",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Stellt sicher: genau eine Einstellungs-Zeile pro User
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )


def downgrade() -> None:
    """
    Tabelle user_settings entfernen (Rollback).
    Diese Funktion wird ausgeführt wenn: alembic downgrade -1
    """
    op.drop_table("user_settings")
