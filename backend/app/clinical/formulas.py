"""Формулы почечной функции и веса (раздел 4.1.3 ТЗ).

Все функции чистые: без БД и побочных эффектов, возвращают float без округления.
"""
from __future__ import annotations

from dataclasses import dataclass

UMOL_PER_MGDL_CREATININE = 88.4
CM_PER_INCH = 2.54


@dataclass(frozen=True)
class FormulaInfo:
    code: str
    name: str
    description: str
    requires_weight: bool
    requires_height: bool
    output_unit: str


FORMULAS: dict[str, FormulaInfo] = {
    "cockcroft_gault": FormulaInfo(
        code="cockcroft_gault",
        name="Cockcroft-Gault",
        description="Клиренс креатинина (CrCl), зависит от возраста, пола и веса.",
        requires_weight=True,
        requires_height=False,
        output_unit="mL/min",
    ),
    "ckd_epi_2021": FormulaInfo(
        code="ckd_epi_2021",
        name="CKD-EPI 2021",
        description="СКФ (eGFR) без расовой поправки, не зависит от веса.",
        requires_weight=False,
        requires_height=False,
        output_unit="mL/min/1.73m2",
    ),
}


def creatinine_mg_dl(creatinine_umol_l: float) -> float:
    return creatinine_umol_l / UMOL_PER_MGDL_CREATININE


def cockcroft_gault(age_years: float, weight_kg: float, creatinine_umol_l: float, sex: str) -> float:
    scr = creatinine_mg_dl(creatinine_umol_l)
    crcl = ((140 - age_years) * weight_kg) / (72 * scr)
    if sex == "female":
        crcl *= 0.85
    return crcl


def ckd_epi_2021(age_years: float, creatinine_umol_l: float, sex: str) -> float:
    scr = creatinine_mg_dl(creatinine_umol_l)
    female = sex == "female"
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    ratio = scr / k
    egfr = 142 * (min(ratio, 1) ** a) * (max(ratio, 1) ** -1.200) * (0.9938 ** age_years)
    if female:
        egfr *= 1.012
    return egfr


def ideal_body_weight(height_cm: float, sex: str) -> float:
    """Devine IBW. Для очень малого роста может быть <= 0 — проверяется вызывающим кодом."""
    inches = height_cm / CM_PER_INCH
    base = 45.5 if sex == "female" else 50.0
    return base + 2.3 * (inches - 60)


def adjusted_body_weight(tbw_kg: float, ibw_kg: float) -> float:
    return ibw_kg + 0.4 * (tbw_kg - ibw_kg)


def body_mass_index(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def compute_renal_function(
    formula_code: str, age_years: float, weight_kg: float | None, creatinine_umol_l: float, sex: str
) -> float:
    if formula_code == "cockcroft_gault":
        if weight_kg is None:
            raise ValueError("Cockcroft-Gault requires weight")
        return cockcroft_gault(age_years, weight_kg, creatinine_umol_l, sex)
    if formula_code == "ckd_epi_2021":
        return ckd_epi_2021(age_years, creatinine_umol_l, sex)
    raise ValueError(f"Unknown formula: {formula_code}")


def interpret_renal_function(value: float) -> str:
    if value >= 90:
        return "normal"
    if value >= 60:
        return "mild_impairment"
    if value >= 30:
        return "moderate_impairment"
    if value >= 15:
        return "severe_impairment"
    return "kidney_failure"
