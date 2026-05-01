from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import bootstrap_admin
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

    @app.get("/health", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
