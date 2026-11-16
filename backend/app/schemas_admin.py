"""Модели ответов справочников, админки и дашборда (ТЗ 6.4–6.8).

Нужны, чтобы OpenAPI описывал эти ответы и openapi-typescript генерировал типы клиента.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import Role


class FormulaOut(BaseModel):
    code: str = Field(examples=["cockcroft_gault"])
    name: str
    description: str | None
    requires_weight: bool
    requires_height: bool
    output_unit: str = Field(examples=["mL/min"])


class OverrideReasonOut(BaseModel):
    code: str = Field(examples=["clinical_judgment"])
    display_name: str
    category: str


class DrugMetaOut(BaseModel):
    id: int
    drug_code: str = Field(examples=["VANCO_IV"])
    drug_name: str = Field(examples=["Ванкомицин"])
    atc_code: str | None
    route: str = Field(examples=["IV"])
    formulation: str | None
    rounding_step_mg: float


class DrugOut(DrugMetaOut):
    is_active: bool
    created_at: datetime


class RuleOut(BaseModel):
    id: int
    drug_id: int
    version: int
    indication: str
    formula_code: str
    weight_rule: str
    rrt_mode: str
    min_crcl: float | None
    max_crcl: float | None
    max_allowed_aki: str
    min_age_years: int
    max_age_years: int
    pregnancy_contraindicated: bool
    dose_mg: float | None
    dose_per_kg: float | None
    loading_dose_per_kg: float | None
    frequency_hours: int | None
    infusion_duration_min: int | None
    max_daily_dose_mg: float | None
    tdm_required: bool
    clinical_note: str | None
    source: str
    effective_from: datetime
    retired_at: datetime | None
    created_at: datetime
    created_by: int | None


class RuleVersionGroup(BaseModel):
    indication: str
    version: int
    is_active: bool
    retired_at: datetime | None
    rules: list[RuleOut]


class RuleListOut(BaseModel):
    drug_id: int
    versions: list[RuleVersionGroup]


class RuleVersionCreated(BaseModel):
    indication: str
    version: int
    brackets: int
    retired_rows: int = Field(description="Сколько строк прежней версии закрыто")


class ImportedItem(RuleVersionCreated):
    drug_code: str


class ImportResult(BaseModel):
    imported: list[ImportedItem]


class UserAdminOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserInvited(UserAdminOut):
    temp_password: str = Field(description="Показывается один раз")
    setup_url: str


class OrgListItem(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime
    users_count: int
    calculations_count: int


class OrgOut(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime


class SeedResult(BaseModel):
    drugs_added: int
    rules_added: int


class OrgCreated(BaseModel):
    id: int
    code: str
    admin_user_id: int
    admin_email: str
    temp_password: str = Field(description="Показывается один раз")
    setup_url: str
    seeded: SeedResult | None


class HealthOut(BaseModel):
    status: str = Field(examples=["ok"])
    db: str = Field(examples=["ok"])
    version: str = Field(examples=["1.0.0"])
    uptime_seconds: int


class Period(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: datetime = Field(alias="from")
    to: datetime


class RecStats(BaseModel):
    total: int
    accepted: int
    overridden: int
    rejected: int
    pending: int
    accepted_pct: float
    overridden_pct: float
    rejected_pct: float


class ReasonStat(BaseModel):
    code: str
    count: int
    percentage: float


class DrugStat(BaseModel):
    code: str
    name: str
    count: int


class HistBucket(BaseModel):
    bucket: str
    count: int


class Perf(BaseModel):
    p50_ms: float | None
    p95_ms: float | None


class ChainStatus(BaseModel):
    valid: bool
    total_records: int
    last_verified_at: datetime | None
    first_invalid_id: int | None


class DashboardMetrics(BaseModel):
    period: Period
    recommendations: RecStats
    override_reasons_top: list[ReasonStat]
    drugs_top: list[DrugStat]
    renal_function_histogram: list[HistBucket]
    performance: Perf
    audit_chain: ChainStatus
    failsafe_rate: float
