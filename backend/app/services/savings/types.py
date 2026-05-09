"""Interne Dataclasses für Sparfach-Berechnungen (ohne HTTP)."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BoxSummary:
    """
    Aggregierte Kennzahlen eines Sparfachs — wird aus Terms und Buchungen berechnet.

    Entspricht inhaltlich dem Response-Schema BoxSummaryRead; hier nur für die Service-Schicht.
    """

    total_deposited: Decimal
    total_penalties: Decimal
    net_amount: Decimal
    target_amount: Decimal | None
    personal_amount_per_term: Decimal | None
    progress_pct: Decimal | None
    terms_open: int
    terms_fulfilled: int
    terms_missed: int
