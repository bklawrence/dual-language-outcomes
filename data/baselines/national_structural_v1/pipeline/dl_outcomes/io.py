"""Strict CSV I/O, nullable values, stable record keys and source hashes."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5


def record_id(kind: str, *parts) -> str:
    """Deterministic research-record key; does not claim verified entity continuity."""
    value = json.dumps([kind, *parts], ensure_ascii=False, separators=(",", ":"))
    return f"{kind}-{uuid5(NAMESPACE_URL, 'dual-language-outcomes:' + value).hex}"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path, *, legacy=False):
    """Only explicitly legacy inputs may have blank lines before their header."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if legacy:
            lines = iter(stream)
            for line in lines:
                if line.strip():
                    import itertools
                    stream = itertools.chain([line], lines)
                    break
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise ValueError(f"Missing/duplicate CSV header: {path}")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"Ragged CSV records: {path}")
    return rows


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: "" if row.get(name) is None else row.get(name, "") for name in fields})


def school_year(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", value) or int(value[-2:]) != (int(value[:4]) + 1) % 100:
        raise ValueError(f"Invalid academic year: {value!r}")
    return value


def nullable(value):
    if value is None or str(value).strip().casefold() in {"", "null", "none", "nan", "n/a", "na"}:
        return None
    return str(value).strip()


def grade_scope(value):
    text = str(value or "").strip()
    compact = re.sub(r"[\s_-]+", "", text).casefold()
    if compact in {"allgrades", "all"}:
        return "all_grades"
    if compact in {"alltestedgrades", "alltested"}:
        return "all_tested_grades"
    if compact in {"k", "kindergarten"}:
        return "K"
    if compact in {"pk", "prek", "prekindergarten"}:
        return "PK"
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?(?:grade)?", compact)
    if match and 1 <= int(match[1]) <= 12:
        return str(int(match[1]))
    raise ValueError(f"Unmapped grade scope: {value!r}; retain and review the native label")
