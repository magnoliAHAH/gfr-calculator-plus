"""Идемпотентный seed (ТЗ 9.4): super_admin из env (SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD).

Запуск: python -m scripts.seed
Справочники (формулы, причины override) создаёт миграция; препараты и правила копируются
в организацию при онбординге (POST /admin/organizations) либо флагом SEED_DEMO_ORG=1 здесь.
"""
from __future__ import annotations

import os

from sqlalchemy import text

from app.config import get_settings
from app.db import dispose_engines, tx
from app.seeding import run_seed, seed_org_formulary


def seed_demo_org() -> None:
    """Опциональная демо-организация с готовым формуляром (для презентаций)."""
    with tx(None, privileged=True) as conn:
        conn.execute(text("INSERT INTO organizations (name, code) VALUES ('Demo Hospital', 'demo') "
                          "ON CONFLICT (code) DO NOTHING"))
        org_id = conn.execute(text("SELECT id FROM organizations WHERE code = 'demo'")).scalar_one()
        print("demo formulary:", seed_org_formulary(conn, org_id))


def main() -> None:
    settings = get_settings()
    if not (settings.super_admin_email and settings.super_admin_password):
        print("SUPER_ADMIN_EMAIL/SUPER_ADMIN_PASSWORD not set: super_admin was not created")
    run_seed()
    if os.environ.get("SEED_DEMO_ORG") == "1":
        seed_demo_org()
    dispose_engines()
    print("seed done")


if __name__ == "__main__":
    main()
