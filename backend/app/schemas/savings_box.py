"""
Pydantic-Schemas für Sparfach-API (Requests/Responses).

Beträge: dasselbe Komma→Punkt-Normalisierungsmuster wie bei subscriptions (manuelle API-Clients).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.savings_box import (
    SavingsBookingType,
    SavingsBoxStatus,
    SavingsInterval,
    SavingsTermStatus,
)


def _normalize_amount(v: object) -> object:
    """Wie subscriptions: Strings mit Dezimalkomma für Decimal verwertbar machen."""
    if isinstance(v, str):
        return v.replace(",", ".")
    return v


class SavingsBoxCreate(BaseModel):
    """Anlegen eines neuen Sparfachs."""

    name: str
    location: str | None = None
    box_number: str | None = None
    start_date: date
    end_date: date
    interval: SavingsInterval
    min_amount_per_term: Decimal
    penalty_amount: Decimal | None = None
    target_amount: Decimal | None = None
    personal_amount_per_term: Decimal | None = None

    @field_validator(
        "min_amount_per_term",
        "penalty_amount",
        "target_amount",
        "personal_amount_per_term",
        mode="before",
    )
    @classmethod
    def normalize_money(cls, v: object) -> object:
        return _normalize_amount(v)


class SavingsBoxUpdate(BaseModel):
    """PATCH auf Stammdaten (keine Datums-/Intervall-/Schließfelder)."""

    name: str | None = None
    location: str | None = None
    box_number: str | None = None
    target_amount: Decimal | None = None
    personal_amount_per_term: Decimal | None = None

    @field_validator("target_amount", "personal_amount_per_term", mode="before")
    @classmethod
    def normalize_money(cls, v: object) -> object:
        return _normalize_amount(v)


class SavingsBoxCloseRequest(BaseModel):
    """Abschluss eines Sparfachs mit Ist-Auszahlungsbetrag."""

    actual_amount: Decimal
    note: str | None = None

    @field_validator("actual_amount", mode="before")
    @classmethod
    def normalize_money(cls, v: object) -> object:
        return _normalize_amount(v)


class SavingsBookingCreate(BaseModel):
    """
    Neue Buchung.

    deposit/penalty: savings_term_id ist Pflicht (422 durch Service wenn None).
    manual: Term optional.
    """

    savings_term_id: uuid.UUID | None = None
    booking_type: SavingsBookingType
    amount: Decimal
    booking_date: date
    note: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_money(cls, v: object) -> object:
        return _normalize_amount(v)


class SavingsBookingUpdate(BaseModel):
    """PATCH Buchung — Typ und Term sind unveränderlich."""

    amount: Decimal | None = None
    booking_date: date | None = None
    note: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_money(cls, v: object) -> object:
        return _normalize_amount(v)


class SavingsTermRead(BaseModel):
    """Ein Termin in API-Antworten."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    due_date: date
    expected_amount: Decimal
    status: SavingsTermStatus


class SavingsBookingRead(BaseModel):
    """Eine Buchung in API-Antworten."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    savings_term_id: uuid.UUID | None
    booking_type: SavingsBookingType
    amount: Decimal
    booking_date: date
    note: str | None


class BoxSummaryRead(BaseModel):
    """Aggregierte Kennzahlen — wird im Service berechnet, nicht aus einer Zeile gelesen."""

    total_deposited: Decimal
    total_penalties: Decimal
    net_amount: Decimal
    target_amount: Decimal | None
    personal_amount_per_term: Decimal | None
    progress_pct: Decimal | None
    terms_open: int
    terms_fulfilled: int
    terms_missed: int


class SavingsBoxRead(BaseModel):
    """
    Liste oder Einzelabruf ohne eingebettete Term-/Booking-Listen.

    Kein from_attributes: summary und next_open_due_date kommen aus dem Service,
    nicht aus der savings_boxes-Zeile — der Router baut das Objekt explizit.
    """

    id: uuid.UUID
    name: str
    location: str | None
    box_number: str | None
    start_date: date
    end_date: date
    interval: SavingsInterval
    min_amount_per_term: Decimal
    penalty_amount: Decimal | None
    status: SavingsBoxStatus
    next_open_due_date: date | None
    summary: BoxSummaryRead


class SavingsBoxDetail(SavingsBoxRead):
    """Detail inkl. Terminen, Buchungen und Abschlussfeldern."""

    terms: list[SavingsTermRead]
    bookings: list[SavingsBookingRead]
    summary: BoxSummaryRead
    closed_at: datetime | None
    closing_actual_amount: Decimal | None
    closing_expected_amount: Decimal | None
    closing_note: str | None
