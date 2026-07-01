"""FastAPI app: serves the Leaflet map and a read-only events API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import LOCAL_TZ
from core import store

app = FastAPI(title="Cap Hill Explorer")
_STATIC = Path(__file__).parent / "static"
_TZ = ZoneInfo(LOCAL_TZ)


@app.get("/api/events")
def events(
    date: Optional[str] = Query(None, description="YYYY-MM-DD (Seattle-local); default tonight"),
    q: Optional[str] = Query(None, description="full-text search"),
    upcoming: bool = Query(False, description="ignore day; return next events from now"),
):
    conn = store.connect()

    if upcoming:
        # Start at local midnight *today* (not `now`), so a "what's on tonight"
        # view still shows events that began earlier this evening.
        local_midnight = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        start = local_midnight.astimezone(timezone.utc)
        rows = store.query(conn, start=start, text=q)
        conn.close()
        label = datetime.now(_TZ).date().isoformat()
        return {"date": label, "mode": "upcoming", "count": len(rows), "events": rows}

    # Interpret `date` as a Seattle-local calendar day, then convert the
    # day's [00:00, 24:00) local window to UTC for the stored (UTC) events.
    if date:
        local_day = datetime.fromisoformat(date).replace(tzinfo=_TZ)
    else:
        local_day = datetime.now(_TZ)
    local_start = local_day.replace(hour=0, minute=0, second=0, microsecond=0)
    start = local_start.astimezone(timezone.utc)
    end = (local_start + timedelta(days=1)).astimezone(timezone.utc)

    rows = store.query(conn, start=start, end=end, text=q)
    conn.close()
    return {"date": local_start.date().isoformat(), "mode": "day",
            "count": len(rows), "events": rows}


@app.post("/api/refresh")
def refresh(
    frm: Optional[str] = Query(None, alias="from", description="YYYY-MM-DD Seattle-local"),
    to: Optional[str] = Query(None, description="YYYY-MM-DD Seattle-local"),
):
    """Re-pull sources over a Seattle-local day window (default: today only)."""
    import refresh as refresh_mod

    today = datetime.now(_TZ).date()
    start_day = datetime.fromisoformat(frm).date() if frm else today
    end_day = datetime.fromisoformat(to).date() if to else start_day

    since = datetime.combine(start_day, datetime.min.time(), _TZ).astimezone(timezone.utc)
    # inclusive end day -> add a day so the last day's evening events are covered
    until = (datetime.combine(end_day, datetime.min.time(), _TZ)
             + timedelta(days=1)).astimezone(timezone.utc)

    summary = refresh_mod.run(since=since, until=until)
    return {"ok": True, "from": start_day.isoformat(), "to": end_day.isoformat(), **summary}


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")


@app.get("/sw.js")
def service_worker():
    # served from root so its scope covers the whole origin (not just /static)
    return FileResponse(
        _STATIC / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


# PWA assets are referenced with root-relative paths (so they also work under a
# GitHub Pages subpath); serve them from / in local dev too.
_ROOT_ASSETS = {
    "favicon.svg": "image/svg+xml",
    "manifest.webmanifest": "application/manifest+json",
    "apple-touch-icon.png": "image/png",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
}


@app.get("/{fname}")
def root_asset(fname: str):
    media = _ROOT_ASSETS.get(fname)
    if media is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(_STATIC / fname, media_type=media)


app.mount("/static", StaticFiles(directory=_STATIC), name="static")
