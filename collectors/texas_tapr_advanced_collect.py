
#!/usr/bin/env python3
"""Collect 2023-24 Texas TAPR statewide campus CSV and audit its columns.

TEA's redesigned site uses #ccyy and #tapr, then may start a download
without navigating its SASoutput iframe. This collector handles both paths.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

SOURCE_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)
VERSION = "2026-11-03-direct-download-and-iframe-v3"
EXPECTED_CSV = "tapr_2024_campus_additional_grades3to8.csv"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def describe_controls(frame):
    return frame.locator("input,select,button,a").evaluate_all(
        """els => els.map(e => ({
          tag: e.tagName,
          id: e.id || '',
          name: e.name || '',
          type: e.type || '',
          value: e.value || '',
          text: (e.innerText || '').trim().slice(0, 160),
          context: (e.closest('tr,li,label,fieldset')?.innerText || '')
                    .trim().slice(0, 200),
          options: e.tagName === 'SELECT'
            ? Array.from(e.options).map(o => ({value:o.value, text:o.text.trim()}))
            : null
        }))"""
    )


def snapshot(page, diagnostics: Path, label: str) -> None:
    diagnostics.mkdir(parents=True, exist_ok=True)
    for frame in page.frames:
        suffix = "main" if frame == page.main_frame else "iframe"
        name = f"{label}_{suffix}"
        try:
            (diagnostics / f"{name}.html").write_text(
                frame.content(), encoding="utf-8"
            )
            write_json(
                diagnostics / f"{name}_controls.json",
                {"url": frame.url, "controls": describe_controls(frame)},
            )
        except Exception as exc:
            print(f"Diagnostic warning ({name}): {exc}", flush=True)
    try:
        page.screenshot(
            path=str(diagnostics / f"{label}.png"),
            full_page=True,
            timeout=15000,
        )
    except Exception as exc:
        print(f"Screenshot warning: {exc}", flush=True)


def is_new_form(frame) -> bool:
    return bool(
        frame
        and frame.url != "about:blank"
        and "tapr_dd_blank_iframe" not in frame.url.lower()
    )


def pick_group_if_unambiguous(frame) -> bool:
    """Avoid a guess when the new TEA form has unknown control labels."""
    candidates = []
    for select in frame.locator("select").all():
        options = select.locator("option").evaluate_all(
            """els => els.map(e => ({value:e.value, text:e.text.trim()}))"""
        )
        for option in options:
            title = option["text"]
            if (re.search(r"additional\s+student\s+groups", title, re.I)
                and re.search(r"3\s*(?:to|-|–)\s*8", title, re.I)):
                candidates.append((select, option["value"], title))
    if len(candidates) == 1:
        select, value, title = candidates[0]
        print(f"Selecting: {title}", flush=True)
        select.select_option(value=value)
        return True
    return False


def download_to_file(download, outdir: Path) -> Path:
    name = download.suggested_filename or "unnamed_file"
    raw = outdir / "diagnostics" / "tea_download.raw"
    raw.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(raw)
    with raw.open("rb") as handle:
        signature = handle.read(8192)

    if signature.startswith(b"PK\x03\x04"):
        destination = outdir / "diagnostics" / "tea_download.zip"
    elif signature.lstrip().lower().startswith((b"<html", b"<!doctype html")):
        destination = outdir / "diagnostics" / "tea_response.html"
    else:
        # TEA may use a generic filename despite returning comma-delimited data.
        first_line = signature.split(b"\n", 1)[0]
        if b"," not in first_line:
            destination = outdir / "diagnostics" / "tea_unrecognized_response.txt"
        else:
            destination = outdir / EXPECTED_CSV

    raw.replace(destination)
    print(
        f"Download: {name}; saved {destination.stat().st_size} "
        f"bytes to {destination}", flush=True
    )
    return destination


def audit_csv(path: Path, outdir: Path, download_name: str) -> None:
    if path.suffix.lower() != ".csv":
        raise RuntimeError(
            f"TEA delivered {download_name!r}, not a CSV; see diagnostics"
        )
    if path.stat().st_size < 100:
        raise RuntimeError("Downloaded file is too small to be campus data")

    with path.open(encoding="utf-8-sig", errors="replace", newline="") as file:
        reader = csv.reader(file)
        first_rows = [next(reader, []) for _ in range(3)]

    if len(first_rows[0]) < 2:
        raise RuntimeError("The response does not look like a CSV data table")

    # Newly redesigned reports can put data descriptions on the first row.
    header_candidates = [item for row in first_rows[:3] for item in row]
    matches = sorted({
        field for field in header_candidates
        if re.search(r"(?:^|[^A-Z0-9])(?:C?DQ|C?DT)(?:[^A-Z0-9]|$)",
                     field.upper())
        or re.match(r"^C?(?:DQ|DT)[A-Z0-9_]", field.upper())
    })

    receipt = {
        "collector_version": VERSION,
        "source_url": SOURCE_URL,
        "original_filename": download_name,
        "bytes": path.stat().st_size,
        "first_three_rows_preview": [row[:12] for row in first_rows],
        "candidate_DQ_DT_fields": len(matches),
        "DQ_DT_field_examples": matches[:20],
        "interpretation": "Unverified until the TEA codebook is checked",
    }
    write_json(outdir / "download_receipt.json", receipt)
    print(json.dumps(receipt, indent=2), flush=True)
    if not matches:
        raise RuntimeError(
            "TEA supplied a CSV, but no DQ/DT program-group columns were "
            "found in its first three rows. This may be the general TAPR "
            "download rather than the advanced student-groups download. "
            "Do not import it as dual-language outcomes."
        )


def collect(outdir: Path) -> Path:
    from playwright.sync_api import sync_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    diagnostics = outdir / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    events = []
    downloads = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(20000)

        page.on("download", lambda d: downloads.append(d))

        def record_response(response):
            if "/cgi/sas/broker" in response.url:
                events.append({
                    "event": "response",
                    "status": response.status,
                    "url_without_query": response.url.split("?")[0],
                    "content_type": response.headers.get("content-type", ""),
                    "content_disposition": response.headers.get(
                        "content-disposition", ""
                    ),
                })
                print(f"TEA SAS response: HTTP {response.status}", flush=True)

        def record_failure(request):
            if "/cgi/sas/broker" in request.url:
                events.append({
                    "event": "request_failed",
                    "url_without_query": request.url.split("?")[0],
                    "failure": request.failure,
                })

        page.on("response", record_response)
        page.on("requestfailed", record_failure)

        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=90000)
            page.locator("#ccyy").wait_for(timeout=30000)
            print(f"Actual landing page: {page.url}", flush=True)
            snapshot(page, diagnostics, "01_initial")

            page.locator("#ccyy").select_option(value="2024")
            page.locator("#tapr").select_option(value="all_c")
            print("Selected 2023-24 / All campuses", flush=True)
            snapshot(page, diagnostics, "02_selected")

            # This site may stream an attachment while leaving the iframe
            # on its initial introduction page. Check downloads FIRST.
            deadline = time.monotonic() + 90
            embedded = None
            while time.monotonic() < deadline:
                if downloads:
                    break
                candidate = page.frame(name="SASoutput")
                if is_new_form(candidate):
                    embedded = candidate
                    print(f"TEA loaded embedded form: {candidate.url}", flush=True)
                    break
                page.wait_for_timeout(1000)

            if embedded is not None and not downloads:
                snapshot(page, diagnostics, "03_embedded_form")
                if not pick_group_if_unambiguous(embedded):
                    raise RuntimeError(
                        "TEA loaded an embedded form, but the required "
                        "Additional Student Groups (grades 3-8) option could "
                        "not be identified uniquely. Review 03_embedded_form "
                        "diagnostics before changing the selector."
                    )
                snapshot(page, diagnostics, "04_group_selected")
                buttons = embedded.locator(
                    "button,input[type=submit],input[type=button]"
                )
                matching = []
                for button in buttons.all():
                    title = (
                        (button.get_attribute("value") or "") + " "
                        + (button.inner_text(timeout=2000) or "")
                    ).strip()
                    if re.search(r"download|export|generate", title, re.I):
                        matching.append(button)
                if len(matching) != 1:
                    raise RuntimeError(
                        "Cannot uniquely identify an embedded Download button; "
                        "see 04_group_selected diagnostics"
                    )
                matching[0].click()
                deadline = time.monotonic() + 120
                while not downloads and time.monotonic() < deadline:
                    page.wait_for_timeout(1000)

            if not downloads:
                raise RuntimeError(
                    "No download and no usable embedded form. "
                    "Inspect 02_selected iframe snapshots and the SAS "
                    "network-response log for a redirect, server error, "
                    "or other TEA download behavior."
                )

            download = downloads[0]
            path = download_to_file(download, outdir)
            audit_csv(path, outdir, download.suggested_filename)
            return path

        except Exception:
            snapshot(page, diagnostics, "error")
            raise
        finally:
            write_json(diagnostics / "sas_network_events.json", events)
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir", type=Path,
        default=Path("results/texas/tapr_download"),
    )
    args = parser.parse_args()
    print(f"Collector version: {VERSION}", flush=True)
    print(f"Public TEA source: {SOURCE_URL}", flush=True)
    result = collect(args.outdir)
    print(f"Validated candidate download: {result}", flush=True)


if __name__ == "__main__":
    main()
