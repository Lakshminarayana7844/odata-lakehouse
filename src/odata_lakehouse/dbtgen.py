"""Scaffold dbt staging models for synced tables.

Generates one staging model per synced Parquet file: a select that reads
the file through DuckDB's read_parquet, plus a schema.yml with not_null
and unique tests on the key columns. This is a starting point a data
engineer edits, not a finished dbt project.
"""
import os

MODEL_SQL = """{{{{ config(materialized='view') }}}}

select *
from read_parquet('{parquet_path}')
"""


def _column_yml(name: str, key: bool) -> str:
    if not key:
        return f"      - name: {name}\n"
    return (
        f"      - name: {name}\n"
        "        tests:\n"
        "          - not_null\n"
        "          - unique\n"
    )


def scaffold(out_dir: str, tables: dict[str, dict]) -> list[str]:
    """Write stg_<table>.sql and schema.yml.

    `tables` maps table name to {"parquet": path, "keys": [key columns],
    "columns": [all columns]}. Returns the list of files written.
    """
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    yml = ["version: 2", "", "models:"]
    for table, spec in sorted(tables.items()):
        sql_path = os.path.join(out_dir, f"stg_{table}.sql")
        with open(sql_path, "w") as fh:
            fh.write(MODEL_SQL.format(parquet_path=spec["parquet"]))
        written.append(sql_path)
        keys = set(spec.get("keys", []))
        yml.append(f"  - name: stg_{table}")
        yml.append(f'    description: "Staging model over the synced {table} lakehouse file"')
        yml.append("    columns:")
        for col in spec.get("columns", []):
            yml.append(_column_yml(col, col in keys).rstrip("\n"))
    yml_path = os.path.join(out_dir, "schema.yml")
    with open(yml_path, "w") as fh:
        fh.write("\n".join(yml) + "\n")
    written.append(yml_path)
    return written
