"""
app/routers/subscriptions.py — HTTP-Endpunkte für Abo-Verwaltung.

Alle Routen hier sind durch "EditorOrAdminUser" geschützt:
FastAPI prüft bei jedem Request automatisch ob der Aufrufer
eingeloggt ist UND die Rolle 'editor' oder 'admin' hat.

Warum nicht "CurrentUser"?
User mit der Rolle 'default' sind im Wartezustand — sie haben noch keine
Rolle zugewiesen bekommen und dürfen keine Daten sehen. Erst nach der
Rollenzuweisung durch einen Admin bekommt der User Zugriff.

Ein User kann immer nur seine eigenen Abos sehen und bearbeiten.
"""

import uuid

from fastapi import APIRouter, UploadFile, status

from app.config import get_settings
from app.dependencies import DatabaseSession, EditorOrAdminUser
from app.schemas.subscription import (
    BillingHistoryEntry,
    IntervalChangeRequest,
    OverviewRead,
    PriceChangeRequest,
    PriceHistoryEntry,
    ScheduledPaymentRead,
    SubscriptionCreate,
    SubscriptionDetail,
    SubscriptionRead,
    SubscriptionUpdate,
    SuspendPayload,
)
from app.services.subscriptions import (
    cancel_subscription,
    create_subscription,
    delete_billing_history_entry,
    delete_price_history_entry,
    delete_subscription,
    get_billing_history,
    get_overview,
    get_price_history,
    get_scheduled_payments,
    get_subscription_detail,
    interval_change,
    list_subscriptions,
    price_change,
    resume_subscription,
    subscription_to_read,
    suspend_subscription,
    update_subscription,
    upload_subscription_logo,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionRead])
def get_subscriptions(user: EditorOrAdminUser, session: DatabaseSession) -> list[SubscriptionRead]:
    """
    Gibt alle Abos des eingeloggten Users zurück.

    Sortiert nach Fälligkeitsdatum (nächste Fälligkeit zuerst).
    Enthält alle Status (active, suspended, canceled).
    """
    subs = list_subscriptions(session, user.id)
    return [subscription_to_read(s) for s in subs]


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: SubscriptionCreate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Legt ein neues Abo für den eingeloggten User an.

    Erwartet als JSON:
    { "name": "Netflix", "amount": 9.99, "interval": "monthly", "started_on": "2026-06-01" }
    Gibt HTTP 201 Created zurück (= "erfolgreich angelegt").
    next_due_date wird serverseitig berechnet — nicht mehr im Body mitschicken.
    """
    sub = create_subscription(session, user.id, payload)
    return subscription_to_read(sub)


@router.get("/overview", response_model=OverviewRead)
def overview(user: EditorOrAdminUser, session: DatabaseSession) -> OverviewRead:
    """
    Gibt eine Übersicht der Abos zurück.

    monthly_total: Summe aller aktiven Abo-Beträge (normiert auf Monat).
    upcoming:      Aktive Abos, die in den nächsten 30 Tagen fällig sind.

    Warum steht diese Route VOR /{subscription_id}?
    FastAPI prüft Routen in der Reihenfolge wie sie definiert sind.
    Käme /overview nach /{subscription_id}, würde FastAPI versuchen
    "overview" als UUID zu lesen — das schlägt mit HTTP 422 fehl.
    """
    result = get_overview(session, user.id)
    return OverviewRead(
        monthly_total=result.monthly_total,
        upcoming=[subscription_to_read(s) for s in result.upcoming],
    )


@router.get("/{subscription_id}", response_model=SubscriptionDetail)
def detail(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionDetail:
    """
    Gibt ein einzelnes Abo mit berechneten Kostenkennzahlen zurück (Detailseite, v0.2.3).

    Enthält zusätzlich zu SubscriptionRead:
      - monatlich          (auf Monatsbasis normierter Betrag)
      - tatsaechlich       (Summe aller tatsächlich gezahlten Perioden)
      - intervalle         (Anzahl Zahlungsperioden seit Abschluss)
      - dieses_kalenderjahr (Jahreskosten inkl. Preisankündigungen)

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    # get_subscription_detail gibt bereits ein fertiges SubscriptionDetail zurück
    return get_subscription_detail(session, subscription_id, user.id)


