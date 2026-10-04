"""Builds a FastAPI app with the shared health, readiness and metrics endpoints."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import db_is_ready, init_db
from .metrics import install_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_app(service: str, router: APIRouter, version: str = "1.0.0") -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        get_settings()  # fail fast if a required variable is missing
        init_db(service)
        yield

    app = FastAPI(title=service, version=version, lifespan=lifespan)
    install_metrics(app, service)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness: the process is up. Does not touch the database."""
        return {"status": "ok", "service": service}

    @app.get("/ready", tags=["ops"])
    def ready():
        """Readiness: the database answers."""
        if db_is_ready():
            return {"status": "ready", "service": service}
        return JSONResponse(status_code=503, content={"status": "not ready", "service": service})

    app.include_router(router)
    return app
