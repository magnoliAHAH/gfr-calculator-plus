"""Pydantic-модели API: решения врача и аудит (ТЗ 6.2, 6.3)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Decision = Literal["accepted", "overridden", "contraindication_acknowledged"]


class DecisionRequest(BaseModel):
    decision: Decision = Field(examples=["overridden"])
    override_reason_category: str | None = Field(default=None, description="Обязательно при overridden",
                                                 examples=["clinical_judgment"])
    override_reason_text: str | None = Field(default=None, description="Минимум 5 символов при overridden",
                                             examples=["Планируется CRRT"])
    new_dose_mg: float | None = Field(default=None, gt=0, examples=[1000])
    new_frequency_hours: int | None = Field(default=None, gt=0, examples=[24])


class DecisionResponse(BaseModel):
    audit_id: int = Field(description="ID расчёта, к которому относится решение", examples=[123])
    decision_audit_id: int = Field(description="ID записи решения в аудите", examples=[125])
    decision: Decision
    decision_at: datetime


class AuditEntry(BaseModel):
    id: int
    created_at: datetime
    record_type: Literal["calculation", "decision"]
    parent_audit_id: int | None
    user: dict[str, Any] = Field(examples=[{"id": 5, "full_name": "Иванов И.И."}])
    patient_ref: str
    drug: dict[str, Any] | None = Field(examples=[{"code": "VANCO_IV", "name": "Ванкомицин"}])
    rule_id: int | None
    rule_version: int | None
    input_data: dict[str, Any]
    recommended_dose: dict[str, Any] | None
    calculation_mode: str
    doctor_decision: str = Field(description="Для расчёта — текущее решение (pending, если не принято)")
    override_reason_category: str | None
    override_reason_text: str | None
    override_new_dose_mg: float | None
    override_new_frequency_hours: int | None
    decision_at: datetime | None
    record_hash: str
    prev_hash: str


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    page: int
    limit: int


class VerifyResponse(BaseModel):
    valid: bool
    first_invalid_id: int | None
    total_records_checked: int
    verified_at: datetime