@router.get("/{subscription_id}/price-history", response_model=list[PriceHistoryEntry])
def price_history(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[PriceHistoryEntry]:
    """
    Gibt die Preishistorie eines Abos zurück (Slice E).

    Jeder Eintrag bedeutet "ab valid_from gilt Betrag X".
    Einträge sind absteigend nach Datum sortiert (neuester Preis zuerst).
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    entries = get_price_history(session, subscription_id, user.id)
    return [PriceHistoryEntry.model_validate(e) for e in entries]


@router.delete(
    "/{subscription_id}/price-history/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_price_history_entry_endpoint(
    subscription_id: uuid.UUID,
    entry_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """
    Löscht einen einzelnen Preishistorie-Eintrag (v0.2.4).

    Erlaubt wenn:
    - Mindestens ein weiterer Eintrag für dieses Abo existiert.
    - Keine Buchungen im Zeitraum existieren, in dem dieser Preis galt.

    Fehler:
      - 404 wenn das Abo oder der Eintrag nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn der Eintrag der letzte ist oder Buchungen betroffen sind
    """
    delete_price_history_entry(session, subscription_id, user.id, entry_id)


@router.get("/{subscription_id}/scheduled-payments", response_model=list[ScheduledPaymentRead])
def scheduled_payments(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[ScheduledPaymentRead]:
    """
    Gibt alle Soll-Buchungen eines Abos zurück (Slice G).

    Einträge sind absteigend nach Fälligkeitsdatum sortiert (neueste zuerst).
    Leere Liste wenn noch keine Buchungen generiert wurden oder Buchungshistorie deaktiviert ist.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    entries = get_scheduled_payments(session, subscription_id, user.id)
    return [ScheduledPaymentRead.model_validate(e) for e in entries]


@router.post("/{subscription_id}/suspend", response_model=SubscriptionRead)
def suspend(
    subscription_id: uuid.UUID,
    payload: SuspendPayload,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Setzt ein Abo auf 'suspended' (Soft-Lifecycle).

    Das Abo bleibt in der DB erhalten — keine Daten gehen verloren.
    Optional: access_until angeben, bis wann die Leistung noch nutzbar ist.

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn das Abo bereits suspended oder canceled ist
    """
    sub = suspend_subscription(session, subscription_id, user.id, payload)
    return subscription_to_read(sub)


@router.post("/{subscription_id}/resume", response_model=SubscriptionRead)
def resume(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Setzt ein pausiertes Abo wieder auf 'active'.

    suspended_at und access_until werden geleert.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn das Abo nicht den Status 'suspended' hat
    """
    sub = resume_subscription(session, subscription_id, user.id)
    return subscription_to_read(sub)


@router.post("/{subscription_id}/logo", response_model=SubscriptionRead)
async def upload_logo(
    subscription_id: uuid.UUID,
    logo: UploadFile,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Lädt ein Logo für ein Abo hoch und speichert es auf dem Dateisystem (ADR 0010).

    Erlaubte Dateitypen: JPEG, PNG, WebP. Maximum: 2 MB.
    Das alte Logo wird automatisch gelöscht wenn vorhanden.
    logo_url im Response enthält den relativen Pfad ("logos/<uuid>.ext") —
    das Frontend baut daraus die vollständige URL (/api/uploads/...).

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 422 bei ungültigem Dateityp oder Datei zu groß
    """
    settings = get_settings()
    # Dateiinhalt vollständig lesen — Validierung + Speicherung im Service
    file_content = await logo.read()
    sub = upload_subscription_logo(
        session,
        subscription_id,
        user.id,
        # content_type kann None sein wenn der Client keinen Header schickt
        logo.content_type or "",
        file_content,
        settings.upload_dir,
    )
    return subscription_to_read(sub)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Bearbeitet Name, Intervall oder Notizen eines Abos.

    Es müssen nur die Felder mitgeschickt werden, die sich ändern sollen.
    Hinweis: amount ist hier nicht mehr änderbar (v0.2.3).
    Preisänderungen laufen über POST /subscriptions/{id}/price-change.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    sub = update_subscription(session, subscription_id, user.id, payload)
    return subscription_to_read(sub)


@router.post("/{subscription_id}/price-change", response_model=SubscriptionDetail)
def price_change_endpoint(
    subscription_id: uuid.UUID,
    payload: PriceChangeRequest,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionDetail:
    """
    Trägt eine Preisänderung ein (v0.2.3).

    valid_from kann in der Vergangenheit, heute oder Zukunft liegen:
    - Vergangenheit: korrigiert historische Berechnung von "Tatsächlich"
    - Heute:         sofortige Preisänderung
    - Zukunft:       Ankündigung — Badge in der Detailansicht, fließt in "Dieses Jahr" ein

    Erwartet als JSON:
    { "amount": 12.99, "valid_from": "2026-10-01" }

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    return price_change(session, user.id, subscription_id, payload)


@router.get("/{subscription_id}/billing-history", response_model=list[BillingHistoryEntry])
def billing_history(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> list[BillingHistoryEntry]:
    """
    Gibt die Billing-Historie eines Abos zurück (v0.2.4).

    Jeder Eintrag beschreibt ab wann (valid_from) welcher Betrag, welches Intervall
    und welcher Fälligkeitsanker (anchor_on) gilt.
    Einträge sind absteigend nach Datum sortiert (neuester Eintrag zuerst).

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    entries = get_billing_history(session, subscription_id, user.id)
    return [BillingHistoryEntry.model_validate(e) for e in entries]


@router.delete(
    "/{subscription_id}/billing-history/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_billing_history_entry_endpoint(
    subscription_id: uuid.UUID,
    entry_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """
    Löscht einen einzelnen Billing-History-Eintrag (v0.2.4).

    Erlaubt wenn:
    - Mindestens ein weiterer Eintrag für dieses Abo existiert.
    - Keine Buchungen im Zeitraum existieren, in dem dieser Eintrag galt.

    Fehler:
      - 404 wenn das Abo oder der Eintrag nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn der Eintrag der letzte ist oder Buchungen betroffen sind
    """
    delete_billing_history_entry(session, subscription_id, user.id, entry_id)


@router.post("/{subscription_id}/interval-change", response_model=SubscriptionDetail)
def interval_change_endpoint(
    subscription_id: uuid.UUID,
    payload: IntervalChangeRequest,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionDetail:
    """
    Ändert Abrechnungsintervall und Betrag gemeinsam (v0.2.4).

    valid_from ist die erste Fälligkeit im neuen Intervall — auch der neue Anker.
    Bei rückwirkenden Änderungen mit vorhandenen Buchungen: 409 ohne explizite Bestätigung.

    Erwartet als JSON:
    { "amount": 79.99, "interval": "yearly", "valid_from": "2026-06-01" }
    Mit Bestätigung:
    { ..., "acknowledge_existing_payments": true }

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn für dieses Datum bereits ein Eintrag existiert
      - 409 wenn ab valid_from Buchungen existieren (ohne acknowledge_existing_payments=true)
    """
    return interval_change(session, user.id, subscription_id, payload)


@router.post("/{subscription_id}/cancel", response_model=SubscriptionDetail)
def cancel_endpoint(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
    payload: SuspendPayload | None = None,
) -> SubscriptionDetail:
    """
    Kündigt ein Abo endgültig (v0.2.3).

    Setzt Status auf 'canceled' und schreibt einen Pause-Eintrag in die Historie.
    Das Abo bleibt in der DB erhalten — keine Daten gehen verloren.
    Canceled Abos erhalten keine Soll-Buchungen mehr vom Scheduler.

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
      - 409 wenn das Abo bereits canceled ist
    """
    return cancel_subscription(session, subscription_id, user.id, payload)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> None:
    """
    Löscht ein Abo unwiderruflich (Hard Delete).

    Bevorzugte Aktion in v0.2.2: POST /subscriptions/{id}/suspend statt Delete.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    delete_subscription(session, subscription_id, user.id)
