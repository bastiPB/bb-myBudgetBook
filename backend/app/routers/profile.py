"""
app/routers/profile.py — HTTP-Endpunkte für persönliche User-Einstellungen.

GET  /profile/settings — jeder eingeloggte User (CurrentUser)
PATCH /profile/settings — jeder eingeloggte User (CurrentUser)

Warum CurrentUser und nicht EditorOrAdminUser?
Auch User mit der Rolle 'default' (Wartezustand) sollen ihr Profil einrichten können —
zum Beispiel einen Anzeigenamen setzen, bevor der Admin die Rolle vergibt.
"""

from fastapi import APIRouter

from app.dependencies import CurrentUser, DatabaseSession
from app.schemas.profile import ProfileSettingsRead, ProfileSettingsUpdate
from app.services.profile import get_or_create_user_settings, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/settings", response_model=ProfileSettingsRead)
def read_profile_settings(current_user: CurrentUser, session: DatabaseSession) -> ProfileSettingsRead:
    """
    Gibt die persönlichen Einstellungen des eingeloggten Users zurück.

    Falls noch keine Einstellungs-Zeile existiert, wird sie jetzt angelegt (leere Startwerte).
    Das Frontend braucht diese Daten beim Start für den ModulesContext (Schritt 5).

    Gibt zurück: { "display_name": "...", "avatar_url": null, "modules": {...} }
    Fehler: 401 wenn nicht eingeloggt.
    """
    settings = get_or_create_user_settings(session, current_user.id)
    return ProfileSettingsRead.model_validate(settings)


@router.patch("/settings", response_model=ProfileSettingsRead)
def patch_profile_settings(
    payload: ProfileSettingsUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ProfileSettingsRead:
    """
    Aktualisiert die persönlichen Einstellungen des eingeloggten Users.

    Nur mitgeschickte Felder (nicht None) werden geändert.
    Validierung: Module müssen bekannt und Admin-seitig freigegeben sein → HTTP 400.

    Beispiel: { "modules": {"savings_box": true} }
    Fehler:
      - 401 wenn nicht eingeloggt
      - 400 wenn ein unbekanntes oder gesperrtes Modul aktiviert werden soll
    """
    settings = update_profile(session, current_user.id, payload)
    return ProfileSettingsRead.model_validate(settings)
