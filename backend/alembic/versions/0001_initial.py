"""Начальная схема: таблицы, справочники, RLS, роль приложения, append-only аудит.

Отличия от схемы ТЗ 5.1 (обоснование в README):
  * audit_log append-only: решение врача — отдельная запись (record_type='decision',
    parent_audit_id), иначе UPDATE ломал бы HMAC-цепочку;
  * audit_chain_tip — по одной цепочке на организацию (chain_id='org_<id>'), иначе RLS
    не позволит организации проверить цепочку, в которой перемешаны чужие записи;
  * dosage_rules: + loading_dose_per_kg, min/max_age_years, pregnancy_contraindicated;
  * audit_log: + record_type, parent_audit_id, calc_duration_ms;
  * RLS также на organizations и audit_chain_tip;
  * dosage_rules неизменяема, кроме retired_at (триггер).
"""
from alembic import op

from app.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES_CORE_SQL = """
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    organization_id INT NOT NULL REFERENCES organizations(id),
    email VARCHAR(200) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('super_admin','org_admin','pharmacist','physician','auditor')),
    password_hash VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE drugs (
    id SERIAL PRIMARY KEY,
    organization_id INT NOT NULL REFERENCES organizations(id),
    drug_code VARCHAR(100) NOT NULL,
    drug_name VARCHAR(200) NOT NULL,
    atc_code VARCHAR(20),
    route VARCHAR(50) NOT NULL,
    formulation VARCHAR(100),
    rounding_step_mg NUMERIC(8,2) NOT NULL DEFAULT 250,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, drug_code)
);

CREATE TABLE formulas (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    requires_weight BOOLEAN NOT NULL DEFAULT FALSE,
    requires_height BOOLEAN NOT NULL DEFAULT FALSE,
    output_unit VARCHAR(50) NOT NULL
);

CREATE TABLE override_reasons (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL
);
"""

TABLES_RULES_SQL = """
CREATE TABLE dosage_rules (
    id SERIAL PRIMARY KEY,
    organization_id INT NOT NULL REFERENCES organizations(id),
    drug_id INT NOT NULL REFERENCES drugs(id),
    version INT NOT NULL DEFAULT 1,

    indication VARCHAR(100) NOT NULL,
    formula_code VARCHAR(50) NOT NULL REFERENCES formulas(code),
    weight_rule VARCHAR(20) NOT NULL CHECK (weight_rule IN ('tbw','ibw','abw','auto')),

    rrt_mode VARCHAR(20) NOT NULL DEFAULT 'none'
        CHECK (rrt_mode IN ('none','hd','pd','cvvh','cvvhd','cvvhdf')),
    min_crcl NUMERIC(6,2),
    max_crcl NUMERIC(6,2),
    max_allowed_aki VARCHAR(20) NOT NULL DEFAULT 'stage_1'
        CHECK (max_allowed_aki IN ('none','stage_1','stage_2','stage_3')),
    min_age_years INT NOT NULL DEFAULT 18,
    max_age_years INT NOT NULL DEFAULT 120,
    pregnancy_contraindicated BOOLEAN NOT NULL DEFAULT FALSE,

    dose_mg NUMERIC(10,2),
    dose_per_kg NUMERIC(10,4),
    loading_dose_per_kg NUMERIC(10,4),
    frequency_hours INT,
    infusion_duration_min INT DEFAULT 60,
    max_daily_dose_mg NUMERIC(10,2),

    tdm_required BOOLEAN NOT NULL DEFAULT FALSE,
    clinical_note TEXT,
    source TEXT NOT NULL,

    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by INT REFERENCES users(id),

    CONSTRAINT chk_dose CHECK (dose_mg IS NOT NULL OR dose_per_kg IS NOT NULL),
    CONSTRAINT chk_range CHECK (
        (rrt_mode = 'none' AND min_crcl IS NOT NULL AND max_crcl IS NOT NULL AND min_crcl < max_crcl)
        OR (rrt_mode != 'none' AND min_crcl IS NULL AND max_crcl IS NULL)
    ),
    CONSTRAINT chk_age CHECK (min_age_years >= 0 AND max_age_years <= 120 AND min_age_years <= max_age_years)
);
CREATE INDEX ix_rules_active ON dosage_rules(organization_id, drug_id) WHERE retired_at IS NULL;
"""

TABLES_AUDIT_SQL = """
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    organization_id INT NOT NULL REFERENCES organizations(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    record_type VARCHAR(20) NOT NULL DEFAULT 'calculation'
        CHECK (record_type IN ('calculation','decision')),
    parent_audit_id BIGINT REFERENCES audit_log(id),

    user_id INT NOT NULL REFERENCES users(id),
    patient_ref VARCHAR(100) NOT NULL,

    drug_id INT REFERENCES drugs(id),
    rule_id INT REFERENCES dosage_rules(id),
    rule_version INT,

    input_data JSONB NOT NULL,
    recommended_dose JSONB,
    calculation_mode VARCHAR(30) NOT NULL
        CHECK (calculation_mode IN ('bracket_fallback','blocked_fail_safe')),
    calc_duration_ms NUMERIC(10,2),

    doctor_decision VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (doctor_decision IN ('pending','accepted','overridden','contraindication_acknowledged')),
    override_reason_category VARCHAR(50) REFERENCES override_reasons(code),
    override_reason_text TEXT,
    override_new_dose_mg NUMERIC(10,2),
    override_new_frequency_hours INT,

    decision_at TIMESTAMPTZ,

    prev_hash VARCHAR(64) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,

    is_demo BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_decision_parent CHECK (
        (record_type = 'calculation' AND parent_audit_id IS NULL AND doctor_decision = 'pending')
        OR (record_type = 'decision' AND parent_audit_id IS NOT NULL AND doctor_decision != 'pending')
    )
);
-- Одно решение на расчёт: повторное решение даёт нарушение уникальности -> 409
CREATE UNIQUE INDEX ux_audit_one_decision ON audit_log(parent_audit_id) WHERE record_type = 'decision';
CREATE INDEX ix_audit_org_created ON audit_log(organization_id, created_at DESC);
CREATE INDEX ix_audit_user ON audit_log(user_id, created_at DESC);
CREATE INDEX ix_audit_patient ON audit_log(organization_id, patient_ref, created_at DESC);

CREATE TABLE audit_chain_tip (
    chain_id TEXT PRIMARY KEY,
    organization_id INT NOT NULL UNIQUE REFERENCES organizations(id),
    last_audit_id BIGINT,
    last_hash VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


# Append-only: UPDATE/DELETE запрещены триггером даже для владельца таблицы.
# Правила дозирования: разрешено менять только retired_at (ТЗ 4.5.2: «нельзя редактировать»).
GUARDS_SQL = """
CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_immutable BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

