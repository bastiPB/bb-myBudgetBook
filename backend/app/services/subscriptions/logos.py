"""Logo-Uploads: Dateisystem und DB-Update fuer logo_url."""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.exceptions import InvalidFileError
from app.models.subscription import Subscription

from .access import _check_ownership, _get_subscription_or_raise
from .constants import _ALLOWED_LOGO_TYPES, _LOGO_EXT, _MAX_LOGO_SIZE_BYTES


def upload_subscription_logo(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    content_type: str,
    file_content: bytes,
    upload_dir: str,
) -> Subscription:
    """
    Speichert ein Logo fuer ein Abo auf dem Dateisystem (ADR 0010: lokales Dateisystem).

    Validiert Dateityp (JPEG/PNG/WebP) und Groesse (max. 2 MB).
    Loescht das alte Logo wenn vorhanden, schreibt das neue.
    Speichert den relativen Pfad ("logos/<uuid>.ext") in der DB — nicht die absolute URL.
    Der relative Pfad ist der entscheidende Entwurfsaspekt aus ADR 0010:
    bei spaeterer Migration zu Object Storage aendert sich nur dieser Service-Code.
    """
    # Dateityp pruefen — nur bekannte Bild-Formate akzeptieren
    if content_type not in _ALLOWED_LOGO_TYPES:
        raise InvalidFileError("Ungültiger Dateityp. Erlaubt: JPEG, PNG, WebP.")

    # Dateigroesse pruefen — zu grosse Bilder wuerden die Festplatte belasten
    if len(file_content) > _MAX_LOGO_SIZE_BYTES:
        raise InvalidFileError("Datei zu groß. Maximum: 2 MB.")

    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Altes Logo loeschen wenn vorhanden — Festplatte sauber halten
    if sub.logo_url:
        old_file = Path(upload_dir) / sub.logo_url
        # missing_ok=True: kein Fehler wenn die Datei schon fehlt (z. B. manuell geloescht)
        old_file.unlink(missing_ok=True)

    # Neuen Dateinamen mit UUID generieren — verhindert Kollisionen und Path-Traversal-Angriffe.
    # Niemals den vom Client gelieferten Dateinamen verwenden!
    ext = _LOGO_EXT[content_type]
    relative_path = f"logos/{uuid.uuid4()}{ext}"
    dest = Path(upload_dir) / relative_path
    # Verzeichnis anlegen falls es noch nicht existiert (z. B. erster Upload ueberhaupt)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_content)

    # Nur den relativen Pfad in der DB speichern (ADR 0010: kein absoluter Pfad, keine URL)
    sub.logo_url = relative_path
    session.commit()
    session.refresh(sub)
    return sub
