
#!/usr/bin/env python3
"""Inspect 2023-24 Texas TAPR Grade 3 options after selecting All Campuses.

The exact TEA Step 3 radio value is known from a captured public page.
This collector does not call an outcome successfully collected until its
student-group and grade definitions have been checked.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)
VERSION = "2026-11-03-verified-step3-v4"

CATEGORIES = {
    "3": "STAAR_GR3",
    "4": "STAAR_GR4",
    "5": "STAAR_GR5",
    "bilingual": "BIL1",
}


def save_snapshot(page, folder: Path, label: str) -> None:
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
                encoding="utf-8"
            )

            info = frame.locator(
                "input,select,button,a"
            ).evaluate_all(
                """els => els.map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    id: e.id || '',
                    name: e.name || '',
                    value: e.value || '',
                    text: (e.innerText || '')
                        .trim().slice(0,120),
                    context: (
                        e.closest('tr,li,fieldset,label')
                        ?.innerText || ''
                    ).replace(/\\s+/g,' ')
                        .trim().slice(0,180),
                    options: e.tagName === 'SELECT'
                        ? Array.from(e.options).map(
                            o => ({
                                text: o.text.trim(),
                                value: o.value
                            })
                        )
                        : null
                }))"""
            )

            (
                folder / f"{label}_{name}_controls.json"
            ).write_text(
                json.dumps(
                    {
                        "url": frame.url,
                        "controls": info
                    },
                    indent=2
                ),
                encoding="utf-8"
            )

        except Exception as exc:
            print(
                f"Diagnostic warning for {name}: {exc}",
                flush=True
            )

    try:
        page.screenshot(
            path=str(folder / f"{label}.png"),
            full_page=True
        )
    except Exception as exc:
        print(
            f"Screenshot warning: {exc}",
            flush=True
        )


def collect(outdir: Path, category: str) -> None:
    from playwright.sync_api import sync_playwright

    diagnostics = outdir / "diagnostics"
    diagnostics.mkdir(
        parents=True,
        exist_ok=True
    )

    events = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True
        )

        page = context.new_page()
        page.set_default_timeout(20000)

        downloads = []

        page.on(
            "download",
            lambda item: downloads.append(item)
        )

        page.on(
            "response",
            lambda response: events.append({
                "status": response.status,
                "url": response.url.split("?")[0]
            })
            if "/cgi/sas/broker" in response.url
            else None
        )

        try:
            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=90000
            )

            # The two verified dropdown controls.

            page.locator("#ccyy").select_option(
                "2024"
            )

            page.locator("#tapr").select_option(
                "all_c"
            )

            print(
                "Selected 2023-24 and All Campuses",
                flush=True
            )

            save_snapshot(
                page,
                diagnostics,
                "01_all_campuses"
            )

            frame = page.frame(
                name="SASoutput"
            )

            if frame is None:
                raise RuntimeError(
                    "The TEA SASoutput frame was not found"
                )

            # TEA Step 3: Select a data category.
            # These exact values were recovered
            # from the uploaded form diagnostics.

            radio = frame.locator(
                f'input[name="dsname"][value="{category}"]'
            )

            radio.wait_for(
                state="visible",
                timeout=90000
            )

            print(
                f"Step 3 loaded. Selecting {category}.",
                flush=True
            )

            save_snapshot(
                page,
                diagnostics,
                "02_step3"
            )

            radio.check()

            next_button = frame.locator(
                'input[type="submit"][value^="Next"]'
            )

            if next_button.count() != 1:
                raise RuntimeError(
                    "Cannot uniquely identify "
                    "Step 3 Next button"
                )

            next_button.click(
                timeout=45000
            )

            # The form submits into the same iframe.
            # Wait for its content to change,
            # rather than its URL.

            deadline = time.monotonic() + 65

            while time.monotonic() < deadline:
                body = frame.locator(
                    "body"
                ).inner_text(
                    timeout=15000
                )

                if (
                    "Step 3: Select a data category"
                    not in body
                ):
                    break

                page.wait_for_timeout(500)

            save_snapshot(
                page,
                diagnostics,
                "03_after_next"
            )

            print(
                "=== TEA NEXT FORM TEXT ===",
                flush=True
            )

            print(
                frame.locator("body").inner_text()[:4000],
                flush=True
            )

            print(
                "=== END FORM TEXT ===",
                flush=True
            )

            if downloads:
                for i, item in enumerate(downloads):
                    path = (
                        diagnostics /
                        f"unexpected_download_{i}.bin"
                    )

                    item.save_as(path)

                    print(
                        f"Download saved for audit: {path}",
                        flush=True
                    )

            # We have not yet established which
            # controls on the following form
            # produce grade-specific program results.
            # Preserve the evidence rather than
            # importing potentially incorrect data.

            raise RuntimeError(
                "Step 3 selected successfully. "
                "Review 03_after_next_iframe_1.html "
                "and its controls JSON to identify "
                "the next TEA choices. "
                "No outcomes imported."
            )

        except Exception:
            save_snapshot(
                page,
                diagnostics,
                "error"
            )
            raise

        finally:
            (
                diagnostics / "sas_responses.json"
            ).write_text(
                json.dumps(events, indent=2),
                encoding="utf-8"
            )

            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(
            "results/texas/tapr_download"
        )
    )

    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default="3",
        help=(
            "Grade 3, 4, 5, "
            "or bilingual program results"
        )
    )

    args = parser.parse_args()

    print(
        f"Collector version: {VERSION}",
        flush=True
    )

    collect(
        args.outdir,
        CATEGORIES[args.category]
    )


if __name__ == "__main__":
    main()
