"""v0.2.3 Migration B — Spalten droppen + Enums erweitern

Entfernt aus subscriptions:
  - next_due_date (wird künftig immer aus started_on + N × interval berechnet — BUG-01)
  - suspended_at  (ersetzt durch subscription_pause_history)
  - access_until  (ersetzt durch subscription_pause_history)

Enum-Erweiterungen:
  - paymentstatus: neuer Wert 'paused' (für Pausenperioden im Scheduler)
  - billinginterval: neuer Wert 'semiannual' (halbjährliches Abrechnungsintervall)

Hinweis: ALTER TYPE ... ADD VALUE darf in PostgreSQL nicht innerhalb einer Transaktion
laufen. Alembic stellt dafür autocommit_block() bereit.

Revision ID: k1l2m3n4
Revises: j0k1l2m3
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Enum-Typen erweitern (außerhalb Transaktion — PostgreSQL-Einschränkung).
    2. Veraltete Spalten aus subscriptions entfernen.
    """

    # ALTER TYPE ... ADD VALUE muss außerhalb einer Transaktion laufen.
    # autocommit_block() ist der offizielle Alembic-Weg dafür.
    # IF NOT EXISTS verhindert Fehler bei wiederholten Migrationsversuchen.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'paused'")
        op.execute("ALTER TYPE billinginterval ADD VALUE IF NOT EXISTS 'semiannual'")

    # Spalten entfernen — diese drei Felder sind jetzt in subscription_pause_history
    # (suspended_at, access_until) bzw. werden serverseitig berechnet (next_due_date).
    op.drop_column("subscriptions", "next_due_date")
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "access_until")


def downgrade() -> None:
    """
    Spalten wiederherstellen.

    Hinweis: Die Enum-Werte 'paused' und 'semiannual' können in PostgreSQL nicht
    rückgängig gemacht werden (ALTER TYPE ... DROP VALUE existiert nicht).
    Das downgrade ist daher nur teilweise möglich.
    """
    # Spalten mit nullable=True anlegen, weil die alten Werte nicht mehr vorhanden sind
    op.add_column(
        "subscriptions", sa.Column("next_due_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "subscriptions", sa.Column("suspended_at", sa.Date(), nullable=True)
    )
    op.add_column(
        "subscriptions", sa.Column("access_until", sa.Date(), nullable=True)
    )
