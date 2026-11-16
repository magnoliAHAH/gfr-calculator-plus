"""Pydantic-модели API: аутентификация и расчёт (ТЗ 6.1, 6.2). Поля с description/examples для Swagger."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Sex = Literal["male", "female"]
AkiStage = Literal["none", "stage_1", "stage_2", "stage_3"]
RrtMode = Literal["none", "hd", "pd", "cvvh", "cvvhd", "cvvhdf"]
Role = Literal["super_admin", "org_admin", "pharmacist", "physician", "auditor"]


class LoginRequest(BaseModel):
    email: str = Field(description="Email пользователя", examples=["doctor@hospital.ru"])
    password: str = Field(description="Пароль", examples=["s3cret-pass"])


class UserOut(BaseModel):
    id: int = Field(examples=[5])
    email: str = Field(examples=["doctor@hospital.ru"])
    full_name: str = Field(examples=["Иванов И.И."])
    role: Role = Field(examples=["physician"])
    organization_id: int = Field(examples=[1])
    organization_name: str = Field(examples=["Городская больница №1"])
    must_change_password: bool = Field(default=False, description="Выдан временный пароль: его нужно сменить")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(description="Текущий (временный) пароль")
    new_password: str = Field(min_length=10, max_length=72, description="Новый пароль, 10–72 символа")


class LoginResponse(BaseModel):
    access_token: str = Field(description="JWT (24 ч)")
    token_type: str = Field(default="bearer", examples=["bearer"])
    user: UserOut


class CalculateRequest(BaseModel):
    drug_code: str = Field(description="Код препарата из /meta/drugs", examples=["VANCO_IV"])
    indication: str = Field(description="Показание из /meta/indications", examples=["sepsis_bacteremia"])
    age_years: float = Field(ge=0, le=120, description="Возраст, лет", examples=[45])
    sex_at_birth: Sex = Field(description="Пол при рождении", examples=["male"])
    weight_kg: float | None = Field(default=None, ge=20, le=400, description="Вес, кг", examples=[120])
    height_cm: float | None = Field(default=None, ge=100, le=250, description="Рост, см", examples=[175])
    creatinine_umol_l: float | None = Field(default=None, ge=10, le=3000,
                                            description="Креатинин, мкмоль/л", examples=[110.7])
    aki_stage: AkiStage = Field(description="Стадия ОПП (AKI)", examples=["none"])
    rrt_mode: RrtMode = Field(description="Режим заместительной почечной терапии", examples=["none"])
    pregnancy: bool = Field(description="Беременность", examples=[False])
    ecmo: bool = Field(description="Пациент на ECMO", examples=[False])
    patient_ref: str = Field(min_length=1, max_length=100,
                             description="Псевдоним пациента из МИС. НЕ ФИО.", examples=["p_abc123"])


class FormulaRef(BaseModel):
    code: str = Field(examples=["cockcroft_gault"])
    name: str = Field(examples=["Cockcroft-Gault"])
    source: str = Field(examples=["IDSA 2020 Vancomycin Guidelines"])


class WeightInfo(BaseModel):
    used_kg: float | None = Field(examples=[90.3])
    type: str = Field(examples=["ABW"])
    tbw_kg: float | None = Field(examples=[120.0])
    ibw_kg: float | None = Field(examples=[70.5])
    bmi: float | None = Field(examples=[39.2])


class RenalFunction(BaseModel):
    value: float = Field(examples=[95.2])
    unit: str = Field(examples=["mL/min"])
    interpretation: str = Field(examples=["normal"])


class DoseInfo(BaseModel):
    amount_mg: float = Field(examples=[1350.0])
    frequency_hours: int | None = Field(description="null для однократной дозы", examples=[12])
    single_dose: bool = Field(examples=[False])
    infusion_duration_min: int | None = Field(examples=[60])
    max_daily_dose_mg: float | None = Field(examples=[None])
    loading_dose_mg: float | None = Field(description="Нагрузочная доза в первые сутки", examples=[None])
    capped_by_max_daily: bool = Field(examples=[False])


class Recommendation(BaseModel):
    audit_id: int = Field(examples=[123])
    calculation_mode: Literal["bracket_fallback"]
    formula: FormulaRef
    weight: WeightInfo | None
    renal_function: RenalFunction | None
    dose: DoseInfo
    tdm_required: bool = Field(examples=[True])
    warnings: list[str] = Field(examples=[["Требуется контроль концентрации препарата (TDM)."]])
    rule_version: int = Field(examples=[1])
    rule_id: int = Field(examples=[45])
    generated_at: datetime


class FailSafeResponse(BaseModel):
    audit_id: int = Field(examples=[124])
    calculation_mode: Literal["blocked_fail_safe"]
    no_recommendation_reason: str = Field(examples=["severe_aki_requires_consult"])
    no_recommendation_display: str = Field(examples=["Требуется консультация клинического фармаколога"])
    details: str = Field(examples=["У пациента AKI stage 2."])
    generated_at: datetime
