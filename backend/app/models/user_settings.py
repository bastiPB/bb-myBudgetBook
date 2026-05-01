import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserSettings(BaseModel):
    """
    Persönliche Einstellungen eines Users — maximal eine Zeile pro User.
    Wird NICHT beim Login angelegt, sondern lazy beim ersten Aufruf von
    GET /profile/settings oder PATCH /profile/settings (get_or_create-Pattern, Schritt 4).

    Zwei-Stufen-Sichtbarkeit (ADR 0008):
      Stufe 1 = AppSettings.modules (Admin entscheidet, was systemweit verfügbar ist)
      Stufe 2 = dieses Modell (User entscheidet, was er persönlich nutzen will)
    """
    __tablename__ = "user_settings"

    # Fremdschlüssel auf users.id — UNIQUE stellt sicher, dass jeder User nur eine Zeile hat.
    # ondelete="CASCADE" = wenn ein User gelöscht wird, werden seine Einstellungen automatisch mitgelöscht.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Anzeigename des Users — optional, darf leer bleiben.
    # Fallback im Frontend: E-Mail-Adresse vor dem @-Zeichen (z.B. "max" aus "max@example.com")
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # URL zu einem Profilbild — Platzhalter für v0.2.0, Upload-Feature kommt in v0.2.x
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Welche Module dieser User persönlich aktiviert hat — Stufe 2 der Zwei-Stufen-Sichtbarkeit (ADR 0008)
    # Format: {"savings_box": true, "subscriptions": false, ...}
    # Leeres Dict {} = User hat noch keine Module gewählt → Dashboard zeigt Onboarding-Card
    # WICHTIG: Nur Module die in AppSettings.modules aktiv sind, dürfen hier aktiviert werden.
    #          Validierung in services/profile.py → HTTP 400 bei Verstoß (ADR 0007)
    modules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
