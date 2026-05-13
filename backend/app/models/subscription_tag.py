"""
SQLAlchemy-Modelle für Subscription Tags (v0.2.7).

Tabellen:
- subscription_tags: Tag-Definitionen pro User (Name + Farbe)
- subscription_tag_assignments: M:N-Verbindungstabelle (Abo ↔ Tag)
"""

import uuid

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseModel


# Verbindungstabelle für die M:N-Beziehung zwischen Abos und Tags.
# Keine eigene BaseModel-ID nötig — der zusammengesetzte Primary Key (sub_id + tag_id)
# reicht als eindeutige Identifikation.
# ondelete="CASCADE" auf beiden Seiten: löscht man ein Abo oder einen Tag,
# verschwinden die Zuweisungen automatisch — keine verwaisten Einträge.
subscription_tag_assignments = Table(
    "subscription_tag_assignments",
    Base.metadata,
    Column(
        "subscription_id",
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PG_UUID(as_uuid=True),
        ForeignKey("subscription_tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SubscriptionTag(BaseModel):
    """
    Ein benutzerdefinierter Tag zur Kategorisierung von Abos (v0.2.7).

    Jeder Tag gehört genau einem User und hat einen Namen + eine Farbe.
    Ein Tag kann beliebig vielen Abos desselben Users zugewiesen werden.
    Die Verbindung wird über subscription_tag_assignments hergestellt.
    """

    __tablename__ = "subscription_tags"

    # Fremdschlüssel auf den User — bei User-Löschung fallen alle seine Tags automatisch mit.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Name des Tags — z.B. "Streaming", "KI-Abos", "Server" (max 50 Zeichen)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Farbe als Hex-String aus der vordefinierten Palette — z.B. "#6366f1" (immer 7 Zeichen: # + 6 Hex)
    color: Mapped[str] = mapped_column(String(7), nullable=False)

    # Kein doppelter Tag-Name pro User — DB-Constraint als letzte Sicherheitslinie
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_subscription_tag_user_name"),
    )
