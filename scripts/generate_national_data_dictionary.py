#!/usr/bin/env python3
"""Generate a readable dictionary from the packaged JSON Schema source of truth."""
from pathlib import Path
from dl_outcomes.contracts import catalog


def render():
    schema = catalog()
    lines = ["# National data dictionary", "", f"Schema version: **{schema['x-schema-version']}**. Generated from `src/dl_outcomes/schemas/catalog.json`.", "", "Empty CSV cells are null. IDs and school years remain strings. All listed headers are required, including in zero-row tables.", ""]
    for name, table in schema["$defs"].items():
        lines.extend([f"## {name}", "", table["description"], "", f"Path: `{table['x-path']}`. Primary key: `" + ", ".join(table["x-primary-key"]) + "`.", "", "| Column | Type | Allowed values / reference |", "|---|---|---|"])
        for field, spec in table["properties"].items():
            types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            detail = ", ".join(str(x) for x in spec.get("enum", []) if x is not None)
            reference = table["x-foreign-keys"].get(field)
            if reference:
                detail = f"{reference['table']}.{reference['column']}"
            if spec.get("pattern"):
                detail += ("; " if detail else "") + "pattern: " + spec["pattern"].replace("|", "\\|")
            if "minimum" in spec:
                detail += ("; " if detail else "") + f"minimum {spec['minimum']}"
            if "maximum" in spec:
                detail += ("; " if detail else "") + f"maximum {spec['maximum']}"
            lines.append(f"| `{field}` | {' / '.join(types)} | {detail} |")
        if table.get("x-unique"):
            lines.extend(["", "Additional unique keys:", ""])
            lines.extend("- `" + ", ".join(fields) + "`" for fields in table["x-unique"])
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    (root / "schemas/DATA_DICTIONARY.md").write_text(render(), encoding="utf-8")
