"""rename viewer to editor in userrole enum

Benennt den Enum-Wert 'viewer' → 'editor' im PostgreSQL-Typ 'userrole' um.

Warum reicht ALTER TYPE ohne UPDATE auf der users-Tabelle?
PostgreSQL speichert Enum-Werte intern als OIDs (numerische IDs), nicht als Strings.
Die Spalte users.role enthält also eine OID, kein "viewer"-String.
ALTER TYPE RENAME VALUE ändert nur den Label in pg_enum — die OID bleibt gleich.
Alle bestehenden Zeilen zeigen danach automatisch "editor".

Revision ID: d4e5f6g7
Revises: c3d4e5f6
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6g7"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Benennt den Enum-Wert 'viewer' in 'editor' um.
    Verfügbar ab PostgreSQL 10 — wir verwenden 14+, also kein Problem.
    """
    op.execute("ALTER TYPE userrole RENAME VALUE 'viewer' TO 'editor'")


def downgrade() -> None:
    """
    Macht das Umbenennen rückgängig: 'editor' → 'viewer'.
    """
    op.execute("ALTER TYPE userrole RENAME VALUE 'editor' TO 'viewer'")
