"""Small CLI for collection, reproducible builds, validation and frozen releases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dl-outcomes")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="Build national tables offline from saved pilot inputs")
    commands.add_parser("validate", help="Validate tables, joins, sources and manifest")
    commands.add_parser("schema", help="List table contracts and their paths")
    collect = commands.add_parser("collect-wa-pilot", help="Collect/cache bounded public Washington source snapshots")
    collect.add_argument("--destination", type=Path, help="New immutable vintage directory; existing files are never overwritten")
    release = commands.add_parser("release", help="Freeze a validated release and input/code bundle")
    release.add_argument("release_id")
    analytics = commands.add_parser("export-analytics", help="Export separate Parquet layers and a DuckDB file (analytics extra)")
    analytics.add_argument("--destination", type=Path, required=True)
    baseline = commands.add_parser("baseline", help="Create or verify an immutable national structural baseline")
    baseline_commands = baseline.add_subparsers(dest="baseline_command", required=True)
    baseline_create = baseline_commands.add_parser("create", help="Freeze a new baseline from existing saved evidence")
    baseline_create.add_argument("baseline_id")
    baseline_create.add_argument("--rules", type=Path, required=True)
    baseline_check = baseline_commands.add_parser("check", help="Verify a frozen baseline without reading updated live tables")
    baseline_check.add_argument("baseline_id")
    baseline_check.add_argument("--reproduce", action="store_true", help="Also reproduce the derived views from frozen evidence")
    edc = commands.add_parser("edc", help="Collect, build or verify the partitioned native-scale EDC assessment layer")
    edc_commands = edc.add_subparsers(dest="edc_command", required=True)
    edc_collect = edc_commands.add_parser("collect", help="Download/cache pinned EDC v3.1 source files for spring 2022–2025")
    edc_collect.add_argument("--cache", type=Path)
    edc_collect.add_argument("--workers", type=int, default=4)
    edc_build = edc_commands.add_parser("build", help="Build a new collection from cached original CSVs")
    edc_build.add_argument("--cache", type=Path)
    edc_build.add_argument("--destination", type=Path)
    edc_build.add_argument("--reuse", type=Path, help="Reuse hash-verified source extracts only when the school set and selection are identical")
    edc_check = edc_commands.add_parser("check", help="Verify source receipts, cohort completeness and normalized values")
    edc_check.add_argument("--collection", type=Path)
    edc_check.add_argument("--reproduce", action="store_true", help="Reproduce every normalized cell from saved native rows")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "build":
            from .build import build
            from .validation import validate
            result = build(root)
            result["validation"] = validate(root)["status"]
        elif args.command == "validate":
            from .validation import validate
            result = validate(root)
        elif args.command == "collect-wa-pilot":
            from .collectors.washington import collect
            result = collect(root, args.destination)
        elif args.command == "release":
            from .release import release
            result = release(root, args.release_id)
        elif args.command == "export-analytics":
            from .analytics import export
            result = export(root, args.destination)
        elif args.command == "baseline":
            from .baseline import create, check
            result = (create(root, args.baseline_id, args.rules) if args.baseline_command == "create"
                      else check(root, args.baseline_id, reproduce=args.reproduce))
        elif args.command == "edc":
            if args.edc_command == "collect":
                from .collectors.edc import collect
                collected = collect(root, args.cache, workers=args.workers)
                result = {"version": collected["version"], "source_files": len(collected["sources"]), "failures": collected["failures"]}
            elif args.edc_command == "build":
                from .edc import extract, finalize
                result = extract(root, args.cache, args.destination, args.reuse)
                finalize(root, args.destination)
            else:
                from .edc import check
                result = check(root, args.collection, reproduce=args.reproduce)
        else:
            from .contracts import catalog
            result = {name: value["x-path"] for name, value in catalog()["$defs"].items()}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, ImportError) as exc:
        print(f"dl-outcomes: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
