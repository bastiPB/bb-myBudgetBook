"""Gemeinsame Konstanten fuer den Subscription-Service (Rechnungen, Logos)."""

from decimal import Decimal

from app.models.subscription import BillingInterval

# Umrechnungsfaktoren: wie viel eines Abo-Betrags faellt pro Monat an?
# monthly    → voller Betrag pro Monat
# quarterly  → Betrag geteilt durch 3 (Quartal = 3 Monate)
# semiannual → Betrag geteilt durch 6 (Halbjahr = 6 Monate)
# yearly     → Betrag geteilt durch 12
# biennial   → Betrag geteilt durch 24 (2 Jahre = 24 Monate)
_MONTHLY_FACTOR: dict[BillingInterval, Decimal] = {
    BillingInterval.monthly: Decimal("1"),
    BillingInterval.quarterly: Decimal("1") / Decimal("3"),
    BillingInterval.semiannual: Decimal("1") / Decimal("6"),
    BillingInterval.yearly: Decimal("1") / Decimal("12"),
    BillingInterval.biennial: Decimal("1") / Decimal("24"),
}

# Wie viele Monate stecken in einer Abrechnungsperiode?
# Wird von den Berechnungsalgorithmen genutzt um Faelligkeitsdaten zu ermitteln.
_MONTHS_PER_PERIOD: dict[BillingInterval, int] = {
    BillingInterval.monthly: 1,
    BillingInterval.quarterly: 3,
    BillingInterval.semiannual: 6,
    BillingInterval.yearly: 12,
    BillingInterval.biennial: 24,
}

# Erlaubte Bild-Typen fuer Logo-Uploads (ADR 0010)
_ALLOWED_LOGO_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
# Dateiendung pro Content-Type — UUID-Dateiname verhindert Kollisionen und Path-Traversal
_LOGO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
