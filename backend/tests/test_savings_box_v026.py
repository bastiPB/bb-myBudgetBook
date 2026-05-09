"""
tests/test_savings_box_v026.py — Sparfach (v0.2.6)

- Term-Mathe und Kennzahlen: reine Python-Tests ohne Datenbank.
- Buchungsregeln und Term-Refresh: SQLite-In-Memory nur für die Tabellen
  ``users`` + ``savings_*`` (kein ``Base.metadata.create_all``, weil JSONB-Tabellen
  SQLite nicht unterstützen).
- Router-Smoke: eigene FastAPI-App mit nur ``savings``-Router und Exception-Handlern —
  ohne Lifespan (kein Scheduler, kein PostgreSQL beim App-Start).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db_session
from app.dependencies import _get_current_user
from app.exceptions import (
    SavingsBookingValidationError,
    SavingsBoxClosedError,
    SavingsPenaltyDeleteBlockedError,
    register_exception_handlers,
)
from app.models.savings_box import (
    SavingsBooking,
    SavingsBookingType,
    SavingsBox,
    SavingsBoxStatus,
    SavingsInterval,
    SavingsTerm,
    SavingsTermStatus,
)
from app.models.user import User, UserRole, UserStatus
from app.routers import savings as savings_router
from app.schemas.savings_box import (
    SavingsBookingCreate,
    SavingsBoxCloseRequest,
    SavingsBoxCreate,
)
from app.services.savings.access import assert_box_is_open
from app.services.savings.mutations import (
    create_booking,
    create_box,
    delete_booking,
)
from app.services.savings.terms import compute_box_summary, generate_terms, update_term_statuses


def _patch_savings_service_date(monkeypatch: pytest.MonkeyPatch, frozen: date) -> None:
    """
    Ersetzt ``date`` in ``terms`` und ``mutations``.

    Sonst markiert ``update_term_statuses`` korrekt nach dem gefrorenen Tag — aber
    ``delete_booking`` / ``_sync_term_status_from_deposits`` nutzen noch echtes
    ``date.today()`` und liefern bei „Host liegt vor due_date“ fälschlich ``open``.
    """

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return frozen

    monkeypatch.setattr("app.services.savings.terms.date", FrozenDate)
    monkeypatch.setattr("app.services.savings.mutations.date", FrozenDate)


def _make_savings_sqlite_engine():
    """
    Legt nur die Sparfach-relevanten Tabellen auf SQLite an.

    Ein vollständiges ``create_all`` auf ``Base.metadata`` schlägt fehl, weil andere
    Modelle JSONB (PostgreSQL) verwenden.

    ``StaticPool`` hält eine Connection für alle Threads; ``check_same_thread=False``
    erlaubt Zugriff aus Starlettes TestClient-Threads.
    """
    # Ohne StaticPool: jede neue Connection hätte eine leeres ``:memory:`` — keine Tabellen.
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    SavingsBox.__table__.create(bind=engine)
    SavingsTerm.__table__.create(bind=engine)
    SavingsBooking.__table__.create(bind=engine)
    return engine


@pytest.fixture
def db_session() -> Session:
    """Frische SQLite-Session pro Test."""
    engine = _make_savings_sqlite_engine()
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def editor_user(db_session: Session) -> User:
    """Aktiver Editor-Nutzer — Berechtigung wie in den echten Endpunkten."""
    user = User(
        email=f"editor-{uuid.uuid4().hex[:8]}@test.local",
        password_hash=PasswordHasher().hash("unused-test-secret"),
        role=UserRole.editor,
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def savings_api_client(db_session: Session, editor_user: User):
    """HTTP-Client gegen eine Mini-App nur für ``/savings/boxes``."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(savings_router.router)

    def override_db():
        yield db_session

    def override_user() -> User:
        return editor_user

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[_get_current_user] = override_user

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ─── generate_terms ───────────────────────────────────────────────────────────


