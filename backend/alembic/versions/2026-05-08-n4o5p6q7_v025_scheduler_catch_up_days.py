"""v0.2.5 — app_settings.scheduler_catch_up_days

Catch-up-Fenster fuer den Buchungs-Scheduler (Tage rueckwirkend nachfuellen).
Default 60 Tage wie bisher im Code. Obergrenze wird in der API validiert (max 730).

Revision ID: n4o5p6q7
Revises: m3n4o5p6
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n4o5p6q7"
down_revision: Union[str, Sequence[str], None] = "m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "scheduler_catch_up_days",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.alter_column("app_settings", "scheduler_catch_up_days", server_default=None)


def downgrade() -> None:
    op.drop_column("app_settings", "scheduler_catch_up_days")
