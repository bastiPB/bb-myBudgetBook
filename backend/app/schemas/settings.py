"""
app/schemas/settings.py — Eingabe- und Ausgabe-Schemas für die Settings-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

import uuid

from pydantic import BaseModel, ConfigDict


class AppSettingsRead(BaseModel):
    """
    Ausgabe-Schema für die systemweiten Einstellungen.

    Gibt zurück: { "id": "...", "email_signup_enabled": true, "modules": {"subscriptions": true, ...} }
    from_attributes=True erlaubt Pydantic, direkt aus einem SQLAlchemy-Objekt zu lesen.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_signup_enabled: bool
    # Welche Module systemweit freigeschaltet sind — Key = Modul-Key, Value = true/false
    modules: dict[str, bool]
    # Uhrzeit des täglichen Schedulers im Format "HH:MM"
    scheduler_time: str


class AppSettingsUpdate(BaseModel):
    """
    Eingabe-Schema für das Ändern der systemweiten Einstellungen (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Nur der Admin darf diesen Endpunkt aufrufen (Prüfung im Router).

    Beispiel — Sparfach freischalten:
      { "modules": {"subscriptions": true, "savings_box": true} }

    Beispiel — nur Selbstregistrierung deaktivieren:
      { "email_signup_enabled": false }
    """

    email_signup_enabled: bool | None = None
    # Bei modules: immer den vollständigen gewünschten Zustand schicken — keine Teil-Updates.
    # Das Frontend liest erst GET /settings und schickt dann den aktualisierten Zustand zurück.
    modules: dict[str, bool] | None = None
    # Uhrzeit des Schedulers im Format "HH:MM" — optional, nur bei Änderung mitsenden
    scheduler_time: str | None = None