class TestGenerateTerms:
    """Raster für Spartermine — ohne Datenbank."""

    def test_generate_terms_biweekly_full_year_2026_count(self) -> None:
        """01.01.–31.12.2026, 14-tägig — ein Term pro Rasterfenster inkl. Start und Ende."""
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="B",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.biweekly,
            min_amount_per_term=Decimal("10.00"),
            status=SavingsBoxStatus.active,
        )
        terms = generate_terms(box)
        assert len(terms) == 27

    def test_generate_terms_monthly_single_month_window(self) -> None:
        """01.01.–31.01.2026, monatlich → genau ein Term."""
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="M",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            status=SavingsBoxStatus.active,
        )
        terms = generate_terms(box)
        assert len(terms) == 1
        assert terms[0].due_date == date(2026, 1, 1)

    def test_generate_terms_weekly_short_ranges(self) -> None:
        """Woche: nur Termine bis end_date zählen."""
        box_a = SavingsBox(
            user_id=uuid.uuid4(),
            name="W1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 7),
            interval=SavingsInterval.weekly,
            min_amount_per_term=Decimal("5.00"),
            status=SavingsBoxStatus.active,
        )
        assert len(generate_terms(box_a)) == 1

        box_b = SavingsBox(
            user_id=uuid.uuid4(),
            name="W2",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 14),
            interval=SavingsInterval.weekly,
            min_amount_per_term=Decimal("5.00"),
            status=SavingsBoxStatus.active,
        )
        assert len(generate_terms(box_b)) == 2

    def test_generate_terms_expected_amount_snapshot(self) -> None:
        """expected_amount jedes Terms entspricht dem aktuellen Mindestbetrag der Box."""
        snap = Decimal("42.50")
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="S",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=snap,
            status=SavingsBoxStatus.active,
        )
        for t in generate_terms(box):
            assert t.expected_amount == snap


# ─── update_term_statuses ─────────────────────────────────────────────────────


