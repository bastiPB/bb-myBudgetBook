"""
app/routers/subscriptions.py — HTTP-Endpunkte für Abo-Verwaltung.

Alle Routen hier sind durch "EditorOrAdminUser" geschützt:
FastAPI prüft bei jedem Request automatisch ob der Aufrufer
eingeloggt ist UND die Rolle 'editor' oder 'admin' hat.

Warum nicht "CurrentUser"?
User mit der Rolle 'default' sind im Wartezustand — sie haben noch keine
Rolle zugewiesen bekommen und dürfen keine Daten sehen. Erst nach der
Rollenzuweisung durch einen Admin bekommt der User Zugriff.

Ein User kann immer nur seine eigenen Abos sehen und bearbeiten.
"""

import uuid

from fastapi import APIRouter, status

from app.dependencies import DatabaseSession, EditorOrAdminUser
from app.schemas.subscription import OverviewRead, SubscriptionCreate, SubscriptionRead, SubscriptionUpdate
from app.services.subscriptions import (
    create_subscription,
    delete_subscription,
    get_overview,
    list_subscriptions,
    update_subscription,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionRead])
def get_subscriptions(user: EditorOrAdminUser, session: DatabaseSession) -> list[SubscriptionRead]:
    """
    Gibt alle Abos des eingeloggten Users zurück.

    Sortiert nach Fälligkeitsdatum (nächste Fälligkeit zuerst).
    Nur eingeloggte User erreichbar.
    """
    subs = list_subscriptions(session, user.id)
    return [SubscriptionRead.model_validate(s) for s in subs]


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: SubscriptionCreate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Legt ein neues Abo für den eingeloggten User an.

    Erwartet als JSON: { "name": "...", "amount": 9.99, "next_due_date": "2026-06-01" }
    Gibt HTTP 201 Created zurück (= "erfolgreich angelegt").
    """
    sub = create_subscription(session, user.id, payload)
    return SubscriptionRead.model_validate(sub)


@router.get("/overview", response_model=OverviewRead)
def overview(user: EditorOrAdminUser, session: DatabaseSession) -> OverviewRead:
    """
    Gibt eine Übersicht der Abos zurück.

    monthly_total: Summe aller Abo-Beträge.
    upcoming:      Abos, die in den nächsten 30 Tagen fällig sind.

    Warum steht diese Route VOR /{subscription_id}?
    FastAPI prüft Routen in der Reihenfolge wie sie definiert sind.
    Käme /overview nach /{subscription_id}, würde FastAPI versuchen
    "overview" als UUID zu lesen — das schlägt mit HTTP 422 fehl.
    """
    result = get_overview(session, user.id)
    return OverviewRead(
        monthly_total=result.monthly_total,
        upcoming=[SubscriptionRead.model_validate(s) for s in result.upcoming],
    )


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Bearbeitet ein bestehendes Abo.

    Es müssen nur die Felder mitgeschickt werden, die sich ändern sollen.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    sub = update_subscription(session, subscription_id, user.id, payload)
    return SubscriptionRead.model_validate(sub)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """
    Löscht ein Abo unwiderruflich.

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    delete_subscription(session, subscription_id, user.id)
