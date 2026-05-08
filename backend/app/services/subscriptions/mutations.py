"""Schreibende Subscription-Service-Funktionen (ohne Lifecycle-Statuswechsel)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    BillingEntryDeleteBlockedError,
    BillingHistoryChangeBlockedError,
    BillingHistoryEntryNotFoundError,
    DuplicateBillingHistoryEntryError,
    PriceEntryDeleteBlockedError,
    PriceHistoryEntryNotFoundError,
    ShortBillingSegmentError,
)
from app.models.subscription import (
    Subscription,
    SubscriptionBillingHistory,
    SubscriptionPriceHistory,
    SubscriptionScheduledPayment,
)
from app.schemas.subscription import (
    IntervalChangeRequest,
    PriceChangeRequest,
    SubscriptionCreate,
    SubscriptionDetail,
    SubscriptionUpdate,
)

from .access import _check_ownership, _get_subscription_or_raise
from .billing import (
    applicable_billing_terms,
    applicable_price,
    first_short_billing_segment_message,
    sync_subscription_billing_snapshot,
)
from .readers import get_subscription_detail


def delete_price_history_entry(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    """
    Loescht einen einzelnen Preishistorie-Eintrag — mit Sicherheitspruefungen.

    Geblockt wenn:
    - Es der einzige verbleibende Eintrag ist (Abo ohne Preis ist ungueltig).
    - Es bereits Buchungen fuer den Zeitraum gibt, in dem dieser Preis galt
      (historische Daten wuerden widerspruechlich werden).

    Praezise Bereichspruefung:
    Nicht jede Buchung nach entry.valid_from ist betroffen — nur die im Fenster
    [entry.valid_from, naechster_eintrag.valid_from). So kann ein „mittlerer"
    Eintrag (z. B. eine falsche Zukunfts-Ankuendigung ohne Buchungen) geloescht
    werden, auch wenn spaetere Eintraege mit Buchungen existieren.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Gesuchten Eintrag laden und Zugehoerigkeit pruefen
    entry = session.execute(
        select(SubscriptionPriceHistory).where(
            SubscriptionPriceHistory.id == entry_id,
            SubscriptionPriceHistory.subscription_id == subscription_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise PriceHistoryEntryNotFoundError()

    # Alle Eintraege des Abos laden — fuer Einzel-Check und sub.amount-Update
    all_entries = session.execute(
        select(SubscriptionPriceHistory).where(SubscriptionPriceHistory.subscription_id == subscription_id)
    ).scalars().all()

    # Letzter Eintrag? Dann darf er nicht geloescht werden.
    if len(all_entries) <= 1:
        raise PriceEntryDeleteBlockedError(
            "Der einzige Preiseintrag kann nicht gelöscht werden — "
            "ein Abo braucht mindestens einen Preis."
        )

    # Zeitfenster bestimmen, in dem dieser Eintrag der gueltige Preis war.
    # Falls ein spaeterer Eintrag existiert, endet das Fenster dort.
    # Falls es der letzte Eintrag ist, geht das Fenster bis in die Zukunft.
    later = [e for e in all_entries if e.valid_from > entry.valid_from]
    next_valid_from = min(e.valid_from for e in later) if later else None

    # Buchungen im Preisfenster suchen
    stmt = select(SubscriptionScheduledPayment).where(
        SubscriptionScheduledPayment.subscription_id == subscription_id,
        SubscriptionScheduledPayment.due_date >= entry.valid_from,
    )
    if next_valid_from is not None:
        # Nur Buchungen bis zum naechsten Preiseintrag — danach gilt ein anderer Preis
        stmt = stmt.where(SubscriptionScheduledPayment.due_date < next_valid_from)

    # Es können mehrere Buchungen im Fenster existieren → wir brauchen nur "existiert mindestens eine?"
    affected = session.execute(stmt).scalars().first()
    if affected is not None:
        raise PriceEntryDeleteBlockedError(
            "Dieser Preiseintrag kann nicht gelöscht werden, da bereits Buchungen "
            "für den betroffenen Zeitraum existieren."
        )

    # Verbleibende Eintraege fuer sub.amount-Neuberechnung vorab merken
    remaining = [e for e in all_entries if e.id != entry.id]

    session.delete(entry)

    # sub.amount korrigieren falls der geloeschte Eintrag der aktuell gueltige war.
    # applicable_price() waehlt anhand der verbleibenden Eintraege den richtigen Preis.
    new_amount = applicable_price(date.today(), remaining)
    if new_amount != Decimal("0"):
        sub.amount = new_amount

    session.commit()


def delete_billing_history_entry(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    """
    Loescht einen einzelnen Billing-History-Eintrag — mit Sicherheitspruefungen (v0.2.4).

    Geblockt wenn:
    - Es der einzige verbleibende Eintrag ist (Abo ohne Billing-Terms ist ungueltig).
    - Es bereits Buchungen fuer den Zeitraum gibt, in dem dieser Eintrag galt.

    Zeitfenster-Pruefung:
    Nicht jede Buchung nach entry.valid_from ist betroffen — nur die im Fenster
    [entry.valid_from, naechster_eintrag.valid_from). Ein mittlerer Eintrag ohne
    Buchungen (z. B. falsche Ankuendigung) kann so auch dann geloescht werden,
    wenn spaetere Eintraege mit Buchungen existieren.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Gesuchten Eintrag laden und Zugehoerigkeit pruefen
    entry = session.execute(
        select(SubscriptionBillingHistory).where(
            SubscriptionBillingHistory.id == entry_id,
            SubscriptionBillingHistory.subscription_id == subscription_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise BillingHistoryEntryNotFoundError()

    # Alle Eintraege des Abos laden — fuer Einzel-Check und Snapshot-Update
    all_entries = list(
        session.execute(
            select(SubscriptionBillingHistory).where(
                SubscriptionBillingHistory.subscription_id == subscription_id
            )
        ).scalars().all()
    )

    # Letzter Eintrag? Dann darf er nicht geloescht werden.
    if len(all_entries) <= 1:
        raise BillingEntryDeleteBlockedError(
            "Der einzige Abrechnungseintrag kann nicht gelöscht werden — "
            "ein Abo braucht mindestens einen Eintrag."
        )

    # Der initiale Eintrag (Abo-Start) darf nie gelöscht werden.
    # Warum? Sonst gäbe es keine gültigen Billing-Terms ab started_on und die Zeitleiste wäre "löchrig".
    if entry.valid_from == sub.started_on:
        raise BillingEntryDeleteBlockedError(
            "Der initiale Abrechnungseintrag (Abo-Start) kann nicht gelöscht werden."
        )

    # Zeitfenster bestimmen, in dem dieser Eintrag die gueltigen Konditionen beschrieb.
    # Falls ein spaeterer Eintrag existiert, endet das Fenster dort.
    later = [e for e in all_entries if e.valid_from > entry.valid_from]
    next_valid_from = min(e.valid_from for e in later) if later else None

    # Buchungen im Fenster suchen — nur die sind tatsaechlich von dieser Loeschung betroffen
    stmt = select(SubscriptionScheduledPayment).where(
        SubscriptionScheduledPayment.subscription_id == subscription_id,
        SubscriptionScheduledPayment.due_date >= entry.valid_from,
    )
    if next_valid_from is not None:
        stmt = stmt.where(SubscriptionScheduledPayment.due_date < next_valid_from)

    # Es können mehrere Buchungen im Fenster existieren → wir brauchen nur "existiert mindestens eine?"
    affected = session.execute(stmt).scalars().first()
    if affected is not None:
        raise BillingEntryDeleteBlockedError(
            "Dieser Abrechnungseintrag kann nicht gelöscht werden, da bereits Buchungen "
            "für den betroffenen Zeitraum existieren."
        )

    remaining = [e for e in all_entries if e.id != entry.id]
    # Sicherheitsnetz: remaining muss die Zeitleiste ab started_on weiterhin abdecken.
    earliest_remaining = min(e.valid_from for e in remaining)
    if earliest_remaining > sub.started_on:
        raise BillingEntryDeleteBlockedError(
            "Dieser Abrechnungseintrag kann nicht gelöscht werden, weil danach "
            "kein Abrechnungseintrag ab dem Startdatum mehr existieren würde."
        )
    if sub.started_on <= date.today() and applicable_billing_terms(date.today(), remaining) is None:
        raise BillingEntryDeleteBlockedError(
            "Dieser Abrechnungseintrag kann nicht geloescht werden, weil danach "
            "kein aktuell gueltiger Abrechnungseintrag mehr existieren wuerde."
        )

    session.delete(entry)
    # Snapshot synchronisieren: sub.amount und sub.interval nach Loeschung aktualisieren
    sync_subscription_billing_snapshot(sub, remaining)
    session.commit()


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    payload: SubscriptionCreate,
) -> Subscription:
    """
    Legt ein neues Abo fuer den eingeloggten User an.

    Die user_id kommt aus der Session (eingeloggter User), nicht aus der Anfrage —
    so kann ein User kein Abo unter fremdem Namen anlegen.

    started_on: wenn nicht angegeben, wird das heutige Datum verwendet.
    """
    # started_on aus dem Payload nehmen, oder heute als Fallback
    started_on = payload.started_on if payload.started_on is not None else date.today()

    sub = Subscription(
        user_id=user_id,
        name=payload.name,
        amount=payload.amount,
        interval=payload.interval,
        started_on=started_on,
        notes=payload.notes,
        # status, logo_url — SQLAlchemy-Defaults greifen
    )
    session.add(sub)
    session.flush()  # flush statt commit: sub.id ist jetzt verfuegbar, Transaktion noch offen

    # Initialen Billing-History-Eintrag schreiben (v0.2.4 — ersetzt _record_price_change).
    #
    # Warum hier und nicht erst beim ersten price_change?
    # Ohne diesen Eintrag fehlt der Startpreis nach der ersten Aenderung unwiederbringlich:
    #   Anlage:      9,99 € — kein Eintrag → nach Aenderung auf 12,99 € unbekannt
    #   1. Aenderung → {12,99, Maerz}
    #   2. Aenderung → {14,99, Mai}
    # History: [{12.99, Maerz}, {14.99, Mai}] — Jan–Feb fehlen komplett
    #
    # Mit diesem Eintrag:
    # History: [{9.99, started_on}, {12.99, Maerz}, {14.99, Mai}] →lueckenlose Zeitleiste
    #
    # anchor_on = started_on: der Faelligkeitsrhythmus startet am Abschluss-Datum.
    # valid_from = started_on: rueckwirkend angelegte Abos werden korrekt erfasst.
    initial_bh = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=sub.amount,
        interval=sub.interval,
        valid_from=started_on,
        anchor_on=started_on,
    )
    session.add(initial_bh)

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
    Aktualisiert Name, Intervall oder Notizen eines Abos (PATCH).

    Nur Felder die im Request-Body standen (payload.model_fields_set) werden geaendert.
    notes kann explizit auf null gesetzt werden ({ "notes": null }).

    Hinweis: Preisaenderungen laufen ueber price_change() — nicht mehr ueber diesen Endpoint.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehoert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur die Felder aktualisieren, die der User tatsaechlich mitgeschickt hat.
    #
    # Warum model_fields_set statt "if payload.x is not None"?
    # Bei Optional-Feldern bedeutet None zweierlei:
    #   - "nicht mitgeschickt" (Feld fehlt im JSON)  → soll nichts aendern
    #   - "explizit null"       ({ "notes": null })   → soll Feld leeren
    # model_fields_set enthaelt nur die Felder, die im Request-Body standen.
    for field in payload.model_fields_set:
        setattr(sub, field, getattr(payload, field))

    session.commit()
    session.refresh(sub)
    return sub


def price_change(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    payload: PriceChangeRequest,
) -> SubscriptionDetail:
    """
    Traegt eine Preisaenderung mit frei waehlbarem Gueltigkeitsdatum ein (v0.2.4).

    Schreibt einen Eintrag in subscription_billing_history (nicht mehr price_history).
    Copy-forward-Regel: Intervall und Anker werden vom gueltigen Vorgaenger-Eintrag uebernommen —
    eine Preisaenderung aendert nur den Betrag, der Zahlungsrhythmus bleibt gleich.

    valid_from darf in der Vergangenheit (Korrektur), heute oder Zukunft (Ankuendigung) liegen.
    Gibt die vollstaendige SubscriptionDetail mit neu berechneten Kennzahlen zurueck.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Aktuelle Billing-Historie laden — fuer Duplikat-Check und Copy-forward-Regel
    billing_hist = list(
        session.execute(
            select(SubscriptionBillingHistory).where(
                SubscriptionBillingHistory.subscription_id == subscription_id
            )
        ).scalars().all()
    )

    # Duplikat-Check: existiert bereits ein Eintrag fuer dieses Datum?
    # Kein stilles Ueberschreiben — der User muss den alten Eintrag erst loeschen.
    if any(e.valid_from == payload.valid_from for e in billing_hist):
        raise DuplicateBillingHistoryEntryError(payload.valid_from.isoformat())

    # Copy-forward-Regel: Intervall und Anker vom gueltigen Vorgaenger-Eintrag uebernehmen.
    # include_future=True: auch angekuendigte (zukuenftige) Eintraege einbeziehen —
    # eine Preisaenderung nach einer bereits eingetragenen Ankuendigung uebernimmt deren Rhythmus.
    prev = applicable_billing_terms(payload.valid_from, billing_hist, include_future=True)
    if prev is not None:
        carry_interval = prev.interval
        carry_anchor = prev.anchor_on
    else:
        # Kein Vorgaenger (Preisaenderung liegt vor dem initialen Eintrag): Snapshot als Fallback
        carry_interval = sub.interval
        carry_anchor = payload.valid_from

    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=carry_interval,
        valid_from=payload.valid_from,
        anchor_on=carry_anchor,
    )
    session.add(new_entry)

    # Snapshot synchronisieren: sub.amount und sub.interval auf heute gueltige Terms setzen.
    # Zukuenftige Eintraege (valid_from > heute) aendern den Snapshot noch nicht.
    sync_subscription_billing_snapshot(sub, billing_hist + [new_entry])

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)


def interval_change(
    session: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    payload: IntervalChangeRequest,
) -> SubscriptionDetail:
    """
    Aendert Abrechnungsintervall und Betrag gemeinsam ab einem Datum (v0.2.4).

    Schluesselregel: anchor_on = valid_from — der neue Zahlungsrhythmus startet genau hier.
    Das unterscheidet Intervallwechsel von Preisaenderungen (dort bleibt anchor_on gleich).

    409-Block-Flow (rueckwirkende Aenderungen mit vorhandenen Buchungen):
    - acknowledge_existing_payments=False (default):
      → 409 wenn ab valid_from bereits Scheduled Payments existieren.
      → Die Fehlermeldung nennt die Anzahl der betroffenen Buchungen.
    - acknowledge_existing_payments=True:
      → Speichert trotzdem — bestehende Buchungen bleiben unveraendert (bewusste User-Entscheidung).

    409-Block-Flow (kurze Abrechnungsphase):
    - Nach Duplikat-Check, vor Buchungs-Check: gemergte Historie (inkl. neuem Eintrag) wird
      auf Segmente geprueft, die kuerzer als eine volle Periode sind.
    - acknowledge_short_segment=False (default): 409 mit Hinweis (Marker „Kurze Abrechnungsphase“).
    - acknowledge_short_segment=True: Speichern trotzdem.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Aktuelle Billing-Historie laden — fuer Duplikat-Check
    billing_hist = list(
        session.execute(
            select(SubscriptionBillingHistory).where(
                SubscriptionBillingHistory.subscription_id == subscription_id
            )
        ).scalars().all()
    )

    # Duplikat-Check: existiert bereits ein Eintrag fuer dieses Datum?
    if any(e.valid_from == payload.valid_from for e in billing_hist):
        raise DuplicateBillingHistoryEntryError(payload.valid_from.isoformat())

    # Neuer Eintrag nur im Speicher — fuer Plausibilitaetspruefung noch nicht in der DB.
    new_entry = SubscriptionBillingHistory(
        subscription_id=sub.id,
        amount=payload.amount,
        interval=payload.interval,
        valid_from=payload.valid_from,
        anchor_on=payload.valid_from,
    )

    # Kurze Abrechnungsphase: z.B. jährlich ab 01.08., nächster Historien-Eintrag schon 01.10.
    merged_for_check = sorted(billing_hist + [new_entry], key=lambda e: e.valid_from)
    short_msg = first_short_billing_segment_message(merged_for_check)
    if short_msg and not payload.acknowledge_short_segment:
        raise ShortBillingSegmentError(short_msg)

    # 409-Block: rueckwirkende Aenderungen mit vorhandenen Buchungen erfordern explizite Bestaetigung.
    # Ohne Bestaetigung wird geblockt — der User soll die Konsequenzen bewusst akzeptieren.
    if not payload.acknowledge_existing_payments:
        affected = list(
            session.execute(
                select(SubscriptionScheduledPayment).where(
                    SubscriptionScheduledPayment.subscription_id == subscription_id,
                    SubscriptionScheduledPayment.due_date >= payload.valid_from,
                )
            ).scalars().all()
        )
        if affected:
            raise BillingHistoryChangeBlockedError(
                f"Ab {payload.valid_from.isoformat()} existieren bereits "
                f"{len(affected)} Buchung(en). Bitte mit "
                "acknowledge_existing_payments=true bestätigen, um fortzufahren."
            )

    # Intervallwechsel: anchor_on = valid_from — neuer Rhythmus startet genau hier.
    session.add(new_entry)

    # Snapshot synchronisieren: sub.amount und sub.interval auf heute gueltige Terms setzen.
    sync_subscription_billing_snapshot(sub, billing_hist + [new_entry])

    session.commit()
    return get_subscription_detail(session, subscription_id, user_id)
