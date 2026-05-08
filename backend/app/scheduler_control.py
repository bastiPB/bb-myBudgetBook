"""
app/scheduler_control.py — Verbindung zwischen APScheduler und Admin-Einstellungen.

Warum eigene Datei?
- main.py startet den Scheduler und kennt die Job-ID.
- update_settings() soll die taegliche Uhrzeit ohne App-Neustart anpassen koennen.
- Ein kleines Modul vermeidet Zyklen (services/settings importiert nicht main).

Ohne register_payment_scheduler_job() (z. B. in Unit-Tests ohne Lifespan) sind
Reschedule-Aufrufe harmlos: No-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

# Wird beim App-Start in lifespan gesetzt — vorher None
_scheduler: BackgroundScheduler | None = None
_job_id: str | None = None


def register_payment_scheduler_job(scheduler: BackgroundScheduler, job_id: str) -> None:
    """
    Merkt sich Scheduler und Job-ID fuer spaeteres reschedule_job.

    Args:
        scheduler: Laufende BackgroundScheduler-Instanz.
        job_id: APScheduler-Job-ID (fest in main.py vergeben).
    """
    global _scheduler, _job_id
    _scheduler = scheduler
    _job_id = job_id


def reschedule_payment_scheduler_daily(hhmm: str) -> None:
    """
    Stellt den taeglichen Cron-Job auf eine neue Uhrzeit (Format HH:MM).

    Kein Effekt, wenn der Scheduler noch nicht registriert wurde (Tests).
    """
    if _scheduler is None or _job_id is None:
        return
    hour_str, sep, minute_str = hhmm.partition(":")
    if sep != ":" or len(hour_str) != 2 or len(minute_str) != 2:
        return
    hour, minute = int(hour_str), int(minute_str)
    _scheduler.reschedule_job(_job_id, trigger="cron", hour=hour, minute=minute)
