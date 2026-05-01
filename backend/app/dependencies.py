"""
app/dependencies.py — Wiederverwendbare FastAPI-Abhängigkeiten (Dependencies).

Was ist eine Dependency?
  FastAPI kann Funktionen automatisch aufrufen und das Ergebnis in Endpunkte "injizieren".
  Beispiel: Statt in jedem Endpunkt manuell session = SessionLocal() zu schreiben,
  deklariert man einfach "session: DatabaseSession" als Parameter — FastAPI erledigt den Rest.

Das nennt sich "Dependency Injection" (DI) — ein wichtiges Muster in der Softwareentwicklung.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.exceptions import ForbiddenError, NotAuthenticatedError
from app.models.user import User, UserRole
from app.security import COOKIE_NAME, decode_session_token

# Kurzform für "eine SQLAlchemy-Session, automatisch von FastAPI bereitgestellt"
# Verwendung in Endpunkten: def my_route(session: DatabaseSession) -> ...
DatabaseSession = Annotated[Session, Depends(get_db_session)]


def _get_current_user(request: Request, session: DatabaseSession) -> User:
    """
    Liest und verifiziert den Session-Cookie. Gibt den eingeloggten User zurück.

    Wirft NotAuthenticatedError (HTTP 401) wenn:
      - kein Cookie vorhanden
      - Cookie abgelaufen oder manipuliert
      - User nicht mehr in der DB
    """
    settings = get_settings()

    # Cookie aus dem Request lesen
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise NotAuthenticatedError()

    # Token verifizieren und user_id extrahieren
    user_id_str = decode_session_token(token, settings.app_secret_key)
    if not user_id_str:
        # Token ist abgelaufen oder wurde manipuliert
        raise NotAuthenticatedError()

    # User aus der Datenbank laden
    user = session.get(User, uuid.UUID(user_id_str))
    if not user:
        # User wurde zwischenzeitlich gelöscht
        raise NotAuthenticatedError()

    return user


def _get_admin_user(current_user: Annotated[User, Depends(_get_current_user)]) -> User:
    """
    Prüft ob der eingeloggte User Admin-Rechte hat.

    Baut auf _get_current_user auf (User muss zuerst eingeloggt sein).
    Wirft ForbiddenError (HTTP 403) wenn der User kein Admin ist.
    """
    if current_user.role != UserRole.admin:
        # Kein Admin → Zugriff verweigert
        raise ForbiddenError()
    return current_user


def _get_editor_or_admin_user(current_user: Annotated[User, Depends(_get_current_user)]) -> User:
    """
    Prüft ob der eingeloggte User die Rolle 'editor' oder 'admin' hat.

    Baut auf _get_current_user auf (User muss zuerst eingeloggt sein).
    Wirft ForbiddenError (HTTP 403) wenn der User nur die Rolle 'default' hat.

    Warum diese Trennung?
    'default' ist der Wartezustand nach der Registrierung — der User hat noch
    keine Rolle zugewiesen bekommen und darf keine Daten sehen oder bearbeiten.
    Nur 'editor' und 'admin' dürfen auf Abos zugreifen.
    """
    if current_user.role not in (UserRole.editor, UserRole.admin):
        # default-Rolle → Zugriff verweigert, bis der Admin eine Rolle vergibt
        raise ForbiddenError()
    return current_user


# Kurzformen für die Verwendung in Endpunkten:
#
# Jeder eingeloggte User (Login-Status prüfen, keine Rollenprüfung):
#   def my_route(current_user: CurrentUser) -> ...
#
# Nur editor oder admin (Datenzugriff):
#   def data_route(user: EditorOrAdminUser) -> ...
#
# Nur admins (Benutzerverwaltung):
#   def admin_route(admin: AdminUser) -> ...
#
# FastAPI prüft das automatisch bei jedem Request — kein manuelles Prüfen nötig.
CurrentUser = Annotated[User, Depends(_get_current_user)]
AdminUser = Annotated[User, Depends(_get_admin_user)]
EditorOrAdminUser = Annotated[User, Depends(_get_editor_or_admin_user)]
