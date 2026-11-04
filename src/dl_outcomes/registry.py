"""Reviewed, time-dependent identity aliases override provisional source-group keys."""
from __future__ import annotations

from .io import read_csv, school_year


class IdentityResolver:
    def __init__(self, path):
        self.rows = read_csv(path)
        for row in self.rows:
            if row["review_status"] not in {"accepted", "pending"}:
                raise ValueError("Identity mapping review_status must be accepted or pending")
            for field in ["valid_from_year", "valid_to_year"]:
                if row[field]:
                    school_year(row[field])
            if row["review_status"] == "accepted" and not row["evidence_url"]:
                raise ValueError("Accepted identity mappings need an evidence URL or repo source reference")

    def resolve(self, entity_type, namespace, native_id, year, default):
        matching = []
        for row in self.rows:
            if row["review_status"] != "accepted" or (row["entity_type"], row["namespace"], row["native_id"]) != (entity_type, namespace, str(native_id)):
                continue
            lo, hi = row["valid_from_year"], row["valid_to_year"]
            if year is None and (lo or hi):
                continue
            if year and ((lo and year < lo) or (hi and year > hi)):
                continue
            matching.append(row)
        identities = {row["research_entity_id"] for row in matching}
        if len(identities) > 1:
            raise ValueError(f"Ambiguous reviewed identity mappings: {namespace}:{native_id}, {year}")
        return next(iter(identities)) if identities else default
