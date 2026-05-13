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


class TagNotFoundError(AppError):
    """Wird geworfen, wenn ein Tag anhand seiner ID nicht gefunden wird."""

    def __init__(self) -> None:
        super().__init__("Tag nicht gefunden.", status_code=404)


class TagNameAlreadyExistsError(AppError):
    """Wird geworfen, wenn ein Tag-Name für diesen User bereits existiert."""

    def __init__(self) -> None:
        # HTTP 409 Conflict = die Ressource existiert bereits
        super().__init__("Ein Tag mit diesem Namen existiert bereits.", status_code=409)


class SavingsBoxNotFoundError(AppError):
    """Wird geworfen, wenn ein Sparfach anhand seiner ID nicht gefunden wird."""

    def __init__(self) -> None:
        super().__init__("Sparfach nicht gefunden.", status_code=404)


class SavingsBoxClosedError(AppError):
    """
    Wird geworfen bei Schreibzugriff auf ein bereits abgeschlossenes Sparfach.

    HTTP 409 Conflict — Daten dürfen nach Abschluss nicht mehr geändert werden.
    """

    def __init__(self) -> None:
        super().__init__(
            "Dieses Sparfach ist abgeschlossen und kann nicht mehr geändert werden.",
            status_code=409,
        )


class SavingsBoxNotClosedError(AppError):
    """Wird beim Reopen geworfen, wenn das Sparfach noch nicht abgeschlossen ist."""

    def __init__(self) -> None:
        super().__init__(
            "Das Sparfach ist noch nicht abgeschlossen und kann nicht wieder geöffnet werden.",
            status_code=409,
        )


class SavingsBookingValidationError(AppError):
    """Ungültige Buchungsdaten (Term fehlt, Betrag unter Mindestbetrag, falscher Term)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=422)


class SavingsBookingNotFoundError(AppError):
    """Buchung zur angegebenen ID existiert nicht oder gehört nicht zur Box."""

    def __init__(self) -> None:
        super().__init__("Buchung nicht gefunden.", status_code=404)


class SavingsPenaltyDeleteBlockedError(AppError):
    """Strafe löschen nicht erlaubt, solange keine Einzahlung zum Term existiert."""

    def __init__(self) -> None:
        super().__init__(
            "Die Strafgebühr kann nicht gelöscht werden, solange keine Einzahlung für diesen Term verbucht ist.",
            status_code=409,
        )


class InvalidFileError(AppError):
    """
    Wird geworfen wenn eine hochgeladene Datei die Anforderungen nicht erfüllt.

    Beispiele: falscher Dateityp (nur JPEG/PNG/WebP erlaubt) oder Datei zu groß (max. 2 MB).
    HTTP 422 Unprocessable Entity = Anfrage technisch gültig, Inhalt aber unverarbeitbar.
    """

    def __init__(self, detail: str = "Ungültige Datei.") -> None:
        super().__init__(detail, status_code=422)


class InvalidSubscriptionStatusError(AppError):
    """
    Wird geworfen, wenn ein ungültiger Status-Übergang versucht wird.

    Beispiel: Ein bereits suspendiertes Abo kann nicht nochmals suspendiert werden.
    HTTP 409 Conflict = die aktuelle Ressource erlaubt diese Aktion nicht.
    """

    def __init__(self, detail: str = "Dieser Status-Übergang ist nicht erlaubt.") -> None:
        super().__init__(detail, status_code=409)


class DuplicatePriceEntryError(AppError):
    """
    Wird geworfen, wenn für ein Abo bereits ein Preiseintrag mit demselben Datum existiert.

    HTTP 409 Conflict = die Ressource existiert bereits — bitte erst löschen oder bearbeiten.
    Kein Überschreiben ohne explizite User-Aktion, um Datenverlust zu vermeiden.
    """

    def __init__(self, valid_from: str) -> None:
        super().__init__(
            f"Für das Datum {valid_from} existiert bereits ein Preiseintrag. "
            "Bitte den bestehenden Eintrag zuerst löschen oder bearbeiten.",
            status_code=409,
        )


class PriceHistoryEntryNotFoundError(AppError):
    """Wird geworfen, wenn ein einzelner Preishistorie-Eintrag anhand seiner ID nicht gefunden wird."""

    def __init__(self) -> None:
        super().__init__("Preishistorie-Eintrag nicht gefunden.", status_code=404)


class PriceEntryDeleteBlockedError(AppError):
    """
    Wird geworfen, wenn ein Preishistorie-Eintrag nicht gelöscht werden darf.

    Gründe: letzter verbleibender Eintrag, oder es existieren bereits Buchungen
    für den Zeitraum in dem dieser Preis galt.
    HTTP 409 Conflict = Aktion aufgrund des aktuellen Zustands nicht erlaubt.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason, status_code=409)


class BillingEntryDeleteBlockedError(AppError):
    """
    Wird geworfen, wenn ein Billing-History-Eintrag nicht gelöscht werden darf.

    Gründe: letzter verbleibender Eintrag, initialer Start-Eintrag, oder es existieren
    bereits Buchungen für den Zeitraum in dem dieser Eintrag galt.
    HTTP 409 Conflict = Aktion aufgrund des aktuellen Zustands nicht erlaubt.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason, status_code=409)


# --- v0.2.4: Billing History ---


class DuplicateBillingHistoryEntryError(AppError):
    """
    Wird geworfen, wenn für ein Abo bereits ein Billing-History-Eintrag mit demselben
    Datum (valid_from) existiert.

    HTTP 409 Conflict = der Eintrag existiert bereits — bitte erst löschen oder bearbeiten.
    Kein automatisches Überschreiben, um Datenverlust zu vermeiden.
    """

    def __init__(self, valid_from: str) -> None:
        super().__init__(
            f"Für das Datum {valid_from} existiert bereits ein Abrechnungseintrag. "
            "Bitte den bestehenden Eintrag zuerst löschen oder bearbeiten.",
            status_code=409,
        )


class BillingHistoryEntryNotFoundError(AppError):
    """
    Wird geworfen, wenn ein einzelner Billing-History-Eintrag anhand seiner ID
    nicht gefunden wird.

    HTTP 404 Not Found = Ressource existiert nicht.
    """

    def __init__(self) -> None:
        super().__init__("Abrechnungseintrag nicht gefunden.", status_code=404)


class BillingHistoryChangeBlockedError(AppError):
    """
    Wird geworfen, wenn ein rückwirkender Intervallwechsel bestehende Scheduled Payments
    betrifft und der Nutzer dies noch nicht explizit bestätigt hat.

    HTTP 409 Conflict = Aktion möglich, aber nur mit bewusster Bestätigung
                        (acknowledge_existing_payments=True).

    Der reason-String enthält die Anzahl der betroffenen Buchungen und das Datum.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason, status_code=409)


class ShortBillingSegmentError(AppError):
    """
    Wird geworfen, wenn die Billing-Historie nach einem Intervallwechsel ein Segment
    enthält, das kürzer als eine volle Abrechnungsperiode wäre (typischer Eingabefehler).

    HTTP 409 Conflict = Speichern nur mit acknowledge_short_segment=true.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=409)


def register_exception_handlers(app: FastAPI) -> None:
    """Registriert alle globalen Fehler-Handler an der FastAPI-App."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        # Alle AppError-Unterklassen landen hier — niemals rohe Python-Fehler nach außen!
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
