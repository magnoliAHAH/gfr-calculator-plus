"""Smoke-тест развёрнутого стека (ТЗ 11.2): логин -> расчёт -> решение -> проверка цепочки.

Запуск:  python scripts/smoke.py [BASE_URL]
Переменные: SMOKE_EMAIL / SMOKE_PASSWORD (по умолчанию SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD).
Только стандартная библиотека. Создаёт временную организацию и не трогает существующие данные.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMOKE_BASE_URL", "http://localhost")).rstrip("/")
API = BASE + "/api/v1"


def call(method: str, url: str, body=None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def check(cond: bool, msg: str) -> None:
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


def wait_ready(timeout: int = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if call("GET", BASE + "/health/ready")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    check(False, "API became ready")


def main() -> None:
    wait_ready()
    status, health = call("GET", BASE + "/health")
    check(status == 200 and health["db"] == "ok", "health: db ok")

    email = os.environ.get("SMOKE_EMAIL") or os.environ.get("SUPER_ADMIN_EMAIL")
    password = os.environ.get("SMOKE_PASSWORD") or os.environ.get("SUPER_ADMIN_PASSWORD")
    check(bool(email and password), "SMOKE_EMAIL/SMOKE_PASSWORD (or SUPER_ADMIN_*) are set")
    status, login = call("POST", API + "/auth/login", {"email": email, "password": password})
    check(status == 200, "super_admin login")
    sa = login["access_token"]

    code = "smoke" + uuid.uuid4().hex[:8]
    admin_email = f"admin@{code}.test"
    status, org = call("POST", API + "/admin/organizations", {
        "name": "Smoke Hospital", "code": code, "admin_email": admin_email,
        "admin_full_name": "Smoke Admin"}, sa)
    check(status == 201 and org["temp_password"], "onboarding: org + admin created in 1 request")

    status, login = call("POST", API + "/auth/login", {"email": admin_email, "password": org["temp_password"]})
    check(status == 200, "org admin login with temp password")
    token = login["access_token"]

    body = {"drug_code": "VANCO_IV", "indication": "sepsis_bacteremia", "age_years": 45,
            "sex_at_birth": "male", "weight_kg": 120, "height_cm": 175, "creatinine_umol_l": 110.7,
            "aki_stage": "none", "rrt_mode": "none", "pregnancy": False, "ecmo": False,
            "patient_ref": "p_smoke"}
    started = time.perf_counter()
    status, rec = call("POST", API + "/calculate", body, token)
    elapsed = time.perf_counter() - started
    check(status == 200 and rec["calculation_mode"] == "bracket_fallback", "calculate: recommendation")
    check(rec["dose"]["amount_mg"] == 1350 and rec["weight"]["type"] == "ABW", "dose 1350 mg, ABW")
    check(elapsed < 1.5, f"calculate latency {elapsed * 1000:.0f} ms < 1500 ms")

    status, fs = call("POST", API + "/calculate", body | {"aki_stage": "stage_2"}, token)
    check(status == 200 and fs["calculation_mode"] == "blocked_fail_safe", "calculate: fail-safe on AKI")

    status, dec = call("POST", f"{API}/audit/{rec['audit_id']}/decision", {"decision": "accepted"}, token)
    check(status == 200, "decision: accepted")
    status, _ = call("POST", f"{API}/audit/{rec['audit_id']}/decision", {"decision": "accepted"}, token)
    check(status == 409, "decision: repeat -> 409")

    status, ver = call("GET", f"{API}/audit/{dec['decision_audit_id']}/verify", token=token)
    check(status == 200 and ver["valid"] and ver["total_records_checked"] == 3, "audit chain valid (3 records)")
    print("SMOKE PASSED")


if __name__ == "__main__":
    main()
