# Cap Hill Explorer — Agent Recreation Guide

A complete, from-scratch blueprint for another agent to rebuild this project. It
is a **personal event "meta-scraper"** for Capitol Hill, Seattle: it pulls
"what's on tonight" from several public event sources, geo-filters to a
central-Seattle bounding box, dedups, categorizes, and renders everything on a modern
Leaflet map + searchable sidebar. It ships two ways:

- **Local dev:** a FastAPI app with a live read-only events API + on-demand refresh.
- **Production:** a *static* snapshot (HTML + a JSON blob) published to **GitHub
  Pages**, rebuilt **hourly** by GitHub Actions, installable as a **PWA**, and
  gated behind an **in-browser password** (the event data is AES-encrypted at
  build time). It works great on mobile.

Live: `https://ahdavies6.github.io/cap-hill-explorer/` (personal GH account `ahdavies6`).

---

## 1. Architecture at a glance

```
cap_hill_explorer/
├── config.py            # geo center + SEARCH_BBOX, LOCAL_TZ, SOURCES list, DB path
├── core/
│   ├── models.py        # Event + Address dataclasses; stable uid hashing
│   ├── normalize.py     # RawEvent dict -> Event (tz-aware, UTC-stored)
│   ├── geo.py           # bounding-box test + text-hint fallback; drop out-of-area
│   ├── dedup.py         # exact-uid + fuzzy (title+time) dedup (rapidfuzz)
│   ├── categorize.py    # keyword -> coarse taxonomy w/ emoji (for filter chips)
│   └── store.py         # SQLite + FTS5 store: upsert / query
├── adapters/
│   ├── base.py          # RawEvent TypedDict + SourceAdapter ABC
│   ├── http.py          # shared httpx client, __NEXT_DATA__ + JSON-LD parsers
│   ├── registry.py      # kind-string -> adapter class; build_adapters()
│   ├── meetup.py        # scrapes Meetup __APOLLO_STATE__ (no API)
│   ├── ticketmaster.py  # Discovery API (needs TICKETMASTER_API_KEY; self-disables)
│   ├── do206.py         # DoStuff platform: append .json to date URLs
│   ├── chs_blog.py      # CHS Blog CitySpark `var cSparkLocals = {...}` bundle
│   ├── ical.py          # generic .ics adapter (icalendar)
│   └── rss.py           # generic RSS/Atom adapter (feedparser)
├── refresh.py           # CLI orchestrator: fetch->normalize->geo->dedup->store
├── snapshot.py          # build/ : copy web/static + write data.json snapshot
├── encrypt.mjs          # build step: AES-256-GCM encrypt data.json -> data.enc
├── web/
│   ├── app.py           # FastAPI: /api/events, /api/refresh, static + PWA routes
│   └── static/
│       ├── index.html   # ENTIRE frontend (map, filters, gate, PWA) ~670 lines
│       ├── sw.js        # service worker: cache-first for map tiles + CDN assets
│       ├── manifest.webmanifest, favicon.svg, icon-192/512.png, apple-touch-icon.png
│       ├── robots.txt, ai.txt   # crawler / AI-bot disallow signals
├── seed_sample.py       # inserts a few fake events for offline UI dev
├── source_wishlist.md   # sources we tried but couldn't wire in (+ blockers)
├── pyproject.toml, uv.lock, .python-version   # uv-managed (Python 3.11)
└── .github/workflows/deploy.yml   # hourly cron build + deploy to Pages
```

**Data flow:** `adapters.*.fetch()` → `RawEvent` dicts → `normalize()` → `Event`
→ `geo.locate()` (drop if outside the box) → `dedup()` → `store.upsert()` (SQLite).
Reads: `store.query()` → `/api/events` (dev) or baked into `data.json` (prod).

---

## 2. Tech stack & dependencies

- **Python 3.11**, managed with **uv** (`uv sync --frozen`, `uv run ...`). Deps
  (`pyproject.toml`): `fastapi[standard]` (web + uvicorn), `httpx` (scraping),
  `feedparser` (RSS), `icalendar` (ICS), `python-dateutil` (date parsing),
  `rapidfuzz` (fuzzy dedup). **No database server** — stdlib `sqlite3` w/ FTS5.
- **Node** (only for the build-time encryptor `encrypt.mjs`; uses stdlib
  `node:crypto`, no npm deps). Preinstalled on the CI ubuntu runner.
