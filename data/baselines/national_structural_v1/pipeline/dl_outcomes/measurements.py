"""Parse published values without turning masks or bounds into point estimates."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re


def parse_value(raw, *, source_unit="number", target_unit=None):
    text = "" if raw is None else str(raw).strip()
    result = {"value_raw": text, "value_numeric": None, "value_status": "not_reported", "value_lower_bound": None, "value_upper_bound": None}
    if text.casefold() in {"", "null", "none", "nan", "n/a", "na", "not reported"}:
        return result
    if text.casefold() in {"*", "**", "***", "--", "-", "s", "suppressed", "n<10", "nr", "<n"}:
        result["value_status"] = "suppressed"
        return result
    match = re.fullmatch(r"(<=|>=|<|>|≤|≥)\s*(\d+(?:\.\d+)?)%?", text)
    multiplier = Decimal(100) if source_unit == "proportion" and target_unit == "percent" else Decimal(1)
    if match:
        result["value_status"] = "bounded"
        field = "value_upper_bound" if match[1] in {"<", "<=", "≤"} else "value_lower_bound"
        result[field] = float(Decimal(match[2]) * multiplier)
        return result
    try:
        value = Decimal(text.rstrip("%").replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Unrecognized published value: {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"Nonfinite published value: {raw!r}")
    result.update(value_numeric=float(value * multiplier), value_status="observed")
    return result


def ratio(numerator, denominator):
    """Only derive a rate from two explicitly observed, matching-population counts."""
    n, d = parse_value(numerator), parse_value(denominator)
    if n["value_status"] != "observed" or d["value_status"] != "observed":
        return {"value_raw": "", "value_numeric": None, "value_status": "not_reported", "value_lower_bound": None, "value_upper_bound": None}
    if d["value_numeric"] == 0:
        return {"value_raw": "", "value_numeric": None, "value_status": "not_applicable", "value_lower_bound": None, "value_upper_bound": None}
    if not 0 <= n["value_numeric"] <= d["value_numeric"]:
        raise ValueError("Numerator outside the reported denominator")
    result = parse_value(100 * n["value_numeric"] / d["value_numeric"])
    result["value_status"] = "derived"
    result["value_raw"] = ""
    return result
