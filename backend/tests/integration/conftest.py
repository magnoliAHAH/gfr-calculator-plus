"""Фикстуры интеграционных тестов: реальная БД, организации, пользователи, токены."""
from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import get_settings, normalize_url
from app.db import dispose_engines, tx
from app.security import create_access_token, hash_password
from app.seeding import seed_org_formulary
from tests.conftest import TEST_DB

ROLES = ("super_admin", "org_admin", "pharmacist", "physician", "auditor")
PASSWORD = "Test-pass-123"
_counter = itertools.count(1)
_PW_HASH = hash_password(PASSWORD)  # bcrypt cost 12 — считаем один раз на всю сессию

TRUNCATE = ("TRUNCATE audit_chain_tip, audit_log, dosage_rules, drugs, users, organizations "
            "RESTART IDENTITY CASCADE")


@pytest.fixture(scope="session", autouse=True)
def _database():
    get_settings.cache_clear()
    dispose_engines()
    engine = create_engine(normalize_url(TEST_DB))
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1 FROM organizations LIMIT 1"))
    except Exception as exc:  # БД нет или миграции не применены
        pytest.skip(f"PostgreSQL недоступен или не мигрирован: {type(exc).__name__}", allow_module_level=False)
    with engine.begin() as conn:
        conn.execute(text(TRUNCATE))
    yield engine
    dispose_engines()
    engine.dispose()


@pytest.fixture(scope="session")
def client(_database) -> TestClient:
    from app.main import app

    return TestClient(app)


class Org:
    def __init__(self, org_id: int, code: str, users: dict[str, dict]):
        self.id = org_id
        self.code = code
        self.users = users

    def headers(self, role: str) -> dict:
        u = self.users[role]
        token = create_access_token(u["id"], self.id, role)
        return {"Authorization": f"Bearer {token}"}


def make_org(seed: bool = True) -> Org:
    n = next(_counter)
    code = f"org{n}"
    with tx(None, privileged=True) as conn:
        org_id = conn.execute(
            text("INSERT INTO organizations (name, code) VALUES (:n, :c) RETURNING id"),
            {"n": f"Hospital {n}", "c": code}).scalar_one()
        users = {}
        for role in ROLES:
            uid = conn.execute(
                text("INSERT INTO users (organization_id, email, full_name, role, password_hash) "
                     "VALUES (:o, :e, :n, :r, :h) RETURNING id"),
                {"o": org_id, "e": f"{role}@{code}.test", "n": f"{role} {n}", "r": role,
                 "h": _PW_HASH}).scalar_one()
            users[role] = {"id": uid, "email": f"{role}@{code}.test"}
        if seed:
            seed_org_formulary(conn, org_id)
    return Org(org_id, code, users)


@pytest.fixture(scope="session")
def org_a(_database) -> Org:
    return make_org()


@pytest.fixture(scope="session")
def org_b(_database) -> Org:
    return make_org()


@pytest.fixture
def fresh_org(_database) -> Org:
    return make_org()


def calc_body(**overrides) -> dict:
    """Demo-сценарий 1 (ожирение) по умолчанию."""
    body = {
        "drug_code": "VANCO_IV", "indication": "sepsis_bacteremia", "age_years": 45,
        "sex_at_birth": "male", "weight_kg": 120, "height_cm": 175, "creatinine_umol_l": 110.7,
        "aki_stage": "none", "rrt_mode": "none", "pregnancy": False, "ecmo": False,
        "patient_ref": "p_test_1",
    }
    body.update(overrides)
    return body
