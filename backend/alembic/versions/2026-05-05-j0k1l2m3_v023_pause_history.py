"""v0.2.3 Migration A — subscription_pause_history anlegen + Datenmigration

Neue Tabelle:
  - subscription_pause_history: Protokolliert jede Pause/Resume-Episode eines Abos.
    Ersetzt die alten Einzel-Spalten suspended_at / access_until in subscriptions.

Datenmigration:
  - Bestehende Abos mit status IN ('suspended', 'canceled') und suspended_at IS NOT NULL
    bekommen automatisch einen Eintrag in subscription_pause_history.

Revision ID: j0k1l2m3
Revises: i9j0k1l2
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j0k1l2m3"
down_revision: Union[str, Sequence[str], None] = "i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Tabelle subscription_pause_history anlegen.
    2. Bestehende suspended/canceled-Abos in die neue Tabelle migrieren.
    """

    # Neue Tabelle: jede Pause ist ein eigener Datensatz.
    # Dadurch kann ein Abo beliebig oft pausiert und wieder aktiviert werden,
    # ohne dass wir mehr als eine Spalte brauchen.
    op.create_table(
        "subscription_pause_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        # paused_at: Datum, an dem das Abo pausiert/gekündigt wurde
        sa.Column("paused_at", sa.Date(), nullable=False),
        # resumed_at: Datum der Reaktivierung — NULL wenn noch pausiert
        sa.Column("resumed_at", sa.Date(), nullable=True),
        # access_until: bis wann Zugriff noch besteht — NULL wenn sofortig
        sa.Column("access_until", sa.Date(), nullable=True),
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
    )

    # Index: damit Abfragen "alle Pausen eines Abos" effizient sind
    op.create_index(
        "ix_subscription_pause_history_subscription_id",
        "subscription_pause_history",
        ["subscription_id"],
    )

    # Datenmigration: bestehende suspended/canceled-Abos übernehmen.
    # Wir lesen direkt aus der DB und schreiben den ersten Pause-Eintrag.
    # import uuid direkt hier — damit kein Modul-Import am Anfang der Datei nötig ist.
    import uuid as _uuid

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, suspended_at, access_until FROM subscriptions "
            "WHERE status IN ('suspended', 'canceled') AND suspended_at IS NOT NULL"
        )
    ).fetchall()

    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO subscription_pause_history "
                "(id, subscription_id, paused_at, resumed_at, access_until, created_at, updated_at) "
                "VALUES (:id, :sub_id, :paused_at, NULL, :access_until, NOW(), NOW())"
            ),
            {
                "id": str(_uuid.uuid4()),
                "sub_id": str(row.id),
                "paused_at": row.suspended_at,
                "access_until": row.access_until,
            },
        )


def downgrade() -> None:
    """
    Tabelle subscription_pause_history entfernen (Datenmigration ist irreversibel —
    die ursprünglichen suspended_at/access_until-Werte sind in Migration B gedroppt).
    """
    op.drop_index(
        "ix_subscription_pause_history_subscription_id",
        table_name="subscription_pause_history",
    )
    op.drop_table("subscription_pause_history")
