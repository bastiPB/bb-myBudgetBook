from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AppSettings(BaseModel):
    """
    Systemweite Einstellungen der App — es gibt immer genau eine Zeile in dieser Tabelle.
    Diese Zeile wird automatisch durch die Migration e5f6g7h8 angelegt.

    Zwei-Stufen-Sichtbarkeit (ADR 0008):
      Stufe 1 = dieses Modell (Admin entscheidet, was systemweit verfügbar ist)
      Stufe 2 = UserSettings (User entscheidet, was er persönlich nutzen will)
    """
    __tablename__ = "app_settings"

    # Ob neue User sich selbst registrieren können (True) oder nur der Admin Accounts anlegen darf (False)
    email_signup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Welche Module systemweit freigeschaltet sind — Stufe 1 der Zwei-Stufen-Sichtbarkeit (ADR 0008)
    # Format: {"subscriptions": true, "savings_box": false, ...}
    # JSONB = binäres JSON in PostgreSQL — schneller als Text-JSON, unterstützt GIN-Indexierung
    # Neue Module brauchen keine neue DB-Spalte, nur einen neuen Key in diesem Objekt (ADR 0007)
    modules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {"subscriptions": True})

    # Uhrzeit, zu der der Scheduler täglich Soll-Buchungen generiert — Format "HH:MM"
    # Wird beim App-Start in main.py ausgelesen und an APScheduler übergeben
    scheduler_time: Mapped[str] = mapped_column(String(5), nullable=False, default="03:00")