class TestUpdateTermStatuses:
    """DB-Session nötig — SQLite wie oben."""

    def test_sets_missed_and_creates_penalty(self, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        """Überfälliger offener Term → missed + eine Penalty-Buchung."""
        user = User(
            email=f"u-{uuid.uuid4().hex[:8]}@t.local",
            password_hash=PasswordHasher().hash("x"),
            role=UserRole.editor,
            status=UserStatus.active,
        )
        db_session.add(user)
        db_session.flush()

        box = SavingsBox(
            user_id=user.id,
            name="Box",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            penalty_amount=Decimal("2.00"),
            status=SavingsBoxStatus.active,
        )
        db_session.add(box)
        db_session.flush()

        term = SavingsTerm(
            savings_box_id=box.id,
            due_date=date(2026, 5, 10),
            expected_amount=Decimal("10.00"),
            status=SavingsTermStatus.open,
        )
        db_session.add(term)
        db_session.commit()

        _patch_savings_service_date(monkeypatch, date(2026, 5, 20))
        update_term_statuses(db_session, box)
        db_session.commit()

        db_session.refresh(term)
        assert term.status == SavingsTermStatus.missed
        penalties = [
            b
            for b in db_session.query(SavingsBooking).filter(SavingsBooking.savings_box_id == box.id)
            if b.booking_type == SavingsBookingType.penalty
        ]
        assert len(penalties) == 1
        assert penalties[0].amount == Decimal("2.00")

    def test_update_term_statuses_idempotent(self, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zweiter Aufruf erzeugt keine zweite Penalty-Zeile."""
        user = User(
            email=f"u2-{uuid.uuid4().hex[:8]}@t.local",
            password_hash=PasswordHasher().hash("x"),
            role=UserRole.editor,
            status=UserStatus.active,
        )
        db_session.add(user)
        db_session.flush()

        box = SavingsBox(
            user_id=user.id,
            name="Box2",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            penalty_amount=Decimal("1.00"),
            status=SavingsBoxStatus.active,
        )
        db_session.add(box)
        db_session.flush()

        term = SavingsTerm(
            savings_box_id=box.id,
            due_date=date(2026, 4, 1),
            expected_amount=Decimal("10.00"),
            status=SavingsTermStatus.open,
        )
        db_session.add(term)
        db_session.commit()

        _patch_savings_service_date(monkeypatch, date(2026, 5, 1))
        update_term_statuses(db_session, box)
        db_session.commit()
        update_term_statuses(db_session, box)
        db_session.commit()

        count = (
            db_session.query(SavingsBooking)
            .filter(
                SavingsBooking.savings_box_id == box.id,
                SavingsBooking.booking_type == SavingsBookingType.penalty,
            )
            .count()
        )
        assert count == 1


# ─── compute_box_summary ────────────────────────────────────────────────────────


class TestComputeBoxSummary:
    """Nur Datenobjekte — keine Session."""

    def test_summary_net_amount(self) -> None:
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="X",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10"),
            status=SavingsBoxStatus.active,
        )
        terms = []
        bookings = [
            SavingsBooking(
                savings_box_id=box.id,
                booking_type=SavingsBookingType.deposit,
                amount=Decimal("50"),
                booking_date=date(2026, 2, 1),
            ),
            SavingsBooking(
                savings_box_id=box.id,
                booking_type=SavingsBookingType.penalty,
                amount=Decimal("5"),
                booking_date=date(2026, 2, 2),
            ),
        ]
        summary = compute_box_summary(box, terms, bookings)
        assert summary.total_deposited == Decimal("50")
        assert summary.total_penalties == Decimal("5")
        assert summary.net_amount == Decimal("45")

    def test_summary_progress_pct_with_target(self) -> None:
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="Y",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10"),
            target_amount=Decimal("100"),
            status=SavingsBoxStatus.active,
        )
        bookings = [
            SavingsBooking(
                savings_box_id=box.id,
                booking_type=SavingsBookingType.deposit,
                amount=Decimal("50"),
                booking_date=date(2026, 3, 1),
            ),
        ]
        summary = compute_box_summary(box, [], bookings)
        assert summary.progress_pct == Decimal("50.00")

    def test_summary_progress_pct_none_without_target(self) -> None:
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="Z",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10"),
            target_amount=None,
            status=SavingsBoxStatus.active,
        )
        bookings = [
            SavingsBooking(
                savings_box_id=box.id,
                booking_type=SavingsBookingType.deposit,
                amount=Decimal("99"),
                booking_date=date(2026, 3, 1),
            ),
        ]
        summary = compute_box_summary(box, [], bookings)
        assert summary.progress_pct is None

    def test_summary_term_counts(self) -> None:
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="C",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10"),
            status=SavingsBoxStatus.active,
        )
        terms = [
            SavingsTerm(
                savings_box_id=box.id,
                due_date=date(2026, 2, 1),
                expected_amount=Decimal("10"),
                status=SavingsTermStatus.open,
            ),
            SavingsTerm(
                savings_box_id=box.id,
                due_date=date(2026, 3, 1),
                expected_amount=Decimal("10"),
                status=SavingsTermStatus.fulfilled,
            ),
            SavingsTerm(
                savings_box_id=box.id,
                due_date=date(2026, 4, 1),
                expected_amount=Decimal("10"),
                status=SavingsTermStatus.missed,
            ),
        ]
        summary = compute_box_summary(box, terms, [])
        assert summary.terms_open == 1
        assert summary.terms_fulfilled == 1
        assert summary.terms_missed == 1


# ─── mutations + access ─────────────────────────────────────────────────────────


class TestMutationsAndAccess:
    """Geschäftsregeln gegen echte SQLite-Session."""

    def test_create_booking_deposit_below_minimum_rejected(self, db_session: Session, editor_user: User) -> None:
        payload_box = SavingsBoxCreate(
            name="Low",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("25.00"),
        )
        box = create_box(db_session, editor_user.id, payload_box)
        term_id = (
            db_session.query(SavingsTerm).filter(SavingsTerm.savings_box_id == box.id).order_by(SavingsTerm.due_date).first().id
        )
        bad = SavingsBookingCreate(
            savings_term_id=term_id,
            booking_type=SavingsBookingType.deposit,
            amount=Decimal("10.00"),
            booking_date=date(2026, 6, 15),
        )
        with pytest.raises(SavingsBookingValidationError):
            create_booking(db_session, box.id, editor_user.id, bad)

    def test_create_booking_deposit_at_minimum_accepted(self, db_session: Session, editor_user: User) -> None:
        payload_box = SavingsBoxCreate(
            name="Ok",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("25.00"),
        )
        box = create_box(db_session, editor_user.id, payload_box)
        term_id = (
            db_session.query(SavingsTerm).filter(SavingsTerm.savings_box_id == box.id).order_by(SavingsTerm.due_date).first().id
        )
        ok = SavingsBookingCreate(
            savings_term_id=term_id,
            booking_type=SavingsBookingType.deposit,
            amount=Decimal("25.00"),
            booking_date=date(2026, 6, 15),
        )
        booking = create_booking(db_session, box.id, editor_user.id, ok)
        assert booking.amount == Decimal("25.00")

    def test_create_booking_penalty_without_term_id_rejected(self, db_session: Session, editor_user: User) -> None:
        payload_box = SavingsBoxCreate(
            name="P",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
        )
        box = create_box(db_session, editor_user.id, payload_box)
        bad = SavingsBookingCreate(
            savings_term_id=None,
            booking_type=SavingsBookingType.penalty,
            amount=Decimal("5.00"),
            booking_date=date(2026, 7, 15),
        )
        with pytest.raises(SavingsBookingValidationError):
            create_booking(db_session, box.id, editor_user.id, bad)

    def test_delete_penalty_without_deposit_rejected(
        self, db_session: Session, editor_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Nur ein Term → genau eine Auto-Penalty (mehrere überfällige Termine → mehrere Strafzeilen).
        single_day = date(2026, 5, 10)
        payload_box = SavingsBoxCreate(
            name="DelPen",
            start_date=single_day,
            end_date=single_day,
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            penalty_amount=Decimal("3.00"),
        )
        box = create_box(db_session, editor_user.id, payload_box)
        term = db_session.query(SavingsTerm).filter(SavingsTerm.savings_box_id == box.id).order_by(SavingsTerm.due_date).first()

        _patch_savings_service_date(monkeypatch, date(2026, 6, 15))
        update_term_statuses(db_session, box)
        db_session.commit()

        penalty = (
            db_session.query(SavingsBooking)
            .filter(
                SavingsBooking.savings_box_id == box.id,
                SavingsBooking.booking_type == SavingsBookingType.penalty,
                SavingsBooking.savings_term_id == term.id,
            )
            .one()
        )
        with pytest.raises(SavingsPenaltyDeleteBlockedError):
            delete_booking(db_session, box.id, editor_user.id, penalty.id)

    def test_delete_penalty_with_deposit_allowed(
        self, db_session: Session, editor_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        single_day = date(2026, 5, 10)
        payload_box = SavingsBoxCreate(
            name="DelPenOk",
            start_date=single_day,
            end_date=single_day,
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            penalty_amount=Decimal("3.00"),
        )
        box = create_box(db_session, editor_user.id, payload_box)
        term = db_session.query(SavingsTerm).filter(SavingsTerm.savings_box_id == box.id).order_by(SavingsTerm.due_date).first()

        _patch_savings_service_date(monkeypatch, date(2026, 6, 15))
        update_term_statuses(db_session, box)
        db_session.commit()

        penalty = (
            db_session.query(SavingsBooking)
            .filter(
                SavingsBooking.savings_box_id == box.id,
                SavingsBooking.booking_type == SavingsBookingType.penalty,
                SavingsBooking.savings_term_id == term.id,
            )
            .one()
        )

        dep = SavingsBookingCreate(
            savings_term_id=term.id,
            booking_type=SavingsBookingType.deposit,
            amount=Decimal("10.00"),
            booking_date=date(2026, 6, 14),
        )
        create_booking(db_session, box.id, editor_user.id, dep)

        delete_booking(db_session, box.id, editor_user.id, penalty.id)

        remaining = (
            db_session.query(SavingsBooking)
            .filter(
                SavingsBooking.savings_box_id == box.id,
                SavingsBooking.booking_type == SavingsBookingType.penalty,
            )
            .count()
        )
        assert remaining == 0

    def test_delete_deposit_resets_term_to_missed(
        self, db_session: Session, editor_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Ein Term an festem Datum (wie Penalty-Tests) — sonst mehrere überfällige
        # Termine oder Randfälle beim Monatsraster.
        single_day = date(2026, 5, 10)
        payload_box = SavingsBoxCreate(
            name="DelDep",
            start_date=single_day,
            end_date=single_day,
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10.00"),
            penalty_amount=None,
        )
        box = create_box(db_session, editor_user.id, payload_box)
        term = db_session.query(SavingsTerm).filter(SavingsTerm.savings_box_id == box.id).order_by(SavingsTerm.due_date).first()
        term_id = term.id

        _patch_savings_service_date(monkeypatch, date(2026, 6, 15))
        db_session.refresh(box)
        update_term_statuses(db_session, box)
        db_session.commit()

        row = db_session.get(SavingsTerm, term_id)
        assert row is not None
        assert row.status == SavingsTermStatus.missed

        dep_payload = SavingsBookingCreate(
            savings_term_id=term_id,
            booking_type=SavingsBookingType.deposit,
            amount=Decimal("10.00"),
            booking_date=date(2026, 6, 1),
        )
        booking = create_booking(db_session, box.id, editor_user.id, dep_payload)
        db_session.refresh(row)
        assert row.status == SavingsTermStatus.fulfilled

        delete_booking(db_session, box.id, editor_user.id, booking.id)
        row = db_session.get(SavingsTerm, term_id)
        assert row is not None
        assert row.status == SavingsTermStatus.missed

    def test_assert_box_is_open_raises_on_closed(self) -> None:
        box = SavingsBox(
            user_id=uuid.uuid4(),
            name="Closed",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            interval=SavingsInterval.monthly,
            min_amount_per_term=Decimal("10"),
            status=SavingsBoxStatus.closed,
        )
        with pytest.raises(SavingsBoxClosedError):
            assert_box_is_open(box)


# ─── Router smoke ──────────────────────────────────────────────────────────────


class TestRouterSmoke:
    """Mini-App + Dependency-Overrides."""

    def test_create_box_generates_terms(self, savings_api_client: TestClient, editor_user: User) -> None:
        body = {
            "name": "API-Box",
            "start_date": "2026-02-01",
            "end_date": "2026-04-30",
            "interval": "monthly",
            "min_amount_per_term": "15.00",
        }
        res = savings_api_client.post("/savings/boxes", json=body)
        assert res.status_code == 201
        data = res.json()
        assert len(data["terms"]) == 3

    def test_get_box_detail_returns_summary(self, savings_api_client: TestClient, editor_user: User) -> None:
        # Start in der Zukunft — GET triggert echtes ``date.today()``; mit 2026-Terminen
        # wären je nach Rechnerdatum alle Termine bereits „verpasst“ und terms_open==0.
        body = {
            "name": "SumBox",
            "start_date": "2099-03-01",
            "end_date": "2099-05-31",
            "interval": "monthly",
            "min_amount_per_term": "20.00",
        }
        created = savings_api_client.post("/savings/boxes", json=body).json()
        box_id = created["id"]

        detail = savings_api_client.get(f"/savings/boxes/{box_id}")
        assert detail.status_code == 200
        js = detail.json()
        assert "summary" in js
        assert js["summary"]["terms_open"] == 3

    def test_create_booking_below_minimum_returns_422(self, savings_api_client: TestClient, editor_user: User) -> None:
        body = {
            "name": "422Box",
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
            "interval": "monthly",
            "min_amount_per_term": "30.00",
        }
        created = savings_api_client.post("/savings/boxes", json=body).json()
        box_id = created["id"]
        term_id = created["terms"][0]["id"]

        bad_booking = {
            "savings_term_id": term_id,
            "booking_type": "deposit",
            "amount": "5.00",
            "booking_date": "2026-04-15",
        }
        res = savings_api_client.post(f"/savings/boxes/{box_id}/bookings", json=bad_booking)
        assert res.status_code == 422

    def test_closed_box_rejects_booking(self, savings_api_client: TestClient, editor_user: User) -> None:
        body = {
            "name": "ClosedAPI",
            "start_date": "2026-05-01",
            "end_date": "2026-07-31",
            "interval": "monthly",
            "min_amount_per_term": "12.00",
        }
        created = savings_api_client.post("/savings/boxes", json=body).json()
        box_id = created["id"]
        term_id = created["terms"][0]["id"]

        close_body = {"actual_amount": "100.00", "note": "done"}
        close_res = savings_api_client.post(f"/savings/boxes/{box_id}/close", json=close_body)
        assert close_res.status_code == 200

        booking = {
            "savings_term_id": term_id,
            "booking_type": "deposit",
            "amount": "12.00",
            "booking_date": "2026-06-01",
        }
        res = savings_api_client.post(f"/savings/boxes/{box_id}/bookings", json=booking)
        assert res.status_code == 409

