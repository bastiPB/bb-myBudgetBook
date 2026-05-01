"""
app/schemas/subscription.py — Eingabe- und Ausgabe-Schemas für Abo-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.subscription import BillingInterval


class SubscriptionCreate(BaseModel):
    """
    Eingabe-Schema für ein neues Abo.

    Erwartet als JSON: { "name": "...", "amount": 9.99, "next_due_date": "2026-06-01", "interval": "monthly" }
    interval ist optional — fehlt es, wird "monthly" angenommen.
    """

    name: str
    amount: Decimal
    next_due_date: date
    interval: BillingInterval = BillingInterval.monthly


class SubscriptionUpdate(BaseModel):
    """
    Eingabe-Schema für das Bearbeiten eines Abos (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Beispiel: nur den Betrag ändern: { "amount": 12.99 }
    """

    name: str | None = None
    amount: Decimal | None = None
    next_due_date: date | None = None
    interval: BillingInterval | None = None


class SubscriptionRead(BaseModel):
    """
    Ausgabe-Schema für ein Abo.

    from_attributes=True erlaubt Pydantic, direkt aus einem SQLAlchemy-Objekt zu lesen.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount: Decimal
    next_due_date: date
    interval: BillingInterval


class OverviewRead(BaseModel):
    """
    Ausgabe-Schema für die Übersicht.

    monthly_total: Summe aller Abo-Beträge, auf Monatsbasis normiert.
                   (z.B. 89.90 € jährlich → 7.49 € monatlich)
    upcoming:      Abos, die in den nächsten 30 Tagen fällig sind.
    """

    monthly_total: Decimal
    upcoming: list[SubscriptionRead]
