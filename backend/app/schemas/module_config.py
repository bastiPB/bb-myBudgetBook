"""
app/schemas/module_config.py — Eingabe- und Ausgabe-Schemas für Modul-Konfigurationen.

Modul-Konfigurationen sind Opt-in-Einstellungen, die der User pro Modul wählen kann.
Sie steuern z. B. ob der Scheduler Buchungshistorie aufzeichnet (Slice F).
"""

from pydantic import BaseModel


class UserModuleConfigRead(BaseModel):
    """
    Ausgabe-Schema für die Modul-Konfiguration des eingeloggten Users.

    Flacht die JSONB-Spalte 'config' in der DB auf einzelne Felder ab,
    damit das Frontend keine verschachtelten Objekte verarbeiten muss.

    Beide Felder haben Default False — User muss aktiv opt-in wählen.
    """

    subscription_cumulative_calculation: bool = False
    subscription_booking_history: bool = False


class UserModuleConfigUpdate(BaseModel):
    """
    Eingabe-Schema für PATCH /profile/module-config.

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Beispiel: nur Buchungshistorie aktivieren: { "subscription_booking_history": true }
    """

    subscription_cumulative_calculation: bool | None = None
    subscription_booking_history: bool | None = None
