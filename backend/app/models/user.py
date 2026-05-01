import enum

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """
    Die drei Rollen im System.
    str + Enum kombiniert = Werte sind normale Strings ("admin", "editor", "default"),
    was die Speicherung in der DB und JSON-Serialisierung vereinfacht.
    """
    admin = "admin"      # Vollzugriff: Daten + Benutzerverwaltung
    editor = "editor"    # Darf alle Daten sehen und bearbeiten — keine Benutzerverwaltung
    default = "default"  # Kein Datenzugriff — Wartezustand bis zur Rollenzuweisung


class UserStatus(str, enum.Enum):
    """
    Lebenszyklus eines User-Accounts.
    pending = wartet auf Admin-Freigabe
    active  = darf sich einloggen
    """
    pending = "pending"
    active = "active"


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Rolle des Users — neu registrierte User starten immer als "default"
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"),
        default=UserRole.default,
        nullable=False,
    )

    # Status des Accounts — neu registrierte User starten als "pending" (wartet auf Freigabe)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="userstatus"),
        default=UserStatus.pending,
        nullable=False,
    )
