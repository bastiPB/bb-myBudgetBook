"""
app/services/subscriptions.py — Business-Logik für Abo-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle Funktionen prüfen: darf dieser User dieses Abo sehen / ändern?
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, InvalidFileError, InvalidSubscriptionStatusError, SubscriptionNotFoundError
from app.models.subscription import BillingInterval, Subscription, SubscriptionPriceHistory, SubscriptionScheduledPayment, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SuspendPayload

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


def _get_subscription_or_raise(session: Session, subscription_id: uuid.UUID) -> Subscription:
    """
    Hilfsfunktion: Abo laden und 404 werfen wenn es nicht existiert.

    Wird von mehreren Service-Funktionen verwendet um Duplikate zu vermeiden.
    """
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()
    return sub


def _check_ownership(sub: Subscription, user_id: uuid.UUID) -> None:
    """
    Hilfsfunktion: Prüft ob das Abo dem angegebenen User gehört.

    Wirft ForbiddenError wenn nicht — so kann kein User fremde Abos bearbeiten.
    """
    if sub.user_id != user_id:
        raise ForbiddenError()


def list_subscriptions(session: Session, user_id: uuid.UUID) -> list[Subscription]:
    """
    Gibt alle Abos des eingeloggten Users zurück, sortiert nach Fälligkeitsdatum.

    Gibt alle Status zurück (active, suspended, canceled) — die UI kann filtern.
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

    monthly_total: Summe aller aktiven Abo-Beträge (suspended/canceled zählen nicht mehr).
    upcoming:      Aktive Abos, deren next_due_date innerhalb der nächsten 30 Tage liegt.
    """
    subs = list_subscriptions(session, user_id)

    # Nur aktive Abos in die Berechnung einbeziehen — suspendierte kosten nichts mehr
    active_subs = [s for s in subs if s.status == SubscriptionStatus.active]

    # Jeden Betrag auf Monatsbasis umrechnen und aufaddieren.
    # Beispiel: 89.90 € jährlich → 89.90 / 12 = 7.49 € monatlich
    monthly_total = sum(
        (s.amount * _MONTHLY_FACTOR[s.interval] for s in active_subs),
        Decimal("0"),
    )

    # Abos filtern: nur aktive, die in den nächsten 30 Tagen fällig werden
    today = date.today()
    cutoff = today + timedelta(days=30)
    upcoming = [s for s in active_subs if today <= s.next_due_date <= cutoff]

    return OverviewResult(monthly_total=monthly_total, upcoming=upcoming)


def get_subscription(session: Session, subscription_id: uuid.UUID, user_id: uuid.UUID) -> Subscription:
    """
    Gibt ein einzelnes Abo zurück.

    Neu in v0.2.2 — wird von der Detailseite genutzt (Slice C).
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)
    return sub


@dataclass
class SubscriptionDetailResult:
    """Zwischenergebnis für den Detail-Endpunkt — kein HTTP, nur Daten."""

    sub: Subscription
    monthly_cost_normalized: Decimal
    yearly_cost_normalized: Decimal
    total_paid_estimate: Decimal


def _compute_total_paid_estimate(
    amount: Decimal,
    interval: BillingInterval,
    started_on: date,
) -> Decimal:
    """
    Schätzt den bisher gezahlten Gesamtbetrag seit Abschluss.

    Fallback-Funktion für den Fall dass keine Preishistorie vorhanden ist.
    Die exakte Berechnung mit echter Preishistorie erledigt _compute_total_paid_exact.

    Warum Monats-Arithmetik statt Tage?
    Tagesbasiert wäre ungenau (Monatslängen variieren).
    Monatsbasiert mit ganzzahligem floor ist einfach und intuitiv nachvollziehbar.
    """
    today = date.today()
    if started_on > today:
        return Decimal("0")

    # Wie viele Monate sind seit started_on vergangen? (abgerundet)
    months_elapsed = (today.year - started_on.year) * 12 + (today.month - started_on.month)

    # Wie viele volle Abrechnungsperioden stecken in diesen Monaten?
    months_per_period: dict[BillingInterval, int] = {
        BillingInterval.monthly:   1,
        BillingInterval.quarterly: 3,
        BillingInterval.yearly:    12,
        BillingInterval.biennial:  24,
    }
    # +1: die erste Zahlung am started_on zählt immer, auch wenn noch keine volle
    # Periode vergangen ist. Ohne +1 würde ein frisch angelegtes Abo 0,00 € zeigen.
    full_periods = months_elapsed // months_per_period[interval] + 1

    return (amount * Decimal(full_periods)).quantize(Decimal("0.01"))


