"""
app/services/scheduler_service.py — Business-Logik für den täglichen Buchungs-Scheduler.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Sie wird von APScheduler in main.py aufgerufen oder manuell per Admin-Endpoint getriggert.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import (
    PaymentStatus,
    Subscription,
    SubscriptionPauseHistory,
    SubscriptionPriceHistory,
    SubscriptionScheduledPayment,
    SubscriptionStatus,
)
from app.models.user_module_configurations import UserModuleConfiguration
from app.schemas.module_config import UserModuleConfigRead, UserModuleConfigUpdate
from app.services.subscriptions import (
    _MONTHS_PER_PERIOD,
    applicable_price,
    compute_due_dates,
    is_in_pause,
)

# Wie viele Tage rückwirkend werden verpasste Fälligkeiten nachgefüllt?
# 60 Tage = zwei Monate Puffer, z.B. nach längerem Server-Ausfall.
CATCH_UP_DAYS = 60


def get_or_create_module_config(session: Session, user_id: uuid.UUID) -> UserModuleConfiguration:
    """
    Gibt die Modul-Konfiguration des Users zurück — legt sie an, wenn noch keine existiert.

    Warum get_or_create statt einfach SELECT?
    Beim ersten Aufruf existiert noch kein Eintrag (Tabelle startet leer).
    Statt dem User eine Fehlermeldung zu zeigen, legen wir die Zeile transparent an.
    Default-Werte aus dem Model greifen: config = {} → alle Features default false.
    """
    config = session.execute(
        select(UserModuleConfiguration).where(UserModuleConfiguration.user_id == user_id)
    ).scalar_one_or_none()

    if config is None:
        # Erste Verwendung: leere Konfiguration anlegen (alle Toggles default false)
        config = UserModuleConfiguration(user_id=user_id, config={})
        session.add(config)
        session.commit()
        session.refresh(config)

    return config


def read_module_config(session: Session, user_id: uuid.UUID) -> UserModuleConfigRead:
    """
    Gibt die Modul-Konfiguration als Schema zurück.

    Flacht das JSONB-config-Dict auf einzelne Felder ab.
    Fehlt ein Key im Dict, wird der Schema-Default (False) verwendet.
    """
    db_config = get_or_create_module_config(session, user_id)
    raw = db_config.config or {}
    return UserModuleConfigRead(
        subscription_cumulative_calculation=raw.get("subscription_cumulative_calculation", False),
        subscription_booking_history=raw.get("subscription_booking_history", False),
    )


def update_module_config(
    session: Session, user_id: uuid.UUID, payload: UserModuleConfigUpdate
) -> UserModuleConfigRead:
    """
    Aktualisiert die Modul-Konfiguration des Users.

    Nur die im payload gesetzten Felder werden geändert (None = keine Änderung).
    Gibt die aktualisierte Konfiguration als Schema zurück.
    """
    db_config = get_or_create_module_config(session, user_id)

    # dict kopieren und nur gesetzte Felder überschreiben
    # Warum kopieren? SQLAlchemy erkennt Änderungen an JSONB-Dicts nur bei Zuweisung eines neuen Objekts.
    new_config = dict(db_config.config or {})

    if payload.subscription_booking_history is not None:
        new_config["subscription_booking_history"] = payload.subscription_booking_history

    if payload.subscription_cumulative_calculation is not None:
        new_config["subscription_cumulative_calculation"] = payload.subscription_cumulative_calculation

    # Neues dict zuweisen (nicht in-place mutieren) — so erkennt SQLAlchemy die Änderung
    db_config.config = new_config
    session.commit()
    session.refresh(db_config)

    return UserModuleConfigRead(
        subscription_cumulative_calculation=new_config.get("subscription_cumulative_calculation", False),
        subscription_booking_history=new_config.get("subscription_booking_history", False),
    )


def generate_scheduled_payments(session: Session) -> int:
    """
    Erzeugt Soll-Buchungen für alle aktiven und suspendierten Abos mit Buchungshistorie.

    Neu in v0.2.3 gegenüber v0.2.2:
    - Period-basiert: due_date = berechneter Fälligkeitstag (nicht mehr date.today())
    - Catch-up: Fälligkeiten bis 60 Tage rückwirkend werden nachgefüllt
    - suspended → paused-Einträge (kein Betrag, Status "paused")
    - canceled → gar keine Einträge (Tabelle endet sauber)
    - N+1 eliminiert: Pause-History per Bulk für alle Abos geladen

    Gibt die Anzahl der neu erzeugten Einträge zurück.

    Warum Idempotenz?
    Der Scheduler kann täglich mehrfach laufen (Restart, Retry).
    Wir prüfen im Code, ob der Eintrag schon existiert (erster Schutz).
    Der UNIQUE-Constraint (subscription_id, due_date) in der DB ist die zweite Verteidigungslinie.
    """
    today = date.today()
    # Frühester Fälligkeitstag, der noch berücksichtigt wird (60-Tage-Fenster)
    cutoff = today - timedelta(days=CATCH_UP_DAYS)
    created_count = 0

    # Alle User-IDs ermitteln, die subscription_booking_history aktiviert haben.
    # Die Konfigurationstabelle ist klein — Python-Filter ist ausreichend.
    all_configs = session.execute(select(UserModuleConfiguration)).scalars().all()
    enabled_user_ids = {
        cfg.user_id
        for cfg in all_configs
        if (cfg.config or {}).get("subscription_booking_history", False)
    }

    if not enabled_user_ids:
        # Kein User hat Buchungshistorie aktiviert — nichts zu tun
        return 0

    # Alle nicht-canceled Abos dieser User laden (active + suspended).
    # canceled Abos bekommen keine neuen Einträge — die Tabelle endet dort sauber.
    subscriptions = session.execute(
        select(Subscription).where(
            Subscription.user_id.in_(enabled_user_ids),
            Subscription.status != SubscriptionStatus.canceled,
        )
    ).scalars().all()

    # Pause-History für alle betroffenen Abos auf einmal laden.
    # Warum Bulk-Load? Sonst wäre es N+1: eine DB-Abfrage pro Abo.
    # defaultdict(list) gibt für unbekannte sub_ids automatisch [] zurück.
    sub_ids = [s.id for s in subscriptions]
    all_pauses = session.execute(
        select(SubscriptionPauseHistory).where(
            SubscriptionPauseHistory.subscription_id.in_(sub_ids)
        )
    ).scalars().all()
    pauses_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for p in all_pauses:
        pauses_by_sub[p.subscription_id].append(p)

    # Preishistorie für alle Abos auf einmal laden — analog zu Pause-History.
    # Wird pro Fälligkeitstag gebraucht um den damals gültigen Preis zu ermitteln.
    all_prices = session.execute(
        select(SubscriptionPriceHistory).where(
            SubscriptionPriceHistory.subscription_id.in_(sub_ids)
        )
    ).scalars().all()
    prices_by_sub: dict[uuid.UUID, list] = defaultdict(list)
    for p in all_prices:
        prices_by_sub[p.subscription_id].append(p)

    for sub in subscriptions:
        # Periodenlänge in Monaten (monthly=1, quarterly=3, semiannual=6, ...)
        period_months = _MONTHS_PER_PERIOD[sub.interval]
        # Pause- und Preiseinträge für dieses Abo (leere Liste wenn keine vorhanden)
        pause_hist = pauses_by_sub[sub.id]
        price_hist = prices_by_sub[sub.id]

        # Alle Fälligkeitsdaten vom Abo-Beginn bis heute berechnen
        for due in compute_due_dates(sub.started_on, period_months, today):
            # Catch-up-Fenster: verpasste Daten die zu weit zurückliegen überspringen
            if due < cutoff:
                continue

            # Existiert Eintrag schon? (erster Idempotenz-Schutz)
            existing = session.execute(
                select(SubscriptionScheduledPayment).where(
                    SubscriptionScheduledPayment.subscription_id == sub.id,
                    SubscriptionScheduledPayment.due_date == due,
                )
            ).scalar_one_or_none()
            if existing:
                # Eintrag existiert bereits — überspringen
                continue

            if is_in_pause(due, pause_hist):
                # Fälligkeitstag liegt in einer Pause-Episode:
                # Status = paused, kein Betrag fällig
                status = PaymentStatus.paused
                amount = None
            else:
                # Betrag aus Preishistorie für diesen Fälligkeitstag — nicht sub.amount.
                # sub.amount kann stale sein wenn eine Preisankündigung wirksam wurde.
                status = PaymentStatus.pending
                amount = applicable_price(due, price_hist)

            session.add(SubscriptionScheduledPayment(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                due_date=due,
                amount=amount,
                status=status,
            ))
            created_count += 1

    if created_count > 0:
        session.commit()

    return created_count
