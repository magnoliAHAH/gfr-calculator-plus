import pytest

from app.clinical.types import RuleData
from app.seed_data import DRUGS, RULES

_DRUG_BY_CODE = {d["drug_code"]: d for d in DRUGS}


def rules_for(drug_code: str, **overrides) -> list[RuleData]:
    """Seed-правила препарата в виде RuleData (id нумеруются подряд)."""
    out = []
    drug_rules = [x for x in RULES if x["drug_code"] == drug_code]
    for i, r in enumerate(drug_rules, start=1):
        data = dict(
            id=i,
            version=1,
            formula_code=r["formula_code"],
            weight_rule=r["weight_rule"],
            source=r["source"],
            rrt_mode=r["rrt_mode"],
            min_crcl=r["min_crcl"],
            max_crcl=r["max_crcl"],
            dose_mg=r.get("dose_mg"),
            dose_per_kg=r.get("dose_per_kg"),
            loading_dose_per_kg=r.get("loading_dose_per_kg"),
            frequency_hours=r["frequency_hours"],
            max_daily_dose_mg=r.get("max_daily_dose_mg"),
            tdm_required=r["tdm_required"],
            clinical_note=r.get("clinical_note"),
            rounding_step_mg=float(_DRUG_BY_CODE[drug_code]["rounding_step_mg"]),
        )
        data.update(overrides)
        out.append(RuleData(**data))
    return out


@pytest.fixture
def vanco():
    return rules_for("VANCO_IV")


@pytest.fixture
def amikacin():
    return rules_for("AMIKACIN_IV")


@pytest.fixture
def colistin():
    return rules_for("COLISTIN_IV")
