"""Quick endpoint test script."""
import urllib.request
import json

BASE = "http://localhost:5000"

endpoints = [
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/check?asin=B08N5WRWNW"),
    ("GET", "/prices?asin=B08N5WRWNW"),
    ("GET", "/images?asin=B08N5WRWNW"),
    ("GET", "/export/csv?asin=B08N5WRWNW"),
    ("GET", "/export/json?asin=B08N5WRWNW"),
    ("GET", "/alerts"),
    ("GET", "/docs"),
]

for method, path in endpoints:
    url = BASE + path
    try:
        req = urllib.request.Request(url, method=method)
        resp = urllib.request.urlopen(req)
        print(f"OK  {resp.status}  {path}")
    except urllib.error.HTTPError as e:
        print(f"FAIL {e.code}  {path}  ({e.reason})")
    except Exception as e:
        print(f"ERR       {path}  ({e})")

# Test POST endpoints
import urllib.parse

post_endpoints = [
    ("/bulk-check", {"asins": ["B08N5WRWNW"]}),
    ("/alerts/subscribe", {"asin": "B08N5WRWNW"}),
    ("/alerts/check", {}),
]

for path, body in post_endpoints:
    url = BASE + path
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req)
        print(f"OK  {resp.status}  POST {path}")
    except urllib.error.HTTPError as e:
        print(f"FAIL {e.code}  POST {path}  ({e.reason})")
    except Exception as e:
        print(f"ERR       POST {path}  ({e})")
