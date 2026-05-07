"""v0.2.4 — Neue Tabelle subscription_billing_history

Erstellt subscription_billing_history als Abloesung fuer subscription_price_history.
Die neue Tabelle historisiert Preis, Intervall und Faelligkeitsanker gemeinsam.

Datenmigration:
- Alle Eintraege aus subscription_price_history werden uebernommen.
- interval = aktuell gespeichertes Intervall des Abos (subscriptions.interval).
- anchor_on = started_on des Abos (erster Anker = Abo-Start).

subscription_price_history bleibt fuer eine Uebergangsrelease erhalten.

Revision ID: m3n4o5p6
Revises: l2m3n4o5
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


billinginterval_enum = postgresql.ENUM(
    "monthly",
    "quarterly",
    "semiannual",
    "yearly",
    "biennial",
    name="billinginterval",
    create_type=False,
)


def upgrade() -> None:
    """
    Neue Tabelle subscription_billing_history anlegen und mit Daten fuellen.

    Wichtig: Der PostgreSQL-Enum "billinginterval" existiert bereits durch
    subscriptions.interval. Deshalb create_type=False — sonst wirft PostgreSQL
    einen "type already exists"-Fehler.
    """

    # 1. Neue Tabelle anlegen
    op.create_table(
        "subscription_billing_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        # create_type=False: Enum "billinginterval" bereits vorhanden — nicht nochmal anlegen
        sa.Column(
            "interval",
            billinginterval_enum,
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("anchor_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # Kein zweiter Eintrag mit demselben valid_from fuer dasselbe Abo
        sa.UniqueConstraint(
            "subscription_id",
            "valid_from",
            name="uq_billing_history_valid_from",
        ),
    )

    # Index fuer schnelle Abfragen aller History-Eintraege eines Abos
    op.create_index(
        "ix_subscription_billing_history_subscription_id",
        "subscription_billing_history",
        ["subscription_id"],
    )

    # 2. Bestehende Preis-Historie migrieren
    # Jeder Eintrag aus subscription_price_history bekommt:
    # - interval = aktuell gespeichertes Intervall des Abos
    # - anchor_on = started_on des Abos (erster Anker war immer der Abo-Start)
    #
    # Python-UUIDs statt gen_random_uuid() — Projekt-Policy: kein pgcrypto benoetigt.
    import uuid as _uuid

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT
                ph.subscription_id,
                ph.amount,
                ph.valid_from,
                s.interval,
                s.started_on
            FROM subscription_price_history ph
            JOIN subscriptions s ON s.id = ph.subscription_id
            ORDER BY ph.subscription_id, ph.valid_from
            """
        )
    ).fetchall()

    for row in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO subscription_billing_history
                    (id, subscription_id, amount, interval, valid_from, anchor_on)
                VALUES
                    (:id, :subscription_id, :amount, :interval, :valid_from, :anchor_on)
                """
            ),
            {
                "id": str(_uuid.uuid4()),
                "subscription_id": str(row.subscription_id),
                "amount": row.amount,
                "interval": row.interval,
                "valid_from": row.valid_from,
                "anchor_on": row.started_on,
            },
        )


def downgrade() -> None:
    """
    subscription_billing_history entfernen.

    subscription_price_history bleibt erhalten (sie wurde in upgrade() nicht veraendert).
    """
    op.drop_index(
        "ix_subscription_billing_history_subscription_id",
        table_name="subscription_billing_history",
    )
    op.drop_table("subscription_billing_history")
    # Den Enum-Typ nicht loeschen — er wird weiterhin von subscriptions.interval genutzt.
