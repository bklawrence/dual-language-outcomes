
#!/usr/bin/env python3
"""Collect 2023-24 statewide Texas TAPR campus CSVs.

Four separate categories are collected:
STAAR grades 3, 4, 5, and BE/ESL all grades.

Results remain separate until their measures and
student-group definitions have been verified.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)

BROKER = "https://rptsvr1.tea.texas.gov/cgi/sas/broker"

VERSION = "2026-11-03-four-category-download-v6"

CATEGORIES = {
    "grade3": "STAAR_GR3",
    "grade4": "STAAR_GR4",
    "grade5": "STAAR_GR5",
    "bilingual_all_grades": "BIL1",
}

STEP3_URL = BROKER + "?" + urlencode({
    "_service": "marykay",
    "_program": "perfrept.perfmast.sas",
    "_debug": "0",
    "ccyy": "2024",
    "tapr": "all_c",
    "prgopt": "reports/tapr/dd/dd_tapr.sas",
})


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
    )


def save_diagnostics(page, folder, label):
    folder.mkdir(parents=True, exist_ok=True)

    for index, frame in enumerate(page.frames):
        name = (
            "main"
            if frame == page.main_frame
            else f"iframe_{index}"
        )

        stem = folder / f"{label}_{name}"

        try:
            stem.with_suffix(".html").write_text(
                frame.content(),
                encoding="utf-8",
            )

            controls = frame.locator(
                "input,select,button"
            ).evaluate_all(
                """xs => xs.map(x => ({
                    tag: x.tagName,
                    name: x.name || '',
                    type: x.type || '',
                    value: x.value || '',
                    checked: x.checked === true,
                    options: x.tagName === 'SELECT'
                        ? Array.from(x.options).map(o => ({
                            text: o.text.trim(),
                            value: o.value
                        }))
                        : null
                }))"""
            )

            write_json(
                stem.with_name(
                    stem.name + "_controls.json"
                ),
                {
                    "url_without_query":
                        frame.url.split("?")[0],
                    "controls": controls,
                },
            )

        except Exception as exc:
            print(
                f"Diagnostic warning ({label}): {exc}",
                flush=True,
            )

    try:
        page.screenshot(
            path=str(folder / f"{label}.png"),
            full_page=True,
            timeout=15000,
        )
    except Exception:
        pass


def csv_audit(path, original_name, category):
    """Inspect the downloaded file before treating it as data."""

    with path.open("rb") as handle:
        signature = handle.read(2048)

    if signature.lstrip().lower().startswith(
        (b"<html", b"<!doctype html")
    ):
        raise RuntimeError(
            "TEA returned HTML instead of a CSV"
        )

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
            ]

            if len(members) != 1:
                raise RuntimeError(
                    f"ZIP contains {len(members)} CSV files"
                )

            with archive.open(members[0]) as binary:
                reader = csv.reader(
                    io.TextIOWrapper(
                        binary,
                        encoding="utf-8-sig",
                        errors="replace",
                        newline="",
                    )
                )
                header = next(reader, [])
                sample = next(reader, [])

    else:
        with path.open(
            encoding="utf-8-sig",
            errors="replace",
            newline="",
        ) as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            sample = next(reader, [])

    if len(header) < 5:
        raise RuntimeError(
            "Downloaded response lacks a plausible CSV header"
        )

    candidates = []

    for heading in header:
        clean = re.sub(
            r"[^A-Z0-9]", "", heading.upper()
        )

        if (
            len(clean) >= 4
            and clean.startswith("C")
            and clean[1:3] in {"DQ", "DT", "DJ", "DK"}
        ):
            candidates.append({
                "column": heading,
                "group_code": clean[1:3],
            })

    return {
        "category": category,
        "original_filename": original_name,
        "raw_bytes": path.stat().st_size,
        "header_column_count": len(header),
        "first_header_columns": header[:20],
        "first_row_preview": sample[:12],
        "candidate_program_column_count":
            len(candidates),
        "candidate_program_columns":
            candidates[:40],
        "program_codebook_status": "UNVERIFIED",
        "grade_by_program_join_status": "UNVERIFIED",
    }


def collect_category(
    context, output, diagnostics, label, category
):
    page = context.new_page()
    page.set_default_timeout(20000)

    folder = diagnostics / label
    events = []

    def log_response(response):
        if "/cgi/sas/broker" in response.url:
            events.append({
                "status": response.status,
                "method": response.request.method,
                "content_type": response.headers.get(
                    "content-type", ""
                ),
                "content_disposition":
                    response.headers.get(
                        "content-disposition", ""
                    ),
            })

    page.on("response", log_response)

    try:
        page.goto(
            URL,
            wait_until="load",
            timeout=90000,
        )

        page.locator("#ccyy").select_option(
            value="2024"
        )

        page.wait_for_selector("#SASoutput")

        frame = page.frame(name="SASoutput")

        if frame is None:
            raise RuntimeError(
                "SASoutput iframe missing"
            )

        frame.wait_for_url(
            re.compile(
                r"tapr_dd_blank_iframe\.html\?year=2024"
            ),
            timeout=30000,
        )

        frame.wait_for_load_state(
            "load",
            timeout=30000,
        )

        page.locator("#tapr").select_option(
            value="all_c"
        )

        radio = frame.locator(
            f'input[name="dsname"][value="{category}"]'
        )

        try:
            radio.wait_for(
                state="visible",
                timeout=25000,
            )

        except PlaywrightTimeout:
            print(
                f"{label}: opening verified Step 3 URL",
                flush=True,
            )

            frame.goto(
                STEP3_URL,
                wait_until="domcontentloaded",
                timeout=90000,
            )

            radio.wait_for(
                state="visible",
                timeout=45000,
            )

        radio.check()

        save_diagnostics(
            page,
            folder,
            "01_category_selected",
        )

        next_button = frame.locator(
            'input[type="submit"][value^="Next"]'
        )

        if next_button.count() != 1:
            raise RuntimeError(
                "Step 3 Next button is ambiguous"
            )

        next_button.click(timeout=30000)

        download_button = frame.locator(
            'input[type="submit"][value^="Download Data"]'
        )

        download_button.wait_for(
            state="visible",
            timeout=90000,
        )

        keys = frame.locator(
            'input[type="checkbox"][name="key"]'
        )

        metrics = frame.locator(
            'input[type="checkbox"][name="var_type"]'
        )

        if keys.count() == 0 or metrics.count() != 3:
            raise RuntimeError(
                "Unexpected data-selection form: "
                f"{keys.count()} elements and "
                f"{metrics.count()} metrics"
            )

        # Include all data elements and all three
        # metrics: numerator, denominator, and rate.

        for index in range(keys.count()):
            if not keys.nth(index).is_checked():
                keys.nth(index).check()

        for index in range(metrics.count()):
            if not metrics.nth(index).is_checked():
                metrics.nth(index).check()

        frame.locator(
            'select[name="datafmt"]'
        ).select_option(value="csv")

        save_diagnostics(
            page,
            folder,
            "02_ready_to_download",
        )

        print(
            f"{label}: downloading "
            f"{keys.count()} data elements, "
            "numerators, denominators, rates, CSV",
            flush=True,
        )

        with page.expect_download(
            timeout=180000
        ) as download_info:
            download_button.click(timeout=30000)

        download = download_info.value

        raw = folder / "response.raw"

        raw.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        download.save_as(raw)

        audit = csv_audit(
            raw,
            download.suggested_filename,
            category,
        )

        write_json(
            folder / "header_audit.json",
            audit,
        )

        archive_path = (
            output / f"tapr_2024_{label}.zip"
        )

        if zipfile.is_zipfile(raw):
            shutil.copy2(raw, archive_path)

        else:
            with zipfile.ZipFile(
                archive_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                archive.write(
                    raw,
                    arcname=f"tapr_2024_{label}.csv",
                )

        raw.unlink()

        audit["archive_path"] = str(archive_path)

        print(
            f"{label}: downloaded "
            f"{audit['raw_bytes']} bytes; "
            f"{audit['header_column_count']} columns; "
            f"{audit['candidate_program_column_count']} "
            "candidate program columns",
            flush=True,
        )

        return audit

    except Exception:
        save_diagnostics(
            page,
            folder,
            "error",
        )
        raise

    finally:
        write_json(
            folder / "sas_events.json",
            events,
        )
        page.close()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(
            "results/texas/tapr_download"
        ),
    )

    args = parser.parse_args()

    output = args.outdir
    output.mkdir(parents=True, exist_ok=True)

    diagnostics = output / "diagnostics"

    print(
        f"Collector version: {VERSION}",
        flush=True,
    )

    results = []
    failures = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True
        )

        try:
            for label, category in CATEGORIES.items():
                print(
                    f"Starting {label} ({category})",
                    flush=True,
                )

                try:
                    result = collect_category(
                        context,
                        output,
                        diagnostics,
                        label,
                        category,
                    )
                    results.append(result)

                except Exception as exc:
                    failures.append({
                        "category": label,
                        "error": str(exc),
                    })

                    print(
                        f"FAILED {label}: {exc}",
                        flush=True,
                    )

        finally:
            browser.close()

    receipt = {
        "version": VERSION,
        "source_url": URL,
        "year": "2023-24",
        "geography": "all Texas campuses",
        "completed_categories": results,
        "failed_categories": failures,
        "note": (
            "Grade-specific campus outcomes and "
            "BE/ESL all-grades outcomes remain separate. "
            "No grade-by-program results are presumed."
        ),
    }

    write_json(
        output / "download_receipt.json",
        receipt,
    )

    print(
        json.dumps(
            {
                "completed": len(results),
                "failed": len(failures),
            },
            indent=2,
        ),
        flush=True,
    )

    if failures:
        raise SystemExit(
            "One or more downloads failed. "
            "See the diagnostic artifact."
        )

    print(
        "Four separate public TEA source archives saved.",
        flush=True,
    )


if __name__ == "__main__":
    main()
