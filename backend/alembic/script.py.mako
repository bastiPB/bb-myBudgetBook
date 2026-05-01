"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Revision-IDs — Alembic nutzt diese, um die Reihenfolge der Migrationen zu verwalten
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Änderungen anwenden (Vorwärts-Migration)."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Änderungen rückgängig machen (Rückwärts-Migration / Rollback)."""
    ${downgrades if downgrades else "pass"}
