"""Build the enabled adapter list from config.SOURCES."""

from __future__ import annotations

from adapters.base import SourceAdapter
from adapters.chs_blog import CHSBlogAdapter
from adapters.do206 import Do206Adapter
from adapters.ical import ICalAdapter
from adapters.meetup import MeetupAdapter
from adapters.rss import RSSAdapter
from adapters.ticketmaster import TicketmasterAdapter
from config import SOURCES

_KINDS = {
    "ical": ICalAdapter,
    "rss": RSSAdapter,
    "meetup": MeetupAdapter,
    "ticketmaster": TicketmasterAdapter,
    "do206": Do206Adapter,
    "chs-blog": CHSBlogAdapter,
}


def build_adapters() -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    for src in SOURCES:
        cls = _KINDS.get(src["kind"])
        if cls is None:
            continue
        adapters.append(cls(src["id"], src["url"], src.get("scope", "local")))
    return adapters
