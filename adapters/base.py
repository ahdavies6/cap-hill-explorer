"""SourceAdapter interface. Mirrors the adapter/plugin shape used by
Gancio and Mobilizon's event importer: each source is one class that
yields RawEvent dicts over a time window."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypedDict


class RawEvent(TypedDict, total=False):
    """Loosely-typed payload emitted by adapters, before normalization."""

    origin_id: str
    title: str
    description: str
    url: str
    begins_on: Any  # datetime | str
    ends_on: Any
    location_text: str
    lat: float
    lng: float
    category: str
    picture_url: str


class SourceAdapter(ABC):
    id: str
    kind: str  # "ical" | "rss" | "api" | "html"
    scope: str  # "local" | "national" | "intl"

    def __init__(self, source_id: str, url: str, scope: str = "local") -> None:
        self.id = source_id
        self.url = url
        self.scope = scope

    @abstractmethod
    def fetch(self, since: datetime, until: datetime) -> list[RawEvent]:
        """Return raw events beginning within [since, until)."""
        raise NotImplementedError
