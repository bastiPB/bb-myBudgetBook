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
from app.schemas.subscription import (
    OverviewRead,
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionUpdate,
    SuspendPayload,
)
from app.services.subscriptions import (
    create_subscription,
    delete_subscription,
    get_overview,
    get_subscription,
    list_subscriptions,
    resume_subscription,
    suspend_subscription,
    update_subscription,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionRead])
def get_subscriptions(user: EditorOrAdminUser, session: DatabaseSession) -> list[SubscriptionRead]:
    """
    Gibt alle Abos des eingeloggten Users zurück.

    Sortiert nach Fälligkeitsdatum (nächste Fälligkeit zuerst).
    Enthält alle Status (active, suspended, canceled).
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

    Erwartet als JSON:
    { "name": "Netflix", "amount": 9.99, "next_due_date": "2026-06-01" }
    Gibt HTTP 201 Created zurück (= "erfolgreich angelegt").
    """
    sub = create_subscription(session, user.id, payload)
    return SubscriptionRead.model_validate(sub)


@router.get("/overview", response_model=OverviewRead)
def overview(user: EditorOrAdminUser, session: DatabaseSession) -> OverviewRead:
    """
    Gibt eine Übersicht der Abos zurück.

    monthly_total: Summe aller aktiven Abo-Beträge (normiert auf Monat).
    upcoming:      Aktive Abos, die in den nächsten 30 Tagen fällig sind.

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


@router.get("/{subscription_id}", response_model=SubscriptionRead)
def detail(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Gibt ein einzelnes Abo zurück (Detailansicht).

    Neu in v0.2.2 — wird von der Detailseite genutzt (Slice C).
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    sub = get_subscription(session, subscription_id, user.id)
    return SubscriptionRead.model_validate(sub)


@router.post("/{subscription_id}/suspend", response_model=SubscriptionRead)
def suspend(
    subscription_id: uuid.UUID,
    payload: SuspendPayload,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Setzt ein Abo auf 'suspended' (Soft-Lifecycle).

    Das Abo bleibt in der DB erhalten — keine Daten gehen verloren.
    Optional: access_until angeben, bis wann die Leistung noch nutzbar ist.

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn das Abo bereits suspended oder canceled ist
    """
    sub = suspend_subscription(session, subscription_id, user.id, payload)
    return SubscriptionRead.model_validate(sub)


@router.post("/{subscription_id}/resume", response_model=SubscriptionRead)
def resume(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Setzt ein pausiertes Abo wieder auf 'active'.

    suspended_at und access_until werden geleert.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn das Abo nicht den Status 'suspended' hat
    """
    sub = resume_subscription(session, subscription_id, user.id)
    return SubscriptionRead.model_validate(sub)


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
    Wenn amount sich ändert, wird automatisch ein Eintrag in price_history geschrieben.
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
    Löscht ein Abo unwiderruflich (Hard Delete).

    Bevorzugte Aktion in v0.2.2: POST /subscriptions/{id}/suspend statt Delete.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    delete_subscription(session, subscription_id, user.id)
