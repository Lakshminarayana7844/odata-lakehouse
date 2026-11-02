"""In-process OData v4 mock server for tests.

Serves two entity sets with top/skip pagination, $filter on a watermark
column (numeric comparison only) and nextLink pagination, over a real
local HTTP server so the client code path is exercised end to end.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PRODUCTS = [
    {"ProductID": i, "ProductName": f"Product {i}", "UnitPrice": 10.0 + i, "LastModified": 1000 + i}
    for i in range(1, 26)
]
CATEGORIES = [
    {"CategoryID": i, "CategoryName": f"Category {i}"}
    for i in range(1, 6)
]
DATA = {"Products": PRODUCTS, "Categories": CATEGORIES}
PAGE_SIZE = 10


def _apply_filter(rows: list[dict], filter_expr: str | None) -> list[dict]:
    if not filter_expr:
        return rows
    match = re.fullmatch(r"(\w+) gt (\d+)", filter_expr.strip())
    if not match:
        return rows
    column, value = match.group(1), int(match.group(2))
    return [r for r in rows if r.get(column) is not None and r[column] > value]


def make_server() -> tuple[HTTPServer, str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            set_name = parsed.path.strip("/").split("/")[-1]
            query = parse_qs(parsed.query)
            rows = list(DATA.get(set_name, []))
            rows = _apply_filter(rows, (query.get("$filter") or [None])[0])
            skip = int((query.get("$skip") or ["0"])[0])
            page = rows[skip: skip + PAGE_SIZE]
            body: dict = {"value": page}
            if skip + PAGE_SIZE < len(rows):
                body["@odata.nextLink"] = f"/{set_name}?$skip={skip + PAGE_SIZE}"
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"
