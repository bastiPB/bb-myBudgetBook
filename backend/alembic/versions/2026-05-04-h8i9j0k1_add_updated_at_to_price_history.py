"""Slice E Fix — updated_at zu subscription_price_history hinzufügen

Die Slice-A-Migration hat updated_at aus subscription_price_history ausgelassen,
obwohl das Modell von BaseModel erbt (created_at + updated_at).
SQLAlchemy versucht beim SELECT die Spalte zu lesen → ProgrammingError.

Semantische Anmerkung: Preishistorie-Einträge werden nie geändert.
updated_at hat hier keinen fachlichen Wert, ist aber Pflicht durch BaseModel.

Revision ID: h8i9j0k1
Revises: g7h8i9j0
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    updated_at zur bestehenden subscription_price_history-Tabelle hinzufügen.
    server_default=NOW() füllt alle vorhandenen Zeilen automatisch.
    """
    op.add_column(
        "subscription_price_history",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            # Bestehende Zeilen bekommen das aktuelle Datum als Startwert
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """
    updated_at wieder entfernen (Rollback auf Slice A).
    """
    op.drop_column("subscription_price_history", "updated_at")