def _compute_total_paid_exact(
    history: list[SubscriptionPriceHistory],
    interval: BillingInterval,
) -> Decimal:
    """
    Berechnet den bisherigen Gesamtbetrag exakt anhand der Preishistorie (Slice E).

    Für jedes Preis-Segment (von valid_from bis zum nächsten Eintrag oder heute)
    werden die vollen Abrechnungsperioden gezählt und mit dem Betrag multipliziert.

    Beispiel (monatlich):
      {9.99, Jan} → {12.99, März} → {14.99, Mai}
      Jan–Feb: 2 Monate // 1 = 2 Perioden × 9.99  = 19.98
      März–Apr: 2 Monate // 1 = 2 Perioden × 12.99 = 25.98
      Mai: 0 Monate // 1 = 0 Perioden × 14.99 = 0.00  (laufende Periode)
      Gesamt: 45.96

    Warum Monate statt Tage?
    Konsistent mit _compute_total_paid_estimate — gleiche Arithmetik, gleiche Intuition.
    """
    if not history:
        return Decimal("0")

    # Aufsteigend nach valid_from sortieren → ältester Eintrag zuerst
    sorted_history = sorted(history, key=lambda e: e.valid_from)
    today = date.today()

    months_per_period: dict[BillingInterval, int] = {
        BillingInterval.monthly:   1,
        BillingInterval.quarterly: 3,
        BillingInterval.yearly:    12,
        BillingInterval.biennial:  24,
    }
    period_months = months_per_period[interval]

    total = Decimal("0")
    for i, entry in enumerate(sorted_history):
        segment_start = entry.valid_from
        is_last = (i + 1 >= len(sorted_history))
        # Ende des Segments: entweder der nächste Preiseintrag oder heute
        segment_end = sorted_history[i + 1].valid_from if not is_last else today

        if segment_end <= segment_start:
            continue

        # Monate in diesem Segment (ganzzahlig — Tagesanteil wird ignoriert)
        months = (
            (segment_end.year - segment_start.year) * 12
            + (segment_end.month - segment_start.month)
        )
        full_periods = months // period_months

        # Letztes Segment: +1 für die Zahlung die am segment_start (= Startdatum oder
        # Preisänderungsdatum) bereits stattgefunden hat.
        # Ohne +1: Abo gestartet am 3.5., heute 4.5. → 0 Monate → 0 Zahlungen (falsch).
        # Mit +1: 0 Monate + 1 = 1 Zahlung (korrekt — man zahlt beim Abschluss sofort).
        if is_last:
            full_periods += 1

        total += entry.amount * Decimal(full_periods)

    return total.quantize(Decimal("0.01"))


def get_subscription_detail(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SubscriptionDetailResult:
    """
    Gibt ein Abo mit berechneten Kostenkennzahlen zurück (Slice C/E).

    total_paid_estimate wird ab Slice E exakt via Preishistorie berechnet.
    Ist keine Historie vorhanden (Altdaten vor v0.2.2), greift der Schätzwert.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Monatlichen Normwert berechnen (gleiche Logik wie in get_overview)
    monthly = sub.amount * _MONTHLY_FACTOR[sub.interval]

    # Preishistorie laden — ab v0.2.2 immer vorhanden (initialer Eintrag in create_subscription)
    history_stmt = (
        select(SubscriptionPriceHistory)
        .where(SubscriptionPriceHistory.subscription_id == subscription_id)
        .order_by(SubscriptionPriceHistory.valid_from)
    )
    history = list(session.execute(history_stmt).scalars().all())

    # Exakte Berechnung wenn Historie vorhanden, sonst Schätzung als Fallback
    if history:
        total = _compute_total_paid_exact(history, sub.interval)
    else:
        total = _compute_total_paid_estimate(sub.amount, sub.interval, sub.started_on)

    return SubscriptionDetailResult(
        sub=sub,
        monthly_cost_normalized=monthly.quantize(Decimal("0.01")),
        yearly_cost_normalized=(monthly * Decimal("12")).quantize(Decimal("0.01")),
        total_paid_estimate=total,
    )


def get_price_history(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionPriceHistory]:
    """
    Gibt die Preishistorie eines Abos zurück, absteigend nach Datum (neueste zuerst).

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    stmt = (
        select(SubscriptionPriceHistory)
        .where(SubscriptionPriceHistory.subscription_id == subscription_id)
        # Neuester Eintrag zuerst — so erscheint der aktuelle Preis oben in der UI
        .order_by(SubscriptionPriceHistory.valid_from.desc())
    )
    return list(session.execute(stmt).scalars().all())


def get_scheduled_payments(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SubscriptionScheduledPayment]:
    """
    Gibt alle Soll-Buchungen eines Abos zurück, absteigend nach Fälligkeitsdatum.

    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    stmt = (
        select(SubscriptionScheduledPayment)
        .where(SubscriptionScheduledPayment.subscription_id == subscription_id)
        # Neueste Buchung zuerst — so sieht der User die aktuellsten Einträge oben
        .order_by(SubscriptionScheduledPayment.due_date.desc())
    )
    return list(session.execute(stmt).scalars().all())


def create_subscription(
    session: Session,
    user_id: uuid.UUID,
    payload: SubscriptionCreate,
) -> Subscription:
    """
    Legt ein neues Abo für den eingeloggten User an.

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
        next_due_date=payload.next_due_date,
        interval=payload.interval,
        started_on=started_on,
        notes=payload.notes,
        # status, logo_url, suspended_at, access_until — SQLAlchemy-Defaults greifen
    )
    session.add(sub)
    session.flush()  # flush statt commit: sub.id ist jetzt verfügbar, Transaktion noch offen

    # Initialen Preis sofort in die Preishistorie schreiben.
    #
    # Warum hier und nicht erst beim ersten update?
    # Ohne diesen Eintrag ist der Startpreis nach der ersten Preisänderung unwiederbringlich verloren:
    #   Anlage:    9,99 € — kein Eintrag in history → nach Änderung auf 12,99 € unbekannt
    #   1. Änderung → {12,99, März}
    #   2. Änderung → {14,99, Mai}
    # History: [{12.99, März}, {14.99, Mai}] — Jan–Feb fehlen komplett
    #
    # Mit diesem Fix:
    # History: [{9.99, started_on}, {12.99, März}, {14.99, Mai}] → lückenlose Zeitleiste
    # valid_from = started_on (nicht heute) damit rückwirkende Abos korrekt erfasst werden.
    _record_price_change(session, sub, sub.amount, valid_from=started_on)

    session.commit()
    session.refresh(sub)
    return sub


