"""
Termin-Generierung, automatische „verpasst“-Markierung + Strafbuchungen, Kennzahlen.

Alle Funktionen nutzen sync Session / reine Datenobjekte — wie der Rest des Backends.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.savings_box import (
    SavingsBooking,
    SavingsBookingType,
    SavingsBox,
    SavingsBoxStatus,
    SavingsInterval,
    SavingsTerm,
    SavingsTermStatus,
)
from app.services.savings.constants import DAYS_PER_INTERVAL
from app.services.savings.types import BoxSummary


def generate_terms(box: SavingsBox) -> list[SavingsTerm]:
    """
    Erzeugt alle Spartermine von start_date bis end_date (inkl.).

    Jeder Term erhält expected_amount = min_amount_per_term (Snapshot zum Anlagezeitpunkt).
    weekly/biweekly: Schrittweite in Tagen; monthly: relativedelta(months=1).
    """
    expected = box.min_amount_per_term
    terms: list[SavingsTerm] = []

    if box.interval == SavingsInterval.monthly:
        current = box.start_date
        while current <= box.end_date:
            terms.append(
                SavingsTerm(
                    savings_box_id=box.id,
                    due_date=current,
                    expected_amount=expected,
                    status=SavingsTermStatus.open,
                )
            )
            current = current + relativedelta(months=1)
        return terms

    step_days = DAYS_PER_INTERVAL[box.interval]
    if step_days <= 0:
        raise ValueError("weekly/biweekly erwarten positive DAYS_PER_INTERVAL")

    current = box.start_date
    delta = timedelta(days=step_days)
    while current <= box.end_date:
        terms.append(
            SavingsTerm(
                savings_box_id=box.id,
                due_date=current,
                expected_amount=expected,
                status=SavingsTermStatus.open,
            )
        )
        current = current + delta
    return terms


def update_term_statuses(session: Session, box: SavingsBox) -> None:
    """
    Markiert überfällige offene Termine als missed und legt ggf. Strafbuchungen an.

    Nur für aktive Boxen — bei status=closed keine Änderungen (Abschluss ist unveränderlich).
    Für jeden open-Term mit due_date < heute: status → missed.
    Wenn penalty_amount gesetzt und > 0: höchstens eine penalty-Buchung pro Term (Idempotenz).

    Kein session.commit — der Aufrufer schließt die Transaktion.
    """
    if box.status == SavingsBoxStatus.closed:
        return

    today = date.today()

    stmt = select(SavingsTerm).where(
        SavingsTerm.savings_box_id == box.id,
        SavingsTerm.status == SavingsTermStatus.open,
    )
    open_terms = list(session.scalars(stmt))

    penalty_rate = box.penalty_amount
    wants_penalty = penalty_rate is not None and penalty_rate > 0

    for term in open_terms:
        if term.due_date >= today:
            continue

        term.status = SavingsTermStatus.missed

        if not wants_penalty:
            continue

        if _term_has_penalty_booking(session, term.id):
            continue

        session.add(
            SavingsBooking(
                savings_box_id=box.id,
                savings_term_id=term.id,
                booking_type=SavingsBookingType.penalty,
                amount=penalty_rate,
                booking_date=today,
                note=None,
            )
        )


def _term_has_penalty_booking(session: Session, term_id: uuid.UUID) -> bool:
    """True wenn bereits eine Strafe für diesen Term existiert (egal welcher Betrag)."""
    stmt = (
        select(SavingsBooking.id)
        .where(
            SavingsBooking.savings_term_id == term_id,
            SavingsBooking.booking_type == SavingsBookingType.penalty,
        )
        .limit(1)
    )
    return session.execute(stmt).first() is not None


def compute_box_summary(
    box: SavingsBox,
    terms: list[SavingsTerm],
    bookings: list[SavingsBooking],
) -> BoxSummary:
    """
    Berechnet Kennzahlen aus Terms und Buchungen — ohne Datenbankzugriff.

    total_deposited / total_penalties summieren nur Buchungen der jeweiligen Typen.
    net_amount = Einzahlungen minus Strafen (manuelle Buchungen fließen nicht in diese Summen ein).
    """
    total_deposited = Decimal("0")
    total_penalties = Decimal("0")
    for b in bookings:
        if b.booking_type == SavingsBookingType.deposit:
            total_deposited += b.amount
        elif b.booking_type == SavingsBookingType.penalty:
            total_penalties += b.amount

    net_amount = total_deposited - total_penalties

    target = box.target_amount
    progress_pct: Decimal | None = None
    if target is not None and target > 0:
        progress_pct = (net_amount / target * Decimal("100")).quantize(Decimal("0.01"))

    open_c = fulfilled_c = missed_c = 0
    for t in terms:
        if t.status == SavingsTermStatus.open:
            open_c += 1
        elif t.status == SavingsTermStatus.fulfilled:
            fulfilled_c += 1
        elif t.status == SavingsTermStatus.missed:
            missed_c += 1

    return BoxSummary(
        total_deposited=total_deposited,
        total_penalties=total_penalties,
        net_amount=net_amount,
        target_amount=box.target_amount,
        personal_amount_per_term=box.personal_amount_per_term,
        progress_pct=progress_pct,
        terms_open=open_c,
        terms_fulfilled=fulfilled_c,
        terms_missed=missed_c,
    )
