"""Tag-Service-Funktionen für das Subscription-Modul (v0.2.7)."""

import uuid
from collections import defaultdict

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, TagNameAlreadyExistsError, TagNotFoundError
from app.models.subscription_tag import SubscriptionTag, subscription_tag_assignments

from .access import _check_ownership, _get_subscription_or_raise


def get_all_tags(session: Session, user_id: uuid.UUID) -> list[SubscriptionTag]:
    """
    Gibt alle Tags des Users zurück, alphabetisch sortiert nach Name.
    Wird vom TagManagementModal und TagSelector im Frontend geladen.
    """
    stmt = (
        select(SubscriptionTag)
        .where(SubscriptionTag.user_id == user_id)
        .order_by(SubscriptionTag.name)
    )
    return list(session.execute(stmt).scalars().all())


def create_tag(session: Session, user_id: uuid.UUID, name: str, color: str) -> SubscriptionTag:
    """
    Legt einen neuen Tag an.
    Wirft TagNameAlreadyExistsError (409) wenn der Name für diesen User schon existiert.
    Der Name wird von Pydantic bereits bereinigt — kein weiteres strip() nötig.
    """
    tag = SubscriptionTag(user_id=user_id, name=name, color=color)
    session.add(tag)
    try:
        session.commit()
    except IntegrityError:
        # UNIQUE-Constraint (user_id, name) verletzt → Name bereits vorhanden
        session.rollback()
        raise TagNameAlreadyExistsError()
    session.refresh(tag)
    return tag


def update_tag(
    session: Session,
    tag_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str | None,
    color: str | None,
) -> SubscriptionTag:
    """
    Ändert Name und/oder Farbe eines Tags.

    Wirft TagNotFoundError (404) wenn der Tag nicht existiert.
    Wirft ForbiddenError (403) wenn der Tag einem anderen User gehört.
    Wirft TagNameAlreadyExistsError (409) wenn der neue Name bereits vergeben ist.
    """
    tag = session.get(SubscriptionTag, tag_id)
    if tag is None:
        raise TagNotFoundError()
    if tag.user_id != user_id:
        # Kein Hinweis ob der Tag existiert — verhindert User-Enumeration
        raise ForbiddenError()

    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise TagNameAlreadyExistsError()

    session.refresh(tag)
    return tag


def delete_tag(session: Session, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """
    Löscht einen Tag.
    Alle Zuweisungen zu Abos fallen durch ondelete=CASCADE automatisch weg.

    Wirft TagNotFoundError (404) wenn der Tag nicht existiert.
    Wirft ForbiddenError (403) wenn der Tag einem anderen User gehört.
    """
    tag = session.get(SubscriptionTag, tag_id)
    if tag is None:
        raise TagNotFoundError()
    if tag.user_id != user_id:
        raise ForbiddenError()

    session.delete(tag)
    session.commit()


def set_subscription_tags(
    session: Session,
    subscription_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> list[SubscriptionTag]:
    """
    Ersetzt die komplette Tag-Zuweisung eines Abos (PUT-Semantik).

    Alle bisherigen Zuweisungen werden gelöscht und durch die neue Liste ersetzt.
    Leere tag_ids → alle Tags vom Abo entfernen.

    Wirft ForbiddenError wenn das Abo oder ein Tag nicht dem User gehört.
    """
    # Abo-Existenz + Ownership prüfen
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    tags: list[SubscriptionTag] = []
    if tag_ids:
        # Nur Tags laden, die dem User gehören — fremde IDs werden stillschweigend gefiltert
        # und danach durch den len()-Vergleich als Fehler erkannt.
        tags = list(session.execute(
            select(SubscriptionTag).where(
                SubscriptionTag.id.in_(tag_ids),
                SubscriptionTag.user_id == user_id,
            )
        ).scalars().all())

        # Wenn weniger Tags gefunden als angefragt → mindestens eine fremde/ungültige ID dabei
        if len(tags) != len(set(tag_ids)):
            raise ForbiddenError()

    # Alte Zuweisungen löschen
    session.execute(
        delete(subscription_tag_assignments).where(
            subscription_tag_assignments.c.subscription_id == subscription_id
        )
    )

    # Neue Zuweisungen einfügen
    if tags:
        session.execute(
            insert(subscription_tag_assignments).values([
                {"subscription_id": subscription_id, "tag_id": t.id}
                for t in tags
            ])
        )

    session.commit()
    # Alphabetisch zurückgeben — konsistente Reihenfolge für das Frontend
    return sorted(tags, key=lambda t: t.name)


def get_tags_for_subscription(session: Session, subscription_id: uuid.UUID) -> list[SubscriptionTag]:
    """
    Gibt alle Tags eines einzelnen Abos zurück, alphabetisch sortiert.
    Wird beim Laden der Detailansicht genutzt (Slice C — single-sub-Pfad).
    """
    stmt = (
        select(SubscriptionTag)
        .join(subscription_tag_assignments, SubscriptionTag.id == subscription_tag_assignments.c.tag_id)
        .where(subscription_tag_assignments.c.subscription_id == subscription_id)
        .order_by(SubscriptionTag.name)
    )
    return list(session.execute(stmt).scalars().all())


def bulk_load_tags(
    session: Session,
    subscription_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[SubscriptionTag]]:
    """
    Lädt Tags für mehrere Abos in genau zwei DB-Queries (Bulk-Load-Optimierung).

    Verhindert das N+1-Problem: ohne Bulk-Load würde eine Query pro Abo entstehen.
    Wird in list_subscriptions() genutzt — dort gibt es N Abos.

    Rückgabe: { subscription_id → [Tag, Tag, ...] }
    Abos ohne Tags erscheinen nicht im Dict.
    """
    if not subscription_ids:
        return {}

    # Query 1: Alle Zuweisungen für die gegebenen Abos laden
    assignments = session.execute(
        select(
            subscription_tag_assignments.c.subscription_id,
            subscription_tag_assignments.c.tag_id,
        ).where(subscription_tag_assignments.c.subscription_id.in_(subscription_ids))
    ).all()

    if not assignments:
        return {}

    # Alle beteiligten Tag-IDs deduplizieren (Set vermeidet doppelte Ladungen)
    all_tag_ids = list({row.tag_id for row in assignments})

    # Query 2: Alle Tags auf einmal laden
    tags_by_id: dict[uuid.UUID, SubscriptionTag] = {
        t.id: t for t in session.execute(
            select(SubscriptionTag)
            .where(SubscriptionTag.id.in_(all_tag_ids))
        ).scalars().all()
    }

    # Nach Subscription-ID gruppieren
    result: dict[uuid.UUID, list[SubscriptionTag]] = defaultdict(list)
    for row in assignments:
        if row.tag_id in tags_by_id:
            result[row.subscription_id].append(tags_by_id[row.tag_id])

    # Jede Tag-Liste alphabetisch sortieren
    for sub_id in result:
        result[sub_id].sort(key=lambda t: t.name)

    return dict(result)
