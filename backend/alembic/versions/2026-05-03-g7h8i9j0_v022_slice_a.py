"""v0.2.2 Slice A — neue Felder für subscriptions + Tabelle subscription_price_history

Änderungen an Tabelle subscriptions:
- status (Enum: active/suspended/canceled) — Soft-Lifecycle statt sofort löschen
- started_on (Date) — wann wurde das Abo abgeschlossen?
- notes (Text, optional) — freies Notizenfeld
- logo_url (String, optional) — Pfad zum Provider-Logo (kommt Slice D)
- suspended_at (Date, optional) — wann wurde das Abo pausiert/gekündigt?
- access_until (Date, optional) — bis wann ist die Leistung noch verfügbar?

Neue Tabelle subscription_price_history:
- Zeichnet Preisänderungen auf (kein API-Endpoint in v0.2.2, nur silent write)

Revision ID: g7h8i9j0
Revises: f6g7h8i9
Create Date: 2026-05-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0"
down_revision: Union[str, Sequence[str], None] = "f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL-Enum-Typ für den Abo-Status — separat definiert damit upgrade/downgrade ihn nutzen können
subscriptionstatus_enum = sa.Enum("active", "suspended", "canceled", name="subscriptionstatus")


def upgrade() -> None:
    """
    Neue Felder und Tabellen anlegen.
    Diese Funktion wird ausgeführt wenn: alembic upgrade head
    """

    # 1. Den neuen Enum-Typ in PostgreSQL anlegen (muss vor der Spalte existieren).
    # checkfirst=True verhindert Fehler wenn der Typ bereits existiert (z.B. bei mehrfachem Run).
    subscriptionstatus_enum.create(op.get_bind(), checkfirst=True)

    # 2. Neue Spalten zur bestehenden subscriptions-Tabelle hinzufügen.
    # server_default="active" sorgt dafür, dass alle bestehenden Zeilen den Wert "active" bekommen.
    op.add_column(
        "subscriptions",
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "canceled", name="subscriptionstatus"),
            nullable=False,
            server_default="active",
        ),
    )
    # server_default=sa.text("CURRENT_DATE") = PostgreSQL-Funktion, gibt das heutige Datum zurück
    op.add_column(
        "subscriptions",
        sa.Column("started_on", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
    )
    op.add_column("subscriptions", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("subscriptions", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("subscriptions", sa.Column("suspended_at", sa.Date(), nullable=True))
    op.add_column("subscriptions", sa.Column("access_until", sa.Date(), nullable=True))

    # 3. Neue Tabelle für Preishistorie — Daten laufen ab sofort mit, API/UI folgen in Slice E.
    op.create_table(
        "subscription_price_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        # valid_from = ab wann gilt dieser Preis (= Datum der Änderung)
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # ondelete="CASCADE": wenn ein Abo gelöscht wird, fällt seine Preishistorie automatisch mit
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index auf subscription_id anlegen — PostgreSQL erstellt FK-Indizes NICHT automatisch.
    # Ohne Index: bei "Zeig mir alle Preiseinträge für Abo X" wird die ganze Tabelle gescannt.
    # Entspricht index=True im SubscriptionPriceHistory-Modell.
    op.create_index(
        "ix_subscription_price_history_subscription_id",
        "subscription_price_history",
        ["subscription_id"],
    )


def downgrade() -> None:
    """
    Änderungen rückgängig machen (Rollback).
    Diese Funktion wird ausgeführt wenn: alembic downgrade -1
    """

    # Reihenfolge: Index und abhängige Tabelle zuerst löschen, dann Spalten, dann Enum-Typ
    op.drop_index("ix_subscription_price_history_subscription_id", table_name="subscription_price_history")
    op.drop_table("subscription_price_history")
    op.drop_column("subscriptions", "access_until")
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "logo_url")
    op.drop_column("subscriptions", "notes")
    op.drop_column("subscriptions", "started_on")
    op.drop_column("subscriptions", "status")
    # Enum-Typ löschen — muss nach den Spalten kommen, die ihn verwenden
    subscriptionstatus_enum.drop(op.get_bind(), checkfirst=True)
