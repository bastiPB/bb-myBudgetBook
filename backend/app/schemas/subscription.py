"""
app/schemas/subscription.py — Eingabe- und Ausgabe-Schemas für Abo-Endpunkte.

Schemas beschreiben, was die API als JSON erwartet oder zurückgibt.
Pydantic prüft automatisch ob die Daten das richtige Format haben.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.subscription import BillingInterval, PaymentStatus, SubscriptionStatus
from app.schemas.subscription_tag import TagRead


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
      "interval": "monthly",
      "started_on": "2026-01-01",  (optional — default: heute)
      "notes": "..."               (optional)
    }

    Hinweis: next_due_date wird in v0.2.3 serverseitig berechnet — nicht mehr im Body.
    amount: JSON-Number oder String — Strings mit Komma ("9,99") werden normalisiert.
    """

    name: str
    amount: Decimal
    # Interval: monthly/quarterly/semiannual/yearly/biennial
    interval: BillingInterval = BillingInterval.monthly
    # Abschlussdatum: optional, default wird im Service auf heute gesetzt.
    # Darf in der Zukunft liegen — z.B. Abo vorausbuchen (L-04 aufgehoben).
    started_on: date | None = None
    notes: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        """Normalisiert Komma → Punkt damit Pydantic auf Decimal parsen kann."""
        return _normalize_amount(v)


class SubscriptionUpdate(BaseModel):
    """
    Eingabe-Schema für das Bearbeiten eines Abos (PATCH).

    Alle Felder sind optional — es muss nur das mitgeschickt werden, was sich ändert.

    Hinweis: amount und interval sind hier nicht mehr enthalten.
    - Preisänderungen: POST /subscriptions/{id}/price-change
    - Intervallwechsel: POST /subscriptions/{id}/interval-change  (v0.2.4)
    """

    name: str | None = None
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
    Ausgabe-Schema für ein Abo in der Listenansicht.

    from_attributes=True erlaubt Pydantic, direkt aus einem SQLAlchemy-Objekt zu lesen.
    next_due_date wird nicht in der DB gespeichert — der Service berechnet es aus
    started_on + N × interval und setzt es vor der Rückgabe.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount: Decimal
    # Nicht in der DB — wird im Service via compute_next_due_date() befüllt
    next_due_date: date | None = None
    interval: BillingInterval
    status: SubscriptionStatus
    started_on: date
    notes: str | None
    logo_url: str | None
    # Tags: leer wenn keine Tags zugewiesen — wird im Service aus subscription_tag_assignments geladen
    tags: list[TagRead] = []


class SubscriptionDetail(SubscriptionRead):
    """
    Ausgabe-Schema für die Detailseite eines Abos (v0.2.3).

    Erweitert SubscriptionRead um vier berechnete Kostenkennzahlen.
    Diese Felder stehen nicht in der DB — der Service berechnet sie beim Abruf.

    monatlich:             Betrag auf Monatsbasis normiert (z.B. 89,90 € jährlich → 7,49 €)
    tatsaechlich:          Summe aller tatsächlich gezahlten Perioden (Pausen ausgenommen)
    intervalle:            Anzahl nicht-pausierter Zahlungsperioden seit Abo-Beginn
    dieses_kalenderjahr:   Summe aller Perioden im aktuellen Jahr (inkl. angekündigter Preise)
    """

    monatlich: Decimal
    tatsaechlich: Decimal
    intervalle: int
    dieses_kalenderjahr: Decimal


