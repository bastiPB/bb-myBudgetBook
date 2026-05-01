"""
app/services/auth.py — Business-Logik für Authentifizierung.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Sie bekommt Daten rein, macht ihre Arbeit, gibt ein Ergebnis zurück.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import AccountPendingError, EmailAlreadyExistsError, InvalidCredentialsError
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate

# PasswordHasher ist das Argon2id-Objekt — einmal erstellen, mehrfach verwenden
# Argon2id ist der sicherste Passwort-Hashing-Algorithmus (Stand 2024)
_ph = PasswordHasher()


def register_user(session: Session, payload: UserCreate) -> User:
    """
    Legt einen neuen User in der Datenbank an.

    Neue User starten immer mit:
      - role = "default"   (eingeschränkte Rechte)
      - status = "pending" (wartet auf Admin-Freigabe, kann sich NICHT einloggen)

    Wirft EmailAlreadyExistsError, wenn die E-Mail bereits registriert ist.
    Gibt den neu erstellten User zurück.
    """
    # Passwort hashen — niemals Klartext in die DB!
    hashed_password = _ph.hash(payload.password)

    new_user = User(
        email=payload.email,
        password_hash=hashed_password,
        role=UserRole.default,   # Standardrolle für neue Nutzer
        status=UserStatus.pending,  # Muss erst von Admin freigegeben werden
    )
    session.add(new_user)

    try:
        session.commit()
        # User-Objekt mit den DB-Werten (z.B. id, created_at) aktualisieren
        session.refresh(new_user)
    except IntegrityError:
        # IntegrityError = Datenbank-Constraint verletzt → E-Mail existiert bereits
        session.rollback()
        raise EmailAlreadyExistsError()

    return new_user


def login_user(session: Session, payload: UserCreate) -> User:
    """
    Prüft E-Mail, Passwort und Account-Status. Gibt den User zurück wenn alles stimmt.

    Prüfreihenfolge:
      1. E-Mail bekannt?       → sonst InvalidCredentialsError
      2. Passwort korrekt?     → sonst InvalidCredentialsError
      3. Status == "active"?   → sonst AccountPendingError
      4. Hash veraltet?        → neuen Hash speichern (rehash-on-login)

    Warum Passwort VOR Status prüfen?
    Timing-Konsistenz: immer ungefähr gleich viel Zeit verbrauchen,
    egal ob E-Mail existiert oder nicht — erschwert Enumeration-Angriffe.
    """
    # Schritt 1: User anhand der E-Mail in der DB suchen
    stmt = select(User).where(User.email == payload.email)
    user = session.execute(stmt).scalar_one_or_none()

    if user is None:
        # E-Mail nicht gefunden — gleiche Fehlermeldung wie bei falschem Passwort
        raise InvalidCredentialsError()

    # Schritt 2: Passwort prüfen
    try:
        _ph.verify(user.password_hash, payload.password)
    except VerifyMismatchError:
        raise InvalidCredentialsError()

    # Schritt 3: Account-Status prüfen
    # Erst NACH der Passwortprüfung — so weiß ein Angreifer nicht ob die E-Mail existiert
    if user.status != UserStatus.active:
        raise AccountPendingError()

    # Schritt 4: Hash-Parameter prüfen — wurden die Argon2-Parameter seit dem letzten
    # Passwort-Speichern erhöht? Falls ja, Hash aktualisieren solange das Klartext-
    # Passwort noch im Speicher liegt (nur beim Login möglich!).
    if _ph.check_needs_rehash(user.password_hash):
        user.password_hash = _ph.hash(payload.password)
        session.commit()

    return user
