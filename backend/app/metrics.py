"""Метрики Prometheus (ТЗ 8.3). Лейблы — только шаблоны маршрутов и коды, без PHI."""
from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "path"])
CALCULATE_TOTAL = Counter("calculate_total", "Calculations by result", ["result"])
AUDIT_CHAIN_ERRORS = Counter("audit_chain_errors_total", "Audit chain integrity/key errors")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _metrics(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - start)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
