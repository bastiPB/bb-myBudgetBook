"""Slice F — subscription_scheduled_payments + user_module_configurations + scheduler_time

Neue Tabellen:
  - subscription_scheduled_payments: Soll-Buchungen pro Abo-Tag (Scheduler-Output)
  - user_module_configurations: Opt-in-Einstellungen pro User für Module

Neue Spalte:
  - app_settings.scheduler_time: Uhrzeit (HH:MM), zu der der Scheduler täglich läuft

Revision ID: i9j0k1l2
Revises: h8i9j0k1
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Tabelle subscription_scheduled_payments erstellen (Enum 'paymentstatus' wird automatisch angelegt)
    2. Tabelle user_module_configurations erstellen
    3. Spalte scheduler_time zu app_settings hinzufügen
    """

    # Tabelle für tägliche Soll-Buchungen des Schedulers.
    # Hinweis: create_table legt den Enum-Typ 'paymentstatus' automatisch an,
    # wenn es die sa.Enum-Spalte verarbeitet. Kein manuelles .create() nötig.
    # UNIQUE(subscription_id, due_date) ist das Herzstück der Idempotenz:
    # Der Scheduler kann beliebig oft laufen, ohne Duplikate zu erzeugen.
    op.create_table(
        "subscription_scheduled_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "matched", "missed", name="paymentstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "due_date", name="uq_scheduled_payment"),
    )
    # Index auf subscription_id für schnelle Abfragen "alle Buchungen eines Abos"
    op.create_index(
        "ix_subscription_scheduled_payments_subscription_id",
        "subscription_scheduled_payments",
        ["subscription_id"],
    )

    # Tabelle für Modul-Sub-Einstellungen pro User (1:1 mit users).
    # JSONB erlaubt flexible Keys ohne neue Spalten — ADR 0007.
    op.create_table(
        "user_module_configurations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_module_configuration"),
    )

    # scheduler_time zur einzigen app_settings-Zeile hinzufügen.
    # server_default="03:00" füllt die vorhandene Zeile automatisch.
    op.add_column(
        "app_settings",
        sa.Column(
            "scheduler_time",
            sa.String(5),
            nullable=False,
            server_default="03:00",
        ),
    )


def downgrade() -> None:
    """
    Alle Änderungen aus upgrade() in umgekehrter Reihenfolge rückgängig machen.
    """
    op.drop_column("app_settings", "scheduler_time")
    op.drop_table("user_module_configurations")
    op.drop_index(
        "ix_subscription_scheduled_payments_subscription_id",
        table_name="subscription_scheduled_payments",
    )
    op.drop_table("subscription_scheduled_payments")

    # Enum-Typ nach dem DROP der Tabelle entfernen
    paymentstatus = postgresql.ENUM("pending", "matched", "missed", name="paymentstatus")
    paymentstatus.drop(op.get_bind())
