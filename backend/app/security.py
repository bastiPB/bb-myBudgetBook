"""
app/security.py — Hilfsfunktionen rund um Session-Cookies.

Wir verwenden signierte Cookies mit der Bibliothek "itsdangerous".
Ein signierter Cookie ist wie ein Brief mit Siegel:
  - Der Inhalt (user_id) ist lesbar, aber nicht fälschbar.
  - Wenn jemand den Cookie manipuliert, wird die Signatur ungültig.
  - Der Cookie läuft nach MAX_AGE_SECONDS automatisch ab.

Das Passwort (Argon2id-Hashing) ist in services/auth.py implementiert.
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Name des Cookies im Browser
COOKIE_NAME = "session"

# Cookie läuft nach 30 Tagen ab (in Sekunden)
MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def create_session_token(user_id: str, secret_key: str) -> str:
    """
    Erstellt einen signierten Token, der die user_id enthält.

    Der Token wird als Cookie-Wert gesetzt.
    Nur der Server kann ihn verifizieren (dank secret_key).
    """
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(user_id)


def decode_session_token(token: str, secret_key: str) -> str | None:
    """
    Liest und verifiziert einen Session-Token.

    Gibt die user_id zurück, wenn der Token gültig ist.
    Gibt None zurück, wenn der Token ungültig oder abgelaufen ist.
    """
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        # max_age prüft ob der Token noch nicht abgelaufen ist
        return serializer.loads(token, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        # Manipulierter oder abgelaufener Token — kein Fehler werfen, nur None zurückgeben
        return None