class OverviewRead(BaseModel):
    """
    Ausgabe-Schema für die Übersicht.

    monthly_total: Summe aller aktiven Abo-Beträge, auf Monatsbasis normiert.
                   Abos mit started_on in der Zukunft zählen nicht dazu (L-09).
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


class PriceChangeRequest(BaseModel):
    """
    Eingabe-Schema für POST /subscriptions/{id}/price-change (v0.2.3).

    Erlaubt Preisänderungen in der Vergangenheit, heute oder Zukunft:
    - Vergangenheit: korrigiert historische Berechnung von tatsaechlich
    - Zukunft:       zeigt Ankündigungs-Badge in der UI (Vorschau-Charakter)
    """

    amount: Decimal
    # Ab welchem Datum gilt der neue Preis? ISO-Format: "2026-10-01"
    valid_from: date

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        """Normalisiert Komma → Punkt damit Pydantic auf Decimal parsen kann."""
        return _normalize_amount(v)


class PauseHistoryEntry(BaseModel):
    """
    Ausgabe-Schema für einen Pause-Eintrag (v0.2.3).

    Jeder Eintrag steht für eine Pause-Episode des Abos.
    resumed_at ist None solange das Abo noch pausiert ist.
    """

    model_config = ConfigDict(from_attributes=True)

    paused_at: date
    resumed_at: date | None
    access_until: date | None


class ScheduledPaymentRead(BaseModel):
    """
    Ausgabe-Schema für eine geplante Buchung (Slice F).

    Wird vom Scheduler erzeugt — je ein Eintrag pro Abo und Fälligkeitstag.
    status: pending (ausstehend), paused (Abo war pausiert), matched (bezahlt), missed (verfallen)
    amount: None wenn paused (kein Betrag fällig in Pausenzeitraum)
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    due_date: date
    amount: Optional[Decimal]
    status: PaymentStatus


# --- v0.2.4: Billing History ---


class BillingHistoryEntry(BaseModel):
    """
    Ausgabe-Schema für einen Billing-History-Eintrag (v0.2.4).

    Beschreibt einen Zeitabschnitt der Abrechnungsbedingungen:
    - amount:     Betrag pro Periode
    - interval:   Abrechnungsintervall
    - valid_from: Ab wann gilt dieser Eintrag?
    - anchor_on:  Von wo aus werden Fälligkeiten berechnet?
                  Bei Preisänderung: gleich wie vorheriger Eintrag.
                  Bei Intervallwechsel: = valid_from (neuer Rhythmus startet hier).

    Wird für GET /subscriptions/{id}/billing-history und die Frontend-Historientabelle genutzt.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    amount: Decimal
    interval: BillingInterval
    valid_from: date
    anchor_on: date


class IntervalChangeRequest(BaseModel):
    """
    Eingabe-Schema für POST /subscriptions/{id}/interval-change (v0.2.4).

    Ändert Abrechnungsintervall und Betrag gemeinsam ab einem Datum.
    valid_from ist die erste Fälligkeit im neuen Intervall — von dort startet auch anchor_on.

    acknowledge_existing_payments:
      False (default): Der Endpoint blockt mit 409, wenn ab valid_from bereits
                       Scheduled Payments existieren.
      True:            Speichert die neue Billing-Historie trotzdem — bestehende
                       Scheduled Payments bleiben unverändert (bewusste User-Entscheidung).

    acknowledge_short_segment:
      False (default): Blockt mit 409, wenn durch die neue Historie eine Abrechnungsphase
                       kürzer als eine volle Periode des Intervalls entstünde (z.B. jährlich
                       ab 01.08., nächster Eintrag schon 01.10.).
      True:            Speichert trotzdem — bewusste Bestätigung durch den Nutzer.
    """

    amount: Decimal
    interval: BillingInterval
    # Erste Fälligkeit im neuen Intervall — wird auch als anchor_on gesetzt
    valid_from: date
    # Sicherheits-Flag: bei rückwirkenden Änderungen mit vorhandenen Buchungen nötig
    acknowledge_existing_payments: bool = False
    # Sicherheits-Flag: kurze Abrechnungsphase zwischen zwei Historien-Einträgen
    acknowledge_short_segment: bool = False

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v: object) -> object:
        """Normalisiert Komma → Punkt damit Pydantic auf Decimal parsen kann."""
        return _normalize_amount(v)
