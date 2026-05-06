"""v0.2.3 — Scheduled Payment amount nullable for paused entries

Erlaubt amount=NULL in subscription_scheduled_payments, damit pausierte
Perioden ohne Zahlungsbetrag gespeichert werden koennen.

Revision ID: l2m3n4o5
Revises: k1l2m3n4
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2m3n4o5"
down_revision: Union[str, Sequence[str], None] = "k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow NULL amount for paused scheduled payments."""
    op.alter_column(
        "subscription_scheduled_payments",
        "amount",
        existing_type=sa.Numeric(10, 2),
        nullable=True,
    )


def downgrade() -> None:
    """Restore NOT NULL constraint for amount."""
    op.alter_column(
        "subscription_scheduled_payments",
        "amount",
        existing_type=sa.Numeric(10, 2),
        nullable=False,
    )
