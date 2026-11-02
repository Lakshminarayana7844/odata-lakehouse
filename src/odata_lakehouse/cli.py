"""Command line interface.

    odata-lakehouse sync Products --base-url https://services.odata.org/V4/Northwind/Northwind.svc \
        --out ./lake --state ./state.json --watermark LastModified --keys ProductID
    odata-lakehouse validate ./lake/products.parquet --contract ./contracts/products.json
    odata-lakehouse scaffold-dbt ./lake --keys products:ProductID --out ./dbt/models/staging
"""
import argparse
import json
import os

import pyarrow.parquet as pq

from odata_lakehouse.client import ODataClient
from odata_lakehouse.contracts import load_contract, validate_parquet
from odata_lakehouse.dbtgen import scaffold
from odata_lakehouse.state import WatermarkStore
from odata_lakehouse.sync import sync_entity_set


def _cmd_sync(args) -> int:
    client = ODataClient(args.base_url)
    store = WatermarkStore(args.state)
    report = sync_entity_set(
        client,
        args.entity_set,
        args.out,
        store,
        watermark_column=args.watermark,
        key_columns=args.keys.split(",") if args.keys else None,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


def _cmd_validate(args) -> int:
    contract = load_contract(args.contract)
    violations = validate_parquet(args.parquet, contract)
    if violations:
        for v in violations:
            print(f"VIOLATION: {v}")
        return 1
    print(f"{args.parquet}: contract OK")
    return 0


def _cmd_scaffold(args) -> int:
    tables: dict[str, dict] = {}
    key_map = dict(pair.split(":", 1) for pair in (args.keys or []))
    for name in sorted(os.listdir(args.lake)):
        if not name.endswith(".parquet"):
            continue
        table = name[: -len(".parquet")]
        path = os.path.abspath(os.path.join(args.lake, name))
        columns = pq.read_table(path).column_names
        keys = key_map.get(table, "").split(",") if key_map.get(table) else []
        tables[table] = {"parquet": path, "keys": [k for k in keys if k], "columns": columns}
    if not tables:
        print(f"no parquet files in {args.lake}")
        return 1
    for path in scaffold(args.out, tables):
        print(f"wrote {path}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="odata-lakehouse")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="sync an entity set to Parquet")
    p_sync.add_argument("entity_set")
    p_sync.add_argument("--base-url", required=True)
    p_sync.add_argument("--out", default="./lake")
    p_sync.add_argument("--state", default="./.odata_lakehouse_state.json")
    p_sync.add_argument("--watermark")
    p_sync.add_argument("--keys", help="comma-separated key columns (required for incremental)")
    p_sync.set_defaults(func=_cmd_sync)

    p_val = sub.add_parser("validate", help="validate a Parquet file against a contract")
    p_val.add_argument("parquet")
    p_val.add_argument("--contract", required=True)
    p_val.set_defaults(func=_cmd_validate)

    p_dbt = sub.add_parser("scaffold-dbt", help="generate dbt staging models for a lake directory")
    p_dbt.add_argument("lake")
    p_dbt.add_argument("--keys", nargs="*", help="table:Key1,Key2 entries")
    p_dbt.add_argument("--out", required=True)
    p_dbt.set_defaults(func=_cmd_scaffold)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
