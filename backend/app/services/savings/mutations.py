"""
Schreibende Sparfach-Operationen (anlegen, patchen, Buchungen).

Transaktionsende per session.commit() — wie bei subscriptions/mutations.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    SavingsBookingNotFoundError,
    SavingsBookingValidationError,
    SavingsPenaltyDeleteBlockedError,
)
from app.models.savings_box import (
    SavingsBooking,
    SavingsBookingType,
    SavingsBox,
    SavingsBoxStatus,
    SavingsTerm,
    SavingsTermStatus,
)
from app.schemas.savings_box import (
    SavingsBookingCreate,
    SavingsBookingUpdate,
    SavingsBoxCreate,
    SavingsBoxUpdate,
)

from .access import assert_box_is_open, get_box_or_404
from .terms import _term_has_penalty_booking, generate_terms


def create_box(session: Session, user_id: uuid.UUID, payload: SavingsBoxCreate) -> SavingsBox:
    """
    Legt Sparfach inkl. aller Termine an.

    Ein session.flush() ist nötig, bevor Term-Zeilen den FK auf savings_boxes setzen dürfen.
    """
    box = SavingsBox(
        user_id=user_id,
        name=payload.name,
        location=payload.location,
        box_number=payload.box_number,
        start_date=payload.start_date,
        end_date=payload.end_date,
        interval=payload.interval,
        min_amount_per_term=payload.min_amount_per_term,
        penalty_amount=payload.penalty_amount,
        target_amount=payload.target_amount,
        personal_amount_per_term=payload.personal_amount_per_term,
        status=SavingsBoxStatus.active,
    )
    session.add(box)
    session.flush()

    for term in generate_terms(box):
        session.add(term)

    session.commit()
    session.refresh(box)
    return box


def update_box(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SavingsBoxUpdate,
) -> SavingsBox:
    """PATCH Stammdaten (nur gesetzte Felder)."""
    box = get_box_or_404(session, box_id, user_id)
    assert_box_is_open(box)

    for field in payload.model_fields_set:
        setattr(box, field, getattr(payload, field))

    session.commit()
    session.refresh(box)
    return box


def create_booking(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SavingsBookingCreate,
) -> SavingsBooking:
    """Legt eine Buchung an und aktualisiert ggf. den Term-Status (Einzahlungen)."""
    box = get_box_or_404(session, box_id, user_id)
    assert_box_is_open(box)

    if payload.booking_type == SavingsBookingType.deposit:
        if payload.savings_term_id is None:
            raise SavingsBookingValidationError(
                "Für eine Einzahlung muss savings_term_id gesetzt sein."
            )
        term = _require_term_in_box(session, payload.savings_term_id, box.id)
        if payload.amount < term.expected_amount:
            raise SavingsBookingValidationError(
                f"Betrag muss mindestens {term.expected_amount} betragen."
            )
        booking = _build_booking_row(box.id, payload)
        session.add(booking)
        session.flush()
        _sync_term_and_penalty_after_deposit_change(session, box, term)

    elif payload.booking_type == SavingsBookingType.penalty:
        if payload.savings_term_id is None:
            raise SavingsBookingValidationError(
                "Für eine Strafgebühr muss savings_term_id gesetzt sein."
            )
        _require_term_in_box(session, payload.savings_term_id, box.id)
        booking = _build_booking_row(box.id, payload)
        session.add(booking)

    else:
        # manual
        if payload.savings_term_id is not None:
            _require_term_in_box(session, payload.savings_term_id, box.id)
        booking = _build_booking_row(box.id, payload)
        session.add(booking)

    session.commit()
    session.refresh(booking)
    return booking


def update_booking(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
    booking_id: uuid.UUID,
    payload: SavingsBookingUpdate,
) -> SavingsBooking:
    """Aktualisiert Betrag, Buchungsdatum und Notiz einer Buchung."""
    box = get_box_or_404(session, box_id, user_id)
    assert_box_is_open(box)

    booking = _get_booking_in_box_or_404(session, box_id, booking_id)

    for field in payload.model_fields_set:
        setattr(booking, field, getattr(payload, field))

    if (
        booking.booking_type == SavingsBookingType.deposit
        and booking.savings_term_id is not None
        and "amount" in payload.model_fields_set
    ):
        term = session.get(SavingsTerm, booking.savings_term_id)
        if term is None:
            raise SavingsBookingValidationError("Term zur Buchung nicht gefunden.")
        if booking.amount < term.expected_amount:
            raise SavingsBookingValidationError(
                f"Betrag muss mindestens {term.expected_amount} betragen."
            )
        _sync_term_and_penalty_after_deposit_change(session, box, term)

    session.commit()
    session.refresh(booking)
    return booking


def delete_booking(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
    booking_id: uuid.UUID,
) -> None:
    """Löscht eine Buchung mit Typ-spezifischen Regeln."""
    box = get_box_or_404(session, box_id, user_id)
    assert_box_is_open(box)

    booking = _get_booking_in_box_or_404(session, box_id, booking_id)

    if booking.booking_type == SavingsBookingType.penalty:
        term_id = booking.savings_term_id
        # Ohne Term-Bezug gibt es keine Einzahlungsregel — löschen erlauben (Datenkorrektur).
        if term_id is not None and not _term_has_any_deposit(session, term_id):
            raise SavingsPenaltyDeleteBlockedError()
        session.delete(booking)

    elif booking.booking_type == SavingsBookingType.deposit:
        term_id = booking.savings_term_id
        session.delete(booking)
        session.flush()
        if term_id is not None:
            term = session.get(SavingsTerm, term_id)
            if term is not None:
                _sync_term_and_penalty_after_deposit_change(session, box, term)

    else:
        session.delete(booking)

    session.commit()


def _build_booking_row(box_pk: uuid.UUID, payload: SavingsBookingCreate) -> SavingsBooking:
    """Erzeugt das SavingsBooking-ORM-Objekt aus der Create-Payload."""
    return SavingsBooking(
        savings_box_id=box_pk,
        savings_term_id=payload.savings_term_id,
        booking_type=payload.booking_type,
        amount=payload.amount,
        booking_date=payload.booking_date,
        note=payload.note,
    )


def _require_term_in_box(session: Session, term_id: uuid.UUID, box_pk: uuid.UUID) -> SavingsTerm:
    """Lädt einen Term oder wirft 422 wenn er nicht zur Box gehört."""
    term = session.get(SavingsTerm, term_id)
    if term is None or term.savings_box_id != box_pk:
        raise SavingsBookingValidationError("Der Term gehört nicht zu diesem Sparfach.")
    return term


def _get_booking_in_box_or_404(
    session: Session,
    box_pk: uuid.UUID,
    booking_id: uuid.UUID,
) -> SavingsBooking:
    """Lädt eine Buchung dieser Box oder wirft SavingsBookingNotFoundError."""
    stmt = select(SavingsBooking).where(
        SavingsBooking.id == booking_id,
        SavingsBooking.savings_box_id == box_pk,
    )
    booking = session.scalars(stmt).first()
    if booking is None:
        raise SavingsBookingNotFoundError()
    return booking


def _term_has_qualifying_deposit(session: Session, term: SavingsTerm) -> bool:
    """True wenn mindestens eine Einzahlung >= erwartetem Mindestbetrag existiert."""
    stmt = select(SavingsBooking).where(
        SavingsBooking.savings_term_id == term.id,
        SavingsBooking.booking_type == SavingsBookingType.deposit,
    )
    for b in session.scalars(stmt):
        if b.amount >= term.expected_amount:
            return True
    return False


def _sync_term_status_from_deposits(session: Session, term: SavingsTerm) -> None:
    """Setzt Term-Status aus vorhandenen Einzahlungen (erfüllt / offen / verpasst)."""
    today = date.today()
    if _term_has_qualifying_deposit(session, term):
        term.status = SavingsTermStatus.fulfilled
        return
    term.status = SavingsTermStatus.missed if term.due_date < today else SavingsTermStatus.open


def _maybe_create_miss_penalty(session: Session, box: SavingsBox, term: SavingsTerm) -> None:
    """Legt eine automatische Strafe für einen verpassten Term an (idempotent)."""
    if term.status != SavingsTermStatus.missed:
        return
    penalty_rate = box.penalty_amount
    if penalty_rate is None or penalty_rate <= 0:
        return
    if _term_has_penalty_booking(session, term.id):
        return
    session.add(
        SavingsBooking(
            savings_box_id=box.id,
            savings_term_id=term.id,
            booking_type=SavingsBookingType.penalty,
            amount=penalty_rate,
            booking_date=date.today(),
            note=None,
        )
    )


def _sync_term_and_penalty_after_deposit_change(
    session: Session,
    box: SavingsBox,
    term: SavingsTerm,
) -> None:
    """Nach Änderungen an Einzahlungen Term neu auswerten und ggf. Strafe ergänzen."""
    _sync_term_status_from_deposits(session, term)
    if term.status == SavingsTermStatus.missed:
        _maybe_create_miss_penalty(session, box, term)


def _term_has_any_deposit(session: Session, term_id: uuid.UUID) -> bool:
    """Mind. eine Einzahlungsbuchung zu diesem Term (ohne Mindestbetrag-Prüfung)."""
    stmt = (
        select(SavingsBooking.id)
        .where(
            SavingsBooking.savings_term_id == term_id,
            SavingsBooking.booking_type == SavingsBookingType.deposit,
        )
        .limit(1)
    )
    return session.execute(stmt).first() is not None
