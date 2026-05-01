"""
app/services/profile.py — Business-Logik für persönliche User-Einstellungen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models.user_settings import UserSettings
from app.schemas.profile import ProfileSettingsUpdate
from app.services.settings import get_settings

# Alle bekannten Modul-Keys — muss mit MODULE_REGISTRY im Frontend übereinstimmen (Schritt 5).
# Neues Modul hinzufügen = neuen Key hier ergänzen + neues Objekt im Frontend-Registry.
MODULE_KEYS: frozenset[str] = frozenset({
    "subscriptions",
    "savings_box",
    "vacation_fund",
    "household_budget",
    "fund_savings",
    "stock_portfolio",
})


def get_or_create_user_settings(session: Session, user_id: uuid.UUID) -> UserSettings:
    """
    Gibt die persönlichen Einstellungen des Users zurück.

    Falls noch keine Zeile existiert, wird sie jetzt angelegt (leere Module, kein Name).
    Das nennt sich "lazy initialization" — die Zeile entsteht erst beim ersten Profil-Zugriff,
    NICHT beim Login. So bleibt der Login-Vorgang schlank und einfach.

    Wird von GET und PATCH /profile/settings aufgerufen.
    """
    settings = session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()

    if settings is None:
        # Erste Profil-Anfrage dieses Users — Zeile anlegen mit leeren Startwerten
        settings = UserSettings(user_id=user_id, modules={})
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return settings


def update_profile(
    session: Session,
    user_id: uuid.UUID,
    payload: ProfileSettingsUpdate,
) -> UserSettings:
    """
    Aktualisiert die persönlichen Einstellungen des Users.

    Nur non-None-Felder werden geändert (PATCH-Semantik).

    Validierung bei modules:
      1. Alle Keys müssen bekannte Module sein (gegen MODULE_KEYS) → HTTP 400
      2. Nur Admin-freigegebene Module dürfen auf true gesetzt werden → HTTP 400

    Gibt die aktualisierte UserSettings-Zeile zurück.
    """
    user_settings = get_or_create_user_settings(session, user_id)

    if payload.display_name is not None:
        user_settings.display_name = payload.display_name

    if payload.avatar_url is not None:
        user_settings.avatar_url = payload.avatar_url

    if payload.modules is not None:
        # --- Validierung 1: Nur bekannte Module-Keys erlaubt ---
        # Verhindert Tippfehler und unbekannte Module-Keys in der DB (ADR 0007)
        unknown_keys = set(payload.modules.keys()) - MODULE_KEYS
        if unknown_keys:
            raise AppError(
                f"Unbekannte Module: {', '.join(sorted(unknown_keys))}",
                status_code=400,
            )

        # --- Validierung 2: Nur Admin-freigegebene Module dürfen aktiviert werden ---
        # Stufe 1 des Zwei-Stufen-Modells (ADR 0008): Admin-Sperrung hat immer Vorrang
        app_settings = get_settings(session)
        for key, enabled in payload.modules.items():
            if enabled and not app_settings.modules.get(key, False):
                raise AppError(
                    f"Modul '{key}' ist systemweit nicht freigegeben.",
                    status_code=400,
                )

        # Neues dict zuweisen statt in-place Mutation — SQLAlchemy erkennt die Änderung nur so
        user_settings.modules = dict(payload.modules)

    session.commit()
    session.refresh(user_settings)
    return user_settings
