"""
tools/hash_password.py — Argon2id Passwort-Generator

Dieses Tool hilft beim Erzeugen eines sicheren Argon2id-Passwort-Hashes,
der direkt in die .env-Datei eingetragen werden kann.

VERWENDUNG:
  docker compose run --rm backend python tools/hash_password.py

WANN BRAUCHE ICH DAS?
  Wenn du ADMIN_PASSWORD in .env als fertigen Hash eintragen möchtest
  statt als Klartext-Passwort. Beide Varianten funktionieren — der Hash
  ist etwas sicherer, weil kein Klartext in der .env-Datei steht.

  Klartext:  ADMIN_PASSWORD=meinPasswort
  Hash:      ADMIN_PASSWORD=$argon2id$v=19$m=65536,...
"""

import getpass
import sys

from argon2 import PasswordHasher
from argon2.exceptions import HashingError


def main() -> None:
    print("=" * 50)
    print("  BB-myBudgetBook — Argon2id Passwort-Generator")
    print("=" * 50)
    print()
    print("Das erzeugte Hash kann direkt als ADMIN_PASSWORD")
    print("in die .env-Datei eingetragen werden.")
    print()

    # getpass versteckt die Eingabe — das Passwort wird nicht angezeigt
    try:
        password = getpass.getpass("Passwort eingeben:    ")
        confirm  = getpass.getpass("Passwort bestätigen:  ")
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(0)

    # Eingaben vergleichen
    if password != confirm:
        print("\nFehler: Passwörter stimmen nicht überein.")
        sys.exit(1)

    # Mindestlänge prüfen (nur eine Warnung, kein harter Fehler)
    if len(password) < 12:
        print("\nWarnung: Passwort ist kürzer als 12 Zeichen — bitte ein stärkeres wählen.")

    # Argon2id-Hash erzeugen
    ph = PasswordHasher()
    try:
        hashed = ph.hash(password)
    except HashingError as e:
        print(f"\nFehler beim Hashen: {e}")
        sys.exit(1)

    print()
    print("=" * 50)
    print("Dein Argon2id-Hash (in .env eintragen):")
    print()
    print(hashed)
    print()
    print("In .env eintragen als:")
    print(f"  ADMIN_PASSWORD={hashed}")
    print("=" * 50)


if __name__ == "__main__":
    main()
