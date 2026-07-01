"""Dedup: drop events that are the same happening from different sources.
Exact match on uid, then fuzzy match on (title, start-time proximity)."""

from __future__ import annotations

from datetime import timedelta

from rapidfuzz import fuzz

from core.models import Event

_TITLE_THRESHOLD = 88  # rapidfuzz token_sort_ratio
_TIME_WINDOW = timedelta(hours=2)


def dedup(events: list[Event]) -> list[Event]:
    """Return events with duplicates removed. Earlier-listed sources win."""
    kept: list[Event] = []
    seen_uids: set[str] = set()

    for ev in events:
        if ev.uid in seen_uids:
            continue
        if any(_is_dup(ev, k) for k in kept):
            continue
        kept.append(ev)
        seen_uids.add(ev.uid)

    return kept


def _is_dup(a: Event, b: Event) -> bool:
    if abs(a.begins_on - b.begins_on) > _TIME_WINDOW:
        return False
    return fuzz.token_sort_ratio(a.title, b.title) >= _TITLE_THRESHOLD
