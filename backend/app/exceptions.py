from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Basis-Fehlerklasse für alle App-Fehler. Alle eigenen Fehler erben von hier."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# --- Auth-Fehler ---

class EmailAlreadyExistsError(AppError):
    """Wird geworfen, wenn jemand versucht sich mit einer bereits registrierten E-Mail anzumelden."""

    def __init__(self) -> None:
        # HTTP 409 Conflict = die Ressource existiert bereits
        super().__init__("E-Mail wird bereits verwendet.", status_code=409)


class InvalidCredentialsError(AppError):
    """Wird geworfen, wenn E-Mail oder Passwort beim Login falsch sind."""

    def __init__(self) -> None:
        # Bewusst vage: wir verraten nicht ob E-Mail oder Passwort falsch ist
        # (sonst könnte jemand gültige E-Mails "erraten")
        super().__init__("E-Mail oder Passwort ist falsch.", status_code=401)


class NotAuthenticatedError(AppError):
    """Wird geworfen, wenn ein nicht eingeloggter User auf eine geschützte Route zugreift."""

    def __init__(self) -> None:
        # HTTP 401 Unauthorized = bitte zuerst einloggen
        super().__init__("Nicht eingeloggt.", status_code=401)


class AccountPendingError(AppError):
    """Wird geworfen, wenn ein User versucht sich einzuloggen, dessen Account noch pending ist."""

    def __init__(self) -> None:
        # HTTP 403 Forbidden = eingeloggt wäre prinzipiell möglich, aber noch nicht freigegeben
        super().__init__("Account wartet auf Admin-Freigabe.", status_code=403)


class ForbiddenError(AppError):
    """Wird geworfen, wenn ein User eine Aktion ausführen will, für die er keine Berechtigung hat."""

    def __init__(self) -> None:
        # HTTP 403 Forbidden = eingeloggt, aber nicht berechtigt
        super().__init__("Keine Berechtigung für diese Aktion.", status_code=403)


# --- Ressourcen-Fehler ---

class UserNotFoundError(AppError):
    """Wird geworfen, wenn ein User anhand seiner ID nicht gefunden wird."""

    def __init__(self) -> None:
        # HTTP 404 Not Found = Ressource existiert nicht
        super().__init__("User nicht gefunden.", status_code=404)


class SubscriptionNotFoundError(AppError):
    """Wird geworfen, wenn ein Abo anhand seiner ID nicht gefunden wird."""

    def __init__(self) -> None:
        super().__init__("Abo nicht gefunden.", status_code=404)


class InvalidSubscriptionStatusError(AppError):
    """
    Wird geworfen, wenn ein ungültiger Status-Übergang versucht wird.

    Beispiel: Ein bereits suspendiertes Abo kann nicht nochmals suspendiert werden.
    HTTP 409 Conflict = die aktuelle Ressource erlaubt diese Aktion nicht.
    """

    def __init__(self, detail: str = "Dieser Status-Übergang ist nicht erlaubt.") -> None:
        super().__init__(detail, status_code=409)


def register_exception_handlers(app: FastAPI) -> None:
    """Registriert alle globalen Fehler-Handler an der FastAPI-App."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        # Alle AppError-Unterklassen landen hier — niemals rohe Python-Fehler nach außen!
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
