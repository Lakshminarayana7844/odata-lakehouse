import json

import pyarrow.parquet as pq

from odata_lakehouse.cli import main
from tests.mock_odata import PRODUCTS, make_server


def test_cli_sync_validate_scaffold(tmp_path, capsys):
    srv, base = make_server()
    try:
        out = str(tmp_path / "lake")
        state = str(tmp_path / "state.json")
        rc = main(["sync", "Products", "--base-url", base, "--out", out, "--state", state])
        assert rc == 0
        report = json.loads(capsys.readouterr().out)
        assert report["rows_in_file"] == len(PRODUCTS)
    finally:
        srv.shutdown()

    contract = tmp_path / "products.json"
    contract.write_text(json.dumps({"columns": {
        "ProductID": {"type": "int", "required": True},
        "ProductName": {"type": "string", "required": True},
    }}))
    rc = main(["validate", report["output"], "--contract", str(contract)])
    assert rc == 0
    assert "contract OK" in capsys.readouterr().out

    staging = str(tmp_path / "staging")
    rc = main(["scaffold-dbt", out, "--keys", "products:ProductID", "--out", staging])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "stg_products.sql" in printed
    table = pq.read_table(report["output"])
    assert "ProductID" in table.column_names


def test_cli_validate_fails_on_violation(tmp_path, capsys):
    import pyarrow as pa

    path = tmp_path / "t.parquet"
    pq.write_table(pa.table({"a": [1]}), path)
    contract = tmp_path / "c.json"
    contract.write_text(json.dumps({"columns": {"b": {"type": "int", "required": True}}}))
    rc = main(["validate", str(path), "--contract", str(contract)])
    assert rc == 1
    assert "VIOLATION" in capsys.readouterr().out
