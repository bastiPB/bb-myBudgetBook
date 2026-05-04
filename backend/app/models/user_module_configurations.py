import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserModuleConfiguration(BaseModel):
    """
    Speichert pro User individuelle Einstellungen für einzelne Module.

    Warum eine eigene Tabelle statt Felder in user_settings?
    user_settings enthält allgemeine Profildaten (Display-Name, Avatar).
    Diese Tabelle ist für Modul-Sub-Einstellungen gedacht — sie wächst
    mit jedem neuen Modul, ohne die Profil-Tabelle aufzublähen.

    Das JSONB-Feld 'config' speichert beliebige Key-Value-Paare, z.B.:
    {
      "subscription_booking_history": true,
      "subscription_cumulative_calculation": false
    }
    Neue Keys brauchen keine neue Spalte — ADR 0007.
    """
    __tablename__ = "user_module_configurations"

    # 1:1-Beziehung zum User — jeder User hat genau eine Konfigurationszeile
    # UNIQUE stellt sicher, dass get_or_create keine Duplikate erzeugen kann
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Modul-Einstellungen als JSONB — erlaubt flexible Erweiterung ohne neue Spalten
    # default={} = leeres Dict beim ersten Anlegen, User muss opt-in wählen
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
