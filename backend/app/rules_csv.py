"""Импорт/экспорт правил в CSV (ТЗ 4.5.2).

Обязательные колонки по ТЗ: drug_code, indication, formula, weight_rule, min_crcl, max_crcl,
dose_mg, frequency_hours, tdm, source. Дополнительные (необязательные, нужны для round-trip):
dose_per_kg, loading_dose_per_kg, max_daily_dose_mg, rrt_mode, max_allowed_aki, clinical_note.
Одна группа строк (drug_code, indication) = одна новая версия правил.
"""
from __future__ import annotations

import csv
import io

from pydantic import ValidationError

from app.errors import ApiError
from app.rules_specs import BracketSpec, RuleVersionSpec

REQUIRED = ("drug_code", "indication", "formula", "weight_rule", "min_crcl", "max_crcl",
            "dose_mg", "frequency_hours", "tdm", "source")
EXTRA = ("dose_per_kg", "loading_dose_per_kg", "max_daily_dose_mg", "rrt_mode", "max_allowed_aki",
         "clinical_note")
EXPORT_COLUMNS = REQUIRED + EXTRA
MAX_BYTES = 1_000_000
MAX_ROWS = 2000
_TRUE = {"1", "true", "yes", "y", "да"}
_FALSE = {"", "0", "false", "no", "n", "нет"}


def _num(row: dict, key: str, cast=float):
    v = (row.get(key) or "").strip()
    return None if v == "" else cast(v)


def _bool(v: str | None) -> bool:
    s = (v or "").strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f"invalid boolean '{v}'")


def parse_csv(raw: bytes) -> dict[tuple[str, str], RuleVersionSpec]:
    """Возвращает спецификации по (drug_code, indication). Любая ошибка — 400 с номерами строк."""
    if len(raw) > MAX_BYTES:
        raise ApiError(400, "CSV too large", f"File exceeds {MAX_BYTES} bytes")
    try:
        text_ = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(400, "Invalid CSV", "File must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text_))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise ApiError(400, "Invalid CSV", f"Missing columns: {', '.join(missing)}")

    errors: list[dict] = []
    groups: dict[tuple[str, str], list[tuple[int, dict, BracketSpec]]] = {}
    for n, raw_row in enumerate(reader, start=2):  # строка 1 — заголовок
        if n - 1 > MAX_ROWS:
            raise ApiError(400, "CSV too large", f"More than {MAX_ROWS} rows")
        row = {(k or "").strip(): (v or "") for k, v in raw_row.items()}
        try:
            bracket = BracketSpec(
                rrt_mode=(row.get("rrt_mode") or "none").strip() or "none",
                min_crcl=_num(row, "min_crcl"), max_crcl=_num(row, "max_crcl"),
                dose_mg=_num(row, "dose_mg"), dose_per_kg=_num(row, "dose_per_kg"),
                loading_dose_per_kg=_num(row, "loading_dose_per_kg"),
                frequency_hours=_num(row, "frequency_hours", int),
                max_daily_dose_mg=_num(row, "max_daily_dose_mg"),
                tdm_required=_bool(row.get("tdm")),
                clinical_note=(row.get("clinical_note") or "").strip() or None,
            )
            for req in ("drug_code", "indication", "formula", "weight_rule", "source"):
                if not row[req].strip():
                    raise ValueError(f"'{req}' is empty")
        except (ValueError, ValidationError) as exc:
            msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            errors.append({"row": n, "message": msg})
            continue
        groups.setdefault((row["drug_code"].strip(), row["indication"].strip()), []).append((n, row, bracket))

    if not groups and not errors:
        errors.append({"row": 0, "message": "File contains no data rows"})
    specs: dict[tuple[str, str], RuleVersionSpec] = {}
    for key, items in groups.items():
        first = items[0][1]
        try:
            for n, row, _ in items:  # параметры, общие для группы, должны совпадать
                for col in ("formula", "weight_rule", "source"):
                    if row[col].strip() != first[col].strip():
                        raise ValueError(f"row {n}: '{col}' differs within {key[0]}/{key[1]}")
            specs[key] = RuleVersionSpec(
                indication=key[1], formula_code=first["formula"].strip(),
                weight_rule=first["weight_rule"].strip(),
                max_allowed_aki=(first.get("max_allowed_aki") or "stage_1").strip() or "stage_1",
                source=first["source"].strip(), brackets=[b for _, _, b in items])
        except (ValueError, ValidationError) as exc:
            msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            errors.append({"row": items[0][0], "message": f"{key[0]}/{key[1]}: {msg}"})
    if errors:
        raise ApiError(400, "Invalid CSV", f"{len(errors)} error(s) in file; nothing was imported",
                       extra={"errors": errors[:50]})
    return specs


def render_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    for r in rows:
        out = []
        for col in EXPORT_COLUMNS:
            key = {"formula": "formula_code", "tdm": "tdm_required"}.get(col, col)
            v = r.get(key)
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif v is None:
                v = ""
            elif isinstance(v, float) and v == int(v):
                v = int(v)
            elif col == "clinical_note" or col == "source":
                v = _neutralize(str(v))
            out.append(v)
        writer.writerow(out)
    return buf.getvalue()


def _neutralize(value: str) -> str:
    """Защита от CSV-инъекций при открытии в Excel: ячейка не должна начинаться с формулы."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value
