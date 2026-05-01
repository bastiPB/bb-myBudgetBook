"""
app/schemas/profile.py — Eingabe- und Ausgabe-Schemas für die Profil-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

from pydantic import BaseModel, ConfigDict


class ProfileSettingsRead(BaseModel):
    """
    Ausgabe-Schema für die persönlichen Einstellungen eines Users.

    Gibt zurück:
      {
        "display_name": "Sparfuchs",   -- oder null wenn noch nicht gesetzt
        "avatar_url": null,            -- Platzhalter, Upload folgt in v0.2.x
        "modules": {"savings_box": true, "subscriptions": false}
      }

    from_attributes=True erlaubt Pydantic, direkt aus einem SQLAlchemy-Objekt zu lesen.
    """

    model_config = ConfigDict(from_attributes=True)

    # Optionaler Anzeigename — Fallback im Frontend: E-Mail-Adresse vor dem @
    display_name: str | None
    # URL zu einem Profilbild — Upload-Feature folgt in v0.2.x
    avatar_url: str | None
    # Persönliche Modul-Auswahl des Users — Key = Modul-Key, Value = true/false
    modules: dict[str, bool]


class ProfileSettingsUpdate(BaseModel):
    """
    Eingabe-Schema für das Ändern der persönlichen Einstellungen (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Jeder eingeloggte User darf seinen eigenen Profil-Eintrag aktualisieren.

    Beispiel — Sparfach aktivieren:
      { "modules": {"savings_box": true, "subscriptions": true} }

    Beispiel — nur den Anzeigenamen setzen:
      { "display_name": "Sparfuchs" }

    Hinweis zu modules: immer den vollständigen gewünschten Zustand schicken.
    Das Frontend liest erst GET /profile/settings und schickt den aktualisierten Zustand zurück.

    Hinweis zu display_name: None = keine Änderung (nicht: Feld leeren).
    """

    display_name: str | None = None
    # Platzhalter — kein Upload in v0.2.0, nur URL-Eingabe möglich
    avatar_url: str | None = None
    modules: dict[str, bool] | None = None
