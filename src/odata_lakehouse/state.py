"""Watermark state for incremental syncs.

One JSON file tracks, per table, the highest watermark value synced so
far. The file is the only state: delete it to force a full reload.
"""
import json
import os
import tempfile


class WatermarkStore:
    def __init__(self, path: str):
        self.path = path
        self._state = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path) as fh:
            return json.load(fh)

    def get(self, table: str) -> str | None:
        return self._state.get(table)

    def set(self, table: str, watermark) -> None:
        if watermark is not None:
            self._state[table] = watermark

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.path)))
        with os.fdopen(fd, "w") as fh:
            json.dump(self._state, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
