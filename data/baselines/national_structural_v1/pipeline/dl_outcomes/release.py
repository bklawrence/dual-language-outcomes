"""Freeze reproducible data, config and pipeline bytes without publishing them."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import zipfile

from .io import digest
from .validation import validate


def release(root: Path, release_id: str):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", release_id):
        raise ValueError("Release ID must be a filename-safe identifier")
    validate(root)
    build_manifest = json.loads((root / "data/curated/manifest.json").read_text())
    destination = root / "data/releases" / release_id
    if destination.exists():
        raise ValueError("Release already exists; choose a new ID. Frozen releases are never overwritten.")
    destination.mkdir(parents=True)
    paths = set(build_manifest["inputs"]) | set(build_manifest["pipeline_files"]) | set(build_manifest["outputs"])
    paths.update(build_manifest.get("reports", {}))
    paths.update(["data/curated/manifest.json", "pyproject.toml", "requirements-lock.txt"])
    baseline_index = root / 'data/baselines/index.json'
    if baseline_index.exists():
        paths.add('data/baselines/index.json')
        for baseline_id in json.loads(baseline_index.read_text()):
            prefix = 'data/baselines/' + baseline_id + '/'
            frozen = json.loads((root / prefix / 'manifest.json').read_text())
            paths.update(prefix + name for name in frozen['files'])
            paths.add(prefix + 'manifest.json')
    bundle = destination / "research_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(paths):
            archive.write(root / relative, arcname=relative)
        archive.writestr("REPRODUCE.md", "# Reproduce this local research release\n\nCreate a Python 3.10+ virtual environment, install with `python -m pip install -r requirements-lock.txt -e .`, then run `dl-outcomes validate` and `dl-outcomes build`. The build uses only the archived inputs and configs. Source vintages and scope limitations remain explicit in data/curated/manifest.json. Install requirements-analytics-lock.txt for optional Parquet/DuckDB exports. This is a partial research pilot, not a national census.\n")
    manifest = {"release_id": release_id, "created_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": build_manifest["schema_version"], "build_id": build_manifest["build_id"],
                "bundle": "research_bundle.zip", "bundle_sha256": digest(bundle), "bundle_files": sorted(paths | {"REPRODUCE.md"}),
                "inputs": build_manifest["inputs"], "outputs": build_manifest["outputs"],
                "status": "local_pilot_release_not_published", "limitations": build_manifest["limitations"]}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"release_id": release_id, "manifest": str((destination / "manifest.json").relative_to(root)),
            "bundle": str(bundle.relative_to(root)), "bundle_sha256": manifest["bundle_sha256"]}
