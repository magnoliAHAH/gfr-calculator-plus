"""Стратегии выбора веса (раздел 4.1.2, шаг 3)."""
from __future__ import annotations

from dataclasses import dataclass

from app.clinical.failsafe import FailSafe
from app.clinical.formulas import adjusted_body_weight, body_mass_index, ideal_body_weight

OBESITY_BMI = 30.0


@dataclass(frozen=True)
class WeightResult:
    used_kg: float
    type: str  # 'TBW' | 'IBW' | 'ABW'
    tbw_kg: float | None
    ibw_kg: float | None
    bmi: float | None


def select_weight(
    weight_rule: str, weight_kg: float | None, height_cm: float | None, sex: str
) -> WeightResult:
    """Выбирает вес для расчёта по правилу tbw / ibw / abw / auto.

    Бросает FailSafe, если данных не хватает.
    """
    if weight_rule not in ("tbw", "ibw", "abw", "auto"):
        raise ValueError(f"Unknown weight_rule: {weight_rule}")

    if weight_rule in ("ibw", "abw") and height_cm is None:
        raise FailSafe(
            "missing_height_for_weight_rule",
            f"Правило веса «{weight_rule.upper()}» требует рост пациента.",
        )
    if weight_rule in ("tbw", "abw") and weight_kg is None:
        raise FailSafe("missing_weight", "Для расчёта дозы необходим вес пациента.")

    ibw = ideal_body_weight(height_cm, sex) if height_cm is not None else None
    if ibw is not None and ibw <= 0:
        raise FailSafe(
            "invalid_anthropometry",
            "Идеальный вес по формуле Devine не положителен при указанном росте.",
        )
    bmi = body_mass_index(weight_kg, height_cm) if weight_kg is not None and height_cm is not None else None

    if weight_rule == "tbw":
        return WeightResult(weight_kg, "TBW", weight_kg, ibw, bmi)

    if weight_rule == "ibw":
        # Строго IBW, даже если фактический вес меньше (требование для колистина).
        return WeightResult(ibw, "IBW", weight_kg, ibw, bmi)

    if weight_rule == "abw":
        return WeightResult(adjusted_body_weight(weight_kg, ibw), "ABW", weight_kg, ibw, bmi)

    # auto
    if weight_kg is None:
        raise FailSafe("missing_weight", "Для расчёта дозы необходим вес пациента.")
    if height_cm is None:
        return WeightResult(weight_kg, "TBW", weight_kg, None, None)
    if bmi >= OBESITY_BMI:
        return WeightResult(adjusted_body_weight(weight_kg, ibw), "ABW", weight_kg, ibw, bmi)
    if weight_kg < ibw:
        return WeightResult(weight_kg, "TBW", weight_kg, ibw, bmi)
    return WeightResult(ibw, "IBW", weight_kg, ibw, bmi)
