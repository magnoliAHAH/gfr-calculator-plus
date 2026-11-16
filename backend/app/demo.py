"""Demo mode (ТЗ 4.7): публичный расчёт по seed-правилам без БД, без аудита, без интернета.

Ничего не пишется и не читается из БД, поэтому демо не может «засорить» аудит и работает,
даже если БД недоступна. Результат считает то же клиническое ядро, что и /calculate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.clinical.engine import calculate
from app.clinical.failsafe import FailSafe
from app.clinical.types import CalcInput, RuleData
from app.errors import ApiError
from app.schemas import AkiStage, FailSafeResponse, Recommendation, RrtMode, Sex
from app.seed_data import DRUGS, RULES

router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_AUDIT_ID = 0  # демо не пишет в аудит: идентификатор-заглушка, UI скрывает кнопки решений

_ROUNDING = {d["drug_code"]: float(d["rounding_step_mg"]) for d in DRUGS}


class DemoCalculateRequest(BaseModel):
    """Те же поля, что у /calculate, но без patient_ref (демо не связано с пациентом)."""

    drug_code: str = Field(examples=["VANCO_IV"])
    indication: str = Field(examples=["sepsis_bacteremia"])
    age_years: float = Field(ge=0, le=120)
    sex_at_birth: Sex
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    creatinine_umol_l: float | None = Field(default=None, ge=10, le=3000)
    aki_stage: AkiStage = "none"
    rrt_mode: RrtMode = "none"
    pregnancy: bool = False
    ecmo: bool = False


class DemoScenario(BaseModel):
    id: str = Field(examples=["obesity"])
    title: str
    description: str
    message: str = Field(description="Что показывает этот сценарий")
    request: DemoCalculateRequest


SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        id="obesity", title="Ожирение",
        description="45 лет, мужчина, 120 кг, 175 см (BMI 39.2), CrCl около 95 мл/мин. Ванкомицин.",
        message="Система корректирует вес, защищая от передозировки.",
        request=DemoCalculateRequest(
            drug_code="VANCO_IV", indication="sepsis_bacteremia", age_years=45, sex_at_birth="male",
            weight_kg=120, height_cm=175, creatinine_umol_l=110.7),
    ),
    DemoScenario(
        id="aki", title="Острое повреждение почек",
        description="70 лет, женщина, 60 кг, CrCl около 25 мл/мин, AKI стадия 2. Ванкомицин.",
        message="Система не даёт рекомендацию при высоком риске — нужен фармаколог.",
        request=DemoCalculateRequest(
            drug_code="VANCO_IV", indication="sepsis_bacteremia", age_years=70, sex_at_birth="female",
            weight_kg=60, creatinine_umol_l=175, aki_stage="stage_2"),
    ),
    DemoScenario(
        id="renal", title="Коррекция по функции почек",
        description="65 лет, мужчина, 70 кг, CrCl около 25 мл/мин. Амикацин.",
        message="Доза адаптирована к функции почек, не стандартная.",
        request=DemoCalculateRequest(
            drug_code="AMIKACIN_IV", indication="sepsis_bacteremia", age_years=65, sex_at_birth="male",
            weight_kg=70, creatinine_umol_l=257.9),
    ),
]


def seed_rules(drug_code: str, indication: str) -> list[RuleData]:
    """Seed-правила препарата и показания в виде RuleData (id нумеруются подряд, версия 1)."""
    chosen = [r for r in RULES if r["drug_code"] == drug_code and r["indication"] == indication]
    return [
        RuleData(
            id=i, version=1, formula_code=r["formula_code"], weight_rule=r["weight_rule"],
            source=r["source"], rrt_mode=r["rrt_mode"], min_crcl=r["min_crcl"], max_crcl=r["max_crcl"],
            dose_mg=r.get("dose_mg"), dose_per_kg=r.get("dose_per_kg"),
            loading_dose_per_kg=r.get("loading_dose_per_kg"), frequency_hours=r["frequency_hours"],
            max_daily_dose_mg=r.get("max_daily_dose_mg"), tdm_required=r["tdm_required"],
            clinical_note=r.get("clinical_note"), rounding_step_mg=_ROUNDING[drug_code],
        )
        for i, r in enumerate(chosen, start=1)
    ]


class DemoDrug(BaseModel):
    drug_code: str = Field(examples=["VANCO_IV"])
    drug_name: str = Field(examples=["Ванкомицин"])
    indications: list[str] = Field(examples=[["sepsis_bacteremia"]])


@router.get("/drugs", response_model=list[DemoDrug], summary="Препараты и показания demo-режима")
def demo_drugs() -> list[DemoDrug]:
    return [
        DemoDrug(drug_code=d["drug_code"], drug_name=d["drug_name"],
                 indications=sorted({r["indication"] for r in RULES if r["drug_code"] == d["drug_code"]}))
        for d in DRUGS
    ]


@router.get("/scenarios", response_model=list[DemoScenario], summary="Три готовых demo-сценария")
def scenarios() -> list[DemoScenario]:
    return SCENARIOS


@router.post(
    "/calculate",
    response_model=Union[Recommendation, FailSafeResponse],
    summary="Демо-расчёт без аутентификации и без записи в аудит",
    description="Считает по встроенным seed-правилам. `audit_id` всегда 0: запись в аудит не создаётся.",
)
def demo_calculate(body: DemoCalculateRequest):
    if body.drug_code not in _ROUNDING:
        raise ApiError(404, "Drug not found", "Demo supports only the seed drugs: " + ", ".join(sorted(_ROUNDING)))
    rules = seed_rules(body.drug_code, body.indication)
    if not rules:
        raise ApiError(404, "Indication not found", f"No demo rule for indication '{body.indication}'")
    inp = CalcInput(
        age_years=body.age_years, sex_at_birth=body.sex_at_birth, aki_stage=body.aki_stage,
        rrt_mode=body.rrt_mode, pregnancy=body.pregnancy, ecmo=body.ecmo, weight_kg=body.weight_kg,
        height_cm=body.height_cm, creatinine_umol_l=body.creatinine_umol_l)
    now = datetime.now(timezone.utc)
    try:
        rec = calculate(rules, inp)
    except FailSafe as fs:
        return FailSafeResponse(
            audit_id=DEMO_AUDIT_ID, calculation_mode="blocked_fail_safe",
            no_recommendation_reason=fs.reason, no_recommendation_display=fs.display,
            details=fs.details, generated_at=now)
    return Recommendation(audit_id=DEMO_AUDIT_ID, calculation_mode="bracket_fallback",
                          generated_at=now, **rec.to_dict())
