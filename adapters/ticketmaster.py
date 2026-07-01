"""Ticketmaster Discovery API adapter -- concerts, comedy, shows, sports near
Capitol Hill. Free keyed API; key read from TICKETMASTER_API_KEY env var."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from adapters.base import RawEvent, SourceAdapter
from adapters.http import get

_ENDPOINT = "https://app.ticketmaster.com/discovery/v2/events.json"


class TicketmasterAdapter(SourceAdapter):
    kind = "api"

    def __init__(self, source_id: str, url: str = "", scope: str = "local",
                 lat: float = 47.6145, lng: float = -122.3190,
                 radius_miles: int = 3) -> None:
        super().__init__(source_id, url, scope)
        self.lat, self.lng, self.radius = lat, lng, radius_miles
        self.api_key = os.environ.get("TICKETMASTER_API_KEY", "")

    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        if not self.api_key:
            return []
        params: dict[str, Any] = {
            "apikey": self.api_key,
            "latlong": f"{self.lat},{self.lng}",
            "radius": self.radius,
            "unit": "miles",
            "startDateTime": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "size": 100,
            "sort": "date,asc",
        }
        try:
            data = get(_ENDPOINT, params=params).json()
        except Exception:
            return []

        events = data.get("_embedded", {}).get("events", [])
        out: list[RawEvent] = []
        for e in events:
            raw = self._parse(e)
            if raw is not None:
                out.append(raw)
        return out

    def _parse(self, e: dict[str, Any]) -> RawEvent | None:
        start = e.get("dates", {}).get("start", {})
        begins = start.get("dateTime")  # ISO 8601 UTC, e.g. 2026-07-01T02:00:00Z
        if not begins:
            return None

        venue = {}
        lat = lng = None
        embedded = e.get("_embedded", {})
        if embedded.get("venues"):
            venue = embedded["venues"][0]
            loc = venue.get("location", {})
            if loc.get("latitude"):
                lat, lng = float(loc["latitude"]), float(loc["longitude"])

        classifications = e.get("classifications") or [{}]
        segment = classifications[0].get("segment", {}).get("name")

        images = e.get("images") or []
        pic = images[0].get("url") if images else None

        loc_bits = [venue.get("name"), (venue.get("city") or {}).get("name")]
        return {
            "origin_id": str(e.get("id") or ""),
            "title": e.get("name") or "Untitled",
            "description": (e.get("info") or e.get("pleaseNote") or "")[:1500],
            "url": e.get("url"),
            "begins_on": begins,
            "location_text": ", ".join(b for b in loc_bits if b),
            "lat": lat,
            "lng": lng,
            "category": segment,
            "picture_url": pic,
        }
