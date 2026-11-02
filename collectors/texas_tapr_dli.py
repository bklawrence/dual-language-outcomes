
#!/usr/bin/env python3
"""Collect Texas 2023-24 TAPR campus BE/ESL assessment data.

TEA's verified first steps are year=2024, all_c (all campuses), and
SASoutput Step 3 dsname=BIL1 (BE/ESL achievement). The next stages are
navigated conservatively; unfamiliar controls are saved for inspection.

Retries the TEA campus-to-SAS transition with fresh browser pages and
captures HTML/control inventories from unsuccessful attempts.

DQ = two-way dual-language assessment group; DT = one-way.
These are test-taker statistics, NOT full program enrollment counts.

Usage (existing GitHub Actions workflow):
    python3 collectors/texas_tapr_dli.py \
      --roster output/texas/tx_2024_25_all_campuses.csv \
      --out output/texas/tapr --wait-seconds 180
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/"
    "tapr_dd_download.html?year=2024"
)
GROUPS = {"DQ": "two_way_dli", "DT": "one_way_dli"}
STATS = {"N": "numerator", "D": "denominator", "R": "rate"}
CODE = re.compile(r"^[A-Z]D[QT][A-Z0-9_]+[NDR]$", re.I)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, default=str) + "\n",
        encoding="utf-8"
    )


def save_csv(path: Path, rows, columns) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="raise"
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024), b""
        ):
            digest.update(chunk)
    return digest.hexdigest()


def control_inventory(frame):
    return frame.evaluate("""() => [...document.querySelectorAll(
        'input,select,button,a')].slice(0,600).map((e,i)=>({
          index:i, tag:e.tagName, type:e.type||'', name:e.name||'',
          id:e.id||'', value:e.value||'', checked:!!e.checked,
          disabled:!!e.disabled, visible:!!(e.offsetWidth ||
              e.offsetHeight || e.getClientRects().length),
          label:(e.labels?.[0]?.innerText ||
                 e.getAttribute('aria-label') ||
                 e.parentElement?.innerText || '')
                 .replace(/\\s+/g,' ').slice(0,180),
          options:e.tagName==='SELECT'
              ? [...e.options].map(o=>({label:o.label,value:o.value,
                  selected:o.selected})).slice(0,250) : undefined
        }))""")


def step_value(frame) -> str:
    try:
        field = frame.locator('input[name="step"]')
        return (
            field.first.input_value(timeout=1500)
            if field.count()
            else ""
        )
    except Exception:
        return ""


def capture(frame, out: Path, label: str, log: dict) -> None:
    """Always preserve TEA response before guessing or retrying."""
    record = {
        "label": label,
        "utc": datetime.now(timezone.utc).isoformat()
    }

    try:
        record["url"] = frame.url
        record["step"] = step_value(frame)
        record["body_excerpt"] = frame.locator("body").inner_text(
            timeout=3000
        )[:600]

        (out / f"tx_tapr_{label}.html").write_text(
            frame.content(),
            encoding="utf-8"
        )

        save_json(
            out / f"tx_tapr_{label}_controls.json",
            control_inventory(frame)
        )

    except Exception as exc:
        record["capture_error"] = str(exc)[:500]

    log["stages"].append(record)
    save_json(out / "tx_tapr_download_debug.json", log)


def start_campus(page, log: dict, attempt: int) -> None:
    response = page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    status = response.status if response else None

    log["events"].append({
        "attempt": attempt,
        "main_http_status": status
    })

    if status != 200:
        raise RuntimeError(
            f"TEA main page returned HTTP {status}"
        )

    page.locator("#ccyy").wait_for(
        state="visible",
        timeout=15000
    )

    page.locator("#ccyy").select_option(value="2024")
    page.locator("#tapr").select_option(value="all_c")

    log["events"].append({
        "attempt": attempt,
        "selected_year": "2024",
        "selected_type": "all_c"
    })


def wait_for_bil1(
    page,
    out: Path,
    log: dict,
    attempt: int,
    timeout=40
):
    deadline = time.monotonic() + timeout
    frame = None
    previous_url = None

    while time.monotonic() < deadline:
        frame = page.frame(name="SASoutput")

        if frame:
            try:
                if frame.url != previous_url:
                    log["events"].append({
                        "attempt": attempt,
                        "iframe_url": frame.url
                    })
                    previous_url = frame.url

                if frame.locator(
                    'input[name="dsname"][value="BIL1"]'
                ).count() == 1:
                    capture(
                        frame,
                        out,
                        f"attempt{attempt}_BIL1_ready",
                        log
                    )
                    return frame

            except Exception as exc:
                log["events"].append({
                    "attempt": attempt,
                    "iframe_poll_error": str(exc)[:300]
                })

        page.wait_for_timeout(700)

    capture(
        frame if frame else page,
        out,
        f"attempt{attempt}_SAS_not_ready",
        log
    )

    log["events"].append({
        "attempt": attempt,
        "result": "BIL1_not_found",
        "last_iframe_url": frame.url if frame else None
    })

    save_json(out / "tx_tapr_download_debug.json", log)
    return None


def next_button(frame):
    """Return unique Next/Continue submit control."""

    controls = frame.locator(
        'input[type="submit"],button[type="submit"]'
    )

    candidates = []

    for i in range(controls.count()):
        control = controls.nth(i)

        desc = (
            (control.get_attribute("value") or "")
            + " "
            + (control.inner_text(timeout=2000) or "")
        )

        if re.search(r"next|continue", desc, re.I):
            candidates.append(i)

    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one Next/Continue control; "
            f"found {candidates}"
        )

    return controls.nth(candidates[0])


def advance(
    frame,
    page,
    out: Path,
    log: dict,
    label: str
):
    before_step = step_value(frame)
    before_url = frame.url
    before_html = frame.content()

    next_button(frame).click(timeout=20000)

    for _ in range(65):
        page.wait_for_timeout(600)
        current = page.frame(name="SASoutput")

        if not current:
            continue

        try:
            changed = (
                step_value(current) != before_step
                or current.url != before_url
                or current.content() != before_html
            )

            if changed:
                log["events"].append({
                    "advance": label,
                    "from_step": before_step,
                    "to_step": step_value(current)
                })

                capture(current, out, label, log)
                return current

        except Exception:
            pass

    current = page.frame(name="SASoutput")

    capture(
        current if current else page,
        out,
        label + "_timeout",
        log
    )

    raise RuntimeError(
        f"TEA did not advance after {label}"
    )


def select_csv_format(frame, log: dict) -> bool:
    """Select an explicitly labeled CSV option."""

    changed = False
    dropdowns = frame.locator("select")

    for i in range(dropdowns.count()):
        select = dropdowns.nth(i)

        if not select.is_visible() or not select.is_enabled():
            continue

        options = select.evaluate(
            """e => [...e.options].map(o => ({
              label:o.label, value:o.value
            }))"""
        )

        matches = [
            o for o in options
            if re.search(
                r"csv|comma.delimited",
                o["label"],
                re.I
            )
        ]

        if len(matches) == 1:
            select.select_option(
                value=matches[0]["value"]
            )

            log["events"].append({
                "selected_csv": matches[0]
            })

            changed = True

    radios = frame.locator('input[type="radio"]')
    matches = []

    for i in range(radios.count()):
        radio = radios.nth(i)

        if not radio.is_visible() or not radio.is_enabled():
            continue

        label = radio.evaluate(
            """e => (
              e.labels?.[0]?.innerText ||
              e.parentElement?.innerText ||
              ''
            )"""
        )

        if re.search(
            r"csv|comma.delimited",
            label,
            re.I
        ):
            matches.append(i)

    if len(matches) == 1:
        radios.nth(matches[0]).check()

        log["events"].append({
            "selected_csv_radio": matches[0]
        })

        changed = True

    return changed


def select_fields(frame, log: dict) -> bool:
    """Choose fields when TEA presents a field checklist.

    Does not select unlabeled radio buttons or invent
    additional BE/ESL categories.
    """

    checkboxes = frame.locator(
        'input[type="checkbox"]'
    )

    available = []

    for i in range(checkboxes.count()):
        checkbox = checkboxes.nth(i)

        if (
            checkbox.is_visible()
            and checkbox.is_enabled()
        ):
            available.append(i)

    if len(available) > 200:
        raise RuntimeError(
            "Too many field checkboxes; "
            "inspect controls before selecting"
        )

    if not available:
        return False

    for i in available:
        checkboxes.nth(i).check(timeout=10000)

    log["events"].append({
        "field_checkboxes_checked": len(available)
    })

    return True


def click_export(frame, log: dict) -> bool:
    controls = frame.locator(
        'input[type="submit"],button[type="submit"]'
    )

    matches = []

    for i in range(controls.count()):
        control = controls.nth(i)

        desc = (
            (control.get_attribute("value") or "")
            + " "
            + (control.inner_text(timeout=2000) or "")
        )

        if re.search(
            r"download|export|generate|get data",
            desc,
            re.I
        ):
            matches.append(i)

    if len(matches) == 1:
        controls.nth(matches[0]).click(timeout=20000)

        log["events"].append({
            "export_submit_clicked": True
        })

        return True

    links = frame.locator("a[href]")
    candidates = []

    for i in range(links.count()):
        item = links.nth(i)

        href = item.get_attribute("href") or ""
        label = item.inner_text(timeout=2000) or ""

        file_link = re.search(
            r"\.(csv|dat|txt)([?#]|$)",
            href,
            re.I
        )

        export_link = re.fullmatch(
            r"\s*download(?: csv| data)?\s*",
            label,
            re.I
        )

        if file_link or export_link:
            candidates.append(i)

    if len(candidates) == 1:
        links.nth(candidates[0]).click(timeout=20000)

        log["events"].append({
            "export_link_clicked": True
        })

        return True

    return False


def fetch(
    out: Path,
    wait_seconds: int,
    attempts: int = 3
) -> Path:
    from playwright.sync_api import sync_playwright

    log = {
        "started_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": URL,
        "verified_category": "BIL1",
        "events": [],
        "stages": []
    }

    save_json(
        out / "tx_tapr_download_debug.json",
        log
    )

    downloads = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            context = browser.new_context(
                accept_downloads=True
            )

            try:
                frame = None
                page = None

                # Fresh page on every attempt.
                for attempt in range(1, attempts + 1):
                    trial = context.new_page()

                    trial.on(
                        "download",
                        lambda d: downloads.append(d)
                    )

                    trial.on(
                        "response",
                        lambda r, a=attempt: log[
                            "events"
                        ].append({
                            "attempt": a,
                            "sas_http_status": r.status,
                            "sas_url": r.url[:260]
                        })
                        if "/cgi/sas/broker" in r.url
                        else None
                    )

                    try:
                        start_campus(
                            trial,
                            log,
                            attempt
                        )

                        stage3 = wait_for_bil1(
                            trial,
                            out,
                            log,
                            attempt
                        )

                        if stage3:
                            page = trial
                            frame = stage3
                            break

                    except Exception as exc:
                        log["events"].append({
                            "attempt": attempt,
                            "error": (
                                f"{type(exc).__name__}: "
                                f"{exc}"
                            )[:450]
                        })

                    save_json(
                        out / "tx_tapr_download_debug.json",
                        log
                    )

                    trial.close()

                    if attempt < attempts:
                        time.sleep(2 * attempt)

                if not frame:
                    raise RuntimeError(
                        f"BIL1 form not loaded after "
                        f"{attempts} attempts; see "
                        "tx_tapr_attempt*_SAS_not_ready.html "
                        "and debug JSON"
                    )

                # Step 3: verified BE/ESL category.
                category = frame.locator(
                    'input[name="dsname"][value="BIL1"]'
                )

                category.check(timeout=15000)

                if not category.is_checked():
                    raise RuntimeError(
                        "BIL1 selection did not persist"
                    )

                capture(
                    frame,
                    out,
                    "step3_BIL1_selected",
                    log
                )

                frame = advance(
                    frame,
                    page,
                    out,
                    log,
                    "step4_after_BIL1"
                )

                # Later steps: only proceed when
                # controls are identifiable.
                for stage in range(4, 10):
                    if downloads:
                        break

                    capture(
                        frame,
                        out,
                        f"step{stage}_before_selection",
                        log
                    )

                    if click_export(frame, log):
                        break

                    picked = select_fields(
                        frame,
                        log
                    )

                    picked = (
                        select_csv_format(frame, log)
                        or picked
                    )

                    if not picked:
                        raise RuntimeError(
                            "TEA Step "
                            f"{step_value(frame) or stage} "
                            "needs an unrecognized selection. "
                            "Inspect "
                            f"tx_tapr_step{stage}_"
                            "before_selection_controls.json"
                        )

                    capture(
                        frame,
                        out,
                        f"step{stage}_selected",
                        log
                    )

                    frame = advance(
                        frame,
                        page,
                        out,
                        log,
                        f"step{stage + 1}_after_next"
                    )

                deadline = (
                    time.monotonic() + wait_seconds
                )

                while (
                    not downloads
                    and time.monotonic() < deadline
                ):
                    page.wait_for_timeout(750)

                if not downloads:
                    capture(
                        page.frame(name="SASoutput") or page,
                        out,
                        "final_no_download",
                        log
                    )

                    raise RuntimeError(
                        "TEA did not start a download; "
                        "see final controls"
                    )

                download = downloads[0]

                suffix = Path(
                    download.suggested_filename
                ).suffix.lower()

                if suffix not in (
                    ".csv",
                    ".txt",
                    ".dat"
                ):
                    suffix = ".bin"

                destination = out / (
                    "tx_tapr_2023_24_campus_raw"
                    + suffix
                )

                download.save_as(
                    str(destination)
                )

                log["suggested_filename"] = (
                    download.suggested_filename
                )

                log["download_bytes"] = (
                    destination.stat().st_size
                )

                with destination.open("rb") as f:
                    head = (
                        f.read(300)
                        .lstrip()
                        .lower()
                    )

                if (
                    destination.stat().st_size < 200
                    or head.startswith((
                        b"<html",
                        b"<!doctype"
                    ))
                ):
                    raise RuntimeError(
                        "Downloaded TEA response "
                        "is empty or HTML"
                    )

                return destination

            finally:
                context.close()
                browser.close()

    except Exception as exc:
        log["error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        raise

    finally:
        save_json(
            out / "tx_tapr_download_debug.json",
            log
        )


def parse_download(
    path: Path,
    out: Path,
    roster: Path
) -> dict:
    if path.suffix.lower() not in (
        ".csv",
        ".txt",
        ".dat"
    ):
        raise ValueError(
            "TEA returned unsupported file type "
            f"{path.suffix}"
        )

    delimiter = (
        "\t"
        if path.suffix.lower() in (
            ".txt",
            ".dat"
        )
        else ","
    )

    with roster.open(
        newline="",
        encoding="utf-8-sig"
    ) as f:
        rows = csv.DictReader(f)

        if "texas_campus_id" not in (
            rows.fieldnames or []
        ):
            raise ValueError(
                "Texas roster has no texas_campus_id"
            )

        roster_ids = {
            r["texas_campus_id"].strip()
            for r in rows
        }

    with path.open(
        newline="",
        encoding="utf-8-sig",
        errors="replace"
    ) as f:
        reader = csv.reader(
            f,
            delimiter=delimiter
        )

        initial = [
            next(reader, [])
            for _ in range(5)
        ]

        ranks = [
            (
                sum(
                    bool(
                        CODE.fullmatch(c.strip())
                    )
                    for c in row
                ),
                i
            )
            for i, row in enumerate(initial)
        ]

        number_of_codes, header_index = max(ranks)

        if number_of_codes == 0:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "sample_rows": [
                        r[:80]
                        for r in initial
                    ],
                    "sample_widths": [
                        len(r)
                        for r in initial
                    ]
                }
            )

            raise ValueError(
                "No DQ/DT variables found; "
                "inspect header audit"
            )

        f.seek(0)

        reader = csv.reader(
            f,
            delimiter=delimiter
        )

        for _ in range(header_index):
            next(reader)

        headers = next(reader)

        selected = [
            (
                i,
                c.strip(),
                GROUPS[
                    c.strip()[1:3].upper()
                ],
                STATS[
                    c.strip()[-1].upper()
                ]
            )
            for i, c in enumerate(headers)
            if CODE.fullmatch(c.strip())
        ]

        id_index = next(
            (
                i
                for i, c in enumerate(headers)
                if re.search(
                    r"campus.*(?:id|number)|^campus$",
                    c,
                    re.I
                )
            ),
            0
        )

        save_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_dictionary.csv"
            ),
            [
                {
                    "variable_code": code,
                    "student_group": group,
                    "statistic": stat
                }
                for _, code, group, stat in selected
            ],
            [
                "variable_code",
                "student_group",
                "statistic"
            ]
        )

        columns = [
            "texas_campus_id",
            "school_year",
            "student_group",
            "variable_code",
            "statistic",
            "raw_value",
            "numeric_value",
            "value_status",
            "in_roster"
        ]

        seen = defaultdict(
            lambda: {
                "one_way_dli": set(),
                "two_way_dli": set()
            }
        )

        counts = Counter()
        source_rows = 0
        invalid_ids = 0

        with gzip.open(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_values.csv.gz"
            ),
            "wt",
            encoding="utf-8",
            newline=""
        ) as fz:
            writer = csv.DictWriter(
                fz,
                fieldnames=columns
            )

            writer.writeheader()

            for row in reader:
                if (
                    not row
                    or len(row) <= id_index
                ):
                    continue

                source_rows += 1

                cid = (
                    row[id_index]
                    .strip()
                    .lstrip("'\u2019")
                )

                if not re.fullmatch(
                    r"\d{9}",
                    cid
                ):
                    invalid_ids += 1
                    continue

                for i, code, group, stat in selected:
                    raw = (
                        row[i].strip()
                        if i < len(row)
                        else ""
                    )

                    if not raw:
                        continue

                    number = raw.replace(
                        ",",
                        ""
                    )

                    valid = bool(
                        re.fullmatch(
                            r"\d+(?:\.\d+)?",
                            number
                        )
                    )

                    writer.writerow({
                        "texas_campus_id": cid,
                        "school_year": "2023-24",
                        "student_group": group,
                        "variable_code": code,
                        "statistic": stat,
                        "raw_value": raw,
                        "numeric_value": (
                            number if valid else ""
                        ),
                        "value_status": (
                            "numeric"
                            if valid
                            else "masked_or_other"
                        ),
                        "in_roster": (
                            "yes"
                            if cid in roster_ids
                            else "no"
                        )
                    })

                    counts[
                        (
                            group,
                            stat,
                            (
                                "numeric"
                                if valid
                                else "masked_or_other"
                            )
                        )
                    ] += 1

                    if (
                        stat == "denominator"
                        and valid
                        and float(number) > 0
                    ):
                        seen[cid][group].add(code)

        save_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_campus_evidence.csv"
            ),
            [
                {
                    "texas_campus_id": cid,
                    "school_year": "2023-24",
                    "one_way_positive_denominator_variables": (
                        len(g["one_way_dli"])
                    ),
                    "two_way_positive_denominator_variables": (
                        len(g["two_way_dli"])
                    ),
                    "in_2024_25_campus_roster": (
                        "yes"
                        if cid in roster_ids
                        else "no"
                    )
                }
                for cid, g in sorted(seen.items())
            ],
            [
                "texas_campus_id",
                "school_year",
                "one_way_positive_denominator_variables",
                "two_way_positive_denominator_variables",
                "in_2024_25_campus_roster"
            ]
        )

        report = {
            "status": "extracted",
            "source_file": str(path),
            "source_sha256": sha256(path),
            "source_rows": source_rows,
            "invalid_campus_ids": invalid_ids,
            "header_row": header_index + 1,
            "DLI_fields": len(selected),
            "campuses_with_positive_assessment_denominators": (
                len(seen)
            ),
            "metric_status_counts": {
                "|".join(k): v
                for k, v in sorted(counts.items())
            },
            "caution": (
                "Test-taker groups are not full "
                "program enrollment. Suppressed "
                "or missing values are not zeros."
            )
        }

        save_json(
            out / "tx_tapr_2023_24_report.json",
            report
        )

        return report


def main():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--out",
        type=Path,
        default=Path("output/texas/tapr")
    )

    p.add_argument(
        "--roster",
        type=Path,
        default=Path(
            "output/texas/"
            "tx_2024_25_all_campuses.csv"
        )
    )

    p.add_argument(
        "--input",
        type=Path,
        help=(
            "Use a previously downloaded "
            "official TAPR CSV/TXT"
        )
    )

    p.add_argument(
        "--wait-seconds",
        type=int,
        default=180
    )

    p.add_argument(
        "--attempts",
        type=int,
        default=3
    )

    args = p.parse_args()

    args.out.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        source = (
            args.input
            or fetch(
                args.out,
                args.wait_seconds,
                args.attempts
            )
        )

        print(
            json.dumps(
                parse_download(
                    source,
                    args.out,
                    args.roster
                ),
                indent=2
            )
        )

    except Exception as exc:
        save_json(
            args.out / "tx_tapr_collector_failure.json",
            {
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "traceback": (
                    traceback.format_exc()[-4500:]
                ),
                "source_url": URL
            }
        )

        raise


if __name__ == "__main__":
    main()
