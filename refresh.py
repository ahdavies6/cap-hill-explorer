"""CLI: run every adapter over a window, normalize, geo-filter to Capitol
Hill, dedup, store. Usage: uv run python refresh.py [--days N]"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_env(path: str = ".env") -> None:
    """Minimal .env loader so TICKETMASTER_API_KEY is available (no new dep)."""
    p = Path(__file__).parent / path
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_env()

from adapters.registry import build_adapters
from core import geo, store
from core.dedup import dedup
from core.normalize import normalize


def run(
    days: int = 14,
    only: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    if since is None:
        since = datetime.now(timezone.utc)
    if until is None:
        until = since + timedelta(days=days)

    collected = []
    per_source: dict[str, int] = {}
    for adapter in build_adapters():
        if only and adapter.id != only:
            continue
        try:
            raws = adapter.fetch(since, until)
        except Exception as exc:  # one bad source shouldn't kill the run
            print(f"[warn] {adapter.id} failed: {exc}")
            continue
        kept = 0
        for raw in raws:
            ev = normalize(raw, adapter.id)
            if ev is None:
                continue
            located = geo.locate(ev)  # None if outside Capitol Hill
            if located is None:
                continue
            collected.append(located)
            kept += 1
        per_source[adapter.id] = kept
        print(f"[ok]   {adapter.id}: {len(raws)} fetched -> {kept} in Capitol Hill")

    deduped = dedup(collected)
    conn = store.connect()
    n = store.upsert(conn, deduped)
    conn.close()
    dupes = len(collected) - len(deduped)
    print(f"\nStored {n} events ({dupes} dupes removed).")
    return {"stored": n, "dupes": dupes, "per_source": per_source}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--source", default=None, help="run only this source id")
    args = ap.parse_args()
    run(args.days, args.source)
