# odata-lakehouse

Sync any OData v4 service into a local Parquet lakehouse, with incremental
watermarks, schema contracts and dbt staging scaffolding.

OData is the API style exposed by SAP systems (S/4HANA, BW/4HANA OData
services, SAP Gateway) and many others. This tool pulls entity sets into
Parquet files you can query with DuckDB, polars or pandas, keeps them fresh
with incremental syncs, and checks them against declared contracts.

Built as a portfolio project for data engineering work on SAP-style data:
pipelines that land enterprise API data in a lakehouse are the daily bread
of BW/4HANA and Databricks work.

## Install

```bash
pip install git+https://github.com/Lakshminarayana7844/odata-lakehouse.git
```

Or from a clone: `pip install .`

## Quickstart

Sync the public Northwind demo service:

```bash
odata-lakehouse sync Products \
  --base-url https://services.odata.org/V4/Northwind/Northwind.svc \
  --out ./lake --state ./state.json --keys ProductID
```

Validate the result against a contract (see `examples/products_contract.json`):

```bash
odata-lakehouse validate ./lake/products.parquet --contract examples/products_contract.json
```

Scaffold dbt staging models for everything in the lake:

```bash
odata-lakehouse scaffold-dbt ./lake --keys products:ProductID --out ./dbt/models/staging
```

`examples/sync_northwind.sh` runs all three steps.

## Incremental sync

Pass `--watermark <column>` (an ISO timestamp or increasing integer column).
The highest synced value is stored in the state file, and later runs fetch
only newer rows and merge them last-write-wins on `--keys`:

```bash
odata-lakehouse sync Products --base-url ... --watermark LastModified --keys ProductID
```

Delete the state file to force a full reload.

## What is inside

| Piece | What it does |
| --- | --- |
| `client.py` | Stdlib OData v4 reader: nextLink and top/skip pagination, retries with backoff |
| `sync.py` | Full and incremental sync to Parquet, last-write-wins merge on key columns |
| `state.py` | JSON watermark store, atomic writes |
| `contracts.py` | Schema contracts: required columns, expected types, null checks, all violations reported |
| `dbtgen.py` | dbt staging models over `read_parquet`, schema.yml with key tests |
| `cli.py` | `sync`, `validate`, `scaffold-dbt` commands |

18 tests cover pagination, filters, retries, watermark state, incremental
merge semantics, contracts, scaffolding and the CLI end to end against an
in-process mock OData server (no network needed).

## Docker

```bash
docker build -t odata-lakehouse .
docker run --rm -v "$PWD/lake:/app/lake" odata-lakehouse sync Products \
  --base-url https://services.odata.org/V4/Northwind/Northwind.svc --out ./lake --keys ProductID
```

## Honest limits

- Read-only. Writes to OData services are deliberately out of scope.
- The incremental `$filter` assumes the service supports `gt` comparisons on
  the watermark column; most OData v4 services do, some restrict filtering.
- OData `$filter` translation is string-based and covers common cases; very
  complex service-specific query behavior may need a custom `params` pass
  through the Python API.
- Large entity sets are materialised in memory before writing. Chunked
  writing is future work.
- The mock server in tests models common OData v4 behavior, not every
  vendor quirk; SAP Gateway services can differ in details (CSRF tokens,
  sap-specific headers) that a production integration would add.
