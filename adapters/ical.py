"""Generic iCal/ICS adapter. Works for seattle.gov, venue calendars,
Luma per-event .ics, etc."""

from __future__ import annotations

from datetime import datetime, date, time, timezone

import httpx
from icalendar import Calendar

from adapters.base import RawEvent, SourceAdapter


def _to_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    return None


class ICalAdapter(SourceAdapter):
    kind = "ical"

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        resp = httpx.get(self.url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)

        out: list[RawEvent] = []
        for comp in cal.walk("VEVENT"):
            begins = _to_dt(comp.get("dtstart").dt) if comp.get("dtstart") else None
            if begins is None or not (since <= begins < until):
                continue
            ends = _to_dt(comp.get("dtend").dt) if comp.get("dtend") else None
            loc = str(comp.get("location") or "")
            geo = comp.get("geo")
            raw: RawEvent = {
                "origin_id": str(comp.get("uid") or ""),
                "title": str(comp.get("summary") or "Untitled"),
                "description": str(comp.get("description") or ""),
                "url": str(comp.get("url") or ""),
                "begins_on": begins,
                "ends_on": ends,
                "location_text": loc,
            }
            if geo is not None:
                try:
                    raw["lat"], raw["lng"] = float(geo.latitude), float(geo.longitude)
                except Exception:
                    pass
            out.append(raw)
        return out
