"""
app/schemas/subscription.py — Eingabe- und Ausgabe-Schemas für Abo-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.subscription import BillingInterval, SubscriptionStatus


class SubscriptionCreate(BaseModel):
    """
    Eingabe-Schema für ein neues Abo.

    Erwartet als JSON:
    {
      "name": "Netflix",
      "amount": "9,99",
      "next_due_date": "2026-06-01",
      "interval": "monthly",
      "started_on": "2026-01-01",  (optional — default: heute)
      "notes": "..."               (optional)
    }

    amount akzeptiert String oder Number — das Backend normalisiert auf Decimal.
    """

    name: str
    amount: Decimal
    next_due_date: date
    interval: BillingInterval = BillingInterval.monthly
    # Abschlussdatum: optional, default wird im Service auf heute gesetzt
    started_on: date | None = None
    notes: str | None = None

    @field_validator("started_on", mode="before")
    @classmethod
    def started_on_not_in_future(cls, v: object) -> object:
        """
        Validiert, dass das Abschlussdatum nicht in der Zukunft liegt.
        Das macht fachlich keinen Sinn — man kann kein Abo "in der Zukunft" abgeschlossen haben.
        """
        if v is None:
            return v
        # Wenn ein Datum übergeben wurde, prüfen ob es heute oder in der Vergangenheit liegt
        if isinstance(v, date) and v > date.today():
            raise ValueError("Abschlussdatum darf nicht in der Zukunft liegen.")
        return v


class SubscriptionUpdate(BaseModel):
    """
    Eingabe-Schema für das Bearbeiten eines Abos (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Beispiel: nur den Betrag ändern: { "amount": 12.99 }

    Hinweis: Wenn amount sich ändert, schreibt der Service automatisch einen
    Eintrag in subscription_price_history (kein API-Endpoint nötig).
    """

    name: str | None = None
    amount: Decimal | None = None
    next_due_date: date | None = None
    interval: BillingInterval | None = None
    notes: str | None = None


class SuspendPayload(BaseModel):
    """
    Eingabe-Schema für den Suspend-Endpunkt (POST /subscriptions/{id}/suspend).

    access_until: optional — bis wann ist die Leistung noch nutzbar?
    Beispiel bei Kündigung mitten im Monat: access_until = letzter Tag des Monats.
    Fehlt access_until, wird das Abo sofort als eingeschränkt markiert.
    """

    access_until: date | None = None


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
    # v0.2.2: neue Felder
    status: SubscriptionStatus
    started_on: date
    notes: str | None
    logo_url: str | None
    suspended_at: date | None
    access_until: date | None


class OverviewRead(BaseModel):
    """
    Ausgabe-Schema für die Übersicht.

    monthly_total: Summe aller aktiven Abo-Beträge, auf Monatsbasis normiert.
                   (z.B. 89.90 € jährlich → 7.49 € monatlich)
                   Suspended/canceled Abos zählen nicht mehr dazu.
    upcoming:      Aktive Abos, die in den nächsten 30 Tagen fällig sind.
    """

    monthly_total: Decimal
    upcoming: list[SubscriptionRead]
