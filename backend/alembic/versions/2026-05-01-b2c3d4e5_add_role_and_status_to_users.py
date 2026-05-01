"""add role and status to users

Fügt die Spalten 'role' und 'status' zur users-Tabelle hinzu.
Beide sind Enum-Typen, die direkt in PostgreSQL als eigene Typen angelegt werden.

Revision ID: b2c3d4e5
Revises: a1b2c3d4
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4"  # Vorgänger: initial schema
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum-Typen als Objekte definieren — werden in upgrade() erstellt und in downgrade() gelöscht
userrole_enum = sa.Enum("admin", "viewer", "default", name="userrole")
userstatus_enum = sa.Enum("pending", "active", name="userstatus")


def upgrade() -> None:
    """
    Enum-Typen in PostgreSQL anlegen und Spalten zur users-Tabelle hinzufügen.
    Bestehende User (falls vorhanden) erhalten Standardwerte.
    """
    # Schritt 1: Enum-Typen in der DB anlegen
    # PostgreSQL speichert Enums als eigene Typen — effizienter als VARCHAR mit Check-Constraint
    userrole_enum.create(op.get_bind(), checkfirst=True)
    userstatus_enum.create(op.get_bind(), checkfirst=True)

    # Schritt 2: Spalten hinzufügen
    # nullable=True zuerst — damit bestehende Zeilen ohne Fehler angelegt werden können
    op.add_column(
        "users",
        sa.Column("role", userrole_enum, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("status", userstatus_enum, nullable=True),
    )

    # Schritt 3: Standardwerte für bereits bestehende Zeilen setzen
    op.execute("UPDATE users SET role = 'default' WHERE role IS NULL")
    op.execute("UPDATE users SET status = 'pending' WHERE status IS NULL")

    # Schritt 4: Spalten auf NOT NULL setzen — ab jetzt sind Werte Pflicht
    op.alter_column("users", "role", nullable=False)
    op.alter_column("users", "status", nullable=False)


def downgrade() -> None:
    """
    Spalten und Enum-Typen wieder entfernen (Rollback).
    Reihenfolge: erst Spalten löschen, dann Enum-Typen.
    """
    op.drop_column("users", "status")
    op.drop_column("users", "role")
    userstatus_enum.drop(op.get_bind(), checkfirst=True)
    userrole_enum.drop(op.get_bind(), checkfirst=True)
