import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from odata_lakehouse.contracts import ContractViolation, load_contract, validate_or_raise, validate_parquet


@pytest.fixture()
def parquet_file(tmp_path):
    table = pa.table({"ProductID": [1, 2, 3], "ProductName": ["a", "b", "c"], "UnitPrice": [1.5, 2.5, None]})
    path = tmp_path / "products.parquet"
    pq.write_table(table, path)
    return str(path)


def test_valid_contract_passes(parquet_file):
    contract = {"columns": {
        "ProductID": {"type": "int", "required": True},
        "ProductName": {"type": "string", "required": True},
        "UnitPrice": {"type": "float"},
    }}
    assert validate_parquet(parquet_file, contract) == []


def test_missing_required_column_reported(parquet_file):
    contract = {"columns": {"CategoryID": {"type": "int", "required": True}}}
    violations = validate_parquet(parquet_file, contract)
    assert violations == ["missing required column: CategoryID"]


def test_wrong_type_and_nulls_reported(parquet_file):
    contract = {"columns": {
        "ProductID": {"type": "string"},
        "UnitPrice": {"type": "float", "required": True},
    }}
    violations = validate_parquet(parquet_file, contract)
    assert any("expected type string" in v for v in violations)
    assert any("null value" in v for v in violations)


def test_validate_or_raise(parquet_file):
    contract = {"columns": {"ProductID": {"type": "bool"}}}
    with pytest.raises(ContractViolation):
        validate_or_raise(parquet_file, contract)


def test_contract_must_have_columns(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        load_contract(str(path))
