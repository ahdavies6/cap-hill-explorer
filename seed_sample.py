"""Seed a small SAMPLE dataset of real Capitol Hill venues so the map demo
is visibly alive before real feeds/API keys are wired in.
These are illustrative placeholder events, NOT scraped listings.
Usage: uv run python seed_sample.py"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import LOCAL_TZ
from core import geo, store
from core.models import Address, Event

# (title, venue, lat, lng, local_hour, url) -- anchored to tonight, Seattle time
_VENUES = [
    ("Happy hour + trivia", "Optimism Brewing", 47.6135, -122.3170, 18, "https://www.optimismbrewing.com/"),
    ("Vinyl listening lounge", "Vermillion", 47.6132, -122.3138, 19, "https://www.vermillionseattle.com/"),
    ("Outdoor movie in the park", "Cal Anderson Park", 47.6156, -122.3190, 20, "https://www.seattle.gov/parks/allparks/cal-anderson-park"),
    ("Standup comedy showcase", "Barboza", 47.6141, -122.3206, 20, "https://www.thebarboza.com/"),
    ("DJ night: synth & shoegaze", "Neumos", 47.6142, -122.3205, 21, "https://www.neumos.com/"),
    ("Indie rock live set", "The Crocodile", 47.6135, -122.3419, 21, "https://www.thecrocodile.com/"),
    ("Queer dance party", "Massive", 47.6139, -122.3210, 22, "https://www.massive.club/"),
]


def build() -> list[Event]:
    tz = ZoneInfo(LOCAL_TZ)
    tonight = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    events = []
    for title, venue, lat, lng, hour, url in _VENUES:
        begins_local = tonight.replace(hour=hour)
        begins = begins_local.astimezone(timezone.utc)
        ev = Event(
            source_id="sample-seed",
            origin_id=f"sample::{venue}::{title}",
            title=title,
            description=f"Sample event at {venue}. Replace with real feed data.",
            begins_on=begins,
            ends_on=begins + timedelta(hours=2),
            category="nightlife",
            url=url,
            address=Address(street=venue, lat=lat, lng=lng),
        )
        located = geo.locate(ev)
        if located:
            events.append(located)
    return events


if __name__ == "__main__":
    conn = store.connect()
    n = store.upsert(conn, build())
    conn.close()
    print(f"Seeded {n} sample Capitol Hill events.")
