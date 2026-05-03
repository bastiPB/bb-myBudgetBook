from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.routers import admin, auth, profile, settings, subscriptions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan-Handler: wird beim Start und Stopp der App ausgeführt.

    Code VOR dem 'yield' läuft beim Start.
    Code NACH dem 'yield' läuft beim Stopp (hier nichts nötig).

    Warum lifespan statt @app.on_event("startup")?
    Die on_event-Methode ist veraltet — lifespan ist der moderne FastAPI-Standard.
    """
    # Admin-Account anlegen falls noch keiner existiert (liest ADMIN_EMAIL + ADMIN_PASSWORD aus .env)
    bootstrap_admin()
    yield


def create_app() -> FastAPI:
    cfg = get_settings()

    # Upload-Verzeichnis anlegen bevor StaticFiles es einbindet —
    # StaticFiles wirft einen Fehler wenn das Verzeichnis nicht existiert.
    upload_path = Path(cfg.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

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

    # /uploads als statisches Verzeichnis bereitstellen (ADR 0010: lokales Dateisystem).
    # Logos liegen unter /uploads/logos/<uuid>.ext und werden über /uploads/logos/... ausgeliefert.
    # Der Vite-Dev-Proxy und Nginx leiten /api/uploads → /uploads weiter — das Frontend
    # greift immer über /api/uploads/... zu, nie direkt über die Backend-URL.
    app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

    @app.get("/health", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
