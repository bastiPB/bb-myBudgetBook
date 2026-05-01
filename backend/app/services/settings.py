"""
app/services/settings.py — Business-Logik für systemweite Einstellungen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Sie liest und schreibt die einzige Zeile in der Tabelle app_settings.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models.app_settings import AppSettings
from app.schemas.settings import AppSettingsUpdate


def get_settings(session: Session) -> AppSettings:
    """
    Gibt die systemweiten Einstellungen zurück.

    Es gibt immer genau eine Zeile in app_settings — angelegt durch Migration e5f6g7h8.
    Wirft einen HTTP-500-Fehler wenn die Zeile fehlt (sollte nie passieren).
    """
    # scalar_one_or_none() gibt das erste Ergebnis zurück oder None wenn nichts gefunden
    settings = session.execute(select(AppSettings)).scalar_one_or_none()
    if settings is None:
        # Sicherheitsnetz — eigentlich legt die Migration die Zeile immer an
        raise AppError("Systemeinstellungen nicht gefunden.", status_code=500)
    return settings


def update_settings(session: Session, payload: AppSettingsUpdate) -> AppSettings:
    """
    Aktualisiert die systemweiten Einstellungen.

    Nur die Felder im payload werden geändert — fehlendes Feld (None) = keine Änderung.
    Gibt die aktualisierte Einstellungs-Zeile zurück.
    """
    settings = get_settings(session)

    # Selbstregistrierung an-/ausschalten — nur wenn der Admin das Feld mitgeschickt hat
    if payload.email_signup_enabled is not None:
        settings.email_signup_enabled = payload.email_signup_enabled

    if payload.modules is not None:
        # Neues dict zuweisen statt in-place Mutation — SQLAlchemy erkennt die Änderung nur so.
        # Hintergrund: SQLAlchemy beobachtet Objekt-Zuweisungen, aber keine dict-Mutationen wie
        # settings.modules["key"] = True. Deshalb immer ein neues dict zuweisen.
        settings.modules = dict(payload.modules)

    session.commit()
    session.refresh(settings)
    return settings
