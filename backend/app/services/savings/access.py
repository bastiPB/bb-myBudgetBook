"""Zugriffsschutz für Sparfächer (404 / 403 / geschlossene Box)."""

import uuid

from sqlalchemy.orm import Session

from app.exceptions import SavingsBoxClosedError, SavingsBoxNotFoundError
from app.models.savings_box import SavingsBox, SavingsBoxStatus


def get_box_or_404(session: Session, box_id: uuid.UUID, user_id: uuid.UUID) -> SavingsBox:
    """
    Lädt eine SavingsBox für den angegebenen Nutzer.

    Wirft SavingsBoxNotFoundError (404), wenn die Box fehlt oder nicht zum Nutzer gehört.
    So lässt sich nicht erkennen, ob eine fremde UUID existiert (vgl. Chunk 7 Done-Kriterien).
    """
    box = session.get(SavingsBox, box_id)
    if box is None or box.user_id != user_id:
        raise SavingsBoxNotFoundError()
    return box


def assert_box_is_open(box: SavingsBox) -> None:
    """
    Stellt sicher, dass das Sparfach noch aktiv ist.

    Vor Create/Update/Delete von Buchungen oder Stammdaten aufrufen.
    Wirft SavingsBoxClosedError (409), wenn status == closed.
    """
    if box.status == SavingsBoxStatus.closed:
        raise SavingsBoxClosedError()
