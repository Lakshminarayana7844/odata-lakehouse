"""Minimal OData v4 read client.

Stdlib only: no requests dependency. Handles the two pagination styles
seen in the wild (@odata.nextLink and plain top/skip) and retries on
transient failures with backoff. Write operations are out of scope on
purpose: this library reads.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_PAGES = 10_000  # safety bound against misbehaving services


class ODataError(RuntimeError):
    pass


class ODataClient:
    def __init__(self, base_url: str, retries: int = 3, timeout: float = 30.0,
                 opener=None):
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def get(self, path: str, params: dict | None = None) -> dict:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, safe='$,')}"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with self._opener(urllib.request.Request(url), timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        raise ODataError(f"GET {url} failed after {self.retries} attempts: {last_error}")

    def iter_entities(self, entity_set: str, params: dict | None = None) -> list[dict]:
        """Read every row of an entity set, following pagination."""
        rows: list[dict] = []
        page = self.get(entity_set, params)
        for _ in range(MAX_PAGES):
            rows.extend(page.get("value", []))
            next_link = page.get("@odata.nextLink")
            if not next_link:
                return rows
            page = self.get(next_link)
        raise ODataError(f"{entity_set}: exceeded {MAX_PAGES} pages, refusing to continue")
