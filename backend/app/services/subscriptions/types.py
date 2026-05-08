"""Interne Dataclasses fuer Subscription-Service-Ergebnisse."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.subscription import BillingInterval, Subscription


@dataclass
class OverviewResult:
    """Zwischenergebnis fuer den Uebersicht-Endpunkt — kein HTTP, nur Daten."""

    monthly_total: Decimal
    upcoming: list[Subscription]


@dataclass
class ComputedDue:
    """
    Eine berechnete Faelligkeit aus der Billing-Historie (v0.2.4).

    Enthaelt nicht nur das Datum, sondern auch Betrag, Intervall und Herkunft —
    damit der Scheduler und die Kennzahl-Funktionen keine zweite Datenbankabfrage
    brauchen um den Preis zu ermitteln.

    due_date:         Faelligkeitstag
    amount:           Betrag der zugehoerigen Abrechnungsperiode
    interval:         Abrechnungsintervall der zugehoerigen Periode
    billing_entry_id: ID des SubscriptionBillingHistory-Eintrags (fuer Tracing)
    """

    due_date: date
    amount: Decimal
    interval: BillingInterval
    billing_entry_id: uuid.UUID | None = None
