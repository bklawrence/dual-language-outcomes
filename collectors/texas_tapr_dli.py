
#!/usr/bin/env python3
"""Texas TAPR campus DLI groups: cautious browser collection and extraction.

Run in GitHub Actions with Playwright. The downloader can fail if TEA refuses
connections; it writes diagnosis rather than pretending that missing = zero.

2023-24 official TAPR advanced data: subgroup DQ (two-way), DT (one-way),
last character N/D/R for numerator/denominator/rate. This is assessment
participation, not whole-program enrollment or a program census.
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
import urllib.request

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


NEW_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/"
    "tapr_dd_download.html?year=2024"
)

OLD_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)

GROUPS = {
    "DQ": "two_way_dli",
    "DT": "one_way_dli",
}

METRICS = {
    "N": "numerator",
    "D": "denominator",
    "R": "rate",
}

# First character identifies dataset.
# Second and third identify the student group.
CODE = re.compile(
    r"^[A-Z]D([QT])[A-Z0-9_]+([NDR])$",
    re.I,
)


def save_json(path, obj):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            obj,
            indent=2,
            default=str,
        ) + "\n",
        encoding="utf-8",
    )


def csv_write(path, rows, names):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=names,
        )
        writer.writeheader()
        writer.writerows(rows)


def hash_file(path):
    h = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def controls(page):
    """Inventory form controls for diagnostics."""

    return page.evaluate(
        """() => Array.from(document.querySelectorAll(
            'select,input,button,a'
        )).slice(0,500).map((x,i)=>({
            index:i,
            tag:x.tagName,
            type:x.type||'',
            id:x.id||'',
            name:x.name||'',
            value:x.value||'',
            checked:!!x.checked,
            disabled:!!x.disabled,
            label:(
                x.labels?.[0]?.innerText ||
                x.getAttribute('aria-label') ||
                x.parentElement?.innerText ||
                ''
            ).replace(/\\s+/g,' ').slice(0,130),
            text:(x.innerText||'')
                .replace(/\\s+/g,' ').slice(0,100),
            options:x.tagName==='SELECT'
                ? Array.from(x.options).map(o=>({
                    label:o.label.trim(),
                    value:o.value,
                    selected:o.selected
                })).slice(0,250)
                : undefined
        }))"""
    )


def snapshot(page, out, name, log):
    """Save HTML, screenshot and control inventory."""

    try:
        (out / f"{name}.html").write_text(
            page.content(),
            encoding="utf-8",
        )

        page.screenshot(
            path=str(out / f"{name}.png"),
            full_page=True,
            timeout=12000,
        )

        log["snapshots"].append(name)

        save_json(
            out / f"{name}_controls.json",
            controls(page),
        )

    except Exception as exc:
        log["events"].append({
            "snapshot_failure": str(exc),
        })


def probe(url, seconds=12):
    """Check whether a TEA page is reachable."""

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; research data collection)"
                ),
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=seconds,
        ) as response:
            return {
                "url": url,
                "http_status": response.status,
                "final_url": response.url,
                "content_type": response.headers.get(
                    "Content-Type",
                    "",
                ),
            }

    except Exception as exc:
        return {
            "url": url,
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


def choose_select(page, patterns, step):
    """Select one unambiguous option from a visible dropdown.

    Does not guess based on DOM position. If the correct
    choice is not identifiable, leave it unchanged.
    """

    matches = []

    for i in range(
        page.locator("select").count()
    ):
        sel = page.locator("select").nth(i)

        if (
            not sel.is_visible()
            or not sel.is_enabled()
        ):
            continue

        options = sel.evaluate(
            """e=>Array.from(e.options).map(o=>({
                label:o.label.trim(),
                value:o.value
            }))"""
        )

        found = [
            option
            for option in options
            if any(
                re.search(
                    pattern,
                    option["label"],
                    re.I,
                )
                for pattern in patterns
            )
        ]

        if len(found) == 1:
            matches.append(
                (i, found[0])
            )

    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous {step} dropdowns: {matches}"
        )

    if not matches:
        return False

    index, option = matches[0]

    page.locator("select").nth(
        index
    ).select_option(
        value=option["value"]
    )

    page.wait_for_timeout(700)

    return {
        "step": step,
        "select": index,
        "label": option["label"],
        "value": option["value"],
    }


def choose_labeled_control(page, terms):
    """Select a checkbox or radio with an explicit label."""

    candidates = page.locator(
        'input[type="checkbox"],'
        'input[type="radio"]'
    )

    hits = []

    for i in range(candidates.count()):
        loc = candidates.nth(i)

        if (
            not loc.is_visible()
            or not loc.is_enabled()
        ):
            continue

        description = loc.evaluate(
            """e=>(
                e.labels?.[0]?.innerText ||
                e.parentElement?.innerText ||
                ''
            ).trim()"""
        )

        if any(
            re.search(
                term,
                description,
                re.I,
            )
            for term in terms
        ):
            hits.append(
                (i, description)
            )

    if len(hits) != 1:
        return False

    index, description = hits[0]

    candidates.nth(
        index
    ).check(force=True)

    page.wait_for_timeout(500)

    return {
        "control": index,
        "label": description[:180],
    }


def select_options(page, log, out):
    """Select Campuses on the main page, then inspect SASoutput.

    TEA's #tapr dropdown automatically submits the form
    into an iframe named SASoutput.

    The additional download choices are not necessarily
    present on the outer document.
    """

    actions = log["selections"]

    selected = {
        "year": False,
        "campus": False,
        "grades": False,
        "be_esl": False,
    }

    year = page.locator("#ccyy")
    typ = page.locator("#tapr")

    if (
        year.count() != 1
        or typ.count() != 1
    ):
        raise RuntimeError(
            "Expected TEA #ccyy and #tapr "
            "controls missing"
        )

    # 2024 identifies the 2023-24 reporting year.
    year.select_option(value="2024")

    selected["year"] = (
        year.input_value() == "2024"
    )

    actions.append({
        "step": "year",
        "value": year.input_value(),
    })

    # all_c = statewide campus-level data.
    #
    # Selecting this value automatically submits
    # TEA's form and loads the next interface
    # into the SASoutput iframe.
    typ.select_option(value="all_c")

    selected["campus"] = (
        typ.input_value() == "all_c"
    )

    actions.append({
        "step": "campuses",
        "value": typ.input_value(),
    })

    # Wait for the SAS application to load.
    frame = None

    for _ in range(35):
        frame = page.frame(
            name="SASoutput"
        )

        if (
            frame
            and "/cgi/sas/broker" in frame.url
        ):
            break

        page.wait_for_timeout(1000)

    else:
        log["frame_url"] = (
            frame.url if frame else None
        )

        raise RuntimeError(
            "TEA did not load the SAS result "
            "iframe after Campuses selection"
        )

    try:
        frame.wait_for_load_state(
            "domcontentloaded",
            timeout=25000,
        )

    except Exception as exc:
        log["events"].append({
            "iframe_load_warning": str(exc)[:300],
        })

    def capture(stage):
        """Save the actual content of the SAS iframe."""

        current = page.frame(
            name="SASoutput"
        )

        if not current:
            return

        try:
            (out / f"tx_tapr_{stage}.html").write_text(
                current.content(),
                encoding="utf-8",
            )

            save_json(
                out / f"tx_tapr_{stage}_controls.json",
                controls(current),
            )

            log["events"].append({
                "iframe_stage": stage,
                "iframe_url": current.url,
            })

        except Exception as exc:
            log["events"].append({
                "iframe_capture_failure": (
                    f"{stage}: {exc}"
                )[:350],
            })

    # Capture TEA's actual second-stage form
    # before trying to interact with it.
    capture("sas_after_campus")

    patterns = {
        "grades": [
            r"grades?\s*3\s*(?:-|–|to)\s*8",
            r"\b3rd\b.*\b8th\b",
            (
                r"Approaches.*Meets.*"
                r"Masters.*(?:3|Grades)"
            ),
        ],
        "be_esl": [
            r"\bBE\s*[/&-]\s*ESL\b",
            r"bilingual.*ESL",
            r"bilingual.*(?:student|group)",
            (
                r"dual.language.*"
                r"(?:one.way|two.way)"
            ),
        ],
    }

    for attempt in range(10):
        progress = False

        frame = page.frame(
            name="SASoutput"
        )

        if not frame:
            break

        for step in (
            "grades",
            "be_esl",
        ):
            if selected[step]:
                continue

            # Search dropdowns inside the iframe.
            choice = choose_select(
                frame,
                patterns[step],
                step,
            )

            # If no dropdown matched, try a
            # uniquely labeled checkbox/radio.
            if not choice:
                choice = choose_labeled_control(
                    frame,
                    patterns[step],
                )

            if choice:
                selected[step] = True

                actions.append({
                    "scope": "SASoutput",
                    **choice,
                })

                progress = True

                page.wait_for_timeout(1200)

                capture(
                    f"sas_after_{step}"
                )

        if (
            selected["grades"]
            and selected["be_esl"]
        ):
            break

        if not progress:
            # Advance through a wizard only if
            # there is one unambiguous Next/Continue
            # button within the iframe.
            next_button = frame.get_by_role(
                "button",
                name=re.compile(
                    r"^(next|continue)$",
                    re.I,
                ),
            )

            if (
                next_button.count() == 1
                and next_button.first.is_enabled()
            ):
                next_button.first.click()

                page.wait_for_timeout(1500)

                actions.append({
                    "scope": "SASoutput",
                    "step": "continue",
                })

                capture(
                    f"sas_after_continue_{attempt}"
                )

            else:
                break

    log["selected"] = selected

    capture("sas_final")

    if (
        not selected["grades"]
        or not selected["be_esl"]
    ):
        raise RuntimeError(
            "Campus selected, but exact grades "
            "3-8 / BE-ESL controls were not "
            "established in SASoutput. "
            "Inspect tx_tapr_sas_final_controls.json "
            "and tx_tapr_sas_final.html before "
            "changing selectors."
        )

    return page.frame(
        name="SASoutput"
    )


def fetch_public(out, wait_seconds):
    """Retrieve TAPR campus CSV using browser automation."""

    from playwright.sync_api import sync_playwright

    log = {
        "utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "urls": [
            NEW_URL,
            OLD_URL,
        ],
        "events": [],
        "snapshots": [],
        "selections": [],
        "probes": [
            probe(NEW_URL),
            probe(OLD_URL),
        ],
    }

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            context = browser.new_context(
                accept_downloads=True,
            )

            downloads = []

            context.on(
                "page",
                lambda p: p.on(
                    "download",
                    lambda d: downloads.append(d),
                ),
            )

            page = context.new_page()

            page.on(
                "download",
                lambda d: downloads.append(d),
            )

            page.on(
                "requestfailed",
                lambda request: log["events"].append({
                    "request_failed": request.url[:200],
                    "reason": request.failure,
                }),
            )

            reached = False

            for label, url in (
                ("new", NEW_URL),
                ("legacy", OLD_URL),
            ):
                try:
                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )

                    page.wait_for_timeout(700)

                    log["events"].append({
                        "page": label,
                        "status": (
                            response.status
                            if response
                            else None
                        ),
                        "final_url": page.url,
                    })

                    snapshot(
                        page,
                        out,
                        f"tx_tapr_{label}_before",
                        log,
                    )

                    reached = True
                    break

                except Exception as exc:
                    log["events"].append({
                        "page": label,
                        "navigation_error": str(exc)[:700],
                    })

            if not reached:
                raise RuntimeError(
                    "TEA refused or failed both "
                    "browser connections. This is "
                    "a network/access failure, "
                    "not a form-selector failure."
                )

            # Select year and campus on outer page,
            # then access the SASoutput iframe.
            target = select_options(
                page,
                log,
                out,
            )

            snapshot(
                page,
                out,
                "tx_tapr_after_selection",
                log,
            )

            # Submit from the SAS iframe, not
            # from the unrelated outer webpage.
            button = target.get_by_role(
                "button",
                name=re.compile(
                    r"^(download|export|generate|"
                    r"download data|download csv|submit)$",
                    re.I,
                ),
            )

            if button.count() == 1:
                button.first.click()

            else:
                submit = target.locator(
                    'input[type="submit"]'
                )

                if submit.count() == 1:
                    submit.first.click()

                else:
                    raise RuntimeError(
                        "No unambiguous export button found"
                    )

            deadline = (
                time.monotonic() + wait_seconds
            )

            while (
                not downloads
                and time.monotonic() < deadline
            ):
                page.wait_for_timeout(900)

            if not downloads:
                snapshot(
                    page,
                    out,
                    "tx_tapr_after_submit_no_download",
                    log,
                )

                raise RuntimeError(
                    "No browser download emitted "
                    "by TEA after export"
                )

            destination = (
                out / "tx_tapr_2023_24_campus_raw.csv"
            )

            log["suggested_filename"] = (
                downloads[0].suggested_filename
            )

            downloads[0].save_as(
                str(destination)
            )

            with destination.open("rb") as f:
                head = (
                    f.read(400)
                    .lstrip()
                    .lower()
                )

            if (
                len(head) < 20
                or head.startswith((
                    b"<!doctype",
                    b"<html",
                    b"pk\x03\x04",
                ))
            ):
                raise RuntimeError(
                    "Download not recognized as CSV; "
                    "inspect the source file"
                )

            log["download_bytes"] = (
                destination.stat().st_size
            )

            context.close()
            browser.close()

            return destination

    except Exception as exc:
        log["failure"] = (
            f"{type(exc).__name__}: {exc}"
        )
        raise

    finally:
        save_json(
            out / "tx_tapr_download_debug.json",
            log,
        )


def read_roster(roster):
    """Read the existing statewide Texas campus registry."""

    with roster.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        rows = csv.DictReader(f)

        if "texas_campus_id" not in (
            rows.fieldnames or []
        ):
            raise ValueError(
                "Texas roster lacks texas_campus_id"
            )

        return {
            row["texas_campus_id"].strip()
            for row in rows
        }


def number(raw):
    """Determine whether a TAPR field is numeric."""

    return bool(
        re.fullmatch(
            r"(?:\d+(?:\.\d*)?|\.\d+)",
            raw.replace(",", "").strip(),
        )
    )


def audit_csv(source, out, roster):
    """Extract DLI variables from TAPR CSV.

    TEA may supply a descriptive header followed
    by a row of variable codes.

    Missing and suppressed values remain missing.
    """

    ids = read_roster(roster)

    if not ids:
        raise ValueError(
            "Empty Texas roster"
        )

    with source.open(
        newline="",
        encoding="utf-8-sig",
        errors="replace",
    ) as f:

        reader = csv.reader(f)

        first_rows = []

        for _ in range(5):
            try:
                first_rows.append(
                    next(reader)
                )
            except StopIteration:
                break

        # Identify which initial row contains
        # the machine-readable DQ/DT variable names.
        scored = []

        for i, row in enumerate(first_rows):
            matches = [
                code.strip().upper()
                for code in row
                if CODE.fullmatch(
                    code.strip()
                )
            ]

            scored.append(
                (len(matches), i)
            )

        nfields, header_index = max(
            scored,
            default=(0, 0),
        )

        if nfields == 0:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "first_rows_samples": [
                        row[:60]
                        for row in first_rows
                    ],
                    "first_rows_lengths": [
                        len(row)
                        for row in first_rows
                    ],
                    "note": (
                        "No DQ/DT variable codes "
                        "in first five rows"
                    ),
                },
            )

            raise ValueError(
                "No DQ/DT headers found: "
                "check download category"
            )

        f.seek(0)

        reader = csv.reader(f)

        for _ in range(header_index):
            next(reader)

        headers = next(reader)

        selected = [
            (
                i,
                code.strip(),
                GROUPS[
                    code.strip()[1:3].upper()
                ],
                METRICS[
                    code.strip()[-1].upper()
                ],
            )
            for i, code in enumerate(headers)
            if CODE.fullmatch(
                code.strip()
            )
        ]

        if not selected:
            raise ValueError(
                "Header identification failed"
            )

        id_index = next(
            (
                i
                for i, name in enumerate(headers)
                if re.search(
                    (
                        r"campus.*(?:id|number)"
                        r"|^campus$"
                    ),
                    name,
                    re.I,
                )
            ),
            0,
        )

        dictionary = [
            {
                "variable_code": code,
                "student_group": group,
                "statistic": metric,
            }
            for _, code, group, metric in selected
        ]

        csv_write(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_dictionary.csv"
            ),
            dictionary,
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

        counts = Counter()

        seen = defaultdict(
            lambda: {
                "one_way_dli": set(),
                "two_way_dli": set(),
            }
        )

        rows_seen = 0
        invalid = 0

        with gzip.open(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_values.csv.gz"
            ),
            "wt",
            newline="",
            encoding="utf-8",
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
                    invalid += 1
                    continue

                for (
                    i,
                    code,
                    group,
                    metric,
                ) in selected:

                    raw = (
                        row[i].strip()
                        if i < len(row)
                        else ""
                    )

                    if not raw:
                        continue

                    status = (
                        "numeric"
                        if number(raw)
                        else "masked_or_other"
                    )

                    writer.writerow({
                        "texas_campus_id": cid,
                        "school_year": "2023-24",
                        "student_group": group,
                        "variable_code": code,
                        "statistic": metric,
                        "raw_value": raw,
                        "numeric_value": (
                            raw
                            if status == "numeric"
                            else ""
                        ),
                        "value_status": status,
                        "in_roster": (
                            "yes"
                            if cid in ids
                            else "no"
                        ),
                    })

                    counts[
                        (
                            group,
                            metric,
                            status,
                        )
                    ] += 1

                    if (
                        metric == "denominator"
                        and status == "numeric"
                        and float(raw) > 0
                    ):
                        seen[cid][group].add(
                            code
                        )

        campus_rows = [
            {
                "texas_campus_id": cid,
                "school_year": "2023-24",
                "one_way_positive_denominator_variables": (
                    len(
                        groups["one_way_dli"]
                    )
                ),
                "two_way_positive_denominator_variables": (
                    len(
                        groups["two_way_dli"]
                    )
                ),
                "in_2024_25_campus_roster": (
                    "yes"
                    if cid in ids
                    else "no"
                ),
            }
            for cid, groups in sorted(
                seen.items()
            )
        ]

        csv_write(
            out / (
                "tx_tapr_2023_24_"
                "dli_campus_evidence.csv"
            ),
            campus_rows,
            [
                "texas_campus_id",
                "school_year",
                "one_way_positive_denominator_variables",
                "two_way_positive_denominator_variables",
                "in_2024_25_campus_roster",
            ],
        )

        result = {
            "status": "extracted",
            "source_file": str(source),
            "sha256": hash_file(source),
            "header_row_number": header_index + 1,
            "campus_id_field": headers[id_index],
            "records_seen": rows_seen,
            "invalid_campus_ids": invalid,
            "dli_columns": len(selected),
            "campuses_with_positive_dli_test_denominators": (
                len(campus_rows)
            ),
            "values": {
                "|".join(key): value
                for key, value in sorted(
                    counts.items()
                )
            },
            "warning": (
                "Assessment subgroup records, "
                "not program enrollment. "
                "Suppressed or missing values "
                "are not zero."
            ),
        }

        save_json(
            out / "tx_tapr_2023_24_report.json",
            result,
        )

        return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--roster",
        type=Path,
        default=Path(
            "output/texas/"
            "tx_2024_25_all_campuses.csv"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "output/texas/tapr"
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "Parse an existing TEA CSV "
            "and skip browser automation"
        ),
    )

    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
    )

    args = parser.parse_args()

    args.out.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        csvfile = (
            args.input
            or fetch_public(
                args.out,
                args.wait_seconds,
            )
        )

        report = audit_csv(
            csvfile,
            args.out,
            args.roster,
        )

        print(
            json.dumps(
                report,
                indent=2,
            )
        )

    except Exception as exc:
        save_json(
            args.out / (
                "tx_tapr_collector_failure.json"
            ),
            {
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "traceback": (
                    traceback.format_exc()[-4500:]
                ),
                "new_url": NEW_URL,
                "legacy_url": OLD_URL,
                "note": (
                    "Network failure cannot be repaired "
                    "by changing form selectors."
                ),
            },
        )

        raise


if __name__ == "__main__":
    main()
