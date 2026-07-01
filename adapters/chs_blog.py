"""Capitol Hill Seattle Blog (CHS) adapter. The CHS 'CHS Calendar' page embeds
a CitySpark white-label calendar; CitySpark's PortalScript endpoint ships a
pre-rendered `var cSparkLocals = {...}` bundle with real, coordinate-tagged
Capitol Hill events (its POST API returns junk without auth, so we parse the
bundle). Neighborhood blog = inherently local flavor: trivia, drink & draw,
comedy, art walks, small shows."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from adapters.base import RawEvent, SourceAdapter
from adapters.http import get

_PORTAL = "https://portal.cityspark.com/PortalScripts/CapitolHillSeattle"
_MARKER = "var cSparkLocals = "


def _extract_bundle(text: str) -> dict[str, Any] | None:
    """Pull the JSON object assigned to `var cSparkLocals` by brace-matching."""
    if _MARKER not in text:
        return None
    raw = text[text.index(_MARKER) + len(_MARKER):]
    depth = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[: i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class CHSBlogAdapter(SourceAdapter):
    kind = "api"

    def __init__(self, source_id: str, url: str = _PORTAL, scope: str = "local") -> None:
        super().__init__(source_id, url or _PORTAL, scope)

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        try:
            data = _extract_bundle(get(self.url).text)
        except Exception:
            return []
        if not data:
            return []

        tag_lookup = {t.get("id"): t for t in data.get("Tags", [])}
        seen: set[str] = set()
        raws: list[RawEvent] = []
        for e in data.get("Events", []) + data.get("Promos", []):
            raw = self._parse(e, tag_lookup)
            if raw is None or raw["origin_id"] in seen:
                continue
            seen.add(raw["origin_id"])
            raws.append(raw)
        return raws

    def _parse(self, e: dict[str, Any], tags: dict[Any, dict]) -> RawEvent | None:
        begins = e.get("StartUTC") or e.get("DateStart")
        if not begins or not e.get("Name"):
            return None

        top = [
            tags[t]["name"]
            for t in (e.get("Tags") or [])
            if t in tags and tags[t].get("parent") is None and tags[t].get("name")
        ]
        loc_bits = [e.get("Venue"), e.get("Address"), e.get("CityState"), e.get("Zip")]
        lat, lng = e.get("latitude"), e.get("longitude")

        return {
            "origin_id": f"cityspark_{e.get('PId')}",
            "title": e.get("Name"),
            "description": (e.get("Description") or e.get("Short") or "")[:1500],
            "url": e.get("PrimaryUrl") or e.get("TicketUrl") or "",
            "begins_on": begins,
            "ends_on": e.get("EndUTC") or e.get("DateEnd"),
            "location_text": ", ".join(b for b in loc_bits if b),
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "category": top[0] if top else None,
            "picture_url": e.get("LargeImg") or e.get("MediumImg") or e.get("SmallImg"),
        }
