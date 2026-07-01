"""Shared HTTP helpers: a browser-ish client + Next.js __NEXT_DATA__ parsing."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

_client = httpx.Client(
    headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
    timeout=25,
    follow_redirects=True,
)

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)


def get(url: str, **kwargs: Any) -> httpx.Response:
    return _client.get(url, **kwargs)


def polite_sleep(seconds: float = 0.4) -> None:
    time.sleep(seconds)


def next_data(html: str) -> dict[str, Any] | None:
    """Extract and parse a Next.js __NEXT_DATA__ blob from a page."""
    m = _NEXT_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def ld_json(html: str) -> list[dict[str, Any]]:
    """Return all schema.org JSON-LD objects on a page, flattening @graph and
    top-level arrays. Handy for schema.org/Event extraction."""
    out: list[dict[str, Any]] = []
    for m in _LDJSON_RE.finditer(html):
        blob = m.group(1).strip()
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if "@graph" in item and isinstance(item["@graph"], list):
                out.extend(g for g in item["@graph"] if isinstance(g, dict))
            else:
                out.append(item)
    return out
