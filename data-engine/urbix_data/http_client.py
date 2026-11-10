from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int | None, body: str):
        super().__init__(f"{status or 'network'} {url} {body[:300]}")
        self.url = url
        self.status = status
        self.body = body


def _ssl_context():
    try:
        import certifi
        import ssl

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def request_json(url: str, *, params: dict | None = None, data: bytes | None = None, timeout: int = 60, headers: dict | None = None):
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"
    merged = {"User-Agent": "URBIX/0.1 (urban-intelligence research)", "Accept": "application/json"}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        merged["X-App-Token"] = token
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, data=data, headers=merged, method="POST" if data is not None else "GET")
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                import json

                return json.loads(text) if text else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = HttpError(url, exc.code, body)
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = HttpError(url, None, str(exc.reason))
        time.sleep(2 * (attempt + 1))
    raise last_error


def request_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "URBIX/0.1 (urban-intelligence research)"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = HttpError(url, exc.code, exc.read().decode("utf-8", errors="replace"))
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = HttpError(url, None, str(exc.reason))
        time.sleep(2 * (attempt + 1))
    raise last_error


class SodaClient:
    def __init__(self, domain: str):
        self.domain = domain

    def fetch(self, dataset_id: str, params: dict | None = None, max_rows: int = 5000, page_size: int = 5000, timeout: int = 90) -> list[dict]:
        params = dict(params or {})
        rows: list[dict] = []
        offset = int(params.pop("$offset", 0) or 0)
        while len(rows) < max_rows:
            page = dict(params)
            page["$limit"] = min(page_size, max_rows - len(rows))
            page["$offset"] = offset
            batch = request_json(f"https://{self.domain}/resource/{dataset_id}.json", params=page, timeout=timeout)
            if not isinstance(batch, list):
                raise HttpError(dataset_id, 200, f"expected a list, got {type(batch).__name__}")
            rows.extend(batch)
            if len(batch) < page["$limit"]:
                break
            offset += len(batch)
        return rows
