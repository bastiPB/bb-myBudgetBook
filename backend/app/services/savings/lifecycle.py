"""Abschließen und erneutes Öffnen eines Sparfachs."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import SavingsBoxNotClosedError
from app.models.savings_box import SavingsBooking, SavingsBookingType, SavingsBox, SavingsBoxStatus
from app.schemas.savings_box import SavingsBoxCloseRequest

from .access import assert_box_is_open, get_box_or_404


def close_savings_box(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SavingsBoxCloseRequest,
) -> SavingsBox:
    """
    Schließt das Sparfach — Snapshot der erwarteten Auszahlung aus Buchungen.

    closing_expected_amount = Summe Einzahlungen − Summe Strafgebühren (manuelle Buchungen außen vor).
    """
    box = get_box_or_404(session, box_id, user_id)
    assert_box_is_open(box)

    bookings = list(
        session.scalars(select(SavingsBooking).where(SavingsBooking.savings_box_id == box.id)).all()
    )
    deposits = Decimal("0")
    penalties = Decimal("0")
    for b in bookings:
        if b.booking_type == SavingsBookingType.deposit:
            deposits += b.amount
        elif b.booking_type == SavingsBookingType.penalty:
            penalties += b.amount

    box.closing_expected_amount = deposits - penalties
    box.closed_at = datetime.now(timezone.utc)
    box.status = SavingsBoxStatus.closed
    box.closing_actual_amount = payload.actual_amount
    box.closing_note = payload.note

    session.commit()
    session.refresh(box)
    return box


def reopen_savings_box(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SavingsBox:
    """Hebt den Abschluss auf — alle Abschlussfelder werden geleert."""
    box = get_box_or_404(session, box_id, user_id)

    if box.status != SavingsBoxStatus.closed:
        raise SavingsBoxNotClosedError()

    box.status = SavingsBoxStatus.active
    box.closed_at = None
    box.closing_actual_amount = None
    box.closing_expected_amount = None
    box.closing_note = None

    session.commit()
    session.refresh(box)
    return box
