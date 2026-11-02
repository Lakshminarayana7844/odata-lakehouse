import pyarrow.parquet as pq
import pytest

from odata_lakehouse.client import ODataClient
from odata_lakehouse.state import WatermarkStore
from odata_lakehouse.sync import sync_entity_set
from tests.mock_odata import PRODUCTS, make_server


@pytest.fixture()
def env(tmp_path):
    srv, base = make_server()
    yield {
        "client": ODataClient(base),
        "store": WatermarkStore(str(tmp_path / "state.json")),
        "out": str(tmp_path / "lake"),
    }
    srv.shutdown()


def test_full_sync_writes_all_rows(env):
    report = sync_entity_set(env["client"], "Products", env["out"], env["store"])
    assert report["mode"] == "full"
    assert report["rows_in_file"] == len(PRODUCTS)
    table = pq.read_table(report["output"])
    assert table.num_rows == len(PRODUCTS)


def test_incremental_sync_fetches_only_new_rows(env):
    sync_entity_set(env["client"], "Products", env["out"], env["store"],
                    watermark_column="LastModified", key_columns=["ProductID"])
    report = sync_entity_set(env["client"], "Products", env["out"], env["store"],
                             watermark_column="LastModified", key_columns=["ProductID"])
    assert report["mode"] == "incremental"
    assert report["fetched"] == 0  # nothing newer than the stored watermark
    assert report["rows_in_file"] == len(PRODUCTS)


def test_incremental_requires_keys(env):
    env["store"].set("products", "1010")
    env["store"].save()
    with pytest.raises(ValueError):
        sync_entity_set(env["client"], "Products", env["out"], env["store"],
                        watermark_column="LastModified")


def test_merge_is_last_write_wins(tmp_path):
    from odata_lakehouse.sync import _merge, _to_table

    existing = _to_table([{"id": 1, "v": "old"}, {"id": 2, "v": "keep"}])
    incoming = _to_table([{"id": 1, "v": "new"}])
    merged = _merge(existing, incoming, ["id"]).to_pylist()
    by_id = {r["id"]: r["v"] for r in merged}
    assert by_id == {1: "new", 2: "keep"}
