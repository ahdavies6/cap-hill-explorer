"""Geo filtering: is an event in the Capitol Hill bbox?"""

from __future__ import annotations

import re
from typing import Optional

from config import CAP_HILL_BBOX, CAP_HILL_CENTER, NEIGHBORHOOD_LABEL
from core.models import Event

# Cheap text hints that a location string is in/around Capitol Hill,
# used when a source gives no coordinates.
_TEXT_HINTS = re.compile(
    r"\b(capitol\s*hill|pike[/\s-]*pine|pike st|pine st|"
    r"broadway|12th ave|15th ave e|neumos|barboza|"
    r"the crocodile|massive|cal anderson)\b",
    re.IGNORECASE,
)


def in_bbox(lat: float, lng: float) -> bool:
    b = CAP_HILL_BBOX
    return (
        b["min_lat"] <= lat <= b["max_lat"]
        and b["min_lng"] <= lng <= b["max_lng"]
    )


def _text_blob(event: Event) -> str:
    parts = [event.title or "", event.description or ""]
    if event.address:
        parts += [
            event.address.street or "",
            event.address.locality or "",
        ]
    return " ".join(parts)


def locate(event: Event) -> Optional[Event]:
    """Return the event if it's in Capitol Hill (tagged + coords backfilled),
    else None. Coordinates win; text hints are the fallback."""
    addr = event.address
    if addr and addr.lat is not None and addr.lng is not None:
        if in_bbox(addr.lat, addr.lng):
            _tag(event)
            return event
        return None

    # No coords: fall back to text hints, then pin to the CapHill centroid.
    if _TEXT_HINTS.search(_text_blob(event)):
        if event.address is None:
            from core.models import Address

            event.address = Address()
        event.address.lat, event.address.lng = CAP_HILL_CENTER
        _tag(event)
        return event

    return None


def _tag(event: Event) -> None:
    if NEIGHBORHOOD_LABEL not in event.tags:
        event.tags.append(NEIGHBORHOOD_LABEL)
    if event.address:
        event.address.locality = event.address.locality or NEIGHBORHOOD_LABEL
