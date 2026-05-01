"""
app/schemas/admin.py — Eingabe-Schemas für Admin-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class RoleUpdate(BaseModel):
    """
    Eingabe-Schema für die Rollenänderung eines Users.

    Erwartet als JSON: { "role": "admin" | "editor" | "default" }
    Pydantic prüft automatisch ob der Wert einer der erlaubten Rollen entspricht.
    """

    role: UserRole


class AdminUserCreate(BaseModel):
    """
    Eingabe-Schema wenn ein Admin direkt einen neuen User anlegt.

    Unterschied zur normalen Selbst-Registrierung (/auth/register):
    - Admin wählt die Rolle direkt
    - User wird sofort als "active" angelegt — kein pending-Schritt, keine Admin-Freigabe nötig
    - Admin gibt das initiale Passwort vor und teilt es dem User mit

    Erwartet als JSON: { "email": "...", "password": "...", "role": "editor" }
    """

    email: EmailStr
    password: str
    # Standardrolle: editor — der häufigste Fall für Familienmitglieder
    role: UserRole = UserRole.editor