CREATE FUNCTION dosage_rules_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'dosage_rules rows cannot be deleted, retire them instead';
    END IF;
    IF (to_jsonb(NEW) - 'retired_at') IS DISTINCT FROM (to_jsonb(OLD) - 'retired_at') THEN
        RAISE EXCEPTION 'dosage_rules rows are immutable, create a new version instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_rules_guard BEFORE UPDATE OR DELETE ON dosage_rules
    FOR EACH ROW EXECUTE FUNCTION dosage_rules_guard();
"""

SEED_REFS_SQL = """
INSERT INTO formulas (code, name, description, requires_weight, requires_height, output_unit) VALUES
 ('cockcroft_gault', 'Cockcroft-Gault', 'Клиренс креатинина (CrCl), зависит от возраста, пола и веса.', TRUE, FALSE, 'mL/min'),
 ('ckd_epi_2021', 'CKD-EPI 2021', 'СКФ (eGFR) без расовой поправки, не зависит от веса.', FALSE, FALSE, 'mL/min/1.73m2');
INSERT INTO override_reasons (code, display_name, category) VALUES
 ('clinical_judgment', 'Клиническое суждение', 'clinical'),
 ('palliative', 'Паллиативная цель', 'clinical'),
 ('dialysis_schedule', 'График диализа', 'clinical'),
 ('pk_data', 'Данные TDM/PK', 'data'),
 ('mdr_pathogen', 'MDR-возбудитель', 'microbiology'),
 ('other', 'Другое', 'other');
"""

RLS_TABLES = ("users", "drugs", "dosage_rules", "audit_log", "audit_chain_tip")
ORG_SETTING = "NULLIF(current_setting('app.organization_id', TRUE), '')::int"

AUTH_LOOKUP_SQL = """
CREATE FUNCTION auth_lookup_user(p_email TEXT)
RETURNS TABLE (id INT, organization_id INT, email VARCHAR, full_name VARCHAR, role VARCHAR,
               password_hash VARCHAR, is_active BOOLEAN, organization_name VARCHAR, org_active BOOLEAN)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $f$
    SELECT u.id, u.organization_id, u.email, u.full_name, u.role, u.password_hash, u.is_active,
           o.name, o.is_active
    FROM users u JOIN organizations o ON o.id = u.organization_id
    WHERE lower(u.email) = lower(p_email)
$f$;
REVOKE ALL ON FUNCTION auth_lookup_user(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_lookup_user(TEXT) TO cdss_app;
"""


def _rls_sql(app_password: str) -> str:
    stmts = [
        # Роль приложения: не владелец таблиц и без BYPASSRLS -> RLS действует.
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cdss_app') THEN "
        f"CREATE ROLE cdss_app LOGIN PASSWORD '{app_password}' NOBYPASSRLS; END IF; END $$;",
        "GRANT USAGE ON SCHEMA public TO cdss_app;",
        "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO cdss_app;",
        "REVOKE UPDATE ON audit_log FROM cdss_app;",
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cdss_app;",
        # Справочники глобальные: приложение их только читает
        "REVOKE INSERT, UPDATE ON formulas, override_reasons FROM cdss_app;",
        # organizations: обычный пользователь видит только свою организацию;
        # создание организаций (super_admin) идёт под владельцем схемы
        "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;",
        f"CREATE POLICY p_org ON organizations USING (id = {ORG_SETTING});",
        "REVOKE INSERT, UPDATE ON organizations FROM cdss_app;",
    ]
    for t in RLS_TABLES:
        stmts.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
        stmts.append(
            f"CREATE POLICY p_{t} ON {t} USING (organization_id = {ORG_SETTING}) "
            f"WITH CHECK (organization_id = {ORG_SETTING});"
        )
    return "\n".join(stmts)


def upgrade() -> None:
    for block in (TABLES_CORE_SQL, TABLES_RULES_SQL, TABLES_AUDIT_SQL, GUARDS_SQL, SEED_REFS_SQL):
        op.execute(block)
    password = get_settings().app_db_password.replace("'", "''")
    op.execute(_rls_sql(password))
    op.execute(AUTH_LOOKUP_SQL)


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS auth_lookup_user(TEXT);"
        "DROP TABLE IF EXISTS audit_chain_tip, audit_log, dosage_rules, override_reasons, "
        "formulas, drugs, users, organizations CASCADE;"
        "DROP FUNCTION IF EXISTS audit_log_immutable();"
        "DROP FUNCTION IF EXISTS dosage_rules_guard();"
    )

