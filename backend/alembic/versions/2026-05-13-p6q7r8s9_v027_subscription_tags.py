"""v0.2.7 — Subscription Tags: Tabellen subscription_tags + subscription_tag_assignments

Revision ID: p6q7r8s9
Revises: o5p6q7r8
Create Date: 2026-05-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p6q7r8s9"
down_revision: Union[str, Sequence[str], None] = "o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Neue Tag-Tabellen anlegen."""

    # subscription_tags: Tag-Definitionen pro User (Name + Hex-Farbe)
    # UNIQUE(user_id, name) verhindert doppelte Tag-Namen pro User.
    op.create_table(
        "subscription_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_subscription_tag_user_name"),
    )

    # subscription_tag_assignments: M:N-Verbindungstabelle (Abo ↔ Tag)
    # Zusammengesetzter Primary Key verhindert Duplikate ohne extra UNIQUE-Constraint.
    # CASCADE auf beiden Seiten: löscht man ein Abo oder einen Tag, fallen Zuweisungen automatisch weg.
    op.create_table(
        "subscription_tag_assignments",
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscription_tags.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Tag-Tabellen wieder entfernen."""

    # Verbindungstabelle zuerst löschen — sie hat Fremdschlüssel auf subscription_tags
    op.drop_table("subscription_tag_assignments")
    op.drop_table("subscription_tags")
