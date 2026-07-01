"""RawEvent -> Event. tz-aware, coords passed through for geo.locate()."""

from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dtparser

from adapters.base import RawEvent
from core.models import Address, Event


def _coerce_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = dtparser.parse(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            return None
    return None


def normalize(raw: RawEvent, source_id: str) -> Event | None:
    begins = _coerce_dt(raw.get("begins_on"))
    if begins is None:
        return None

    address = None
    if raw.get("lat") is not None or raw.get("location_text"):
        address = Address(
            street=raw.get("location_text"),
            lat=raw.get("lat"),
            lng=raw.get("lng"),
        )

    return Event(
        source_id=source_id,
        origin_id=str(raw.get("origin_id") or ""),
        title=str(raw.get("title") or "Untitled").strip(),
        description=raw.get("description"),
        url=raw.get("url"),
        begins_on=begins.astimezone(timezone.utc),
        ends_on=_coerce_dt(raw.get("ends_on")),
        category=raw.get("category"),
        picture_url=raw.get("picture_url"),
        address=address,
        raw=dict(raw),
    )
