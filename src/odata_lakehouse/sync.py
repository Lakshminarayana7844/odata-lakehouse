"""Sync an OData entity set to a Parquet file.

Two modes:
- full: read everything, replace the output file.
- incremental: pass a watermark column (an ISO timestamp or increasing
  integer). Only rows above the stored watermark are fetched and merged
  over the existing file with last-write-wins on the key columns.
"""
import os

import pyarrow as pa
import pyarrow.parquet as pq

from odata_lakehouse.client import ODataClient
from odata_lakehouse.state import WatermarkStore


def _to_table(rows: list[dict]) -> pa.Table:
    if not rows:
        return None
    keys = sorted({k for row in rows for k in row})
    normalized = [{k: row.get(k) for k in keys} for row in rows]
    return pa.Table.from_pylist(normalized)


def _merge(existing: pa.Table, incoming: pa.Table, key_columns: list[str]) -> pa.Table:
    """Last-write-wins upsert on key columns."""
    if existing is None:
        return incoming
    if incoming is None or incoming.num_rows == 0:
        return existing
    combined = pa.concat_tables([existing, incoming], promote_options="default")
    seen: dict = {}
    order: list = []
    records = combined.to_pylist()
    for idx, row in enumerate(records):
        key = tuple(row.get(k) for k in key_columns)
        if key not in seen:
            order.append(key)
        seen[key] = idx
    merged = [records[seen[key]] for key in order]
    return _to_table(merged)


def sync_entity_set(
    client: ODataClient,
    entity_set: str,
    out_dir: str,
    store: WatermarkStore,
    watermark_column: str | None = None,
    key_columns: list[str] | None = None,
    params: dict | None = None,
) -> dict:
    """Sync one entity set. Returns a small run report."""
    table_name = entity_set.lower()
    out_path = os.path.join(out_dir, f"{table_name}.parquet")
    os.makedirs(out_dir, exist_ok=True)

    query = dict(params or {})
    previous_watermark = store.get(table_name) if watermark_column else None
    incremental = bool(watermark_column and previous_watermark)
    if incremental and not key_columns:
        raise ValueError("incremental sync requires key_columns for the merge")
    if incremental:
        filter_expr = f"{watermark_column} gt {previous_watermark}"
        query["$filter"] = f"({query['$filter']}) and {filter_expr}" if query.get("$filter") else filter_expr

    rows = client.iter_entities(entity_set, query)
    incoming = _to_table(rows)

    if incremental and os.path.exists(out_path):
        existing = pq.read_table(out_path)
        table = _merge(existing, incoming, key_columns)
    else:
        table = incoming

    written = 0
    if table is not None and table.num_rows > 0:
        pq.write_table(table, out_path)
        written = table.num_rows

    if watermark_column and rows:
        candidates = [r.get(watermark_column) for r in rows if r.get(watermark_column) is not None]
        if candidates:
            store.set(table_name, max(candidates, key=str))
            store.save()

    return {
        "entity_set": entity_set,
        "mode": "incremental" if incremental else "full",
        "fetched": len(rows),
        "rows_in_file": written,
        "watermark": store.get(table_name),
        "output": out_path,
    }
