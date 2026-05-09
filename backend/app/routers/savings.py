"""
HTTP-Endpunkte für Sparfächer (Savings Box).

Geschützt wie Abos: nur editor oder admin; Zugriff nur auf eigene Boxen (Service prüft per user_id).
"""

import uuid

from fastapi import APIRouter, status

from app.dependencies import DatabaseSession, EditorOrAdminUser
from app.schemas.savings_box import (
    SavingsBookingCreate,
    SavingsBookingRead,
    SavingsBookingUpdate,
    SavingsBoxCloseRequest,
    SavingsBoxCreate,
    SavingsBoxDetail,
    SavingsBoxRead,
    SavingsBoxUpdate,
    SavingsTermRead,
)
from app.services.savings import (
    close_savings_box,
    create_booking,
    create_box,
    delete_booking,
    get_box_detail,
    get_box_list_projection,
    get_box_or_404,
    list_boxes,
    reopen_savings_box,
    savings_box_to_detail,
    savings_box_to_read,
    update_booking,
    update_box,
    update_term_statuses,
)

router = APIRouter(prefix="/savings/boxes", tags=["savings"])


@router.post("", response_model=SavingsBoxDetail, status_code=status.HTTP_201_CREATED)
def create_savings_box(
    payload: SavingsBoxCreate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBoxDetail:
    """Legt Sparfach inkl. Termine an und liefert die Detailansicht."""
    box = create_box(session, user.id, payload)
    box2, terms, bookings, summary = get_box_detail(session, box.id, user.id)
    return savings_box_to_detail(box2, terms, bookings, summary)


@router.get("", response_model=list[SavingsBoxRead])
def get_savings_boxes(user: EditorOrAdminUser, session: DatabaseSession) -> list[SavingsBoxRead]:
    """Liste aller Sparfächer mit Kennzahlen und nächstem offenen Termin."""
    rows = list_boxes(session, user.id)
    return [savings_box_to_read(box, summary, next_open) for box, summary, next_open in rows]


@router.get("/{box_id}", response_model=SavingsBoxDetail)
def get_savings_box_detail(
    box_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBoxDetail:
    """Einzelansicht — vorher werden überfällige Termine und Strafen aktualisiert."""
    box, terms, bookings, summary = get_box_detail(session, box_id, user.id)
    return savings_box_to_detail(box, terms, bookings, summary)


@router.patch("/{box_id}", response_model=SavingsBoxRead)
def patch_savings_box(
    box_id: uuid.UUID,
    payload: SavingsBoxUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBoxRead:
    """Stammdaten anpassen (ohne Term-Refresh-Seiteneffekt)."""
    update_box(session, box_id, user.id, payload)
    box, summary, next_open = get_box_list_projection(session, box_id, user.id)
    return savings_box_to_read(box, summary, next_open)


@router.post("/{box_id}/close", response_model=SavingsBoxDetail)
def close_box(
    box_id: uuid.UUID,
    payload: SavingsBoxCloseRequest,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBoxDetail:
    """Sparfach abschließen."""
    close_savings_box(session, box_id, user.id, payload)
    box, terms, bookings, summary = get_box_detail(session, box_id, user.id)
    return savings_box_to_detail(box, terms, bookings, summary)


@router.post("/{box_id}/reopen", response_model=SavingsBoxDetail)
def reopen_box(
    box_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBoxDetail:
    """Abgeschlossenes Sparfach wieder öffnen."""
    reopen_savings_box(session, box_id, user.id)
    box, terms, bookings, summary = get_box_detail(session, box_id, user.id)
    return savings_box_to_detail(box, terms, bookings, summary)


@router.get("/{box_id}/terms", response_model=list[SavingsTermRead])
def get_savings_terms(
    box_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[SavingsTermRead]:
    """Terminliste (gleicher Refresh wie Detailansicht)."""
    _box, terms, _bookings, _summary = get_box_detail(session, box_id, user.id)
    return [SavingsTermRead.model_validate(t) for t in terms]


@router.post("/{box_id}/terms/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh_savings_terms(
    box_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """Überfällige Termine markieren und ggf. Strafen anlegen — ohne Response-Body."""
    box = get_box_or_404(session, box_id, user.id)
    update_term_statuses(session, box)
    session.flush()
    session.commit()


@router.get("/{box_id}/bookings", response_model=list[SavingsBookingRead])
def get_savings_bookings(
    box_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[SavingsBookingRead]:
    """Buchungsliste (inkl. Term-Refresh wie Detail)."""
    _box, _terms, bookings, _summary = get_box_detail(session, box_id, user.id)
    return [SavingsBookingRead.model_validate(b) for b in bookings]


@router.post("/{box_id}/bookings", response_model=SavingsBookingRead, status_code=status.HTTP_201_CREATED)
def post_savings_booking(
    box_id: uuid.UUID,
    payload: SavingsBookingCreate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBookingRead:
    """Neue Buchung."""
    booking = create_booking(session, box_id, user.id, payload)
    return SavingsBookingRead.model_validate(booking)


@router.patch("/{box_id}/bookings/{booking_id}", response_model=SavingsBookingRead)
def patch_savings_booking(
    box_id: uuid.UUID,
    booking_id: uuid.UUID,
    payload: SavingsBookingUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SavingsBookingRead:
    """Buchung anpassen."""
    booking = update_booking(session, box_id, user.id, booking_id, payload)
    return SavingsBookingRead.model_validate(booking)


@router.delete("/{box_id}/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_savings_booking(
    box_id: uuid.UUID,
    booking_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """Buchung löschen."""
    delete_booking(session, box_id, user.id, booking_id)
