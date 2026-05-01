"""
app/services/subscriptions.py — Business-Logik für Abo-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle Funktionen prüfen: darf dieser User dieses Abo sehen / ändern?
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, SubscriptionNotFoundError
from app.models.subscription import BillingInterval, Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate

# Umrechnungsfaktoren: wie viel eines Abo-Betrags fällt pro Monat an?
# monthly   → voller Betrag pro Monat
# quarterly → Betrag geteilt durch 3 (Quartal = 3 Monate)
# yearly    → Betrag geteilt durch 12
# biennial  → Betrag geteilt durch 24 (2 Jahre = 24 Monate)
_MONTHLY_FACTOR: dict[BillingInterval, Decimal] = {
    BillingInterval.monthly:   Decimal("1"),
    BillingInterval.quarterly: Decimal("1") / Decimal("3"),
    BillingInterval.yearly:    Decimal("1") / Decimal("12"),
    BillingInterval.biennial:  Decimal("1") / Decimal("24"),
}


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurück, sortiert nach Fälligkeitsdatum.

    Wichtig: die WHERE-Klausel stellt sicher, dass ein User niemals Abos
    anderer User sehen kann — auch wenn er eine fremde ID kennt.
    """
    stmt = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.next_due_date)
    )
    return list(session.execute(stmt).scalars().all())


@dataclass
class OverviewResult:
    """Zwischenergebnis für den Übersicht-Endpunkt — kein HTTP, nur Daten."""

    monthly_total: Decimal
    upcoming: list[Subscription]


def get_overview(session: Session, user_id: uuid.UUID) -> OverviewResult:
    """
    Berechnet die monatliche Gesamtsumme und die nächsten fälligen Abos.

    monthly_total: Summe aller Abo-Beträge (ohne Laufzeit-Gewichtung).
    upcoming:      Abos, deren next_due_date innerhalb der nächsten 30 Tage liegt.
    """
    subs = list_subscriptions(session, user_id)

    # Jeden Betrag auf Monatsbasis umrechnen und aufaddieren.
    # Beispiel: 89.90 € jährlich → 89.90 / 12 = 7.49 € monatlich
    monthly_total = sum(
        (s.amount * _MONTHLY_FACTOR[s.interval] for s in subs),
        Decimal("0"),
    )

    # Abos filtern: nur die, die in den nächsten 30 Tagen fällig werden
    today = date.today()
    cutoff = today + timedelta(days=30)
    upcoming = [s for s in subs if today <= s.next_due_date <= cutoff]

    return OverviewResult(monthly_total=monthly_total, upcoming=upcoming)


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    payload: SubscriptionCreate,
) -> Subscription:
    """
    Legt ein neues Abo für den eingeloggten User an.

    Die user_id kommt aus der Session (eingeloggter User), nicht aus der Anfrage —
    so kann ein User kein Abo unter fremdem Namen anlegen.
    """
    sub = Subscription(
        user_id=user_id,
        name=payload.name,
        amount=payload.amount,
        next_due_date=payload.next_due_date,
        interval=payload.interval,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def update_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SubscriptionUpdate,
) -> Subscription:
    """
    Aktualisiert ein bestehendes Abo.

    Nur Felder die im payload mitgeschickt wurden (nicht None) werden geändert.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()

    # Sicherheitsprüfung: User darf nur seine eigenen Abos bearbeiten
    if sub.user_id != user_id:
        raise ForbiddenError()

    # Nur die Felder aktualisieren, die der User tatsächlich mitgeschickt hat
    if payload.name is not None:
        sub.name = payload.name
    if payload.amount is not None:
        sub.amount = payload.amount
    if payload.next_due_date is not None:
        sub.next_due_date = payload.next_due_date
    if payload.interval is not None:
        sub.interval = payload.interval

    session.commit()
    session.refresh(sub)
    return sub


def delete_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """
    Löscht ein Abo unwiderruflich.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()

    # Sicherheitsprüfung: User darf nur seine eigenen Abos löschen
    if sub.user_id != user_id:
        raise ForbiddenError()

    session.delete(sub)
    session.commit()
