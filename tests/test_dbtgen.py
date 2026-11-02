from odata_lakehouse.dbtgen import scaffold


def test_scaffold_writes_models_and_schema(tmp_path):
    out = str(tmp_path / "staging")
    tables = {
        "products": {
            "parquet": "/lake/products.parquet",
            "keys": ["ProductID"],
            "columns": ["ProductID", "ProductName"],
        }
    }
    written = scaffold(out, tables)
    assert len(written) == 2
    sql = open(written[0]).read()
    assert "read_parquet('/lake/products.parquet')" in sql
    yml = open(written[1]).read()
    assert "stg_products" in yml
    assert "not_null" in yml
    assert "unique" in yml


def test_non_key_columns_have_no_tests(tmp_path):
    out = str(tmp_path / "s")
    scaffold(out, {"t": {"parquet": "/p.parquet", "keys": ["id"], "columns": ["id", "note"]}})
    yml = open(f"{out}/schema.yml").read()
    note_block = yml.split("- name: note")[1]
    assert "not_null" not in note_block
