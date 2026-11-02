"""Schema contracts for synced tables.

A contract is a small JSON document naming required columns, expected
types and optional nullability. Validation runs against the synced
Parquet file and reports every violation instead of failing on the
first one.

Contract example:
{
  "table": "products",
  "columns": {
    "ProductID": {"type": "int", "required": true},
    "ProductName": {"type": "string", "required": true},
    "UnitPrice": {"type": "float"}
  }
}
"""
import json

import pyarrow.parquet as pq

TYPE_MAP = {
    "int": {"int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"},
    "float": {"float", "double", "halffloat"},
    "string": {"string", "large_string"},
    "bool": {"bool_"},
    "timestamp": {"date32", "date64", "timestamp[us]", "timestamp[ms]", "timestamp[s]", "timestamp[ns]"},
}


class ContractViolation(Exception):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(f"{len(violations)} contract violation(s)")


def load_contract(path: str) -> dict:
    with open(path) as fh:
        contract = json.load(fh)
    if "columns" not in contract:
        raise ValueError("contract must define 'columns'")
    return contract


def validate_parquet(parquet_path: str, contract: dict) -> list[str]:
    """Return the list of violations; empty means the table passes."""
    table = pq.read_table(parquet_path)
    violations: list[str] = []
    schema = {f.name: str(f.type) for f in table.schema}
    for col, spec in contract["columns"].items():
        if col not in schema:
            if spec.get("required"):
                violations.append(f"missing required column: {col}")
            continue
        expected = spec.get("type")
        if expected:
            accepted = TYPE_MAP.get(expected)
            if accepted is None:
                violations.append(f"{col}: unknown contract type '{expected}'")
            elif schema[col] not in accepted:
                violations.append(f"{col}: expected type {expected}, found {schema[col]}")
        if spec.get("required"):
            nulls = table.column(col).null_count
            if nulls:
                violations.append(f"{col}: {nulls} null value(s) in a required column")
    return violations


def validate_or_raise(parquet_path: str, contract: dict) -> None:
    violations = validate_parquet(parquet_path, contract)
    if violations:
        raise ContractViolation(violations)
