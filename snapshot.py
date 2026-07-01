"""Build the static site: scrape sources, write build/ (flat copy of web/static
plus a generated data.json snapshot). This is what CI publishes to GitHub Pages.

Usage:
    uv run python snapshot.py            # scrape, then build build/
    uv run python snapshot.py --no-fetch # skip scraping, just rebuild from DB
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config import LOCAL_TZ
from core import store

ROOT = Path(__file__).parent
STATIC = ROOT / "web" / "static"
BUILD = ROOT / "build"
_TZ = ZoneInfo(LOCAL_TZ)


def build_snapshot() -> dict:
    """Return the same payload the live /api/events?upcoming=1 endpoint serves:
    every event from local-midnight-today onward (Seattle time)."""
    conn = store.connect()
    local_midnight = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start = local_midnight.astimezone(timezone.utc)
    rows = store.query(conn, start=start)
    conn.close()
    return {
        "date": datetime.now(_TZ).date().isoformat(),
        "mode": "upcoming",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "events": rows,
    }


def build_site() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(STATIC, BUILD)
    snap = build_snapshot()
    (BUILD / "data.json").write_text(json.dumps(snap, ensure_ascii=False))
    print(f"[build] wrote build/data.json ({snap['count']} events, {snap['date']})")
    print(f"[build] site ready at {BUILD}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="skip scraping; rebuild from existing DB")
    ap.add_argument("--days", type=int, default=8, help="scrape window (days ahead)")
    args = ap.parse_args()

    if not args.no_fetch:
        import refresh
        # Scrape from now through `days` ahead. Ticketmaster self-disables in CI
        # (no key) and enrichment happens client-side, so no secrets are needed.
        refresh.run(days=args.days)

    build_site()


if __name__ == "__main__":
    main()
