"""Lifecycle-Aktionen fuer Abos (Pausieren, Fortsetzen, Kuendigen, Hard Delete)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import InvalidSubscriptionStatusError
from app.models.subscription import Subscription, SubscriptionPauseHistory, SubscriptionStatus
from app.schemas.subscription import SubscriptionDetail, SuspendPayload

from .access import _check_ownership, _get_subscription_or_raise
from .readers import get_subscription_detail


def suspend_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SuspendPayload,
) -> Subscription:
    """
    Setzt ein Abo auf 'suspended' und schreibt einen Pause-Eintrag.

    Soft-Lifecycle: das Abo bleibt in der DB — keine Daten gehen verloren.
    Nur aktive Abos koennen suspendiert werden (409 wenn bereits suspended/canceled).
    Der Pause-Eintrag ermoeglicht mehrfaches Pausieren und Resumieren (v0.2.3).
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    if sub.status != SubscriptionStatus.active:
        raise InvalidSubscriptionStatusError(
            f"Nur aktive Abos können suspendiert werden. Aktueller Status: {sub.status.value}"
        )

    today = date.today()
    sub.status = SubscriptionStatus.suspended

    # Pause-Episode in subscription_pause_history festhalten.
    # resumed_at=None bedeutet: Pause noch aktiv (wird beim Resume gesetzt).
    pause = SubscriptionPauseHistory(
        subscription_id=sub.id,
        paused_at=today,
        access_until=payload.access_until,
    )
    session.add(pause)

    session.commit()
    session.refresh(sub)
    return sub


def resume_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Subscription:
    """
    Setzt ein suspendiertes Abo wieder auf 'active'.

    Nur suspended darf zurueck auf active — active oder canceled ergeben keinen Sinn.
    Der letzte offene Pause-Eintrag (resumed_at IS NULL) wird auf heute geschlossen.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    if sub.status != SubscriptionStatus.suspended:
        raise InvalidSubscriptionStatusError(
            f"Nur pausierte Abos können fortgesetzt werden. Aktueller Status: {sub.status.value}"
        )

    # Letzten noch offenen Pause-Eintrag suchen und schliessen.
    # "Offen" bedeutet: resumed_at ist noch NULL.
    open_pause = session.execute(
        select(SubscriptionPauseHistory)
        .where(
            SubscriptionPauseHistory.subscription_id == sub.id,
            SubscriptionPauseHistory.resumed_at.is_(None),
        )
        .order_by(SubscriptionPauseHistory.paused_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if open_pause:
        open_pause.resumed_at = date.today()

    sub.status = SubscriptionStatus.active

    session.commit()
    session.refresh(sub)
    return sub


def cancel_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SuspendPayload | None = None,
) -> SubscriptionDetail:
    """
    Kuendigt ein Abo endgueltig (status = 'canceled').

    Im Gegensatz zu suspend ist canceled final — ein Resumieren ist nicht vorgesehen.
    Ein Pause-Eintrag wird geschrieben damit die Buchungshistorie sauber endet
    (Scheduler erzeugt ab canceled keine weiteren Eintraege mehr).
    access_until aus dem Payload: optional — bis wann ist die Leistung noch nutzbar?
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Bereits gekuendigt? — doppelte Kuendigung sinnlos
    if sub.status == SubscriptionStatus.canceled:
        raise InvalidSubscriptionStatusError("Das Abo ist bereits gekündigt.")

    today = date.today()
    sub.status = SubscriptionStatus.canceled

    # Pause-Eintrag schreiben — markiert den Endpunkt in der Buchungshistorie.
    # paused_at = Kuendigungsdatum, resumed_at = None (endgueltig).
    pause = SubscriptionPauseHistory(
        subscription_id=sub.id,
        paused_at=today,
        access_until=payload.access_until if payload is not None else None,
    )
    session.add(pause)

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)


def delete_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """
    Loescht ein Abo unwiderruflich (Hard Delete).

    In v0.2.2 bleibt DELETE erhalten, aber die bevorzugte Aktion ist Suspend.
    Hard Delete ist nur fuer Abos gedacht, bei denen wirklich keine Historie benoetigt wird.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    session.delete(sub)
    session.commit()
