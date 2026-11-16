"""Выгружает OpenAPI в frontend/openapi.json для генерации типов клиента (openapi-typescript).

Префикс /api/v1 убирается из путей: клиент задаёт его как baseUrl (VITE_API_BASE_URL=/api/v1,
ТЗ 9.3). Пути вне префикса (/health, /metrics) остаются как есть, фронтенд их не вызывает.

Запуск из backend/:  python -m scripts.dump_openapi
"""
from __future__ import annotations

import json
from pathlib import Path

from app.main import app

PREFIX = "/api/v1"
OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    schema["paths"] = {
        (p[len(PREFIX):] if p.startswith(PREFIX) else p): item for p, item in schema["paths"].items()
    }
    schema["servers"] = [{"url": PREFIX}]
    OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
