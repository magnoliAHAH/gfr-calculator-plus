"""Идемпотентный seed: системная организация, super_admin, препараты и правила (ТЗ 9.4).

Все функции вызываются в транзакции владельца схемы (privileged), где RLS обходится.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.db import tx
from app.security import hash_password
from app.seed_data import DRUGS, RULES

SYSTEM_ORG_CODE = "system"


def ensure_system_org(conn: Connection) -> int:
    conn.execute(
        text("INSERT INTO organizations (name, code) VALUES ('System', :c) ON CONFLICT (code) DO NOTHING"),
        {"c": SYSTEM_ORG_CODE},
    )
    return conn.execute(text("SELECT id FROM organizations WHERE code = :c"), {"c": SYSTEM_ORG_CODE}).scalar_one()


def ensure_super_admin(conn: Connection, email: str, password: str, full_name: str) -> int:
    org_id = ensure_system_org(conn)
    existing = conn.execute(text("SELECT id FROM users WHERE lower(email) = lower(:e)"), {"e": email}).scalar()
    if existing:
        return existing
    return conn.execute(
        text("INSERT INTO users (organization_id, email, full_name, role, password_hash) "
             "VALUES (:o, :e, :n, 'super_admin', :h) RETURNING id"),
        {"o": org_id, "e": email, "n": full_name, "h": hash_password(password)},
    ).scalar_one()


def seed_org_formulary(conn: Connection, org_id: int, created_by: int | None = None) -> dict:
    """Копирует seed-препараты и правила в организацию. Повторный вызов ничего не дублирует."""
    drugs_added = rules_added = 0
    for d in DRUGS:
        res = conn.execute(
            text("INSERT INTO drugs (organization_id, drug_code, drug_name, atc_code, route, formulation, "
                 "rounding_step_mg) VALUES (:o, :drug_code, :drug_name, :atc_code, :route, :formulation, "
                 ":rounding_step_mg) ON CONFLICT (organization_id, drug_code) DO NOTHING RETURNING id"),
            {"o": org_id, **d},
        ).scalar()
        if res is not None:
            drugs_added += 1
    drug_ids = {
        r.drug_code: r.id
        for r in conn.execute(text("SELECT id, drug_code FROM drugs WHERE organization_id = :o"), {"o": org_id})
    }
    # Решаем «есть ли уже правила» ОДИН раз на (препарат, показание) и ДО вставки: иначе после
    # первого же брекета остальные пропускались бы.
    already = {
        (drug_id, indication)
        for drug_id, indication in conn.execute(
            text("SELECT DISTINCT drug_id, indication FROM dosage_rules WHERE organization_id = :o"),
            {"o": org_id},
        )
    }
    for r in RULES:
        drug_id = drug_ids[r["drug_code"]]
        if (drug_id, r["indication"]) in already:
            continue  # правила этого показания уже есть (в т.ч. новых версий) — не трогаем
        conn.execute(
            text(
                "INSERT INTO dosage_rules (organization_id, drug_id, version, indication, formula_code, "
                "weight_rule, rrt_mode, min_crcl, max_crcl, dose_mg, dose_per_kg, loading_dose_per_kg, "
                "frequency_hours, max_daily_dose_mg, tdm_required, clinical_note, source, created_by) "
                "VALUES (:o, :d, 1, :indication, :formula_code, :weight_rule, :rrt_mode, :min_crcl, "
                ":max_crcl, :dose_mg, :dose_per_kg, :loading_dose_per_kg, :frequency_hours, "
                ":max_daily_dose_mg, :tdm_required, :clinical_note, :source, :cb)"
            ),
            {"o": org_id, "d": drug_id, "cb": created_by, "dose_mg": None, "loading_dose_per_kg": None,
             "max_daily_dose_mg": None, "clinical_note": None,
             **{k: v for k, v in r.items() if k != "drug_code"}},
        )
        rules_added += 1
    return {"drugs_added": drugs_added, "rules_added": rules_added}


def run_seed() -> None:
    """Точка входа scripts/seed.py: super_admin из env + (опционально) демо-организация."""
    s = get_settings()
    with tx(None, privileged=True) as conn:
        if s.super_admin_email and s.super_admin_password:
            ensure_super_admin(conn, s.super_admin_email, s.super_admin_password, s.super_admin_name)