- **Frontend:** vanilla JS, **Leaflet 1.9.4** (CDN), **CARTO Voyager** raster
  tiles (no key, retina). No build step, no framework — one `index.html`.
- **Hosting:** GitHub Pages (static), GitHub Actions (hourly cron). Free on a
  public repo (unlimited Actions minutes for public repos).

---

## 3. Core data model (`core/models.py`)

Two frozen-ish dataclasses, shaped after Mobilizon's event schema:

- `Address(locality, region, country, postal_code, street, lat, lng, timezone, origin_id)`
- `Event(source_id, origin_id, title, begins_on, url, description, ends_on,
  status, category, language, online_address, address, picture_url, tags, raw, uid)`
  - `begins_on`/`ends_on` are **tz-aware datetimes stored as UTC**.
  - `uid` = `sha1(f"{source_id}::{origin_id}")`, or `sha1(source::title::isotime)`
    when there's no origin id. This is the **stable dedup / upsert key**.
  - `to_dict()` ISO-formats the datetimes for JSON.

## 4. Normalization (`core/normalize.py`)

`normalize(raw: RawEvent, source_id) -> Event | None`: coerces `begins_on` to a
tz-aware datetime (assume UTC if naive), converts to UTC, builds an `Address`
from `lat/lng/location_text`, and returns `None` if there's no start time.

## 5. Geo filter (`core/geo.py`) — the "is it near Capitol Hill?" gate

`locate(event) -> Event | None`:
- If the event **has coordinates**: keep iff they fall inside `SEARCH_BBOX`
  (a central-Seattle lat/lng rectangle, checked by `in_bbox()`), else drop.
- If **no coords**: fall back to a **regex of text hints** (`capitol hill`,
  `pike/pine`, `broadway`, `neumos`, `barboza`, `cal anderson`, `12th ave`, …);
  on a hit, pin it to `CAP_HILL_CENTER` (Pike/Pine centroid) and keep it.
- Kept events get tagged `"Capitol Hill"`.

This is the key spatial constraint — everything outside the box is discarded.
The frontend (map + client-side Ticketmaster) applies the **same** `BBOX`
bounds, so the JS and Python filters agree.

## 6. Dedup (`core/dedup.py`)

`dedup(events)`: drop exact `uid` repeats, then fuzzy dupes — two events are the
same happening if their start times are within **2 hours** AND
`rapidfuzz.token_sort_ratio(title_a, title_b) >= 88`. **Earlier-listed sources
win** (so ordering in `config.SOURCES` is a priority ranking).

## 7. Categorizer (`core/categorize.py`)

