"""Normalized event model, Mobilizon-shaped (see framagit kaihuri/mobilizon
lib/mobilizon/events/event.ex and addresses/address.ex)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class Address:
    locality: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    timezone: Optional[str] = None
    origin_id: Optional[str] = None


@dataclass
class Event:
    source_id: str
    origin_id: str
    title: str
    begins_on: datetime
    url: Optional[str] = None
    description: Optional[str] = None
    ends_on: Optional[datetime] = None
    status: str = "confirmed"  # confirmed | tentative | cancelled
    category: Optional[str] = None
    language: str = "en"
    online_address: Optional[str] = None
    address: Optional[Address] = None
    picture_url: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    uid: str = ""  # stable dedup key, filled by __post_init__

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = self.compute_uid()

    def compute_uid(self) -> str:
        """Stable hash of source + origin id (fallback: title+time)."""
        basis = f"{self.source_id}::{self.origin_id or ''}"
        if not self.origin_id:
            basis = f"{self.source_id}::{self.title}::{self.begins_on.isoformat()}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["begins_on"] = self.begins_on.isoformat()
        d["ends_on"] = self.ends_on.isoformat() if self.ends_on else None
        return d
