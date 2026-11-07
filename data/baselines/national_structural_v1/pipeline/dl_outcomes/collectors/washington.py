"""Bounded public Washington pilot, with immutable bytes and query metadata."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def capture(destination: Path, key: str, dataset: str, query: dict):
    raw_path = destination / (key + ".json")
    meta_path = destination / (key + ".metadata.json")
    if raw_path.exists() or meta_path.exists():
        if not raw_path.exists() or not meta_path.exists():
            raise ValueError(f"Incomplete cached source: {raw_path}")
        meta = json.loads(meta_path.read_text())
        if hashlib.sha256(raw_path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Source hash mismatch: {raw_path}")
        if meta["dataset_id"] != dataset or meta["selection"] != query:
            raise ValueError("Cached selection differs from the requested pilot. Use a new vintage directory; existing snapshots are never overwritten.")
        return meta
    url = f"https://data.wa.gov/resource/{dataset}.json?" + urlencode(query)
    request = Request(url, headers={"User-Agent": "DualLanguageOutcomesResearch/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=55) as response:
        raw = response.read()
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"Expected nonempty public source records: {url}")
    if len(rows) >= int(query["$limit"]):
        raise ValueError("Pilot source safety limit reached; refine the selection or paginate before accepting completeness")
    meta = {"url": url, "dataset_url": f"https://data.wa.gov/d/{dataset}", "dataset_id": dataset,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows), "selection": query, "completeness": "complete for the recorded pilot selection; not statewide outcome coverage"}
    destination.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def collect(root: Path, destination: Path | None = None):
    config = json.loads((root / "config/states/wa.json").read_text())
    destination = destination or root / config["pilot"]["raw_directory"]
    if destination.resolve().parent != (root / "data/raw/wa").resolve():
        raise ValueError("Use a vintage directory directly under data/raw/wa so offline builds can discover it")
    schools = ",".join("'" + str(x) + "'" for x in config["pilot"]["outcome_school_ids"])
    years = ",".join("'" + x + "'" for x in config["pilot"]["school_years"])
    select = f"organizationlevel='School' AND schoolorganizationid in({schools}) AND schoolyear in({years})"
    specs = [
        ("programs", "d4w4-82bk", {"$where": "organizationlevel='School'", "$limit": 10000, "$order": "schoolyear,schoolorganizationid,rowid"}),
        ("academics", "9fjj-2374", {"$where": select + " AND gradelevel in('03','04','05') AND testadministration='SBAC' AND studentgroup in('All Students','English Language Learners','English Learners','Former English Language Learners','Non-English Language Learners')", "$limit": 10000, "$order": "schoolyear,schoolorganizationid,gradelevel,testsubject,studentgroup"}),
        ("demographics", "rxjk-6ieq", {"$where": select, "$limit": 10000, "$order": "schoolyear,schoolorganizationid,gradelevel"}),
    ]
    results = []
    for key, dataset, query in specs:
        meta = capture(destination, key, dataset, query)
        results.append({"source": key, "rows": meta["rows"], "sha256": meta["sha256"]})
    return results
