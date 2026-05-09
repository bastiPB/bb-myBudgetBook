"""
SQLAlchemy-Modelle für das Sparfach-Feature (v0.2.6).

Tabellen und PostgreSQL-Enum-Namen entsprechen der Migration o5p6q7r8.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SavingsInterval(str, enum.Enum):
    """Rhythmus der Spartermine — gespeicherter Enum-Typ savingsinterval."""

    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class SavingsBoxStatus(str, enum.Enum):
    """Lebenszyklus eines Sparfachs — gespeicherter Enum-Typ savingsboxstatus."""

    active = "active"
    closed = "closed"


class SavingsTermStatus(str, enum.Enum):
    """Status eines einzelnen Termins — gespeicherter Enum-Typ savingstermstatus."""

    open = "open"
    fulfilled = "fulfilled"
    missed = "missed"


class SavingsBookingType(str, enum.Enum):
    """Art der Buchung — gespeicherter Enum-Typ savingsbookingtype."""

    deposit = "deposit"
    penalty = "penalty"
    manual = "manual"


class SavingsBox(BaseModel):
    """Ein Sparfach (digitales Kneipenbuch): Nutzer trackt Termine und Beträge."""

    __tablename__ = "savings_boxes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    box_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    interval: Mapped[SavingsInterval] = mapped_column(
        SAEnum(SavingsInterval, name="savingsinterval"),
        nullable=False,
    )

    min_amount_per_term: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    penalty_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    personal_amount_per_term: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    status: Mapped[SavingsBoxStatus] = mapped_column(
        SAEnum(SavingsBoxStatus, name="savingsboxstatus"),
        default=SavingsBoxStatus.active,
        nullable=False,
    )

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closing_actual_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    closing_expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    closing_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavingsTerm(BaseModel):
    """Ein fälliger Spartermin innerhalb eines Sparfachs."""

    __tablename__ = "savings_terms"

    savings_box_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("savings_boxes.id", ondelete="CASCADE"),
        index=True,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    status: Mapped[SavingsTermStatus] = mapped_column(
        SAEnum(SavingsTermStatus, name="savingstermstatus"),
        default=SavingsTermStatus.open,
        nullable=False,
    )


class SavingsBooking(BaseModel):
    """Eine Buchung (Einzahlung, Strafe oder manuelle Buchung)."""

    __tablename__ = "savings_bookings"

    savings_box_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("savings_boxes.id", ondelete="CASCADE"),
        index=True,
    )
    # Bei DELETE des Terms wird die Referenz NULL gesetzt (Migration SET NULL).
    savings_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("savings_terms.id", ondelete="SET NULL"),
        nullable=True,
    )

    booking_type: Mapped[SavingsBookingType] = mapped_column(
        SAEnum(SavingsBookingType, name="savingsbookingtype"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
