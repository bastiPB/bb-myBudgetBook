"""
app/routers/subscription_tags.py — HTTP-Endpunkte für Tag-Verwaltung (v0.2.7).

Tag-CRUD:       GET/POST/PATCH/DELETE /subscriptions/tags
Tag-Zuweisung:  PUT /subscriptions/{subscription_id}/tags

Wichtig: Dieser Router muss in main.py VOR dem subscriptions-Router registriert werden!
GET /subscriptions/tags würde sonst als /{id} mit einem ungültigen UUID gematcht werden.
"""

import uuid

from fastapi import APIRouter, status

from app.dependencies import DatabaseSession, EditorOrAdminUser
from app.schemas.subscription_tag import TagAssignRequest, TagCreate, TagRead, TagUpdate
from app.services.subscriptions.tags import (
    create_tag,
    delete_tag,
    get_all_tags,
    set_subscription_tags,
    update_tag,
)

router = APIRouter(prefix="/subscriptions", tags=["subscription-tags"])


@router.get("/tags", response_model=list[TagRead])
def list_tags(user: EditorOrAdminUser, session: DatabaseSession) -> list[TagRead]:
    """
    Gibt alle Tags des eingeloggten Users zurück, alphabetisch sortiert.
    Wird beim Laden des TagSelectors und des TagManagementModals aufgerufen.
    """
    tags = get_all_tags(session=session, user_id=user.id)
    return [TagRead.model_validate(t) for t in tags]


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_new_tag(body: TagCreate, user: EditorOrAdminUser, session: DatabaseSession) -> TagRead:
    """
    Legt einen neuen Tag an.
    Gibt HTTP 409 zurück wenn der Name für diesen User bereits existiert.
    """
    tag = create_tag(session=session, user_id=user.id, name=body.name, color=body.color)
    return TagRead.model_validate(tag)


@router.patch("/tags/{tag_id}", response_model=TagRead)
def update_existing_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> TagRead:
    """
    Benennt einen Tag um und/oder ändert seine Farbe.
    Alle Body-Felder sind optional — nur gesendete Felder werden geändert.
    """
    tag = update_tag(
        session=session,
        tag_id=tag_id,
        user_id=user.id,
        name=body.name,
        color=body.color,
    )
    return TagRead.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_tag(
    tag_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """
    Löscht einen Tag und automatisch alle Zuweisungen zu Abos (CASCADE).
    """
    delete_tag(session=session, tag_id=tag_id, user_id=user.id)


@router.put("/{subscription_id}/tags", response_model=list[TagRead])
def assign_tags_to_subscription(
    subscription_id: uuid.UUID,
    body: TagAssignRequest,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[TagRead]:
    """
    Setzt die komplette Tag-Zuweisung eines Abos.
    Bestehende Zuweisungen werden vollständig ersetzt.
    Leere Liste → alle Tags vom Abo entfernen.
    """
    tags = set_subscription_tags(
        session=session,
        subscription_id=subscription_id,
        tag_ids=body.tag_ids,
        user_id=user.id,
    )
    return [TagRead.model_validate(t) for t in tags]
