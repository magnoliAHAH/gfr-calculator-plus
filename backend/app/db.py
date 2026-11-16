"""Доступ к БД: два пула соединений и транзакции с tenant-контекстом (ТЗ 4.4.1).

* app-пул — роль cdss_app без BYPASSRLS: RLS действует на все обычные запросы.
* owner-пул — владелец схемы (BYPASSRLS): super_admin, онбординг организаций, seed.

app.organization_id берётся ТОЛЬКО из аутентифицированного пользователя (JWT), не из запроса.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.config import get_settings, normalize_url

_engines: dict[str, Engine] = {}


def _make(url: str) -> Engine:
    return create_engine(normalize_url(url), pool_pre_ping=True, pool_size=10, max_overflow=10)


def owner_engine() -> Engine:
    if "owner" not in _engines:
        _engines["owner"] = _make(get_settings().database_url)
    return _engines["owner"]


def app_engine() -> Engine:
    if "app" not in _engines:
        _engines["app"] = _make(get_settings().effective_app_database_url)
    return _engines["app"]


def dispose_engines() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


@contextmanager
def tx(org_id: int | None, *, privileged: bool = False) -> Iterator[Connection]:
    """Транзакция: commit при выходе, rollback при исключении.

    set_config(..., true) действует только внутри транзакции (аналог SET LOCAL).
    """
    engine = owner_engine() if privileged else app_engine()
    with engine.begin() as conn:
        if org_id is not None:
            conn.execute(text("SELECT set_config('app.organization_id', :o, true)"), {"o": str(org_id)})
        yield conn


def db_ok() -> bool:
    try:
        with app_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
