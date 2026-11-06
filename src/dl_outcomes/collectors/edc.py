"""Version-pinned, resumable public EDC downloads. No cross-state norming."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

VERSION = "3.1"
YEARS = (2022, 2023, 2024, 2025)
SUBJECTS = {"ela", "math", "read", "eng", "wri"}
IDENTITY_FIELDS = ["StateAbbrev", "SchYear", "NCESSchoolID", "StateAssignedSchID",
                   "NCESDistrictID", "StateAssignedDistID", "SchName", "DistName",
                   "SchType", "SchLevel"]
ATTRIBUTION = ("Data sourced from the Education Data Center (www.eddatacenter.org), "
               "a partner project of the National Center for Civic Innovation, Inc.")


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path):
    h = hashlib.md5()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch_file(cache, state, year):
    """Cache original CSV bytes and receipt; an absent release remains explicit."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    key = f"{state}_{year}"
    path, receipt = cache / (key + ".csv"), cache / (key + ".json")
    url = f"https://eddatacenter.org/api/data/{VERSION}?state={state}&year={year}"
    if receipt.exists():
        meta = json.loads(receipt.read_text())
        if meta["url"] != url:
            raise ValueError("Cached request differs: " + key)
        if meta["status"] == "not_available":
            return meta
        etag = (meta.get("etag") or "").strip('"')
        if path.exists() and sha256_file(path) == meta["sha256"] and (not re_md5(etag) or md5_file(path) == etag):
            if re_md5(etag) and not meta.get("server_md5_verified"):
                meta["server_md5_verified"] = True
                receipt.write_text(json.dumps(meta, indent=2) + "\n")
            return meta
        # A gracefully closed but incomplete HTTP stream can otherwise look
        # like a valid short CSV. Keep the failed receipt and fetch it again.
        (cache / (key + ".incomplete.json")).write_text(json.dumps(meta, indent=2) + "\n")
        for stale in [receipt, cache / (key + ".profile.json"), cache / (key + ".schools.csv")]:
            stale.unlink(missing_ok=True)
    temporary = path.with_suffix(".csv.part")
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "DualLanguageOutcomesResearch/1.0"})
            with urlopen(request, timeout=55) as response, temporary.open("wb") as output:
                fingerprint, size = hashlib.sha256(), 0
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(block)
                    fingerprint.update(block)
                    size += len(block)
                expected = response.headers.get("Content-Length")
                etag = (response.headers.get("ETag") or "").strip('"')
                output.flush()
                if expected and int(expected) != size:
                    raise OSError(f"Incomplete EDC download {key}: {size}/{expected} bytes")
                if re_md5(etag) and md5_file(temporary) != etag:
                    raise OSError("EDC download does not match server MD5: " + key)
                meta = dict(state_code=state, spring_year=year, version=VERSION,
                            url=url, resolved_url=response.url, status="downloaded",
                            retrieved_at=datetime.now(timezone.utc).isoformat(),
                            sha256=fingerprint.hexdigest(), bytes=size,
                            content_type=response.headers.get("Content-Type"),
                            etag=response.headers.get("ETag"), expected_bytes=int(expected) if expected else None,
                            server_md5_verified=bool(re_md5(etag)))
            with temporary.open(encoding="utf-8-sig", newline="") as stream:
                header = next(csv.reader(stream))
            if not set(IDENTITY_FIELDS + ["DataLevel", "Subject", "GradeLevel"]).issubset(header):
                raise ValueError("Unexpected EDC CSV header: " + key)
            temporary.replace(path)
            receipt.write_text(json.dumps(meta, indent=2) + "\n")
            return meta
        except HTTPError as exc:
            if exc.code == 404:
                meta = dict(state_code=state, spring_year=year, version=VERSION, url=url,
                            status="not_available", retrieved_at=datetime.now(timezone.utc).isoformat())
                receipt.write_text(json.dumps(meta, indent=2) + "\n")
                return meta
            if attempt == 3:
                raise
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def index_file(cache, state, year):
    """Index identities by source year; no school outcome joins are made here."""
    cache = Path(cache)
    meta = fetch_file(cache, state, year)
    if meta["status"] != "downloaded":
        return meta
    path = cache / f"{state}_{year}.csv"
    index = cache / f"{state}_{year}.schools.csv"
    profile = cache / f"{state}_{year}.profile.json"
    if index.exists() and profile.exists():
        return json.loads(profile.read_text()) | meta
    identities, subjects, groups, grades = set(), set(), set(), set()
    rows = school_rows = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            rows += 1
            if row["DataLevel"] != "School" or row["Subject"] not in SUBJECTS:
                continue
            if row["StateAbbrev"] != state or row["SchYear"] != f"{year-1}-{year%100:02d}":
                raise ValueError("State/year differs from request: " + str(path))
            school_rows += 1
            if None in row or None in row.values():
                raise ValueError(f"Ragged source CSV record {rows}: {path}")
            identities.add(tuple(row.get(f, "") for f in IDENTITY_FIELDS))
            subjects.add(row["Subject"])
            groups.add((row["StudentGroup"], row["StudentSubGroup"]))
            grades.add(row["GradeLevel"])
    with index.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(IDENTITY_FIELDS)
        writer.writerows(sorted(identities))
    result = dict(meta, all_source_rows=rows, school_language_arts_math_rows=school_rows,
                  identity_variants=len(identities), subjects=sorted(subjects),
                  grades=sorted(grades), groups=sorted(groups))
    profile.write_text(json.dumps(result, indent=2) + "\n")
    return result


def collect(root, cache=None, *, workers=4):
    """Fetch the requested years for every state represented in the school cohort."""
    root = Path(root)
    cache = Path(cache or root / ".cache/edc_v3_1")
    with (root / "data/baselines/national_structural_v1/schools.csv").open() as stream:
        states = sorted({r["state_code"] for r in csv.DictReader(stream)})
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(index_file, cache, state, year): (state, year)
                 for state in states for year in YEARS}
        for future in as_completed(tasks):
            state, year = tasks[future]
            try:
                result = future.result()
                results.append(result)
                print(json.dumps({k: result[k] for k in ["state_code", "spring_year", "status"]}
                                 | {"bytes": result.get("bytes", 0),
                                    "school_identities": result.get("identity_variants", 0)}), flush=True)
            except Exception as exc:
                failures.append(dict(state_code=state, spring_year=year, error=str(exc)))
                print(json.dumps(failures[-1]), flush=True)
    summary = dict(version=VERSION, states=states, spring_years=list(YEARS),
                   sources=sorted(results, key=lambda r: (r["state_code"], r["spring_year"])),
                   failures=failures, attribution=ATTRIBUTION)
    (cache / "collection.json").write_text(json.dumps(summary, indent=2) + "\n")
    if failures:
        raise ValueError(f"EDC requests failed: {failures}")
    return summary


def re_md5(value):
    return len(value) == 32 and all(c in "0123456789abcdef" for c in value.lower())
