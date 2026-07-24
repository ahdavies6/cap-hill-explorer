# 🌃 Cap Hill Explorer

**What's happening tonight in Capitol Hill, Seattle** — a personal event
meta-scraper on a map. It pulls events from several public sources (Meetup,
Do206/DoStuff, the CHS Blog calendar, and optionally Ticketmaster),
geo-filters them to a central-Seattle bounding box, dedups, auto-categorizes, and
drops them on a modern Leaflet map with a searchable sidebar.

**Live:** `https://ahdavies6.github.io/cap-hill-explorer/`

## Features

- 🗺️ **Interactive map** (CARTO Voyager tiles) + synced sidebar — click a pin to
  highlight its card and vice versa.
- 🎛️ **Filters:** source & category multi-selects, a **Today / This week** date
  range, and full-text search — all on one row.
- 🔄 **Hourly auto-refresh** via GitHub Actions; a manual **↻ refresh** button too.
- 📱 **Mobile-ready PWA** — installable on iPhone, with a List/Map toggle and
  overlay dropdowns on small screens.
- 🔐 **Private:** event data is **AES-encrypted at build time** and unlocked with
  an in-browser password ("remember my device"); `noindex` + robots/AI-bot
  blocking keep crawlers out.
- 🎟️ **Bring-your-own Ticketmaster key** (optional, browser-only — never
  committed).

## How it's built

Python 3.11 + [uv], vanilla-JS/Leaflet frontend, SQLite+FTS5 store, published as
a static snapshot to GitHub Pages. Live dev server: `uv run uvicorn web.app:app`.

## More

- **`agent_summary.md`** — a full from-scratch rebuild guide (architecture, every
  adapter, the pipeline, encryption, and deployment).
- **`source_wishlist.md`** — event sources that were scoped but couldn't be wired
  in yet, each with its blocker (anti-bot walls, auth, paid tiers).

[uv]: https://github.com/astral-sh/uv
