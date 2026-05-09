"""Gemeinsame Konstanten für den Sparfach-Service (Termin-Abstände)."""

from app.models.savings_box import SavingsInterval

# Kalendertage zwischen zwei Terminen — Grundlage für generate_terms (weekly/biweekly).
# monthly = 0: dort wird dateutil.relativedelta verwendet (ungleiche Monatslängen).
DAYS_PER_INTERVAL: dict[SavingsInterval, int] = {
    SavingsInterval.weekly: 7,
    SavingsInterval.biweekly: 14,
    SavingsInterval.monthly: 0,
}
