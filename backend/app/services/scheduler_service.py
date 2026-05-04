"""
app/services/scheduler_service.py — Business-Logik für den täglichen Buchungs-Scheduler.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Sie wird von APScheduler in main.py aufgerufen oder manuell per Admin-Endpoint getriggert.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import PaymentStatus, Subscription, SubscriptionScheduledPayment
from app.models.user_module_configurations import UserModuleConfiguration
from app.schemas.module_config import UserModuleConfigRead, UserModuleConfigUpdate


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
    Erzeugt tägliche Soll-Buchungen für alle aktiven Abos mit aktivierter Buchungshistorie.

    Gibt die Anzahl der neu erzeugten Einträge zurück.

    Warum Idempotenz?
    Der Scheduler kann täglich mehrfach laufen (Restart, Retry).
    Wir prüfen zuerst im Code, ob der Eintrag schon existiert (erster Schutz).
    Der UNIQUE-Constraint (subscription_id, due_date) in der DB ist die zweite Verteidigungslinie.
    """
    today = date.today()
    created_count = 0

    # Alle User-IDs ermitteln, die subscription_booking_history aktiviert haben.
    # Wir laden alle Konfigurationen und filtern in Python — die Tabelle ist klein.
    all_configs = session.execute(select(UserModuleConfiguration)).scalars().all()
    enabled_user_ids = {
        cfg.user_id
        for cfg in all_configs
        if (cfg.config or {}).get("subscription_booking_history", False)
    }

    if not enabled_user_ids:
        # Kein User hat Buchungshistorie aktiviert — nichts zu tun
        return 0

    # Alle aktiven Abos dieser User laden
    active_subscriptions = session.execute(
        select(Subscription).where(
            Subscription.user_id.in_(enabled_user_ids),
            Subscription.status == "active",
        )
    ).scalars().all()

    for sub in active_subscriptions:
        # Prüfen ob für heute bereits ein Eintrag existiert (erster Idempotenz-Schutz)
        existing = session.execute(
            select(SubscriptionScheduledPayment).where(
                SubscriptionScheduledPayment.subscription_id == sub.id,
                SubscriptionScheduledPayment.due_date == today,
            )
        ).scalar_one_or_none()

        if existing is not None:
            # Eintrag existiert schon — überspringen
            continue

        # Neuen Eintrag anlegen: Betrag zum jetzigen Zeitpunkt (snapshot)
        payment = SubscriptionScheduledPayment(
            id=uuid.uuid4(),
            subscription_id=sub.id,
            due_date=today,
            amount=sub.amount,
            status=PaymentStatus.pending,
        )
        session.add(payment)
        created_count += 1

    if created_count > 0:
        session.commit()

    return created_count
