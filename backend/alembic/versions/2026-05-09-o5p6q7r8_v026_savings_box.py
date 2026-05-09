"""v0.2.6 — Sparfach (Savings Box): Enums + Tabellen savings_boxes, savings_terms, savings_bookings

Revision ID: o5p6q7r8
Revises: n4o5p6q7
Create Date: 2026-05-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "o5p6q7r8"
down_revision: Union[str, Sequence[str], None] = "n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL-Enums mit create_type=False — sonst legt create_table jeden Typ nochmal an
# und wir bekommen DuplicateObject (CREATE TYPE wurde bereits in upgrade() ausgeführt).
# Gleiches Muster wie billinginterval in v024 subscription_billing_history.
savingsinterval_enum = postgresql.ENUM(
    "weekly", "biweekly", "monthly", name="savingsinterval", create_type=False
)
savingsboxstatus_enum = postgresql.ENUM(
    "active", "closed", name="savingsboxstatus", create_type=False
)
savingstermstatus_enum = postgresql.ENUM(
    "open", "fulfilled", "missed", name="savingstermstatus", create_type=False
)
savingsbookingtype_enum = postgresql.ENUM(
    "deposit", "penalty", "manual", name="savingsbookingtype", create_type=False
)


def upgrade() -> None:
    """Neue Savings-Box-Tabellen und Enum-Typen anlegen."""

    savingsinterval_enum.create(op.get_bind(), checkfirst=True)
    savingsboxstatus_enum.create(op.get_bind(), checkfirst=True)
    savingstermstatus_enum.create(op.get_bind(), checkfirst=True)
    savingsbookingtype_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "savings_boxes",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("box_number", sa.String(100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "interval",
            savingsinterval_enum,
            nullable=False,
        ),
        sa.Column("min_amount_per_term", sa.Numeric(10, 2), nullable=False),
        sa.Column("penalty_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("target_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("personal_amount_per_term", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "status",
            savingsboxstatus_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_actual_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("closing_expected_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("closing_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_savings_boxes_user_id", "savings_boxes", ["user_id"])

    op.create_table(
        "savings_terms",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.Column("savings_box_id", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            savingstermstatus_enum,
            nullable=False,
            server_default="open",
        ),
        sa.ForeignKeyConstraint(["savings_box_id"], ["savings_boxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_savings_terms_savings_box_id",
        "savings_terms",
        ["savings_box_id"],
    )

    op.create_table(
        "savings_bookings",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.Column("savings_box_id", sa.UUID(), nullable=False),
        sa.Column("savings_term_id", sa.UUID(), nullable=True),
        sa.Column(
            "booking_type",
            savingsbookingtype_enum,
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["savings_box_id"], ["savings_boxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["savings_term_id"], ["savings_terms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_savings_bookings_savings_box_id",
        "savings_bookings",
        ["savings_box_id"],
    )


def downgrade() -> None:
    """Savings-Tabellen und Enum-Typen entfernen."""

    op.drop_index("ix_savings_bookings_savings_box_id", table_name="savings_bookings")
    op.drop_table("savings_bookings")

    op.drop_index("ix_savings_terms_savings_box_id", table_name="savings_terms")
    op.drop_table("savings_terms")

    op.drop_index("ix_savings_boxes_user_id", table_name="savings_boxes")
    op.drop_table("savings_boxes")

    savingsbookingtype_enum.drop(op.get_bind(), checkfirst=True)
    savingstermstatus_enum.drop(op.get_bind(), checkfirst=True)
    savingsboxstatus_enum.drop(op.get_bind(), checkfirst=True)
    savingsinterval_enum.drop(op.get_bind(), checkfirst=True)
