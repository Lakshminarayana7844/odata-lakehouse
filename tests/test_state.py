from odata_lakehouse.state import WatermarkStore


def test_watermark_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    store = WatermarkStore(path)
    assert store.get("products") is None
    store.set("products", "2026-01-01T00:00:00Z")
    store.save()
    reloaded = WatermarkStore(path)
    assert reloaded.get("products") == "2026-01-01T00:00:00Z"


def test_none_watermark_not_stored(tmp_path):
    store = WatermarkStore(str(tmp_path / "s.json"))
    store.set("t", None)
    assert store.get("t") is None
