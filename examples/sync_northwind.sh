#!/usr/bin/env bash
# Sync the public Northwind OData v4 demo service into ./lake.
# Requires network access to services.odata.org.
set -euo pipefail
odata-lakehouse sync Products \
  --base-url https://services.odata.org/V4/Northwind/Northwind.svc \
  --out ./lake \
  --state ./state.json \
  --keys ProductID
odata-lakehouse validate ./lake/products.parquet --contract examples/products_contract.json
odata-lakehouse scaffold-dbt ./lake --keys products:ProductID --out ./dbt/models/staging
