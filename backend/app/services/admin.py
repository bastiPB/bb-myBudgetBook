"""
app/services/admin.py — Business-Logik für Admin-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle Funktionen hier dürfen nur von Admins aufgerufen werden —
die Prüfung passiert in dependencies.py (AdminUser).
"""

import uuid

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import EmailAlreadyExistsError, ForbiddenError, UserNotFoundError
from app.models.user import User, UserRole, UserStatus
from app.schemas.admin import AdminUserCreate

# PasswordHasher-Instanz — einmal erstellen, mehrfach verwenden (nur Konfiguration, kein Zustand)
_ph = PasswordHasher()


def create_user_as_admin(session: Session, payload: AdminUserCreate) -> User:
    """
    Legt einen neuen User direkt an — sofort active, keine Freigabe nötig.

    Unterschied zur normalen Registrierung (services/auth.py register_user):
    - Status ist direkt "active" statt "pending"
    - Die Rolle wird vom Admin frei gewählt
    - Der Admin teilt das initiale Passwort dem User mit

    Wirft EmailAlreadyExistsError wenn die E-Mail bereits vergeben ist.
    """
    # Passwort hashen — niemals Klartext in die DB!
    hashed_password = _ph.hash(payload.password)

    new_user = User(
        email=payload.email,
        password_hash=hashed_password,
        role=payload.role,
        status=UserStatus.active,  # Direkt active — Admin hat den User bereits freigegeben
    )
    session.add(new_user)

    try:
        session.commit()
        session.refresh(new_user)
    except IntegrityError:
        # IntegrityError = E-Mail existiert bereits (UNIQUE-Constraint)
        session.rollback()
        raise EmailAlreadyExistsError()

    return new_user


def list_users(session: Session) -> list[User]:
    """
    Gibt alle User zurück, sortiert nach Registrierungsdatum (älteste zuerst).
    Nützlich für den Admin, um pending User zu sehen und freizugeben.
    """
    stmt = select(User).order_by(User.created_at)
    return list(session.execute(stmt).scalars().all())


def approve_user(session: Session, user_id: uuid.UUID) -> User:
    """
    Gibt einen pending User frei (setzt status auf "active").

    Nach der Freigabe kann sich der User einloggen.
    Ist der User bereits active, passiert nichts (idempotent = mehrfach aufrufbar ohne Schaden).

    Wirft UserNotFoundError wenn der User nicht existiert.
    """
    user = session.get(User, user_id)
    if not user:
        raise UserNotFoundError()

    # Bereits active → nichts tun, trotzdem erfolgreich zurückgeben
    if user.status != UserStatus.active:
        user.status = UserStatus.active
        session.commit()
        session.refresh(user)

    return user


def update_user_role(
    session: Session,
    user_id: uuid.UUID,
    new_role: UserRole,
    requesting_admin_id: uuid.UUID,
) -> User:
    """
    Ändert die Rolle eines Users.

    Sicherheitsregeln:
    - Ein Admin kann sich nicht selbst degradieren (eigene Rolle ändern ist verboten).
    - Das verhindert, dass der letzte Admin sich aus Versehen ausschließt.

    Wirft UserNotFoundError wenn der User nicht existiert.
    Wirft ForbiddenError wenn ein Admin versucht seine eigene Rolle zu ändern.
    """
    user = session.get(User, user_id)
    if not user:
        raise UserNotFoundError()

    # Admin darf seine eigene Rolle nicht ändern — Schutz vor versehentlichem Selbst-Ausschluss
    if user.id == requesting_admin_id:
        raise ForbiddenError()

    user.role = new_role
    session.commit()
    session.refresh(user)
    return user


def delete_user(
    session: Session,
    user_id: uuid.UUID,
    requesting_admin_id: uuid.UUID,
) -> None:
    """
    Löscht einen User unwiderruflich aus der Datenbank.
    Dank ondelete="CASCADE" werden auch alle Abos des Users automatisch gelöscht.

    Sicherheitsregel:
    - Ein Admin kann sich nicht selbst löschen.

    Wirft UserNotFoundError wenn der User nicht existiert.
    Wirft ForbiddenError wenn ein Admin versucht sich selbst zu löschen.
    """
    user = session.get(User, user_id)
    if not user:
        raise UserNotFoundError()

    # Admin darf sich nicht selbst löschen
    if user.id == requesting_admin_id:
        raise ForbiddenError()

    session.delete(user)
    session.commit()
