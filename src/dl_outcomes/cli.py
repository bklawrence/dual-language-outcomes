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
