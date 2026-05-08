"""
tools/seed_testing_subscription.py — Seed-Skript für ein komplexes Test-Abo.

Legt ein Abo "TestingAboIntervall" in der DB an mit:
- Start in der Vergangenheit (monatlich, 5 EUR)
- Preisaenderung in der Vergangenheit (monatlich, 6 EUR; davor laeuft 5 EUR mindestens 3 Monate)
- Intervallwechsel in der Vergangenheit (vierteljaehrlich)
- Intervallwechsel in der Vergangenheit zurueck auf monatlich (8 EUR)
- Ein paar Scheduled Payments (Buchungshistorie) mit verschiedenen Stati

Warum Script statt per UI klicken?
- Reproduzierbare Testdaten fuer Bugfixing / Regression.
- Spart Zeit beim wiederholten Nachstellen von Edge-Cases.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select

# Robust: Script kann aus beliebigem Working-Directory laufen (Host oder Container).
# Wir haengen das Backend-Root (Ordner ueber "tools/") an sys.path, damit `import app...` klappt.
_THIS_FILE = os.path.abspath(__file__)
_BACKEND_ROOT = os.path.dirname(os.path.dirname(_THIS_FILE))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


def _pick_user(session, email: str | None):
    """
    Waehlt einen User fuer die Seed-Daten.

    - Wenn email gesetzt ist: sucht genau diesen User.
    - Sonst: nimmt den ersten Admin-User.

    Wir erzeugen absichtlich KEINEN neuen User, weil password_hash benoetigt wird.
    """
    # Lazy imports: erlaubt --database-url per ENV zu setzen, bevor Engine gebaut wird.
    from app.models.user import User, UserRole

    if email:
        user = session.execute(select(User).where(User.email == email)).scalars().first()
        if user is None:
            raise RuntimeError(f"User nicht gefunden: {email}")
        return user

    admin = session.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    if admin is None:
        raise RuntimeError(
            "Kein Admin-User in der DB gefunden. "
            "Bitte zuerst App starten (bootstrap_admin) oder --email angeben."
        )
    return admin


def _delete_existing_subscription(session, user_id: uuid.UUID, name: str) -> None:
    """
    Loescht ein vorhandenes Test-Abo gleichen Namens (falls vorhanden).

    Achtung: CASCADE loescht auch History und Scheduled Payments.
    """
    from app.models.subscription import Subscription

    existing = session.execute(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.name == name)
    ).scalars().all()
    for sub in existing:
        session.delete(sub)
    if existing:
        session.commit()


def seed_testing_subscription(email: str | None, force: bool, with_payments: bool) -> uuid.UUID:
    """
    Fuehrt das Seed an der echten DB aus und gibt die Subscription-ID zurueck.
    """
    from app.database import SessionLocal
    from app.models.subscription import (
        BillingInterval,
        PaymentStatus,
        SubscriptionScheduledPayment,
    )
    from app.schemas.subscription import IntervalChangeRequest, PriceChangeRequest, SubscriptionCreate
    from app.services.subscriptions import compute_due_dates_for_billing_history, get_billing_history
    from app.services.subscriptions.mutations import create_subscription, interval_change, price_change

    with SessionLocal() as session:
        user = _pick_user(session, email)
        name = "TestingAboIntervall"

        if force:
            _delete_existing_subscription(session, user.id, name)

        # --- Timeline (alles in der Vergangenheit) ---
        today = date.today()

        # 20 Monate in die Vergangenheit, damit alle Segmente sicher "voll" sind.
        started_on = today - relativedelta(months=20)
        # Preiswechsel nach 4 Monaten (=> 5 EUR lief 4 Monate = >= 3 Monate)
        price_change_on = started_on + relativedelta(months=4)
        # Intervallwechsel zu quarterly nach weiteren 6 Monaten
        quarterly_on = price_change_on + relativedelta(months=6)
        # Ein kompletter Quartals-Zyklus (3 Monate), dann zurück zu monthly
        back_to_monthly_on = quarterly_on + relativedelta(months=3)

        # --- Subscription anlegen ---
        sub = create_subscription(
            session,
            user.id,
            SubscriptionCreate(
                name=name,
                amount=Decimal("5.00"),
                interval=BillingInterval.monthly,
                started_on=started_on,
                notes="Seeded by tools/seed_testing_subscription.py",
            ),
        )

        # --- Preisänderung (monatlich 6 EUR, Anker bleibt gleich) ---
        price_change(
            session,
            user.id,
            sub.id,
            PriceChangeRequest(amount=Decimal("6.00"), valid_from=price_change_on),
        )

        # --- Intervallwechsel zu quarterly (Anker = valid_from) ---
        interval_change(
            session,
            user.id,
            sub.id,
            IntervalChangeRequest(
                amount=Decimal("18.00"),
                interval=BillingInterval.quarterly,
                valid_from=quarterly_on,
                acknowledge_existing_payments=True,
                acknowledge_short_segment=True,
            ),
        )

        # --- Zurueck auf monthly (8 EUR) ---
        interval_change(
            session,
            user.id,
            sub.id,
            IntervalChangeRequest(
                amount=Decimal("8.00"),
                interval=BillingInterval.monthly,
                valid_from=back_to_monthly_on,
                acknowledge_existing_payments=True,
                acknowledge_short_segment=True,
            ),
        )

        if with_payments:
            # --- Ein paar Scheduled Payments (Buchungen) ---
            billing_hist = get_billing_history(session, sub.id, user.id)
            # Wir berechnen Dues bis heute; daraus picken wir ein paar Daten.
            dues = compute_due_dates_for_billing_history(billing_hist, today)
            due_by_date = {d.due_date: d for d in dues}

            # Wähle: 1 Zahlung im quarterly-Fenster + 3 Zahlungen im monthly-8EUR-Fenster
            targets: list[tuple[date, PaymentStatus]] = [
                (quarterly_on, PaymentStatus.matched),
                (back_to_monthly_on, PaymentStatus.matched),
                (back_to_monthly_on + relativedelta(months=1), PaymentStatus.pending),
                (back_to_monthly_on + relativedelta(months=2), PaymentStatus.missed),
            ]

            for due_date, status in targets:
                computed = due_by_date.get(due_date)
                if computed is None:
                    # Wenn der Anker-Tag z.B. auf ein nicht-existentes Datum fällt,
                    # kann sich der due_date verschieben. Dann ueberspringen wir.
                    continue
                session.add(
                    SubscriptionScheduledPayment(
                        id=uuid.uuid4(),
                        subscription_id=sub.id,
                        due_date=due_date,
                        amount=computed.amount,
                        status=status,
                    )
                )
            session.commit()

        return sub.id


def main() -> None:
    """
    CLI-Einstiegspunkt.
    """
    parser = argparse.ArgumentParser(description="Seed: TestingAboIntervall in die DB schreiben.")
    parser.add_argument(
        "--email",
        help="Optional: E-Mail eines existierenden Users. Ohne Angabe wird der erste Admin verwendet.",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Vorher vorhandenes Test-Abo gleichen Namens loeschen.",
    )
    parser.add_argument(
        "--no-payments",
        action="store_true",
        help="Keine Scheduled Payments (Buchungshistorie) anlegen.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "Optional: PostgreSQL-URL fuer lokalen Lauf (z.B. postgresql://user:pass@localhost:5432/db). "
            "Wenn gesetzt, wird DATABASE_URL fuer dieses Script ueberschrieben."
        ),
    )
    args = parser.parse_args()

    if args.database_url:
        # Wichtig: app.database liest DATABASE_URL beim Import. Deshalb ENV vor seed-Funktionen setzen.
        os.environ["DATABASE_URL"] = args.database_url

    sub_id = seed_testing_subscription(email=args.email, force=args.force, with_payments=not args.no_payments)
    print(f"Seed OK. subscription_id={sub_id}")


if __name__ == "__main__":
    main()

