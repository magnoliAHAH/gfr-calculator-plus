"""Модели и валидация набора правил (ТЗ 4.5.2, 5.1)."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.clinical.formulas import FORMULAS

WEIGHT_RULES = ("tbw", "ibw", "abw", "auto")
AKI = ("none", "stage_1", "stage_2", "stage_3")
RRT = ("none", "hd", "pd", "cvvh", "cvvhd", "cvvhdf")


class BracketSpec(BaseModel):
    rrt_mode: str = Field(default="none", description="none/hd/pd/cvvh/cvvhd/cvvhdf")
    min_crcl: float | None = Field(default=None, ge=0, le=9999, description="Только при rrt_mode=none")
    max_crcl: float | None = Field(default=None, gt=0, le=9999, description="Только при rrt_mode=none")
    dose_mg: float | None = Field(default=None, gt=0, description="Фиксированная доза, мг")
    dose_per_kg: float | None = Field(default=None, gt=0, description="Доза, мг/кг")
    loading_dose_per_kg: float | None = Field(default=None, gt=0)
    frequency_hours: int | None = Field(default=None, gt=0, description="null — однократно")
    infusion_duration_min: int | None = Field(default=60, gt=0)
    max_daily_dose_mg: float | None = Field(default=None, gt=0)
    tdm_required: bool = False
    clinical_note: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.rrt_mode not in RRT:
            raise ValueError(f"rrt_mode must be one of {RRT}")
        if self.dose_mg is None and self.dose_per_kg is None:
            raise ValueError("dose_mg or dose_per_kg is required")
        if self.rrt_mode == "none":
            if self.min_crcl is None or self.max_crcl is None or self.min_crcl >= self.max_crcl:
                raise ValueError("min_crcl < max_crcl are required when rrt_mode is 'none'")
        elif self.min_crcl is not None or self.max_crcl is not None:
            raise ValueError("min_crcl/max_crcl must be empty when rrt_mode is not 'none'")
        return self


class RuleVersionSpec(BaseModel):
    indication: str = Field(min_length=1, max_length=100, examples=["sepsis_bacteremia"])
    formula_code: str = Field(examples=["cockcroft_gault"])
    weight_rule: str = Field(examples=["auto"])
    max_allowed_aki: str = Field(default="stage_1")
    min_age_years: int = Field(default=18, ge=0, le=120)
    max_age_years: int = Field(default=120, ge=0, le=120)
    pregnancy_contraindicated: bool = False
    source: str = Field(min_length=1, examples=["IDSA 2020 Vancomycin Guidelines"])
    brackets: list[BracketSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        if self.formula_code not in FORMULAS:
            raise ValueError(f"unknown formula_code, expected one of {sorted(FORMULAS)}")
        if self.weight_rule not in WEIGHT_RULES:
            raise ValueError(f"weight_rule must be one of {WEIGHT_RULES}")
        if self.max_allowed_aki not in AKI:
            raise ValueError(f"max_allowed_aki must be one of {AKI}")
        if self.min_age_years > self.max_age_years:
            raise ValueError("min_age_years must be <= max_age_years")
        check_overlaps(self.brackets)
        return self


def check_overlaps(brackets: list[BracketSpec]) -> None:
    ranges = sorted((b.min_crcl, b.max_crcl) for b in brackets if b.rrt_mode == "none")
    for (_, prev_max), (cur_min, _) in zip(ranges, ranges[1:]):
        if cur_min < prev_max:
            raise ValueError("CrCl brackets overlap")
    seen: set[str] = set()
    for b in brackets:
        if b.rrt_mode != "none":
            if b.rrt_mode in seen:
                raise ValueError(f"duplicate bracket for rrt_mode '{b.rrt_mode}'")
            seen.add(b.rrt_mode)