Deliberately-dumb **ordered keyword matcher** — first bucket whose keywords
appear in `title+category+description` (lowercased, first 400 chars) wins.
Buckets (each with an emoji, in priority order): Games & Trivia 🎲, Books &
Talks 📚, Art & Exhibits 🎨, Comedy 😂, Film 🎬, Theatre & Dance 🎭, Food & Drink
🍔, Music 🎵, Community & Social 🌈, else Other ✨. Specific buckets come before
generic ones (Comedy before Music). Exposes `categorize()`, `EMOJI`, `ORDER`.
`store._from_row()` calls this to add a `category_group` field to every event
(drives the map's category filter chips). **Future work noted in-code:** replace
with embeddings/LLM clustering so buckets emerge from data.

## 8. Store (`core/store.py`)

SQLite (`events.db`) with one `events` table (uid PK, coords, tags/raw as JSON)
plus an **FTS5** virtual table (`events_fts` over title+description) for
full-text search. `upsert()` does `INSERT ... ON CONFLICT(uid) DO UPDATE` then
rebuilds the FTS index. `query(start, end, text)` filters by UTC time window and
optional FTS `MATCH`, ordered by `begins_on`. `_from_row()` adds `category_group`
and drops the bulky `raw` blob from API payloads.

---

## 9. Adapters — how each source is scraped (`adapters/`)

All adapters subclass `SourceAdapter` (`base.py`) and implement
`fetch(since, until) -> list[RawEvent]`. `RawEvent` is a loose `TypedDict`
(`origin_id, title, description, url, begins_on, ends_on, location_text, lat,
lng, category, picture_url`). `registry.build_adapters()` maps each
`config.SOURCES` entry's `kind` string to a class and instantiates it.

`http.py` provides a shared `httpx.Client` with a **browser-ish User-Agent**,
`get()`, `polite_sleep()`, and two HTML extractors: `next_data()` (parses the
`<script id="__NEXT_DATA__">` Next.js blob) and `ld_json()` (schema.org JSON-LD,
flattening `@graph`).

- **meetup.py** (the community-events spine; trivia/board games/book clubs/etc.).
  Meetup killed its free API, so this **scrapes**: hits the public "find events"
  page with several interest keywords (`trivia`, `board games`, `book club`,
  `language`, `run club`, ``), reads event URLs out of the embedded
  `__APOLLO_STATE__` (falling back to a URL regex), then fetches each event's
  detail page and pulls the `Event:*` Apollo object (title, `dateTime`, venue
  `lat/lon`, group name → `category`). Polite sleeps throughout; cap ~80 events.
  **Fragile** — breaks if Meetup changes its Next.js data shape.
- **ticketmaster.py** (concerts/comedy/sports). Uses the **Discovery API**
  (`app.ticketmaster.com/discovery/v2/events.json`), keyed via
  `TICKETMASTER_API_KEY` env var, `latlong` + `radius` (defaults to
  `TM_RADIUS_MILES`, a circle sized to cover the whole box) around the centroid;
  `in_bbox()` then trims the corners.
  **Self-disables** (returns `[]`) when no key is set — so it's silently off in
  CI. In production the browser fetches TM directly (see frontend BYO-key).
- **do206.py** (DoStuff platform: concerts/comedy/culture/food). Clean
  **unauthenticated JSON** — append `.json` to date-listing URLs
  (`/events/YYYY/M/D.json?page=N`); per-event venue objects carry lat/lon.
- **chs_blog.py** (Capitol Hill Seattle Blog's CitySpark calendar; neighborhood
  trivia/drink & draw/comedy/art walks). Its POST API returns junk when
  unauthenticated, so instead we fetch the PortalScript page and **brace-match
  the pre-rendered `var cSparkLocals = {...}` JSON bundle** (~25 coord-tagged
  events, ~2-day window).
- **ical.py / rss.py** — generic reusable adapters (icalendar / feedparser) for
  any future `.ics` or RSS source. Wired into the registry but not in the
  default `SOURCES` list.

See `source_wishlist.md` for sources that were scoped but blocked (EverOut →
AWS WAF JS challenge; Eventbrite → 401 auth wall; official Meetup API → paid Pro
tier) and why — the roadmap for a future "heavyweight" (headless-browser) version.

## 10. Orchestrator (`refresh.py`)

`run(days=14, only=None, since=None, until=None) -> dict`: loops every adapter
over `[since, until)` (defaults now..+days), wrapping each in try/except so one
bad source can't kill the run; normalizes → geo-filters → collects → dedups →
`store.upsert()`. Prints per-source counts. Loads `.env` (a tiny hand-rolled
loader, no python-dotenv dep) so `TICKETMASTER_API_KEY` is picked up locally.
CLI: `uv run python refresh.py [--days N] [--source ID]`.

## 11. Backend (`web/app.py`, FastAPI — local dev only)

- `GET /api/events?upcoming=1` → every event from **Seattle-local midnight
  today** onward (so "tonight" still shows events that started earlier this
  evening). `?date=YYYY-MM-DD` → that Seattle-local calendar day. `?q=` → FTS.
  All time math converts Seattle-local windows → UTC for the UTC-stored rows.
- `POST /api/refresh?from=&to=` → re-scrape a Seattle-local day window on demand
  (default today) via `refresh.run()`.
- `GET /` → `index.html`; `GET /sw.js` → service worker with
  `Service-Worker-Allowed: /`; `GET /{fname}` → root-served PWA assets
  (favicon/manifest/icons) so root-relative paths also work under a Pages
  subpath; `/static` mounted via `StaticFiles`.
- Run: `uv run uvicorn web.app:app --host 127.0.0.1 --port 8811`. Static edits
  serve live; **app.py changes need a restart**.

---

## 12. Frontend (`web/static/index.html`) — the whole UI in one file

Vanilla JS + Leaflet. No framework, no bundler. Key pieces:

- **Map:** Leaflet centered on Pike/Pine, **CARTO Voyager** retina raster tiles
  (Google-Maps-ish, keyless). Custom teardrop `divIcon` pins (`.che-pin`).
- **Dual-mode data load** (`loadEvents()`): try `/api/events?upcoming=1` (dev);
  on failure try **`data.enc`** (encrypted static → runs the password gate) then
  fall back to **`data.json`** (plaintext static). Client-side Ticketmaster
  events are merged in if the user enabled a key.
- **Filters** (state object `F={src:Set,cat:Set,from,to,q}`): a **date range first**
  (far left) — **Today / 3 days / week** quick-range buttons (`setRange()`) then
  year-less **date chips** (`.dchip`: a styled label showing e.g. "Fri Jul 24";
  the real `<input type=date>` is visually hidden and opened via `showPicker()`,
  so the year is stored but never shown) — then source and category
  **multi-select dropdowns** (`buildMulti()`; empty Set = all, with per-option
  live counts), and a **full-text search** box. Controls live on one row that
  **horizontally scrolls** on narrow windows. A **↻ refresh** button re-pulls
  sources for the selected dates (calls `/api/refresh` in dev; just reloads
  `data.json`/`data.enc` in prod).
- **Pin-to-top:** every list card and map popup has a **📌 Pin** toggle; pinned
  events **sort above** everything else (still within the active filters) and
  render **red** (`iconPinned`, `--hot`) on the map + a red left border in the
  list. Pin state (event `uid`s) persists in `localStorage['che_pins']` so it
  survives reopen (like the password). Toggling is **in place**: `togglePin(uid)`
  updates only the one card + marker (class/label swap, `setIcon`, `setZIndexOffset`,
  `setPopupContent`) via an `idxByUid` lookup — it does **not** re-sort or re-render,
  so the current selection and the item's list position are preserved; pinned items
  only float to the top on the next full `apply()` (filter change / refresh / reload,
  which keeps a pinned-first sort). All `.pin-btn` clicks (list + popup) route
  through **one delegated capture-phase** `document` listener, so pinning never
  selects/deselects the card and works identically from map and list. Pinned markers
  carry `zIndexOffset: PIN_Z (1000)` so they stack above an overlapping non-pinned one.
- **Sidebar ↔ map bidirectional highlight:** aligned `cards[]` / `markers[]`
  arrays (null entries for coord-less events). `select(i, fromCard)` highlights the
  chosen card (indigo bg, white text, darker-purple left border via `.card.sel`)
  and its pin (`.che-pin.sel`), **fades all other pins** (`#map.selecting .che-pin{
  opacity:.35}`), and auto-scrolls the list to it via a fast custom easing
  (`fastScrollTo()`). Selecting from the **list** zooms/centers the map on the pin;
  tapping a pin **on the map** keeps the current view (only opens the popup).
  `clearSel()` (on popup close) strips `.sel` from **all** pins (panned-out
  markers can leave stale highlights). A `selecting` guard flag suppresses the
  `popupclose` handler during programmatic popup swaps.
- **Event count** (`#countbar`) stays visible above the scrolling list.
- **Ticketmaster BYO-key:** a **disabled-by-default** button opens a modal to
  paste a personal TM Discovery API key, stored in **localStorage only** (never
  committed / never in the repo). `fetchTicketmaster()` queries TM directly from
  the browser (CORS is open: `access-control-allow-origin: *`), filters to the
  box (shared `BBOX` bounds check), maps TM segment → category.
  Off ⇒ no TM events.
- **Mobile (`@media max-width:760px`):** search dropdowns become **fixed top
  overlays** with a dim backdrop (instead of hiding in the scroll bar); layout
  stacks to a single column; a floating **📋 List / 🗺️ Map toggle** switches
  views (`body.m-map`), because the map can't share the row on a phone.
  `wireViewToggle()` calls `map.invalidateSize()` when showing the map.
- **PWA:** `<head>` links `manifest.webmanifest` (standalone, theme `#6e65c6`,
  any+maskable icons), `apple-touch-icon`, apple-mobile-web-app meta; registers
  `sw.js`. Installable "Add to Home Screen" on iPhone.
- **Password gate** (`#gate` overlay): shown only when `data.enc` is served.
  `decryptPayload(enc, pw)` uses **Web Crypto** (PBKDF2-SHA256 → AES-256-GCM) to
  decrypt in-browser. `unlockEncrypted()` first tries a **remembered password**
  (`localStorage.che_pw`); else prompts, and (if "Remember my device", default
  checked) stores the password. Wrong password → inline error, no data leaks.
- `<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noai,
  noimageai">` — the effective per-page no-index / no-AI signal.

## 13. Service worker (`web/static/sw.js`)

Cache-first for CARTO tile hosts (`basemaps.cartocdn.com`) and CDN assets
(unpkg/cdnjs/Google Fonts) in caches `che-tiles-v1` / `che-assets-v1`; lets
API/HTML/data hit the network. This is what made the map load fast on refresh.

## 14. Static build (`snapshot.py`)

`build_site()`: wipe `build/`, copy `web/static/` into it, and write
`build/data.json` = the exact `/api/events?upcoming=1` payload
(`{date, mode, generated_at, count, events}`) from local-midnight-today onward.
`main()`: unless `--no-fetch`, first calls `refresh.run(days=8)` to scrape fresh.
`--no-fetch` rebuilds from the existing DB. **No secrets needed** — TM is off in
CI, enrichment is client-side.

---

## 15. Encryption gate (`encrypt.mjs` + frontend)

**Why:** GitHub Pages is static — a pure client-side "password" is theater
(anyone can read the JS/data). The real fix: **encrypt the event data at build
time** so the published `data.enc` is ciphertext; only someone with the password
can decrypt it in the browser.

`encrypt.mjs` (Node, stdlib `node:crypto`, run after `snapshot.py`):
- Reads `SITE_PASSWORD` from env. **If unset ⇒ no-op** (leaves plaintext
  `data.json`; used for local dev / ungated builds).
- Else: `PBKDF2-SHA256(password, random 16-byte salt, 150000 iters)` → 256-bit
  AES-GCM key; random 12-byte IV; encrypts `build/data.json`.
- Writes `build/data.enc` = `{v, kdf, iter, salt(b64), iv(b64), ct(b64)}` where
  **`ct` = ciphertext with the 16-byte GCM auth tag appended** (this is exactly
  what the browser's `SubtleCrypto.decrypt` expects — Node's `getAuthTag()` must
  be concatenated onto the ciphertext).
- **Deletes `build/data.json`** so the plaintext is never published.

Browser side (`decryptPayload`): `importKey('raw', pw, 'PBKDF2')` →
`deriveKey({name:'PBKDF2', salt, iterations, hash:'SHA-256'}, …, {name:'AES-GCM',
length:256})` → `decrypt({name:'AES-GCM', iv}, key, ct)`. Verified round-trip
(Node encrypt → WebCrypto decrypt) interops cleanly; wrong password / tampered
ciphertext throws.

## 16. Crawler / AI blocking

- **`web/static/robots.txt`:** `Disallow: /` for `*` plus ~18 explicitly named
  AI/LLM bots (GPTBot, ChatGPT-User, OAI-SearchBot, Google-Extended, ClaudeBot,
  anthropic-ai, CCBot, PerplexityBot, Bytespider, Amazonbot, Applebot-Extended,
  Meta-ExternalAgent, cohere-ai, Diffbot, …).
- **`web/static/ai.txt`:** advisory no-train / no-AI-use policy (`Content-Usage:
  ai=n` etc.).
- **`<meta name="robots" content="noindex,…,noai,noimageai">`** in `index.html`.
- **Important caveat:** robots.txt is only honored at a **domain root**
  (`ahdavies6.github.io/robots.txt`), NOT at a project subpath
  (`…/cap-hill-explorer/robots.txt`). On a github.io **project** page the
  effective lever is the **noindex meta tag** (path-independent) — plus the fact
  that the data is **encrypted** anyway, so a crawler sees only ciphertext + a
  password prompt. The robots/ai files are there for well-behaved bots and any
  future custom domain.

## 17. Deployment (`.github/workflows/deploy.yml`)

- Triggers: hourly `cron: "0 * * * *"`, `workflow_dispatch` (manual button), and
  `push` to `main`. `concurrency: group=pages` (no overlapping deploys).
- Permissions: `contents:read, pages:write, id-token:write`.
- **build** job: checkout → `astral-sh/setup-uv` (Python 3.11) → `uv sync
  --frozen` → `uv run python snapshot.py --days 8` → **`node encrypt.mjs`** (with
  `env: SITE_PASSWORD: ${{ secrets.SITE_PASSWORD }}`) → `upload-pages-artifact`
  (`path: build`).
- **deploy** job: `actions/deploy-pages`.
- Pages source = **GitHub Actions** (set once via
  `gh api -X POST repos/OWNER/REPO/pages -f build_type=workflow`).
- **`SITE_PASSWORD`** is a repo **Actions secret** (`gh secret set SITE_PASSWORD
  --repo ahdavies6/cap-hill-explorer`). Without it the site still builds, just
  unencrypted/ungated.

### URL options
- Default: `https://ahdavies6.github.io/cap-hill-explorer/` (project page).
- User page (root, better robots.txt story): rename repo to
  `ahdavies6.github.io` → served at `https://ahdavies6.github.io/`.
- Custom domain: add a `CNAME` + DNS if desired (free).

### GitHub account hygiene (multi-account)
Built/pushed under the **personal** account `ahdavies6`, NOT the corporate one.
- `~/.bashrc` helpers: `ghwork` / `ghpersonal` (`gh auth switch --user …`, which
  is **global**) + `ghwho`. Default active = work; switch to personal before a
  personal-project push, back to work after.
- **Repo-local git identity** set to `ahdavies6` + `ahdavies6@users.noreply.
  github.com` so the corporate email never leaks into public history (global git
  identity stays corporate).

---

## 18. Config knobs (`config.py`)

- `CAP_HILL_CENTER` = `(47.6145, −122.3190)` (Pike/Pine centroid; map home + TM search center + coord fallback).
- `SEARCH_BBOX` = central-Seattle lat/lng rectangle (the spatial gate, via `in_bbox()`):
  `min_lat 47.595` / `max_lat 47.665` / `min_lng −122.385` / `max_lng −122.275`
  (S = International District, N = lower Ballard/Wallingford/U-District, W = Queen Anne, E = Lake Washington shore).
- `TM_RADIUS_MILES` = `5` (Ticketmaster's API only does center+radius; over-fetch a circle covering the box, then `in_bbox()` trims).
- `LOCAL_TZ` = `America/Los_Angeles` (ALL "today/tonight" logic is Seattle-local).
- `SOURCES` = ordered list of `{id, kind, scope, url}` (order = dedup priority).
- `DB_PATH` = `events.db`. **No secrets in this file.**

## 19. How to run / rebuild / redeploy

```bash
# --- local dev ---
uv sync
uv run python refresh.py --days 8            # scrape into events.db
uv run uvicorn web.app:app --port 8811       # serve live app at :8811
# (optional) uv run python seed_sample.py     # fake events for offline UI work

# --- build the static site locally ---
uv run python snapshot.py --days 8           # scrape + write build/
SITE_PASSWORD=test node encrypt.mjs          # optional: produce build/data.enc
python3 -m http.server -d build 8080         # preview the static build

# --- deploy (personal account) ---
ghpersonal                                   # switch gh to ahdavies6
git add -A && git commit -m "…"              # repo-local identity = ahdavies6
git push origin main                         # triggers the Actions build+deploy
ghwork                                        # switch gh back to work default
# set the gate password once:
gh secret set SITE_PASSWORD --repo ahdavies6/cap-hill-explorer --body '…'
gh workflow run "Build & deploy to Pages" --repo ahdavies6/cap-hill-explorer
```

Verify the gate is live: `curl -s .../data.enc | head -c 40` shows
`{"v":1,"kdf":"PBKDF2…` and `curl -sI .../data.json` 404s.

## 20. Gotchas & lessons learned

- **AES-GCM interop:** Node's auth tag is separate (`getAuthTag()`); WebCrypto
  wants it **appended to the ciphertext**. Concatenate on encrypt, pass the whole
  blob to `subtle.decrypt`.
- **Store the password, not the derived key** ("remember my device") — the salt
  changes every build, so a cached key would be useless next build.
- **robots.txt subpath caveat** (see §16) — meta noindex + encryption are the
  real levers on a github.io project page.
- **Seattle-local vs UTC:** events are stored UTC but every user-facing window is
  computed in `America/Los_Angeles`, anchored at **local midnight today** so
  early-evening events still count as "tonight".
- **`gh auth switch` is global**, not per-directory — hence the bashrc helpers +
  the discipline of switch-before-push, switch-back-after.
- **Never commit** `.env`, `events.db`, or `build/` (all gitignored). The TM key
  lives only in the browser's localStorage; `SITE_PASSWORD` only in the Actions
  secret store.
- **Scrapers are fragile** (Meetup `__APOLLO_STATE__`, CHS `cSparkLocals`): each
  adapter is wrapped in try/except in `refresh.run()` so one breakage degrades
  gracefully instead of taking down the whole refresh.
- **No browser in the build env:** validate `index.html` JS by extracting
  `<script>` blocks and running `node --check`; you can't visually render.
