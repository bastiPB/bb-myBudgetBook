import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class BillingInterval(str, enum.Enum):
    """
    Abrechnungsintervall eines Abos.
    str + Enum kombiniert = Werte sind normale Strings ("monthly", "yearly", ...),
    was die Speicherung in der DB und JSON-Serialisierung vereinfacht.
    """
    monthly = "monthly"      # monatlich
    quarterly = "quarterly"  # vierteljährlich
    yearly = "yearly"        # jährlich
    biennial = "biennial"    # alle 2 Jahre


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    # Fremdschlüssel auf users.id — UUID-Typ muss mit der Zielspalte übereinstimmen.
    # ondelete="CASCADE" bedeutet: wenn ein User gelöscht wird, werden seine Abos automatisch mitgelöscht.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    next_due_date: Mapped[date] = mapped_column(Date)

    # Abrechnungsintervall — bestimmt wie der Betrag auf Monatsbasis umgerechnet wird
    interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, name="billinginterval"),
        default=BillingInterval.monthly,
        nullable=False,
    )
