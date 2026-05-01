import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole, UserStatus


class UserCreate(BaseModel):
    """Eingabe-Schema für Registrierung und Login: E-Mail + Passwort."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """
    Ausgabe-Schema für User-Daten.
    Wird z.B. beim Login oder bei Admin-Abfragen zurückgegeben.
    Enthält KEIN Passwort — das verlässt den Server nie!
    """

    # from_attributes=True erlaubt es, direkt aus einem SQLAlchemy-Objekt zu lesen
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    status: UserStatus


class RegisterResponse(BaseModel):
    """
    Antwort nach erfolgreicher Registrierung.
    Enthält nur eine Statusmeldung — kein Cookie, da Account noch pending ist.
    """

    message: str
