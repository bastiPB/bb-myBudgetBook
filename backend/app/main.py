from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.database import SessionLocal
from app.exceptions import register_exception_handlers
from app.routers import admin, auth, profile, settings, subscriptions
from app.services.scheduler_service import generate_scheduled_payments

# Globale Scheduler-Instanz — wird im lifespan-Handler gestartet und gestoppt.
# BackgroundScheduler läuft in einem eigenen Thread neben dem FastAPI-Prozess.
# Kein Redis, kein Celery nötig — einfache Lösung für tägliche Jobs.
_scheduler = BackgroundScheduler()


def _run_scheduler_job() -> None:
    """
    Funktion, die APScheduler täglich aufruft.

    Öffnet eine eigene DB-Session (der Scheduler-Thread hat keine FastAPI-Request-Session)
    und ruft generate_scheduled_payments auf.
    Fehler werden geloggt, aber nicht weitergeworfen — der Scheduler läuft weiter.
    """
    # with-Statement schließt die Session automatisch, auch wenn eine Exception passiert
    with SessionLocal() as session:
        try:
            count = generate_scheduled_payments(session)
            print(f"[Scheduler] {count} Soll-Buchung(en) erzeugt.")
        except Exception as exc:  # noqa: BLE001
            # Im Fehlerfall nur loggen — der Scheduler soll beim nächsten Tag erneut laufen
            print(f"[Scheduler] Fehler beim Generieren von Buchungen: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan-Handler: wird beim Start und Stopp der App ausgeführt.

    Code VOR dem 'yield' läuft beim Start.
    Code NACH dem 'yield' läuft beim Stopp.

    Warum lifespan statt @app.on_event("startup")?
    Die on_event-Methode ist veraltet — lifespan ist der moderne FastAPI-Standard.
    """
    # Admin-Account anlegen falls noch keiner existiert (liest ADMIN_EMAIL + ADMIN_PASSWORD aus .env)
    bootstrap_admin()

    # Scheduler-Laufzeit aus der DB lesen (scheduler_time = "HH:MM", z. B. "03:00")
    # Warum SessionLocal() statt einer Dependency? Lifespan läuft vor dem ersten Request.
    with SessionLocal() as session:
        from app.services.settings import get_settings as get_db_settings
        db_settings = get_db_settings(session)
        hour, minute = map(int, db_settings.scheduler_time.split(":"))

    # Täglich zur konfigurierten Uhrzeit ausführen
    _scheduler.add_job(_run_scheduler_job, "cron", hour=hour, minute=minute)
    _scheduler.start()

    yield  # App läuft hier — alles danach ist Cleanup beim Stopp

    # APScheduler sauber beenden — laufende Jobs werden abgewartet
    _scheduler.shutdown()


def create_app() -> FastAPI:
    cfg = get_settings()

    app = FastAPI(
        title="BB-myBudgetBook API",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(settings.router)
    app.include_router(profile.router)
    app.include_router(subscriptions.router)

    # Upload-Verzeichnis anlegen und als statisches Verzeichnis einbinden (ADR 0010).
    # Schlägt das Anlegen fehl (z. B. fehlende Rechte in CI-Umgebungen), wird der
    # Mount übersprungen — die App startet trotzdem, nur ohne Upload-Unterstützung.
    upload_path = Path(cfg.upload_dir)
    try:
        upload_path.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
    except (PermissionError, OSError):
        pass

    @app.get("/health", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
