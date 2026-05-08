"""Tests für Scheduler-bezogene Systemeinstellungen (Pydantic)."""

import pytest
from pydantic import ValidationError

from app.schemas.settings import SCHEDULER_CATCH_UP_DAYS_MAX, AppSettingsUpdate


def test_scheduler_catch_up_days_at_max_ok() -> None:
    """Genau Obergrenze ist erlaubt."""
    m = AppSettingsUpdate(scheduler_catch_up_days=SCHEDULER_CATCH_UP_DAYS_MAX)
    assert m.scheduler_catch_up_days == SCHEDULER_CATCH_UP_DAYS_MAX


def test_scheduler_catch_up_days_above_max_rejected() -> None:
    """Über 730 Tage: deutschsprachige Validierung."""
    with pytest.raises(ValidationError) as exc:
        AppSettingsUpdate(scheduler_catch_up_days=SCHEDULER_CATCH_UP_DAYS_MAX + 1)
    err_text = str(exc.value)
    assert "730" in err_text
    assert "rueckwirkend" in err_text or "rückwirkend" in err_text


def test_scheduler_time_invalid_hour_rejected() -> None:
    """25:00 ist ungueltig."""
    with pytest.raises(ValidationError):
        AppSettingsUpdate(scheduler_time="25:00")


def test_scheduler_time_valid() -> None:
    m = AppSettingsUpdate(scheduler_time="03:30")
    assert m.scheduler_time == "03:30"
