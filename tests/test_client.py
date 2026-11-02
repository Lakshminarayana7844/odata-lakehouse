import pytest

from odata_lakehouse.client import ODataClient, ODataError
from tests.mock_odata import PRODUCTS, make_server


@pytest.fixture()
def server():
    srv, base = make_server()
    yield srv, base
    srv.shutdown()


def test_iter_entities_follows_pagination(server):
    _, base = server
    client = ODataClient(base)
    rows = client.iter_entities("Products")
    assert len(rows) == len(PRODUCTS)
    assert rows[0]["ProductID"] == 1
    assert rows[-1]["ProductID"] == 25


def test_filter_is_passed_to_server(server):
    _, base = server
    client = ODataClient(base)
    rows = client.iter_entities("Products", {"$filter": "LastModified gt 1020"})
    assert len(rows) == 5
    assert all(r["LastModified"] > 1020 for r in rows)


def test_retries_exhausted_raises_odata_error():
    def failing_opener(req, timeout=None):
        raise TimeoutError("boom")

    client = ODataClient("http://127.0.0.1:1", retries=2, opener=failing_opener)
    with pytest.raises(ODataError):
        client.get("Products")
