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
    OverviewRead,
    PriceHistoryEntry,
    ScheduledPaymentRead,
    SubscriptionCreate,
    SubscriptionDetail,
    SubscriptionRead,
    SubscriptionUpdate,
    SuspendPayload,
)
from app.services.subscriptions import (
    create_subscription,
    delete_subscription,
    get_overview,
    get_price_history,
    get_scheduled_payments,
    get_subscription_detail,
    list_subscriptions,
    resume_subscription,
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
    return [SubscriptionRead.model_validate(s) for s in subs]


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: SubscriptionCreate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Legt ein neues Abo für den eingeloggten User an.

    Erwartet als JSON:
    { "name": "Netflix", "amount": 9.99, "next_due_date": "2026-06-01" }
    Gibt HTTP 201 Created zurück (= "erfolgreich angelegt").
    """
    sub = create_subscription(session, user.id, payload)
    return SubscriptionRead.model_validate(sub)


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
        upcoming=[SubscriptionRead.model_validate(s) for s in result.upcoming],
    )


@router.get("/{subscription_id}", response_model=SubscriptionDetail)
def detail(
    subscription_id: uuid.UUID,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionDetail:
    """
    Gibt ein einzelnes Abo mit Kostenkennzahlen zurück (Detailseite, Slice C).

    Enthält zusätzlich zu SubscriptionRead:
      - monthly_cost_normalized  (auf Monatsbasis normierter Betrag)
      - yearly_cost_normalized   (× 12)
      - total_paid_estimate      (Schätzung bisheriger Gesamtkosten)

    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    result = get_subscription_detail(session, subscription_id, user.id)
    # SubscriptionRead liest die SQLAlchemy-Felder aus — dann computed fields ergänzen
    sub_data = SubscriptionRead.model_validate(result.sub)
    return SubscriptionDetail(
        **sub_data.model_dump(),
        monthly_cost_normalized=result.monthly_cost_normalized,
        yearly_cost_normalized=result.yearly_cost_normalized,
        total_paid_estimate=result.total_paid_estimate,
    )


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
    return SubscriptionRead.model_validate(sub)


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
    return SubscriptionRead.model_validate(sub)


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
    return SubscriptionRead.model_validate(sub)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    user: EditorOrAdminUser,
    session: DatabaseSession,
) -> SubscriptionRead:
    """
    Bearbeitet ein bestehendes Abo.

    Es müssen nur die Felder mitgeschickt werden, die sich ändern sollen.
    Wenn amount sich ändert, wird automatisch ein Eintrag in price_history geschrieben.
    Fehler:
      - 404 wenn das Abo nicht gefunden wird
      - 403 wenn das Abo einem anderen User gehört
    """
    sub = update_subscription(session, subscription_id, user.id, payload)
    return SubscriptionRead.model_validate(sub)


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