def _record_price_change(
    session: Session,
    sub: Subscription,
    new_amount: Decimal,
    valid_from: date | None = None,
) -> None:
    """
    Schreibt einen Preishistorie-Eintrag.

    Wird von zwei Stellen gerufen:
    - create_subscription: initialer Eintrag mit valid_from = started_on
    - update_subscription: Änderungseintrag mit valid_from = heute (Standard)

    Warum valid_from als Parameter?
    Beim Anlegen eines Abos soll der Startpreis ab dem Abschlussdatum (started_on) gelten,
    nicht ab dem heutigen Tag — sonst klafft eine Lücke in der Zeitleiste für rückwirkende Abos.

    Semantik der Tabelle (valid_from-only-Design):
    Jeder Eintrag bedeutet „ab diesem Datum gilt Preis X".
    Aufeinanderfolgende Einträge bilden eine lückenlose Zeitleiste:
      {9.99, 2026-01-01} → {12.99, 2026-03-01} → {14.99, 2026-05-01}
    Slice E kann daraus den kumulierten Betrag korrekt berechnen.

    Kein API-Endpoint in v0.2.2 — die Daten laufen still mit.
    """
    entry = SubscriptionPriceHistory(
        subscription_id=sub.id,
        amount=new_amount,
        # Explizites Datum wenn übergeben (Abschluss), sonst heute (Änderung)
        valid_from=valid_from if valid_from is not None else date.today(),
    )
    session.add(entry)


def update_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SubscriptionUpdate,
) -> Subscription:
    """
    Aktualisiert ein bestehendes Abo.

    Nur Felder die im Request-Body standen (payload.model_fields_set) werden geändert.
    Wenn sich amount ändert, wird ein Eintrag in subscription_price_history geschrieben.
    notes kann damit auch explizit auf null gesetzt werden ({ "notes": null }).
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Wenn amount sich ändert: neuen Preis ab heute in der Preishistorie festhalten.
    # Semantik: jeder Eintrag sagt "ab valid_from gilt Preis X" — so entsteht eine Zeitleiste.
    # Wir prüfen: payload.amount ist gesetzt UND unterscheidet sich vom aktuellen Wert.
    if payload.amount is not None and payload.amount != sub.amount:
        _record_price_change(session, sub, payload.amount)

    # Nur die Felder aktualisieren, die der User tatsächlich mitgeschickt hat.
    #
    # Warum model_fields_set statt "if payload.x is not None"?
    # Bei Optional-Feldern bedeutet None zweierlei:
    #   - "nicht mitgeschickt" (Feld fehlt im JSON)  → soll nichts ändern
    #   - "explizit null"       ({ "notes": null })   → soll Feld leeren
    # model_fields_set enthält nur die Felder, die im Request-Body standen.
    # Damit kann man "nicht gesendet" und "auf null setzen" sauber unterscheiden.
    for field in payload.model_fields_set:
        setattr(sub, field, getattr(payload, field))

    session.commit()
    session.refresh(sub)
    return sub


def suspend_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SuspendPayload,
) -> Subscription:
    """
    Setzt ein Abo auf 'suspended'.

    Soft-Lifecycle: das Abo bleibt in der DB — keine Daten gehen verloren.
    Nur aktive Abos können suspendiert werden (409 wenn bereits suspended/canceled).

    suspended_at: wird auf heute gesetzt
    access_until: optional — bis wann ist die Leistung noch nutzbar?
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur aktive Abos können suspendiert werden
    if sub.status != SubscriptionStatus.active:
        raise InvalidSubscriptionStatusError(
            f"Nur aktive Abos können suspendiert werden. Aktueller Status: {sub.status.value}"
        )

    # Status-Wechsel durchführen
    sub.status = SubscriptionStatus.suspended
    sub.suspended_at = date.today()
    sub.access_until = payload.access_until  # kann None sein — ist OK

    session.commit()
    session.refresh(sub)
    return sub


