import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class BillingInterval(str, enum.Enum):
    """
    Abrechnungsintervall eines Abos.
    str + Enum kombiniert = Werte sind normale Strings ("monthly", "yearly", ...),
    was die Speicherung in der DB und JSON-Serialisierung vereinfacht.
    """
    monthly    = "monthly"     # monatlich
    quarterly  = "quarterly"   # vierteljährlich
    semiannual = "semiannual"  # halbjährlich — v0.2.3
    yearly     = "yearly"      # jährlich
    biennial   = "biennial"    # alle 2 Jahre


class SubscriptionStatus(str, enum.Enum):
    """
    Lebenszyklus-Status eines Abos.
    active    = läuft normal
    suspended = pausiert oder gekündigt (bleibt in der DB erhalten)
    canceled  = endgültig beendet (für spätere Unterscheidung von suspended)
    """
    active = "active"
    suspended = "suspended"
    canceled = "canceled"


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    # Fremdschlüssel auf users.id — UUID-Typ muss mit der Zielspalte übereinstimmen.
    # ondelete="CASCADE" bedeutet: wenn ein User gelöscht wird, werden seine Abos automatisch mitgelöscht.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    # Abrechnungsintervall — bestimmt wie der Betrag auf Monatsbasis umgerechnet wird
    interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, name="billinginterval"),
        default=BillingInterval.monthly,
        nullable=False,
    )

    # --- v0.2.2: Soft-Lifecycle ---

    # Status: active (default), suspended oder canceled
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscriptionstatus"),
        default=SubscriptionStatus.active,
        nullable=False,
    )

    # Wann wurde das Abo abgeschlossen? Pflichtfeld — default: heute beim Anlegen
    started_on: Mapped[date] = mapped_column(Date, nullable=False)

    # Optionales Notizenfeld (z.B. "Kündigung bis 15. eingereicht")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pfad oder URL zum Provider-Logo — wird in Slice D befüllt
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # suspended_at und access_until entfernt in v0.2.3 — stehen jetzt in subscription_pause_history.
    # next_due_date entfernt in v0.2.3 — wird serverseitig aus started_on + N × interval berechnet.


class PaymentStatus(str, enum.Enum):
    """
    Status einer geplanten Buchung (scheduled payment).
    pending = generiert, aber noch nicht bezahlt/geprüft
    paused  = Abo war in diesem Zeitraum pausiert — kein Betrag fällig (v0.2.3)
    matched = als bezahlt erkannt (Slice G)
    missed  = Fälligkeitsdatum überschritten ohne Match (Slice G)
    """
    pending = "pending"
    paused  = "paused"
    matched = "matched"
    missed  = "missed"


class SubscriptionScheduledPayment(BaseModel):
    """
    Eine täglich generierte Soll-Buchung für ein aktives Abo.

    Der Scheduler erzeugt jeden Tag für jedes aktive Abo mit
    subscription_booking_history=True einen Eintrag — sofern der
    UNIQUE-Constraint (subscription_id, due_date) noch nicht existiert.
    So kann der Scheduler beliebig oft laufen, ohne Duplikate zu erzeugen.
    """
    __tablename__ = "subscription_scheduled_payments"

    # Welches Abo? Bei Löschung des Abos fallen alle Einträge automatisch mit.
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )

    # Fälligkeitsdatum dieser Buchung — zusammen mit subscription_id einzigartig (Idempotenz)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Betrag zum Zeitpunkt der Generierung.
    # Bei pausierten Perioden gibt es keinen zahlbaren Betrag (NULL).
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Status: startet immer als "pending"
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="paymentstatus"),
        default=PaymentStatus.pending,
        nullable=False,
    )

    # UNIQUE-Constraint: verhindert doppelte Einträge für denselben Tag + Abo (Idempotenz-Herzstück)
    __table_args__ = (
        UniqueConstraint("subscription_id", "due_date", name="uq_scheduled_payment"),
    )


class SubscriptionPauseHistory(BaseModel):
    """
    Protokolliert jede Pause-Episode eines Abos (v0.2.3).

    Jeder Eintrag steht für einen Zeitraum, in dem das Abo pausiert oder gekündigt war.
    Durch mehrere Einträge können Abos beliebig oft pausiert und reaktiviert werden.

    paused_at:   Datum, an dem die Pause begann
    resumed_at:  Datum der Reaktivierung — None solange noch pausiert
    access_until: Bis wann Zugriff besteht — None wenn sofort eingestellt
    """
    __tablename__ = "subscription_pause_history"

    # Welches Abo? Bei Löschung des Abos fallen alle Pause-Einträge automatisch mit.
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )

    # Startdatum der Pause
    paused_at: Mapped[date] = mapped_column(Date, nullable=False)

    # Enddatum der Pause — None solange das Abo noch pausiert ist
    resumed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Optionaler letzter Zugriffstag (z.B. Ende des bezahlten Monats)
    access_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class SubscriptionPriceHistory(BaseModel):
    """
    Zeichnet jeden Preiswechsel eines Abos auf.

    Wird still geschrieben wenn sich `amount` ändert — kein API-Endpoint in v0.2.2.
    Ermöglicht später genaue historische Kostenberechnungen (Slice E).
    """
    __tablename__ = "subscription_price_history"

    # Welches Abo? Wenn das Abo gelöscht wird, fällt die Historie automatisch mit.
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )

    # Der neue Betrag ab valid_from
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Ab welchem Datum gilt dieser Preis?
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
