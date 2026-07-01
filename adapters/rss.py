"""Generic RSS/Atom adapter. Works for EverOut, The Stranger,
Bandsintown artist feeds, etc. Location/coords usually absent here,
so geo.locate() leans on text hints downstream."""

from __future__ import annotations

from datetime import datetime, timezone
from time import mktime

import feedparser

from adapters.base import RawEvent, SourceAdapter


def _entry_dt(entry: object) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or (
            entry.get(key) if isinstance(entry, dict) else None
        )
        if val:
            return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
    return None


class RSSAdapter(SourceAdapter):
    kind = "rss"

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        feed = feedparser.parse(self.url)
        out: list[RawEvent] = []
        for entry in feed.entries:
            begins = _entry_dt(entry)
            if begins is None or not (since <= begins < until):
                continue
            summary = getattr(entry, "summary", "") or ""
            out.append(
                {
                    "origin_id": getattr(entry, "id", "") or getattr(entry, "link", ""),
                    "title": getattr(entry, "title", "Untitled"),
                    "description": summary,
                    "url": getattr(entry, "link", ""),
                    "begins_on": begins,
                    "location_text": summary,
                }
            )
        return out
