"""
app/routers/auth.py — HTTP-Endpunkte für Authentifizierung.

Diese Schicht kümmert sich NUR um HTTP:
  - Request entgegennehmen
  - Service aufrufen
  - Cookie setzen / löschen
  - Response zurückgeben

Die eigentliche Logik (Passwort prüfen, User anlegen) ist in services/auth.py.
"""

from fastapi import APIRouter, Response, status

from app.config import get_settings
from app.dependencies import CurrentUser, DatabaseSession
from app.schemas.user import RegisterResponse, UserCreate, UserRead
from app.security import COOKIE_NAME, MAX_AGE_SECONDS, create_session_token
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user_id: str) -> None:
    """
    Hilfsfunktion: setzt den signierten Session-Cookie in der HTTP-Response.
    Ausgelagert damit login und spätere Endpunkte denselben Code verwenden können.
    """
    # get_settings() ist per lru_cache gecacht — kein Objekt wird neu erstellt
    settings = get_settings()
    token = create_session_token(user_id, settings.app_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,   # JavaScript kann den Cookie nicht lesen (Schutz vor XSS)
        samesite="lax",  # Schutz vor CSRF-Angriffen
        # secure=True nur in Produktion — in Entwicklung läuft kein HTTPS
        secure=settings.environment == "production",
    )


@router.post("/register", status_code=status.HTTP_202_ACCEPTED, response_model=RegisterResponse)
def register(payload: UserCreate, session: DatabaseSession) -> RegisterResponse:
    """
    Neuen Benutzer registrieren.

    Erwartet: { "email": "...", "password": "..." }
    Gibt zurück: HTTP 202 + Hinweismeldung (KEIN Cookie — Account ist noch pending!)
    Fehler: 409 wenn E-Mail bereits existiert

    Warum 202 und kein Cookie?
    Neue User starten als "pending" und müssen erst von einem Admin freigegeben werden.
    Erst nach Freigabe kann sich der User einloggen (POST /auth/login).
    """
    register_user(session, payload)
    return RegisterResponse(
        message="Registrierung erfolgreich. Dein Account wartet auf Admin-Freigabe."
    )


@router.post("/login", response_model=UserRead)
def login(payload: UserCreate, response: Response, session: DatabaseSession) -> UserRead:
    """
    Benutzer einloggen.

    Erwartet: { "email": "...", "password": "..." }
    Gibt zurück: User-Daten (ohne Passwort) + setzt Session-Cookie
    Fehler:
      - 401 wenn E-Mail oder Passwort falsch
      - 403 wenn Account noch pending (wartet auf Admin-Freigabe)
    """
    user = login_user(session, payload)
    _set_session_cookie(response, str(user.id))
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """
    Benutzer ausloggen.

    Löscht den Session-Cookie im Browser.
    Gibt HTTP 204 zurück (= "OK, kein Inhalt").
    """
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    """
    Gibt den aktuell eingeloggten User zurück.

    Nützlich für das Frontend, um nach einem Seitenreload zu prüfen ob man noch eingeloggt ist.
    Fehler: 401 wenn kein gültiger Session-Cookie vorhanden
    """
    return UserRead.model_validate(current_user)
