"""Zugriffsschutz und 404-/403-Hilfsfunktionen fuer Abos."""

import uuid

from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, SubscriptionNotFoundError
from app.models.subscription import Subscription


def _get_subscription_or_raise(session: Session, subscription_id: uuid.UUID) -> Subscription:
    """
    Hilfsfunktion: Abo laden und 404 werfen wenn es nicht existiert.

    Wird von mehreren Service-Funktionen verwendet um Duplikate zu vermeiden.
    """
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()
    return sub


def _check_ownership(sub: Subscription, user_id: uuid.UUID) -> None:
    """
    Hilfsfunktion: Prueft ob das Abo dem angegebenen User gehoert.

    Wirft ForbiddenError wenn nicht — so kann kein User fremde Abos bearbeiten.
    """
    if sub.user_id != user_id:
        raise ForbiddenError()
