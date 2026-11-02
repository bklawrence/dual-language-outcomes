
#!/usr/bin/env python3
"""Texas 2023-24 TAPR campus BE/ESL (BIL1) collector.

First tries TEA's observed Step-3 SAS GET URL. If unavailable, opens
TEA's landing page and chooses year 2024 / all_c (campuses). Next chooses
BIL1 on TEA's own form. Later steps are handled only when their controls
are unambiguous; otherwise HTML + controls are saved for diagnosis.

DQ = two-way DLI; DT = one-way DLI. These are assessment subgroup
statistics, NOT full DLI enrollment or definitive campus program listings.
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
from urllib.parse import urlencode


LANDING_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/"
    "tapr_dd_download.html?year=2024"
)

DIRECT_URL = (
    "https://rptsvr1.tea.texas.gov/cgi/sas/broker?"
    + urlencode({
        "_service": "marykay",
        "_program": "perfrept.perfmast.sas",
        "_debug": "0",
        "ccyy": "2024",
        "tapr": "all_c",
        "prgopt": "reports/tapr/dd/dd_tapr.sas",
    })
)

CODE = re.compile(
    r"^[A-Z]D[QT][A-Z0-9_]+[NDR]$",
    re.I,
)

GROUP = {
    "DQ": "two_way_dli",
    "DT": "one_way_dli",
}

STAT = {
    "N": "numerator",
    "D": "denominator",
    "R": "rate",
}

YEAR = "2023-24"


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=columns,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as fh:
        for chunk in iter(
            lambda: fh.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def controls(frame):
    return frame.evaluate(
        """() => [...document.querySelectorAll(
          'input,select,button,a'
        )].slice(0,600).map((e,i)=>({
          index:i,
          tag:e.tagName,
          type:e.type||'',
          id:e.id||'',
          name:e.name||'',
          value:e.value||'',
          checked:!!e.checked,
          disabled:!!e.disabled,
          label:(
            e.labels?.[0]?.innerText ||
            e.getAttribute('aria-label') ||
            e.parentElement?.innerText ||
            ''
          ).replace(/\\s+/g,' ').slice(0,160),
          options:e.tagName==='SELECT'
            ? [...e.options].map(o=>({
                label:o.label,
                value:o.value,
                selected:o.selected
              })).slice(0,250)
            : undefined
        }))"""
    )


def current_frame(page, route):
    if route == "direct_sas":
        return page.main_frame

    return page.frame(name="SASoutput")


def step_value(frame):
    try:
        x = frame.locator('input[name="step"]')

        return (
            x.first.input_value(timeout=1200)
            if x.count()
            else ""
        )

    except Exception:
        return ""


def capture(frame, out, name, log):
    entry = {
        "name": name,
        "utc": datetime.now(timezone.utc).isoformat(),
    }

    if frame:
        try:
            entry["url"] = frame.url
            entry["step"] = step_value(frame)

            entry["body_excerpt"] = (
                frame.locator("body")
                .inner_text(timeout=3000)[:500]
            )

            (out / f"tx_tapr_{name}.html").write_text(
                frame.content(),
                encoding="utf-8",
            )

            save_json(
                out / f"tx_tapr_{name}_controls.json",
                controls(frame),
            )

        except Exception as exc:
            entry["capture_error"] = (
                f"{type(exc).__name__}: {exc}"
            )[:400]

    log["captures"].append(entry)

    save_json(
        out / "tx_tapr_download_debug.json",
        log,
    )


def wait_for_step3(page, route, seconds):
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        frame = current_frame(page, route)

        if frame:
            try:
                selector = frame.locator(
                    'input[name="dsname"][value="BIL1"]'
                )

                if selector.count() == 1:
                    return frame

            except Exception:
                pass

        page.wait_for_timeout(700)

    return None


def next_button(frame):
    candidates = frame.locator(
        'input[type="submit"],'
        'button[type="submit"]'
    )

    matches = []

    for i in range(candidates.count()):
        el = candidates.nth(i)

        label = (
            (el.get_attribute("value") or "")
            + " "
            + (el.inner_text() or "")
        )

        if re.search(
            r"next|continue",
            label,
            re.I,
        ):
            matches.append(i)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected one Next/Continue button; "
            f"found {len(matches)}"
        )

    return candidates.nth(matches[0])


def advance(page, frame, route, out, log, name):
    old_url = frame.url
    old_step = step_value(frame)
    old_html = frame.content()

    next_button(frame).click(timeout=20000)

    for _ in range(65):
        page.wait_for_timeout(500)

        frame = current_frame(page, route)

        if not frame:
            continue

        try:
            changed = (
                frame.url != old_url
                or step_value(frame) != old_step
                or frame.content() != old_html
            )

            if changed:
                capture(frame, out, name, log)
                return frame

        except Exception:
            pass

    capture(
        current_frame(page, route),
        out,
        name + "_timeout",
        log,
    )

    raise RuntimeError(
        f"TEA did not advance from {name}; "
        "see saved controls"
    )


def choose_fields_and_format(frame, log):
    """No guessed radio selections.

    Only visible checkboxes and explicit CSV options.
    """
    selected = False

    checks = frame.locator(
        'input[type="checkbox"]'
    )

    visible = [
        checks.nth(i)
        for i in range(checks.count())
        if (
            checks.nth(i).is_visible()
            and checks.nth(i).is_enabled()
        )
    ]

    if len(visible) > 200:
        raise RuntimeError(
            "Too many fields to select safely"
        )

    for checkbox in visible:
        checkbox.check(timeout=10000)
        selected = True

    if visible:
        log["events"].append({
            "checked_fields": len(visible),
        })

    dropdowns = frame.locator("select")

    for i in range(dropdowns.count()):
        selector = dropdowns.nth(i)

        if (
            not selector.is_visible()
            or not selector.is_enabled()
        ):
            continue

        options = selector.evaluate(
            """e => [...e.options].map(o => ({
                label:o.label,
                value:o.value
            }))"""
        )

        csv_options = [
            o for o in options
            if re.search(
                r"csv|comma.delimited",
                o["label"],
                re.I,
            )
        ]

        if len(csv_options) == 1:
            selector.select_option(
                value=csv_options[0]["value"]
            )

            log["events"].append({
                "csv_option": csv_options[0],
            })

            selected = True

    radios = frame.locator(
        'input[type="radio"]'
    )

    csv_radio = []

    for i in range(radios.count()):
        radio = radios.nth(i)

        if (
            radio.is_visible()
            and radio.is_enabled()
        ):
            label = radio.evaluate(
                """e =>
                    e.labels?.[0]?.innerText ||
                    e.parentElement?.innerText ||
                    ''
                """
            )

            if re.search(
                r"csv|comma.delimited",
                label,
                re.I,
            ):
                csv_radio.append(i)

    if len(csv_radio) == 1:
        radios.nth(csv_radio[0]).check()
        selected = True

        log["events"].append({
            "csv_radio": csv_radio[0],
        })

    return selected


def click_export(frame, log):
    submits = frame.locator(
        'input[type="submit"],'
        'button[type="submit"]'
    )

    matches = []

    for i in range(submits.count()):
        el = submits.nth(i)

        label = (
            (el.get_attribute("value") or "")
            + " "
            + (el.inner_text() or "")
        )

        if re.search(
            r"download|export|generate|get data",
            label,
            re.I,
        ):
            matches.append(i)

    if len(matches) == 1:
        submits.nth(matches[0]).click(
            timeout=20000
        )

        log["events"].append({
            "clicked_export_submit": True,
        })

        return True

    links = frame.locator('a[href]')
    matches = []

    for i in range(links.count()):
        el = links.nth(i)

        href = el.get_attribute("href") or ""
        label = el.inner_text() or ""

        file_link = re.search(
            r"\.(csv|dat|txt)(\?|#|$)",
            href,
            re.I,
        )

        export_link = re.fullmatch(
            r"\s*download( csv| data)?\s*",
            label,
            re.I,
        )

        if file_link or export_link:
            matches.append(i)

    if len(matches) == 1:
        links.nth(matches[0]).click(
            timeout=20000
        )

        log["events"].append({
            "clicked_export_link": True,
        })

        return True

    return False


def fetch(out, wait_seconds, attempts):
    from playwright.sync_api import sync_playwright

    log = {
        "started_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "direct_url": DIRECT_URL,
        "landing_url": LANDING_URL,
        "events": [],
        "captures": [],
        "selected_category": "BIL1",
    }

    save_json(
        out / "tx_tapr_download_debug.json",
        log,
    )

    downloads = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            context = browser.new_context(
                accept_downloads=True,
            )

            # Use a normal callback, not list.append directly.
            # This fixes the Playwright event handler error.
            context.on(
                "page",
                lambda p: p.on(
                    "download",
                    lambda d: downloads.append(d),
                ),
            )

            try:
                page = None
                frame = None
                route_used = None

                # Each attempt uses a fresh page.
                # Try direct SAS first, then landing page.
                for attempt in range(1, attempts + 1):
                    routes = (
                        ("direct_sas", DIRECT_URL),
                        ("landing_page", LANDING_URL),
                    )

                    for route, url in routes:
                        trial = context.new_page()

                        trial.on(
                            "response",
                            lambda resp, a=attempt, r=route:
                                log["events"].append({
                                    "attempt": a,
                                    "route": r,
                                    "sas_http_status": resp.status,
                                    "sas_url": resp.url[:240],
                                })
                                if "/cgi/sas/broker" in resp.url
                                else None,
                        )

                        try:
                            response = trial.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=35000,
                            )

                            status = (
                                response.status
                                if response
                                else None
                            )

                            log["events"].append({
                                "attempt": attempt,
                                "route": route,
                                "http_status": status,
                            })

                            if status != 200:
                                raise RuntimeError(
                                    f"HTTP {status}"
                                )

                            if route == "landing_page":
                                trial.locator(
                                    "#ccyy"
                                ).select_option(
                                    value="2024"
                                )

                                trial.locator(
                                    "#tapr"
                                ).select_option(
                                    value="all_c"
                                )

                            candidate = wait_for_step3(
                                trial,
                                route,
                                seconds=35,
                            )

                            if candidate is None:
                                capture(
                                    current_frame(
                                        trial, route
                                    ) or trial.main_frame,
                                    out,
                                    f"attempt{attempt}_"
                                    f"{route}_not_ready",
                                    log,
                                )

                                raise RuntimeError(
                                    "BIL1 form not returned"
                                )

                            capture(
                                candidate,
                                out,
                                f"attempt{attempt}_"
                                f"{route}_BIL1_ready",
                                log,
                            )

                            page = trial
                            frame = candidate
                            route_used = route

                            break

                        except Exception as exc:
                            log["events"].append({
                                "attempt": attempt,
                                "route": route,
                                "error": (
                                    f"{type(exc).__name__}: "
                                    f"{exc}"
                                )[:500],
                            })

                            save_json(
                                out / "tx_tapr_download_debug.json",
                                log,
                            )

                            trial.close()

                    if frame is not None:
                        break

                    if attempt < attempts:
                        time.sleep(2 * attempt)

                if frame is None:
                    raise RuntimeError(
                        "Both TEA routes failed; "
                        "see diagnostic JSON/HTML"
                    )

                log["route_used"] = route_used

                # Step 3: BE/ESL achievement.
                bil1 = frame.locator(
                    'input[name="dsname"][value="BIL1"]'
                )

                bil1.check(timeout=15000)

                if not bil1.is_checked():
                    raise RuntimeError(
                        "BIL1 was not selected"
                    )

                frame = advance(
                    page,
                    frame,
                    route_used,
                    out,
                    log,
                    "step4_after_BIL1",
                )

                # Later steps only when controls
                # can be identified reliably.
                for stage in range(4, 10):
                    if downloads:
                        break

                    capture(
                        frame,
                        out,
                        f"step{stage}_before_selection",
                        log,
                    )

                    if click_export(frame, log):
                        break

                    if not choose_fields_and_format(
                        frame, log
                    ):
                        raise RuntimeError(
                            "Unrecognized TEA Step "
                            f"{step_value(frame) or stage} "
                            "controls; inspect "
                            f"step{stage}_"
                            "before_selection_controls.json"
                        )

                    capture(
                        frame,
                        out,
                        f"step{stage}_selected",
                        log,
                    )

                    frame = advance(
                        page,
                        frame,
                        route_used,
                        out,
                        log,
                        f"step{stage + 1}_after_next",
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
                        current_frame(
                            page, route_used
                        ) or page.main_frame,
                        out,
                        "final_no_download",
                        log,
                    )

                    raise RuntimeError(
                        "No TEA download event; "
                        "inspect saved controls"
                    )

                download = downloads[0]

                suffix = Path(
                    download.suggested_filename
                ).suffix.lower()

                if suffix not in (
                    ".csv", ".txt", ".dat"
                ):
                    suffix = ".bin"

                dest = out / (
                    "tx_tapr_2023_24_campus_raw"
                    + suffix
                )

                download.save_as(str(dest))

                log["download_original_name"] = (
                    download.suggested_filename
                )

                log["download_bytes"] = (
                    dest.stat().st_size
                )

                with dest.open("rb") as fh:
                    prefix = (
                        fh.read(300).lstrip().lower()
                    )

                if (
                    dest.stat().st_size < 200
                    or prefix.startswith((
                        b"<html",
                        b"<!doctype",
                    ))
                ):
                    raise RuntimeError(
                        "TEA download was empty or HTML"
                    )

                return dest

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
            log,
        )


def parse_download(path, out, roster):
    """Keep raw variable codes, mask indicators and all reported values."""

    if path.suffix.lower() not in (
        ".csv", ".txt", ".dat"
    ):
        raise ValueError(
            "Unsupported downloaded file type: "
            f"{path.suffix}"
        )

    sep = (
        "\t"
        if path.suffix.lower() in (".txt", ".dat")
        else ","
    )

    with roster.open(
        newline="",
        encoding="utf-8-sig",
    ) as fh:
        rows = csv.DictReader(fh)

        if "texas_campus_id" not in (
            rows.fieldnames or []
        ):
            raise ValueError(
                "Roster missing texas_campus_id"
            )

        roster_ids = {
            r["texas_campus_id"].strip()
            for r in rows
        }

    with path.open(
        newline="",
        encoding="utf-8-sig",
        errors="replace",
    ) as fh:
        reader = csv.reader(
            fh,
            delimiter=sep,
        )

        head = [
            next(reader, [])
            for _ in range(5)
        ]

        counts = [
            (
                sum(
                    bool(CODE.fullmatch(c.strip()))
                    for c in row
                ),
                i,
            )
            for i, row in enumerate(head)
        ]

        matched, header_idx = max(counts)

        if matched == 0:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "first_rows": [
                        r[:80] for r in head
                    ],
                    "column_counts": [
                        len(r) for r in head
                    ],
                },
            )

            raise ValueError(
                "No DQ/DT variable codes "
                "in first five rows"
            )

        fh.seek(0)

        reader = csv.reader(
            fh,
            delimiter=sep,
        )

        for _ in range(header_idx):
            next(reader)

        columns = next(reader)

        variables = [
            (
                i,
                c.strip(),
                GROUP[
                    c.strip()[1:3].upper()
                ],
                STAT[
                    c.strip()[-1].upper()
                ],
            )
            for i, c in enumerate(columns)
            if CODE.fullmatch(c.strip())
        ]

        id_cols = [
            i
            for i, c in enumerate(columns)
            if re.search(
                r"campus.*(?:id|number)|^campus$",
                c,
                re.I,
            )
        ]

        if len(id_cols) != 1:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "header_sample": columns[:100],
                    "id_column_matches": id_cols,
                },
            )

            raise ValueError(
                "Cannot identify unique "
                "campus ID column"
            )

        id_index = id_cols[0]

        write_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_dictionary.csv"
            ),
            [
                {
                    "variable_code": code,
                    "student_group": group,
                    "statistic": stat,
                }
                for _, code, group, stat in variables
            ],
            [
                "variable_code",
                "student_group",
                "statistic",
            ],
        )

        fields = [
            "texas_campus_id",
            "school_year",
            "student_group",
            "variable_code",
            "statistic",
            "raw_value",
            "numeric_value",
            "value_status",
            "in_roster",
        ]

        positive = defaultdict(
            lambda: {
                "one_way_dli": set(),
                "two_way_dli": set(),
            }
        )

        stats = Counter()
        rows_seen = 0
        bad_ids = 0

        with gzip.open(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_values.csv.gz"
            ),
            "wt",
            encoding="utf-8",
            newline="",
        ) as gz:
            writer = csv.DictWriter(
                gz,
                fieldnames=fields,
            )

            writer.writeheader()

            for row in reader:
                if (
                    not row
                    or len(row) <= id_index
                ):
                    continue

                rows_seen += 1

                cid = (
                    row[id_index]
                    .strip()
                    .lstrip("'\u2019")
                )

                if not re.fullmatch(
                    r"\d{9}",
                    cid,
                ):
                    bad_ids += 1
                    continue

                for (
                    i, code, group, stat
                ) in variables:
                    raw = (
                        row[i].strip()
                        if i < len(row)
                        else ""
                    )

                    if not raw:
                        continue

                    numeric_value = (
                        raw.replace(",", "")
                    )

                    usable = bool(
                        re.fullmatch(
                            r"\d+(?:\.\d+)?",
                            numeric_value,
                        )
                    )

                    status = (
                        "numeric"
                        if usable
                        else "masked_or_other"
                    )

                    writer.writerow({
                        "texas_campus_id": cid,
                        "school_year": YEAR,
                        "student_group": group,
                        "variable_code": code,
                        "statistic": stat,
                        "raw_value": raw,
                        "numeric_value": (
                            numeric_value
                            if usable
                            else ""
                        ),
                        "value_status": status,
                        "in_roster": (
                            "yes"
                            if cid in roster_ids
                            else "no"
                        ),
                    })

                    stats[
                        (group, stat, status)
                    ] += 1

                    if (
                        stat == "denominator"
                        and usable
                        and float(numeric_value) > 0
                    ):
                        positive[cid][group].add(
                            code
                        )

        write_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_campus_evidence.csv"
            ),
            [
                {
                    "texas_campus_id": cid,
                    "school_year": YEAR,
                    "one_way_positive_denominator_variables":
                        len(g["one_way_dli"]),
                    "two_way_positive_denominator_variables":
                        len(g["two_way_dli"]),
                    "in_2024_25_campus_roster": (
                        "yes"
                        if cid in roster_ids
                        else "no"
                    ),
                }
                for cid, g in sorted(
                    positive.items()
                )
            ],
            [
                "texas_campus_id",
                "school_year",
                "one_way_positive_denominator_variables",
                "two_way_positive_denominator_variables",
                "in_2024_25_campus_roster",
            ],
        )

        report = {
            "status": "extracted",
            "source_file": str(path),
            "source_sha256": sha256(path),
            "source_rows": rows_seen,
            "invalid_campus_ids": bad_ids,
            "header_row": header_idx + 1,
            "DLI_fields": len(variables),
            "campuses_with_positive_assessment_denominators":
                len(positive),
            "metric_status_counts": {
                "|".join(k): v
                for k, v in sorted(
                    stats.items()
                )
            },
            "caution": (
                "Test takers only; "
                "masked/missing is not zero."
            ),
        }

        save_json(
            out / "tx_tapr_2023_24_report.json",
            report,
        )

        return report


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/texas/tapr"),
    )

    parser.add_argument(
        "--roster",
        type=Path,
        default=Path(
            "output/texas/"
            "tx_2024_25_all_campuses.csv"
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        help="Existing official TAPR CSV/TXT",
    )

    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
    )

    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    args.out.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        path = (
            args.input
            or fetch(
                args.out,
                args.wait_seconds,
                args.attempts,
            )
        )

        print(
            json.dumps(
                parse_download(
                    path,
                    args.out,
                    args.roster,
                ),
                indent=2,
            )
        )

    except Exception as exc:
        save_json(
            out_path := (
                args.out /
                "tx_tapr_collector_failure.json"
            ),
            {
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "traceback":
                    traceback.format_exc()[-4500:],
                "direct_sas_url": DIRECT_URL,
                "landing_url": LANDING_URL,
            },
        )

        raise


if __name__ == "__main__":
    main()
