"""Ошибки в формате RFC 7807 (ProblemDetails) + correlation_id (ТЗ 6, 7.9).

В тело ошибок не попадают входные значения (PHI): только путь поля и сообщение.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")
log = logging.getLogger("cdss")

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    def __init__(self, status: int, title: str, detail: str, *, code: str | None = None,
                 headers: dict | None = None, extra: dict | None = None):
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code
        self.headers = headers or {}
        self.extra = extra or {}


def problem(status: int, title: str, detail: str, request: Request | None = None, **extra) -> dict:
    body = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "correlation_id": correlation_id_var.get(),
    }
    if request is not None:
        body["instance"] = request.url.path
    body.update({k: v for k, v in extra.items() if v is not None})
    return body


def _resp(status: int, body: dict, headers: dict | None = None) -> JSONResponse:
    h = {"X-Correlation-ID": correlation_id_var.get(), **(headers or {})}
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_JSON, headers=h)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation(request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        token = correlation_id_var.set(cid[:64])
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-ID"] = cid[:64]
        return response

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return _resp(exc.status, problem(exc.status, exc.title, exc.detail, request,
                                         code=exc.code, **exc.extra), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
                  for e in exc.errors()]
        return _resp(400, problem(400, "Validation error", "Request validation failed", request,
                                  errors=errors))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return _resp(exc.status_code, problem(exc.status_code, "HTTP error", str(exc.detail), request))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Логируем только тип исключения и correlation_id: текст может содержать PHI.
        log.error("unhandled error type=%s path=%s", type(exc).__name__, request.url.path)
        return _resp(500, problem(500, "Internal server error", "Unexpected error", request))
