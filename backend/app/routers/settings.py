"""
app/routers/settings.py — HTTP-Endpunkte für systemweite Einstellungen.

GET  /settings — jeder eingeloggte User (CurrentUser)
  Warum alle User? Das Frontend braucht die Modul-Liste beim App-Start, um zu wissen
  welche Module systemweit verfügbar sind (Stufe 1, ADR 0008).

PATCH /settings — nur Admin (AdminUser)
  Nur der Admin darf systemweite Einstellungen (Module, Selbstregistrierung) ändern.
"""

from fastapi import APIRouter

from app.dependencies import AdminUser, CurrentUser, DatabaseSession
from app.schemas.settings import AppSettingsRead, AppSettingsUpdate
from app.services.settings import get_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettingsRead)
def read_settings(current_user: CurrentUser, session: DatabaseSession) -> AppSettingsRead:
    """
    Gibt die systemweiten Einstellungen zurück.

    Jeder eingeloggte User darf diese Daten lesen — das Frontend braucht sie
    beim Start um die aktiven Module zu berechnen (ModulesContext, Schritt 5).

    Gibt zurück: { "id": "...", "email_signup_enabled": true, "modules": {...} }
    Fehler: 401 wenn nicht eingeloggt.
    """
    # current_user wird hier nur zur Authentifizierungsprüfung verwendet (muss eingeloggt sein)
    return AppSettingsRead.model_validate(get_settings(session))


@router.patch("", response_model=AppSettingsRead)
def patch_settings(
    payload: AppSettingsUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> AppSettingsRead:
    """
    Aktualisiert die systemweiten Einstellungen.

    Nur nicht-None-Felder im payload werden geändert.
    Beispiel — Sparfach systemweit freischalten:
      PATCH /settings
      { "modules": {"subscriptions": true, "savings_box": true} }

    Fehler:
      - 401 wenn nicht eingeloggt
      - 403 wenn kein Admin
    """
    # admin wird hier nur zur Berechtigungsprüfung verwendet (muss Admin sein)
    return AppSettingsRead.model_validate(update_settings(session, payload))
