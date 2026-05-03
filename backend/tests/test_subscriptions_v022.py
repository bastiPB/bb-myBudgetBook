"""
tests/test_subscriptions_v022.py — Tests für v0.2.2 Slice A

Was getestet wird:
1. Schema-Validierung (started_on darf nicht in der Zukunft liegen)
2. Service-Logik mit Mock-Session (Ownership, Statuswechsel, price_history)

Warum Mock-Session?
Für echte DB-Tests brauchen wir einen laufenden PostgreSQL-Container.
Die Mock-Tests hier prüfen die Business-Logik unabhängig von der DB.
Das ist schnell und läuft auch ohne Docker.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from app.exceptions import ForbiddenError, InvalidSubscriptionStatusError, SubscriptionNotFoundError
from app.models.subscription import Subscription, SubscriptionPriceHistory, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SuspendPayload
from app.services.subscriptions import (
    create_subscription,
    suspend_subscription,
    update_subscription,
)


# ─── Hilfsfunktionen für Tests ───────────────────────────────────────────────

def make_active_subscription(user_id: uuid.UUID | None = None) -> Subscription:
    """Erstellt ein Subscription-Objekt mit Status 'active' für Tests."""
    sub = Subscription.__new__(Subscription)  # ohne __init__ — vermeidet DB-Aufruf
    sub.id = uuid.uuid4()
    sub.user_id = user_id or uuid.uuid4()
    sub.name = "Test-Abo"
    sub.amount = Decimal("9.99")
    sub.next_due_date = date.today() + timedelta(days=30)
    sub.interval = "monthly"
    sub.status = SubscriptionStatus.active
    sub.started_on = date.today()
    sub.notes = None
    sub.logo_url = None
    sub.suspended_at = None
    sub.access_until = None
    return sub


def make_mock_session(sub: Subscription | None = None) -> MagicMock:
    """
    Erstellt eine Mock-Session die bei session.get(...) ein Abo zurückgibt.

    MagicMock = Python-Objekt das jede Methode vortäuscht und deren Aufruf aufzeichnet.
    So können wir prüfen ob session.commit(), session.add() etc. aufgerufen wurden.
    """
    session = MagicMock()
    # session.get(Subscription, irgendeine_id) → gibt unser Test-Abo zurück
    session.get.return_value = sub
    return session


# ─── Schema-Validierung ──────────────────────────────────────────────────────

class TestSubscriptionCreateSchema:
    """Prüft ob Pydantic die started_on-Validierung korrekt ausführt."""

    def test_started_on_heute_ist_erlaubt(self) -> None:
        """Das heutige Datum als started_on ist gültig."""
        payload = SubscriptionCreate(
            name="Test",
            amount=Decimal("9.99"),
            next_due_date=date.today() + timedelta(days=30),
            started_on=date.today(),
        )
        assert payload.started_on == date.today()

    def test_started_on_vergangenheit_ist_erlaubt(self) -> None:
        """Ein Datum in der Vergangenheit als started_on ist gültig."""
        past = date.today() - timedelta(days=365)
        payload = SubscriptionCreate(
            name="Test",
            amount=Decimal("9.99"),
            next_due_date=date.today() + timedelta(days=30),
            started_on=past,
        )
        assert payload.started_on == past

    def test_started_on_zukunft_wirft_fehler(self) -> None:
        """Ein Datum in der Zukunft als started_on soll einen Fehler werfen."""
        future = date.today() + timedelta(days=1)
        with pytest.raises(Exception) as exc_info:
            SubscriptionCreate(
                name="Test",
                amount=Decimal("9.99"),
                next_due_date=date.today() + timedelta(days=30),
                started_on=future,
            )
        # Pydantic wirft ValidationError — wir prüfen nur dass es einen Fehler gab
        assert "Abschlussdatum" in str(exc_info.value)

    def test_started_on_zukunft_als_string_wirft_fehler(self) -> None:
        """
        started_on als ISO-String in der Zukunft muss ebenfalls abgelehnt werden.

        Warum dieser Test?
        JSON liefert Datumsfelder immer als String ("2099-01-01"), nicht als date-Objekt.
        Der Validator läuft mit mode='before', also bevor Pydantic coerced.
        Würde er nur isinstance(v, date) prüfen, käme ein String ungeprüft durch —
        Pydantic würde ihn still zu date coercen und ein Zukunftsdatum akzeptieren.
        """
        with pytest.raises(Exception) as exc_info:
            SubscriptionCreate(
                name="Test",
                amount=Decimal("9.99"),
                next_due_date=date.today() + timedelta(days=30),
                started_on="2099-01-01",  # ISO-String wie er aus JSON käme
            )
        assert "Abschlussdatum" in str(exc_info.value)

    def test_started_on_optional_kein_pflichtfeld(self) -> None:
        """Ohne started_on soll das Schema trotzdem gültig sein."""
        payload = SubscriptionCreate(
            name="Test",
            amount=Decimal("9.99"),
            next_due_date=date.today() + timedelta(days=30),
        )
        # Kein started_on → None — der Service setzt dann today()
        assert payload.started_on is None


# ─── Service: create_subscription ────────────────────────────────────────────

class TestCreateSubscription:
    """Prüft ob create_subscription started_on korrekt behandelt."""

    def test_started_on_wird_auf_heute_gesetzt_wenn_nicht_angegeben(self) -> None:
        """
        Wenn started_on nicht übergeben wird, soll der Service heute eintragen.
        """
        user_id = uuid.uuid4()
        session = MagicMock()

        # session.refresh(sub) soll das Objekt zurückgeben das session.add() bekommen hat
        created_sub: list[Subscription] = []
        def fake_refresh(obj: object) -> None:
            if isinstance(obj, Subscription):
                created_sub.append(obj)
        session.refresh.side_effect = fake_refresh

        payload = SubscriptionCreate(
            name="Netflix",
            amount=Decimal("9.99"),
            next_due_date=date.today() + timedelta(days=30),
        )

        create_subscription(session, user_id, payload)

        # Das Abo wurde zur Session hinzugefügt
        assert session.add.called
        # Das erste add()-Argument ist das Subscription-Objekt
        added_sub = session.add.call_args[0][0]
        assert isinstance(added_sub, Subscription)
        assert added_sub.started_on == date.today()

    def test_started_on_aus_payload_wird_gesetzt(self) -> None:
        """Wenn started_on übergeben wird, soll dieser Wert gesetzt werden."""
        user_id = uuid.uuid4()
        session = MagicMock()
        past = date.today() - timedelta(days=100)

        payload = SubscriptionCreate(
            name="Spotify",
            amount=Decimal("4.99"),
            next_due_date=date.today() + timedelta(days=15),
            started_on=past,
        )

        create_subscription(session, user_id, payload)

        added_sub = session.add.call_args[0][0]
        assert added_sub.started_on == past


# ─── Service: suspend_subscription ───────────────────────────────────────────

class TestSuspendSubscription:
    """Prüft den Suspend-Flow."""

    def test_suspend_aktives_abo_setzt_status_auf_suspended(self) -> None:
        """Ein aktives Abo kann suspendiert werden."""
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        session = make_mock_session(sub)

        result = suspend_subscription(session, sub.id, user_id, SuspendPayload())

        assert result.status == SubscriptionStatus.suspended
        assert result.suspended_at == date.today()
        assert session.commit.called

    def test_suspend_setzt_access_until_wenn_angegeben(self) -> None:
        """access_until wird korrekt übernommen."""
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        session = make_mock_session(sub)
        access_date = date.today() + timedelta(days=14)

        result = suspend_subscription(session, sub.id, user_id, SuspendPayload(access_until=access_date))

        assert result.access_until == access_date

    def test_suspend_bereits_suspendiertes_abo_wirft_fehler(self) -> None:
        """Ein bereits suspendiertes Abo kann nicht nochmals suspendiert werden."""
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        sub.status = SubscriptionStatus.suspended  # bereits suspendiert
        session = make_mock_session(sub)

        with pytest.raises(InvalidSubscriptionStatusError):
            suspend_subscription(session, sub.id, user_id, SuspendPayload())

    def test_suspend_nicht_gefundenes_abo_wirft_404(self) -> None:
        """Wenn das Abo nicht existiert, kommt 404."""
        session = make_mock_session(sub=None)  # session.get gibt None zurück

        with pytest.raises(SubscriptionNotFoundError):
            suspend_subscription(session, uuid.uuid4(), uuid.uuid4(), SuspendPayload())

    def test_suspend_fremdes_abo_wirft_forbidden(self) -> None:
        """Ein User darf kein fremdes Abo suspendieren."""
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        sub = make_active_subscription(owner_id)
        session = make_mock_session(sub)

        with pytest.raises(ForbiddenError):
            # other_user_id versucht das Abo von owner_id zu suspendieren
            suspend_subscription(session, sub.id, other_user_id, SuspendPayload())


# ─── Service: update_subscription (price_history) ────────────────────────────

class TestUpdateSubscriptionPriceHistory:
    """Prüft ob bei amount-Änderung ein price_history-Eintrag geschrieben wird."""

    def test_amount_aenderung_schreibt_price_history_eintrag(self) -> None:
        """
        Wenn amount sich ändert, soll ein SubscriptionPriceHistory-Objekt
        zur Session hinzugefügt werden.
        """
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        sub.amount = Decimal("9.99")
        session = make_mock_session(sub)

        payload = SubscriptionUpdate(amount=Decimal("12.99"))
        update_subscription(session, sub.id, user_id, payload)

        # session.add() wurde aufgerufen — prüfe ob ein price_history-Eintrag dabei war
        added_objects = [c[0][0] for c in session.add.call_args_list]
        price_history_entries = [o for o in added_objects if isinstance(o, SubscriptionPriceHistory)]
        assert len(price_history_entries) == 1, "Genau ein price_history-Eintrag erwartet"
        assert price_history_entries[0].amount == Decimal("12.99")
        assert price_history_entries[0].valid_from == date.today()

    def test_gleicher_amount_schreibt_keinen_price_history_eintrag(self) -> None:
        """Wenn sich amount NICHT ändert, soll kein price_history-Eintrag kommen."""
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        sub.amount = Decimal("9.99")
        session = make_mock_session(sub)

        # Gleicher Betrag — keine Änderung
        payload = SubscriptionUpdate(amount=Decimal("9.99"))
        update_subscription(session, sub.id, user_id, payload)

        added_objects = [c[0][0] for c in session.add.call_args_list]
        price_history_entries = [o for o in added_objects if isinstance(o, SubscriptionPriceHistory)]
        assert len(price_history_entries) == 0, "Kein price_history-Eintrag bei gleichem Betrag erwartet"

    def test_name_aenderung_schreibt_keinen_price_history_eintrag(self) -> None:
        """Nur amount-Änderungen lösen price_history aus — nicht name etc."""
        user_id = uuid.uuid4()
        sub = make_active_subscription(user_id)
        session = make_mock_session(sub)

        payload = SubscriptionUpdate(name="Neuer Name")
        update_subscription(session, sub.id, user_id, payload)

        added_objects = [c[0][0] for c in session.add.call_args_list]
        price_history_entries = [o for o in added_objects if isinstance(o, SubscriptionPriceHistory)]
        assert len(price_history_entries) == 0

    def test_update_fremdes_abo_wirft_forbidden(self) -> None:
        """Ein User darf kein fremdes Abo bearbeiten."""
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        sub = make_active_subscription(owner_id)
        session = make_mock_session(sub)

        with pytest.raises(ForbiddenError):
            update_subscription(session, sub.id, other_user_id, SubscriptionUpdate(name="Hack"))
