"""Meetup adapter -- the community-events spine (trivia, board games, drink
& draw, language exchanges, special-interest groups). Meetup killed its free
API, but its Next.js pages embed full event objects in __APOLLO_STATE__, so we
scrape the public 'find events' page(s) for URLs, then each event's detail page
for coordinates + full data. Personal-use scraping; polite delays throughout."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from adapters.base import RawEvent, SourceAdapter
from adapters.http import get, next_data, polite_sleep

_EVENT_URL_RE = re.compile(r"https://www\.meetup\.com/[^/\s\"\\]+/events/(\d+)")

# Interest keywords appended to the base find URL to widen coverage of the
# Meetup-style special-interest events we care most about.
_KEYWORDS = ["trivia", "board games", "book club", "language", "run club", ""]


def _deref(apollo: dict[str, Any], node: Any) -> Any:
    if isinstance(node, dict) and "__ref" in node:
        return apollo.get(node["__ref"], {})
    return node


class MeetupAdapter(SourceAdapter):
    kind = "html"

    def __init__(self, source_id: str, url: str, scope: str = "local",
                 max_events: int = 80) -> None:
        super().__init__(source_id, url, scope)
        self.max_events = max_events

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        urls = self._collect_event_urls()

        out: list[RawEvent] = []
        for url in urls:
            polite_sleep(0.35)
            raw = self._fetch_detail(url)
            if raw is None:
                continue
            begins = raw["begins_on"]
            if isinstance(begins, datetime) and since <= begins < until:
                out.append(raw)
        return out

    def _collect_event_urls(self) -> list[str]:
        """Gather event URLs across several interest-filtered find pages,
        reading Meetup's embedded __APOLLO_STATE__ (richer than the HTML)."""
        seen: set[str] = set()
        urls: list[str] = []
        for kw in _KEYWORDS:
            page_url = self.url + (f"&keywords={kw.replace(' ', '%20')}" if kw else "")
            try:
                polite_sleep(0.3)
                html = get(page_url).text
            except Exception:
                continue

            found = self._urls_from_apollo(html) or self._urls_from_html(html)
            for u in found:
                if u not in seen:
                    seen.add(u)
                    urls.append(u)
                if len(urls) >= self.max_events:
                    return urls
        return urls

    @staticmethod
    def _urls_from_apollo(html: str) -> list[str]:
        data = next_data(html)
        if not data:
            return []
        try:
            apollo = data["props"]["pageProps"]["__APOLLO_STATE__"]
        except (KeyError, TypeError):
            return []
        out = []
        for k, v in apollo.items():
            if k.startswith("Event:") and isinstance(v, dict):
                u = v.get("eventUrl")
                if u:
                    out.append(u.split("?")[0].rstrip("/") + "/")
        return out

    @staticmethod
    def _urls_from_html(html: str) -> list[str]:
        out, seen = [], set()
        for m in _EVENT_URL_RE.finditer(html):
            u = m.group(0).rstrip("/") + "/"
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _fetch_detail(self, url: str) -> RawEvent | None:
        try:
            data = next_data(get(url).text)
        except Exception:
            return None
        if not data:
            return None
        try:
            apollo = data["props"]["pageProps"]["__APOLLO_STATE__"]
        except (KeyError, TypeError):
            return None

        ev = next(
            (v for k, v in apollo.items()
             if k.startswith("Event:") and v.get("title") and v.get("dateTime")),
            None,
        )
        if ev is None:
            return None

        venue = _deref(apollo, ev.get("venue")) or {}
        group = _deref(apollo, ev.get("group")) or {}
        lat, lng = venue.get("lat"), venue.get("lon")

        loc_bits = [venue.get("name"), venue.get("address"), venue.get("city")]
        location_text = ", ".join(b for b in loc_bits if b)

        return {
            "origin_id": str(ev.get("id") or url),
            "title": ev.get("title") or "Untitled",
            "description": (ev.get("description") or "")[:1500],
            "url": ev.get("eventUrl") or url,
            "begins_on": _parse_dt(ev.get("dateTime")),
            "ends_on": _parse_dt(ev.get("endTime")),
            "location_text": location_text,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "category": group.get("name"),
        }


def _parse_dt(value: Any) -> Any:
    """Meetup gives ISO strings with tz offset, e.g. 2026-07-10T19:00:00-07:00."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return value
