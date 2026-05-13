"""
app/schemas/subscription_tag.py — Pydantic-Schemas für Tag-Endpunkte (v0.2.7).

Tags sind benutzerdefinierte Kategorien für Abos (z.B. "Streaming", "KI-Abos").
"""

import uuid

from pydantic import BaseModel, ConfigDict, field_validator

# Erlaubte Hex-Farben aus der vordefinierten Palette (12 Farben).
# Exakt dieselbe Liste wie TAG_COLORS im Frontend (frontend/src/types/tag.ts).
# frozenset für schnelle "in"-Prüfung ohne Seiteneffekte.
ALLOWED_TAG_COLORS: frozenset[str] = frozenset({
    "#6366f1",  # Indigo
    "#8b5cf6",  # Violett
    "#ec4899",  # Pink
    "#ef4444",  # Rot
    "#f97316",  # Orange
    "#eab308",  # Gelb
    "#22c55e",  # Grün
    "#14b8a6",  # Teal
    "#06b6d4",  # Cyan
    "#3b82f6",  # Blau
    "#64748b",  # Slate
    "#a855f7",  # Lila
})


class TagRead(BaseModel):
    """
    Ausgabe-Schema für einen Tag.
    Wird direkt in SubscriptionRead und SubscriptionDetail eingebettet.
    """

    # from_attributes=True: Pydantic liest direkt aus dem SQLAlchemy-ORM-Objekt
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str  # Hex-Farbe aus der Palette, z.B. "#6366f1"


class TagCreate(BaseModel):
    """
    Eingabe-Schema für POST /subscriptions/tags (neuen Tag anlegen).

    name:  1–50 Zeichen, führende/nachgestellte Leerzeichen werden automatisch entfernt.
    color: Muss aus der vordefinierten Palette stammen (12 Farben).
    """

    name: str
    color: str

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        """Leerzeichen am Rand entfernen und Länge prüfen."""
        v = v.strip()
        if not v:
            raise ValueError("Name darf nicht leer sein.")
        if len(v) > 50:
            raise ValueError("Name darf maximal 50 Zeichen lang sein.")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Farbe muss aus der vordefinierten Palette stammen."""
        if v not in ALLOWED_TAG_COLORS:
            raise ValueError("Ungültige Farbe. Bitte eine der vorgegebenen Farben verwenden.")
        return v


class TagUpdate(BaseModel):
    """
    Eingabe-Schema für PATCH /subscriptions/tags/{tag_id}.

    Alle Felder optional — nur was mitgeschickt wird, wird geändert.
    None bedeutet "unverändert lassen", nicht "auf null setzen".
    """

    name: str | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, v: str | None) -> str | None:
        """Leerzeichen am Rand entfernen und Länge prüfen (nur wenn gesetzt)."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Name darf nicht leer sein.")
        if len(v) > 50:
            raise ValueError("Name darf maximal 50 Zeichen lang sein.")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        """Farbe prüfen (nur wenn gesetzt)."""
        if v is None:
            return None
        if v not in ALLOWED_TAG_COLORS:
            raise ValueError("Ungültige Farbe. Bitte eine der vorgegebenen Farben verwenden.")
        return v


class TagAssignRequest(BaseModel):
    """
    Eingabe-Schema für PUT /subscriptions/{id}/tags.

    Erwartet die vollständige aktuelle Tag-Auswahl — auch wenn sich nur einer ändert.
    Leere Liste [] entfernt alle Tags vom Abo.

    Warum PUT statt PATCH?
    PUT bedeutet: "Das hier ist jetzt die komplette Zuweisung."
    Kein Partial-Update nötig — das Frontend verwaltet die Auswahl intern.
    """

    tag_ids: list[uuid.UUID]
