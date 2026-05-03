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


def _normalize_amount(v: object) -> object:
    """
    Normalisiert Betragseingaben vor der Pydantic-Typprüfung (mode='before').

    Komma als Dezimaltrennzeichen wird zu Punkt umgewandelt:
      "9,99"  → "9.99"  → Decimal("9.99") ✓
      "9.99"  → "9.99"  → Decimal("9.99") ✓
      9.99    → 9.99    → Decimal("9.99") ✓  (Zahlen werden unverändert durchgelassen)

    Warum hier und nicht im Frontend?
    Das Frontend sendet bereits einen Number-Wert — dieser Validator greift nur,
    wenn jemand die API direkt mit einem String-Body aufruft (z. B. curl, Postman).
    """
    if isinstance(v, str):
        # Komma durch Punkt ersetzen damit Pydantic auf Decimal parsen kann
        return v.replace(",", ".")
    return v


class SubscriptionCreate(BaseModel):
    """
    Eingabe-Schema für ein neues Abo.

    Erwartet als JSON:
    {
      "name": "Netflix",
      "amount": 9.99,
      "next_due_date": "2026-06-01",
      "interval": "monthly",
      "started_on": "2026-01-01",  (optional — default: heute)
      "notes": "..."               (optional)
    }

    amount: JSON-Number oder String — Strings mit Komma ("9,99") werden normalisiert.
    """

    name: str
    amount: Decimal
    next_due_date: date
    interval: BillingInterval = BillingInterval.monthly
    # Abschlussdatum: optional, default wird im Service auf heute gesetzt
    started_on: date | None = None
    notes: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        """Normalisiert Komma → Punkt damit Pydantic auf Decimal parsen kann."""
        return _normalize_amount(v)

    @field_validator("started_on", mode="before")
    @classmethod
    def started_on_not_in_future(cls, v: object) -> object:
        """
        Validiert, dass das Abschlussdatum nicht in der Zukunft liegt.
        Das macht fachlich keinen Sinn — man kann kein Abo "in der Zukunft" abgeschlossen haben.

        Warum String-Handling nötig?
        Der Validator läuft mit mode='before', also bevor Pydantic den Wert zu date coerced.
        JSON liefert Datumsfelder immer als String ("2026-01-01").
        Würden wir nur isinstance(v, date) prüfen, käme ein String-Zukunftsdatum ungeprüft durch.
        """
        if v is None:
            return v

        # Rohwert in ein date-Objekt umwandeln um vergleichen zu können.
        # date-Objekt: direkt verwenden (z. B. aus internen Aufrufen oder Tests)
        # str:         ISO-Format parsen ("2026-01-01") — so kommt es aus JSON
        # Anderer Typ: unverändert zurückgeben, Pydantic wirft selbst einen Fehler
        check: date | None = None
        if isinstance(v, date):
            check = v
        elif isinstance(v, str):
            try:
                check = date.fromisoformat(v)
            except ValueError:
                return v  # Ungültiges Format — Pydantic meldet den Fehler

        if check is not None and check > date.today():
            raise ValueError("Abschlussdatum darf nicht in der Zukunft liegen.")
        return v


class SubscriptionUpdate(BaseModel):
    """
    Eingabe-Schema für das Bearbeiten eines Abos (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.
    Beispiel: nur den Betrag ändern: { "amount": 12.99 } oder { "amount": "12,99" }

    Hinweis: Wenn amount sich ändert, schreibt der Service automatisch einen
    Eintrag in subscription_price_history (kein API-Endpoint nötig).
    """

    name: str | None = None
    amount: Decimal | None = None
    next_due_date: date | None = None
    interval: BillingInterval | None = None
    notes: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        """Normalisiert Komma → Punkt damit Pydantic auf Decimal parsen kann."""
        return _normalize_amount(v)


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


class SubscriptionDetail(SubscriptionRead):
    """
    Ausgabe-Schema für die Detailseite eines Abos (Slice C).

    Erweitert SubscriptionRead um berechnete Kostenkennzahlen.
    Diese Felder stehen nicht in der DB — der Service berechnet sie beim Abruf.

    monthly_cost_normalized: Betrag auf Monatsbasis normiert
                             (z. B. 89,90 € jährlich → 7,49 € monatlich)
    yearly_cost_normalized:  monthly × 12
    total_paid_estimate:     Schätzung der bisherigen Gesamtkosten
                             (volle Abrechnungsperioden seit started_on × Betrag)
                             Ignoriert Preisänderungen — exakte Werte folgen in Slice E.
    """

    monthly_cost_normalized: Decimal
    yearly_cost_normalized: Decimal
    total_paid_estimate: Decimal


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


class PriceHistoryEntry(BaseModel):
    """
    Ausgabe-Schema für einen Preishistorie-Eintrag (Slice E).

    Jeder Eintrag bedeutet "ab valid_from gilt Betrag amount".
    Aufeinanderfolgende Einträge bilden eine lückenlose Preis-Zeitleiste.
    Beispiel: {9.99, 2026-01-01} → {12.99, 2026-03-01} → {14.99, 2026-05-01}
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    amount: Decimal
    valid_from: date