def resume_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Subscription:
    """
    Setzt ein suspendiertes Abo wieder auf 'active'.

    Nur suspended darf zurück auf active — active oder canceled ergeben keinen Sinn.
    suspended_at und access_until werden beim Resume geleert.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Nur suspendierte Abos können fortgesetzt werden
    if sub.status != SubscriptionStatus.suspended:
        raise InvalidSubscriptionStatusError(
            f"Nur pausierte Abos können fortgesetzt werden. Aktueller Status: {sub.status.value}"
        )

    sub.status = SubscriptionStatus.active
    # Suspend-Felder zurücksetzen — das Abo läuft wieder normal
    sub.suspended_at = None
    sub.access_until = None

    session.commit()
    session.refresh(sub)
    return sub


# Erlaubte Bild-Typen für Logo-Uploads (ADR 0010)
_ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
# Dateiendung pro Content-Type — UUID-Dateiname verhindert Kollisionen und Path-Traversal
_LOGO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def upload_subscription_logo(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    content_type: str,
    file_content: bytes,
    upload_dir: str,
) -> Subscription:
    """
    Speichert ein Logo für ein Abo auf dem Dateisystem (ADR 0010: lokales Dateisystem).

    Validiert Dateityp (JPEG/PNG/WebP) und Größe (max. 2 MB).
    Löscht das alte Logo wenn vorhanden, schreibt das neue.
    Speichert den relativen Pfad ("logos/<uuid>.ext") in der DB — nicht die absolute URL.
    Der relative Pfad ist der entscheidende Entwurfsaspekt aus ADR 0010:
    bei späterer Migration zu Object Storage ändert sich nur dieser Service-Code.
    """
    # Dateityp prüfen — nur bekannte Bild-Formate akzeptieren
    if content_type not in _ALLOWED_LOGO_TYPES:
        raise InvalidFileError("Ungültiger Dateityp. Erlaubt: JPEG, PNG, WebP.")

    # Dateigröße prüfen — zu große Bilder würden die Festplatte belasten
    if len(file_content) > _MAX_LOGO_SIZE_BYTES:
        raise InvalidFileError("Datei zu groß. Maximum: 2 MB.")

    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    # Altes Logo löschen wenn vorhanden — Festplatte sauber halten
    if sub.logo_url:
        old_file = Path(upload_dir) / sub.logo_url
        # missing_ok=True: kein Fehler wenn die Datei schon fehlt (z. B. manuell gelöscht)
        old_file.unlink(missing_ok=True)

    # Neuen Dateinamen mit UUID generieren — verhindert Kollisionen und Path-Traversal-Angriffe.
    # Niemals den vom Client gelieferten Dateinamen verwenden!
    ext = _LOGO_EXT[content_type]
    relative_path = f"logos/{uuid.uuid4()}{ext}"
    dest = Path(upload_dir) / relative_path
    # Verzeichnis anlegen falls es noch nicht existiert (z. B. erster Upload überhaupt)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_content)

    # Nur den relativen Pfad in der DB speichern (ADR 0010: kein absoluter Pfad, keine URL)
    sub.logo_url = relative_path
    session.commit()
    session.refresh(sub)
    return sub


def delete_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """
    Löscht ein Abo unwiderruflich (Hard Delete).

    In v0.2.2 bleibt DELETE erhalten, aber die bevorzugte Aktion ist Suspend.
    Hard Delete ist nur für Abos gedacht, bei denen wirklich keine Historie benötigt wird.
    Wirft SubscriptionNotFoundError wenn das Abo nicht existiert.
    Wirft ForbiddenError wenn das Abo einem anderen User gehört.
    """
    sub = _get_subscription_or_raise(session, subscription_id)
    _check_ownership(sub, user_id)

    session.delete(sub)
    session.commit()
