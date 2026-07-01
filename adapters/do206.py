"""Do206 adapter (DoStuff Media platform). Exposes a clean unauthenticated
JSON API by appending .json to date-listing URLs. Per-event venue objects
carry lat/lon, so bbox filtering is straightforward. Concerts, comedy,
culture, food -- a good complement to Meetup's community events."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from adapters.base import RawEvent, SourceAdapter
from adapters.http import get, polite_sleep

_BASE = "https://do206.com"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()


class Do206Adapter(SourceAdapter):
    kind = "api"

    def __init__(self, source_id: str, url: str = _BASE, scope: str = "local",
                 max_pages: int = 4) -> None:
        super().__init__(source_id, url or _BASE, scope)
        self.max_pages = max_pages

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        out: list[RawEvent] = []
        day = since.astimezone(timezone.utc).date()
        last = until.astimezone(timezone.utc).date()

        while day <= last:
            for page in range(1, self.max_pages + 1):
                url = f"{_BASE}/events/{day.year}/{day.month}/{day.day}.json"
                try:
                    polite_sleep(0.3)
                    data = get(url, params={"page": page}).json()
                except Exception:
                    break
                events = data.get("events", [])
                for e in events:
                    raw = self._parse(e)
                    if raw is not None:
                        out.append(raw)
                total = data.get("paging", {}).get("total_pages", 1)
                if page >= total:
                    break
            day += timedelta(days=1)
        return out

    def _parse(self, e: dict[str, Any]) -> RawEvent | None:
        begins = e.get("tz_adjusted_begin_date")  # Seattle-local ISO w/ offset
        if not begins:
            return None
        v = e.get("venue") or {}
        lat, lng = v.get("latitude"), v.get("longitude")

        aws = (e.get("imagery") or {}).get("aws", {})
        pic = (aws.get("cover_image_h_630_w_1200")
               or aws.get("cover_image_h_300_w_864")
               or aws.get("poster_w_800"))

        return {
            "origin_id": f"do206_{e.get('id')}",
            "title": e.get("title") or "Untitled",
            "description": _strip_html(e.get("description") or e.get("excerpt") or "")[:1500],
            "url": _BASE + e["permalink"] if e.get("permalink") else None,
            "begins_on": begins,
            "ends_on": e.get("tz_adjusted_end_date"),
            "location_text": ", ".join(
                b for b in (v.get("title"), v.get("full_address")) if b
            ),
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "category": e.get("category"),
            "picture_url": pic,
        }
