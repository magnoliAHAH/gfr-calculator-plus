"""FastAPI-приложение CDSS Pilot (ТЗ 6)."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import errors, metrics
from app.config import get_settings
from app.db import db_ok
from app.schemas_admin import HealthOut
from app import demo
from app.routers import (admin_drugs, admin_orgs, admin_rules, admin_users, audit_api, auth,
                         calculate, dashboard, decisions, meta)

_STARTED = time.time()
API_PREFIX = "/api/v1"

DESCRIPTION = (
    "Клинический инструмент поддержки решений для почечного дозирования антимикробных препаратов. "
    "Пилотная версия, не является медицинским изделием (SaMD)."
)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')

    app = FastAPI(
        title="CDSS Pilot — почечное дозирование",
        version=settings.app_version,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_init_oauth={"usePkceWithAuthorizationCodeGrant": False},
    )
    errors.install(app)
    metrics.install(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Correlation-ID"],
    )

    api = APIRouter(prefix=API_PREFIX)
    for module in (auth, meta, calculate, decisions, audit_api, admin_drugs, admin_rules,
                   admin_users, admin_orgs, dashboard, demo):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/health", response_model=HealthOut, tags=["system"], summary="Liveness")
    def health() -> dict:
        ok = db_ok()
        return {"status": "ok" if ok else "degraded", "db": "ok" if ok else "error",
                "version": settings.app_version, "uptime_seconds": int(time.time() - _STARTED)}

    @app.get("/health/ready", tags=["system"], summary="Readiness")
    def ready():
        ok = db_ok()
        body = {"status": "ready" if ok else "not_ready", "db": "ok" if ok else "error"}
        return JSONResponse(body, status_code=200 if ok else 503)

    return app


app = create_app()
