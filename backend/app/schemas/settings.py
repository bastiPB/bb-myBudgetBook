"""
app/schemas/settings.py — Eingabe- und Ausgabe-Schemas für die Settings-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

# Obergrenze Catch-up (API + UI) — ca. zwei Jahre, verhindert Extremwerte
SCHEDULER_CATCH_UP_DAYS_MAX = 730


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
    # Catch-up: verpasste Fälligkeiten bis X Tage zurueck nachfuellen
    scheduler_catch_up_days: int


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
    # Catch-up-Tage (0 … SCHEDULER_CATCH_UP_DAYS_MAX), optional
    scheduler_catch_up_days: int | None = None

    @field_validator("scheduler_time")
    @classmethod
    def validate_scheduler_time(cls, v: str | None) -> str | None:
        """Erlaubt nur gueltige 24h-Uhrzeiten HH:MM."""
        if v is None:
            return v
        if not re.fullmatch(r"\d{2}:\d{2}", v):
            raise ValueError('Uhrzeit muss im Format "HH:MM" sein (00:00 bis 23:59).')
        h, m = int(v[0:2]), int(v[3:5])
        if h > 23 or m > 59:
            raise ValueError("Ungueltige Uhrzeit (Stunde 00–23, Minute 00–59).")
        return v

    @field_validator("scheduler_catch_up_days")
    @classmethod
    def validate_catch_up_days(cls, v: int | None) -> int | None:
        """Begrenzt Catch-up fuer lesbare Fehlermeldungen (deutsch)."""
        if v is None:
            return v
        if v < 0:
            raise ValueError("Catch-up-Tage duerfen nicht negativ sein.")
        if v > SCHEDULER_CATCH_UP_DAYS_MAX:
            raise ValueError(f"Maximal {SCHEDULER_CATCH_UP_DAYS_MAX} Tage rueckwirkend erlaubt.")
        return v