"""
Lesende Sparfach-Operationen — Bulk-Laden für die Listenansicht, Detail mit Term-Refresh.

Nutzt sync Session wie der Rest der App (nicht async).
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.savings_box import SavingsBooking, SavingsBox, SavingsTerm, SavingsTermStatus
from app.schemas.savings_box import (
    BoxSummaryRead,
    SavingsBookingRead,
    SavingsBoxDetail,
    SavingsBoxRead,
    SavingsTermRead,
)

from .access import get_box_or_404
from .terms import compute_box_summary, update_term_statuses
from .types import BoxSummary


def list_boxes(session: Session, user_id: uuid.UUID) -> list[tuple[SavingsBox, BoxSummary, date | None]]:
    """
    Alle Sparfächer des Nutzers (aktiv + geschlossen), sortiert nach start_date absteigend.

    Zwei zusätzliche Queries für alle Terms und alle Buchungen der geladenen Boxen —
    danach Zusammenfassung und nächster offener Term pro Box in Python (kein N+1).
    """
    stmt = (
        select(SavingsBox)
        .where(SavingsBox.user_id == user_id)
        .order_by(SavingsBox.start_date.desc())
    )
    boxes = list(session.scalars(stmt).all())
    if not boxes:
        return []

    box_ids = [b.id for b in boxes]

    terms_stmt = select(SavingsTerm).where(SavingsTerm.savings_box_id.in_(box_ids))
    all_terms = list(session.scalars(terms_stmt).all())

    bookings_stmt = select(SavingsBooking).where(SavingsBooking.savings_box_id.in_(box_ids))
    all_bookings = list(session.scalars(bookings_stmt).all())

    terms_by_box: dict[uuid.UUID, list[SavingsTerm]] = defaultdict(list)
    for t in all_terms:
        terms_by_box[t.savings_box_id].append(t)

    bookings_by_box: dict[uuid.UUID, list[SavingsBooking]] = defaultdict(list)
    for b in all_bookings:
        bookings_by_box[b.savings_box_id].append(b)

    # Stabile Reihenfolge der Termine/Buchungen pro Box (für konsistente Summaries)
    for lst in terms_by_box.values():
        lst.sort(key=lambda x: (x.due_date, x.id))
    for lst in bookings_by_box.values():
        lst.sort(key=lambda x: (x.booking_date, x.id))

    out: list[tuple[SavingsBox, BoxSummary, date | None]] = []
    for box in boxes:
        terms = terms_by_box.get(box.id, [])
        bookings = bookings_by_box.get(box.id, [])
        summary = compute_box_summary(box, terms, bookings)
        next_open = _next_open_due_date(terms)
        out.append((box, summary, next_open))
    return out


def get_box_detail(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[SavingsBox, list[SavingsTerm], list[SavingsBooking], BoxSummary]:
    """
    Lädt eine Box inkl. Terminen und Buchungen und berechnet die Kennzahlen.

    Ruft zuerst update_term_statuses auf (überfällige Termine, idempotente Strafen).
    flush() stellt sicher, dass neu angelegte Penalty-Zeilen in derselben Session sichtbar sind.
    """
    box = get_box_or_404(session, box_id, user_id)
    update_term_statuses(session, box)
    session.flush()
    # Ohne commit würden „missed“ + Strafen beim Schließen der Request-Session verloren gehen.
    session.commit()

    terms = list(
        session.scalars(
            select(SavingsTerm)
            .where(SavingsTerm.savings_box_id == box.id)
            .order_by(SavingsTerm.due_date, SavingsTerm.id)
        ).all()
    )
    bookings = list(
        session.scalars(
            select(SavingsBooking)
            .where(SavingsBooking.savings_box_id == box.id)
            .order_by(SavingsBooking.booking_date.desc(), SavingsBooking.id.desc())
        ).all()
    )
    summary = compute_box_summary(box, terms, bookings)
    return box, terms, bookings, summary


def get_box_list_projection(
    session: Session,
    box_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[SavingsBox, BoxSummary, date | None]:
    """
    Eine Box mit Kennzahlen wie in der Listenansicht — ohne update_term_statuses (kein Seiteneffekt).

    Für PATCH-Antworten nach update_box, damit summary/next_open_due_date konsistent sind.
    """
    box = get_box_or_404(session, box_id, user_id)
    terms = list(
        session.scalars(
            select(SavingsTerm)
            .where(SavingsTerm.savings_box_id == box.id)
            .order_by(SavingsTerm.due_date, SavingsTerm.id)
        ).all()
    )
    bookings = list(
        session.scalars(
            select(SavingsBooking)
            .where(SavingsBooking.savings_box_id == box.id)
            .order_by(SavingsBooking.booking_date, SavingsBooking.id)
        ).all()
    )
    summary = compute_box_summary(box, terms, bookings)
    return box, summary, _next_open_due_date(terms)


def box_summary_to_read(summary: BoxSummary) -> BoxSummaryRead:
    """Wandelt die Service-Dataclass in das API-Response-Schema um."""
    return BoxSummaryRead(
        total_deposited=summary.total_deposited,
        total_penalties=summary.total_penalties,
        net_amount=summary.net_amount,
        target_amount=summary.target_amount,
        personal_amount_per_term=summary.personal_amount_per_term,
        progress_pct=summary.progress_pct,
        terms_open=summary.terms_open,
        terms_fulfilled=summary.terms_fulfilled,
        terms_missed=summary.terms_missed,
    )


def savings_box_to_read(
    box: SavingsBox,
    summary: BoxSummary,
    next_open_due_date: date | None,
) -> SavingsBoxRead:
    """Baut SavingsBoxRead aus ORM-Zeile + berechneter Summary."""
    return SavingsBoxRead(
        id=box.id,
        name=box.name,
        location=box.location,
        box_number=box.box_number,
        start_date=box.start_date,
        end_date=box.end_date,
        interval=box.interval,
        min_amount_per_term=box.min_amount_per_term,
        penalty_amount=box.penalty_amount,
        status=box.status,
        next_open_due_date=next_open_due_date,
        summary=box_summary_to_read(summary),
    )


def savings_box_to_detail(
    box: SavingsBox,
    terms: list[SavingsTerm],
    bookings: list[SavingsBooking],
    summary: BoxSummary,
) -> SavingsBoxDetail:
    """Vollständige Detail-Antwort inkl. Terminen und Buchungen."""
    read = savings_box_to_read(box, summary, _next_open_due_date(terms))
    return SavingsBoxDetail(
        **read.model_dump(),
        terms=[SavingsTermRead.model_validate(t) for t in terms],
        bookings=[SavingsBookingRead.model_validate(b) for b in bookings],
        closed_at=box.closed_at,
        closing_actual_amount=box.closing_actual_amount,
        closing_expected_amount=box.closing_expected_amount,
        closing_note=box.closing_note,
    )


def _next_open_due_date(terms: list[SavingsTerm]) -> date | None:
    """Frühestes Fälligkeitsdatum unter noch offenen Terminen — sonst None."""
    open_dates = [t.due_date for t in terms if t.status == SavingsTermStatus.open]
    return min(open_dates) if open_dates else None
