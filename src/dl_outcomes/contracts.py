"""Load the packaged JSON Schema contracts and convert CSV cells to typed values."""
from __future__ import annotations

from importlib.resources import files
import json
import math

from jsonschema import Draft202012Validator


def catalog():
    result = json.loads(files("dl_outcomes").joinpath("schemas/catalog.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(result)
    return result


def typed_row(row, schema):
    result = {}
    for field, value in row.items():
        definition = schema["properties"].get(field, {})
        types = definition.get("type", "string")
        types = [types] if isinstance(types, str) else types
        if value == "" or value is None:
            result[field] = None
        elif "integer" in types:
            if str(value).strip() != str(int(value)):
                raise ValueError(f"{field}: not an integer: {value}")
            result[field] = int(value)
        elif "number" in types:
            result[field] = float(value)
            if not math.isfinite(result[field]):
                raise ValueError(f"{field}: nonfinite number")
        else:
            result[field] = value
    return result
