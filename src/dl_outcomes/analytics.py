"""Optional typed Parquet/DuckDB export, retaining separate assessment tables."""
from pathlib import Path

from .validation import load, validate


def export(root: Path, destination: Path):
    try:
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Install the analytics extra: pip install -e '.[analytics]'") from exc
    validate(root)
    definition, tables = load(root)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Analytics destination must be empty; existing exports are not overwritten")
    destination.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(destination / "research.duckdb"))
    try:
        for name, rows in tables.items():
            fields = []
            for column, spec in definition["$defs"][name]["properties"].items():
                types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
                dtype = pa.float64() if "number" in types else pa.int64() if "integer" in types else pa.string()
                fields.append(pa.field(column, dtype, nullable="null" in types))
            table = pa.Table.from_pylist(rows, schema=pa.schema(fields))
            pq.write_table(table, destination / (name + ".parquet"))
            connection.register("source_table", table)
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM source_table')
            connection.unregister("source_table")
        from .edc import export_analytics
        assessment_collections = export_analytics(root, destination, connection)
    finally:
        connection.close()
    return {"directory": str(destination), "tables": len(tables), "assessment_collections": assessment_collections, "status": "separate_layers_preserved"}
