"""
app/routers/admin.py — HTTP-Endpunkte für Admin-Operationen.

Alle Routen hier sind durch "AdminUser" geschützt:
FastAPI prüft bei jedem Request automatisch ob der Aufrufer
eingeloggt ist UND die Rolle "admin" hat — sonst kommt HTTP 403.
"""

import uuid

from fastapi import APIRouter, status

from app.dependencies import AdminUser, DatabaseSession
from app.schemas.admin import AdminUserCreate, RoleUpdate
from app.schemas.user import UserRead
from app.services.admin import approve_user, create_user_as_admin, delete_user, list_users, update_user_role
from app.services.scheduler_service import generate_scheduled_payments

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserRead:
    """
    Legt einen neuen User direkt an (sofort active, mit gewählter Rolle).

    Erwartet: { "email": "...", "password": "...", "role": "editor" }
    Gibt HTTP 201 Created zurück.
    Fehler: 409 wenn die E-Mail bereits vergeben ist.

    Wann ist das sinnvoll?
    Wenn der Admin ein Familienmitglied einlädt — der Admin gibt ein initiales
    Passwort vor und teilt es dem Familienmitglied mit. Kein Warten auf Freigabe.
    """
    user = create_user_as_admin(session, payload)
    return UserRead.model_validate(user)


@router.get("/users", response_model=list[UserRead])
def get_users(admin: AdminUser, session: DatabaseSession) -> list[UserRead]:
    """
    Gibt alle registrierten User zurück (sortiert nach Registrierungsdatum).

    Nützlich um pending User zu sehen und freizugeben.
    Nur für Admins erreichbar.
    """
    users = list_users(session)
    # Jedes SQLAlchemy-User-Objekt in ein UserRead-Schema umwandeln
    return [UserRead.model_validate(u) for u in users]


@router.post("/users/{user_id}/approve", response_model=UserRead)
def approve(user_id: uuid.UUID, admin: AdminUser, session: DatabaseSession) -> UserRead:
    """
    Gibt einen pending User frei — er kann sich danach einloggen.

    user_id: UUID des Users (aus der URL)
    Fehler: 404 wenn User nicht gefunden
    """
    user = approve_user(session, user_id)
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}/role", response_model=UserRead)
def change_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserRead:
    """
    Ändert die Rolle eines Users.

    Erwartet als JSON: { "role": "admin" | "editor" | "default" }
    Fehler:
      - 404 wenn User nicht gefunden
      - 403 wenn Admin versucht seine eigene Rolle zu ändern
    """
    user = update_user_role(session, user_id, payload.role, admin.id)
    return UserRead.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: uuid.UUID, admin: AdminUser, session: DatabaseSession) -> None:
    """
    Löscht einen User unwiderruflich.
    Alle Abos des Users werden automatisch mitgelöscht (CASCADE).

    Fehler:
      - 404 wenn User nicht gefunden
      - 403 wenn Admin versucht sich selbst zu löschen
    """
    delete_user(session, user_id, admin.id)


@router.post("/subscriptions/trigger-payments")
def trigger_payments(admin: AdminUser, session: DatabaseSession) -> dict[str, int]:
    """
    Löst den Scheduler manuell aus — erzeugt Soll-Buchungen für heute.

    Nützlich für Tests oder wenn der Scheduler einen Lauf verpasst hat.
    Gibt zurück: { "created": 3 } — Anzahl neu angelegter Einträge.
    Idempotent: bereits vorhandene Einträge werden nicht doppelt erzeugt.
    Nur für Admins erreichbar.
    """
    count = generate_scheduled_payments(session)
    return {"created": count}
