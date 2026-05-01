"""
app/bootstrap.py — Einmalige Initialisierung beim ersten App-Start.

Was passiert hier?
  Beim allerersten Start existiert noch kein Admin-Account.
  Diese Datei liest ADMIN_EMAIL und ADMIN_PASSWORD aus der .env-Datei
  und legt den ersten Admin-Account automatisch an — falls noch keiner existiert.

Danach (bei jedem weiteren Start) erkennt die Funktion, dass ein Admin
bereits vorhanden ist, und tut nichts.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.user import User, UserRole, UserStatus

# Argon2id PasswordHasher für das initiale Admin-Passwort
from argon2 import PasswordHasher
_ph = PasswordHasher()


def _hash_if_plaintext(password: str) -> str:
    """
    Prüft ob das Passwort bereits ein Argon2id-Hash ist oder noch Klartext.

    Argon2id-Hashes beginnen immer mit "$argon2id$" — das ist eindeutig erkennbar.
    So kann der Endnutzer wahlweise Klartext oder einen fertigen Hash in .env eintragen.
    """
    if password.startswith("$argon2"):
        # Bereits ein Hash (erzeugt z.B. mit tools/hash_password.py) — direkt verwenden
        return password
    # Klartext → mit Argon2id hashen
    return _ph.hash(password)


def bootstrap_admin() -> None:
    """
    Legt den initialen Admin-Account an, falls noch keiner existiert.

    Wird beim App-Start aufgerufen (siehe main.py).
    Tut nichts wenn:
      - ADMIN_EMAIL oder ADMIN_PASSWORD nicht gesetzt sind
      - Bereits ein Admin-Account in der DB existiert
    """
    settings = get_settings()

    # Keine Env-Vars gesetzt → nichts tun
    if not settings.admin_email or not settings.admin_password:
        print("Bootstrap: ADMIN_EMAIL oder ADMIN_PASSWORD nicht gesetzt — kein Admin angelegt.")
        return

    # Eigene DB-Session für den Bootstrap (unabhängig von FastAPI-Requests)
    with SessionLocal() as session:
        _create_admin_if_missing(session, settings.admin_email, settings.admin_password)


def _create_admin_if_missing(session: Session, email: str, password: str) -> None:
    """
    Prüft ob ein Admin existiert und legt ihn an falls nicht.
    Ausgelagert um die Logik testbar zu machen.
    """
    # Gibt es bereits irgendeinen Admin in der DB?
    existing_admin = session.execute(
        select(User).where(User.role == UserRole.admin)
    ).scalar_one_or_none()

    if existing_admin:
        # Admin existiert bereits → nichts tun
        print(f"Bootstrap: Admin-Account existiert bereits ({existing_admin.email}) — überspringe.")
        return

    # Passwort hashen falls es Klartext ist
    password_hash = _hash_if_plaintext(password)

    admin = User(
        email=email,
        password_hash=password_hash,
        # Admin startet direkt als "active" — kein Freigabe-Prozess für den ersten Admin
        role=UserRole.admin,
        status=UserStatus.active,
    )
    session.add(admin)

    try:
        session.commit()
        print(f"Bootstrap: Admin-Account '{email}' erfolgreich angelegt.")
    except IntegrityError:
        # E-Mail existiert bereits (aber nicht als Admin) — Konflikt melden
        session.rollback()
        print(f"Bootstrap: WARNUNG — E-Mail '{email}' existiert bereits, Admin wurde NICHT angelegt.")
