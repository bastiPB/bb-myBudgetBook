"""add billing interval to subscriptions

Fügt das Abrechnungsintervall zur subscriptions-Tabelle hinzu.
Bestehende Abos erhalten den Standardwert "monthly".

Revision ID: c3d4e5f6
Revises: b2c3d4e5
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum-Typ als Objekt definieren — wird in upgrade() erstellt und in downgrade() gelöscht
billinginterval_enum = sa.Enum("monthly", "quarterly", "yearly", "biennial", name="billinginterval")


def upgrade() -> None:
    """
    Enum-Typ in PostgreSQL anlegen und interval-Spalte hinzufügen.
    Bestehende Abos erhalten den Standardwert "monthly".
    """
    # Schritt 1: Enum-Typ in der DB anlegen
    billinginterval_enum.create(op.get_bind(), checkfirst=True)

    # Schritt 2: Spalte hinzufügen — zuerst nullable=True damit bestehende Zeilen keinen Fehler werfen
    op.add_column(
        "subscriptions",
        sa.Column("interval", billinginterval_enum, nullable=True),
    )

    # Schritt 3: Alle bestehenden Abos auf "monthly" setzen
    op.execute("UPDATE subscriptions SET interval = 'monthly' WHERE interval IS NULL")

    # Schritt 4: Spalte auf NOT NULL setzen — ab jetzt ist ein Wert Pflicht
    op.alter_column("subscriptions", "interval", nullable=False)


def downgrade() -> None:
    """
    interval-Spalte und Enum-Typ wieder entfernen (Rollback).
    Reihenfolge: erst Spalte löschen, dann Enum-Typ.
    """
    op.drop_column("subscriptions", "interval")
    billinginterval_enum.drop(op.get_bind(), checkfirst=True)
