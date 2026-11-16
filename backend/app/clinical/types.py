"""Структуры данных клинического ядра (без зависимости от ORM)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.clinical.formulas import FORMULAS, interpret_renal_function
from app.clinical.weights import WeightResult

AKI_ORDER = {"none": 0, "stage_1": 1, "stage_2": 2, "stage_3": 3}
SUPPORTED_RRT = ("none", "hd", "pd", "cvvh", "cvvhd", "cvvhdf")


@dataclass(frozen=True)
class RuleData:
    """Строка dosage_rules + параметры препарата, нужные для расчёта."""

    id: int
    version: int
    formula_code: str
    weight_rule: str
    source: str
    rrt_mode: str = "none"
    min_crcl: float | None = None
    max_crcl: float | None = None
    max_allowed_aki: str = "stage_1"
    dose_mg: float | None = None
    dose_per_kg: float | None = None
    loading_dose_per_kg: float | None = None
    frequency_hours: int | None = None
    infusion_duration_min: int | None = 60
    max_daily_dose_mg: float | None = None
    tdm_required: bool = False
    clinical_note: str | None = None
    min_age_years: int = 18
    max_age_years: int = 120
    pregnancy_contraindicated: bool = False
    rounding_step_mg: float = 250.0


@dataclass(frozen=True)
class CalcInput:
    age_years: float
    sex_at_birth: str
    aki_stage: str = "none"
    rrt_mode: str = "none"
    pregnancy: bool = False
    ecmo: bool = False
    weight_kg: float | None = None
    height_cm: float | None = None
    creatinine_umol_l: float | None = None


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


@dataclass
class Recommendation:
    rule: RuleData
    weight: WeightResult | None
    renal_value: float | None
    dose_mg: float
    frequency_hours: int | None
    loading_dose_mg: float | None
    capped: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        r = self.rule
        formula = FORMULAS[r.formula_code]
        w = self.weight
        return {
            "formula": {"code": formula.code, "name": formula.name, "source": r.source},
            "weight": None
            if w is None
            else {
                "used_kg": _r(w.used_kg, 2),
                "type": w.type,
                "tbw_kg": _r(w.tbw_kg, 2),
                "ibw_kg": _r(w.ibw_kg, 2),
                "bmi": _r(w.bmi, 1),
            },
            "renal_function": None
            if self.renal_value is None
            else {
                "value": round(self.renal_value, 1),
                "unit": formula.output_unit,
                "interpretation": interpret_renal_function(self.renal_value),
            },
            "dose": {
                "amount_mg": self.dose_mg,
                "frequency_hours": self.frequency_hours,
                "single_dose": self.frequency_hours is None,
                "infusion_duration_min": r.infusion_duration_min,
                "max_daily_dose_mg": r.max_daily_dose_mg,
                "loading_dose_mg": self.loading_dose_mg,
                "capped_by_max_daily": self.capped,
            },
            "tdm_required": r.tdm_required,
            "warnings": self.warnings,
            "rule_version": r.version,
            "rule_id": r.id,
        }
