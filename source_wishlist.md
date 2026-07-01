# Source Wishlist — not-yet-integrated event sources

Sources we *tried* or scoped for Cap Hill Explorer but couldn't wire into the
lightweight (pure-`httpx`, no-browser) pipeline. Parked here for the future
"heavyweight" version (headless browser, auth flows, paid keys). Each entry:
what content it has, and the blocker that stopped us.

Last updated: 2026-06-30.

---

## Blocked by anti-bot / JS challenge (need a headless browser)

### EverOut (Seattle) — `everout.com/seattle/events/?neighborhood=capitol-hill`
- **Content:** Human-*curated* Capitol Hill event listings — arts, nightlife,
  drag, readings, festivals, food pop-ups. Arguably the best-edited neighborhood
  calendar; strong overlap with what we want.
- **Blocker:** Event list HTML is behind an **AWS WAF JavaScript challenge**
  (plain HTTP → `HTTP 202` with a `challenge.js` token-solve page, zero data).
  Needs a real browser (Playwright + Chromium) to execute the challenge JS.
- **Notes / partial wins:** The per-venue coords API
  `GET /api/locations/{lid}/?market=seattle` is **open** and returns real
  `latitude`/`longitude`. But the venue/occurrence IDs it needs only exist on
  the walled HTML. `/api/attractions/?...&neighborhood=capitol-hill` is open but
  **ignores the neighborhood filter** and returns global movie/artist metadata
  (no dates, no coords). `/api/schedule-dates/` needs an occurrence id + a `cb`
  cache-buster from the walled page. Django SSR; no JSON-LD, no `__NEXT_DATA__`,
  no iCal. → **Revisit with Playwright.**

---

## Blocked by auth / login wall

### Eventbrite — internal search API
- **Content:** Broad ticketed events (workshops, classes, community meetups,
  markets) — a lot of the trivia/board-game/special-interest vibe we prioritize.
- **Blocker:** Internal search API returns **HTTP 401** without an authenticated
  session; the public API's event-search endpoint was retired. → Needs OAuth app
  + token, or browser-session scraping.

### Meetup — official GraphQL API
- **Content:** THE core source for trivia nights, board games, book clubs,
  language exchanges, special-interest socials. (We *do* ingest Meetup, but by
  **scraping** the Next.js `__APOLLO_STATE__`, not via the API.)
- **Blocker:** No free API tier — the official GraphQL API requires a **Meetup
  Pro** subscription (paid) + OAuth. The scrape works for now but is fragile
  (breaks if they change their Next.js data shape). → Revisit with a Pro key for
  a stable, ToS-clean feed.

---

## Junk / unauthenticated-returns-garbage APIs

### CitySpark POST API (the CHS Blog calendar backend)
- **Content:** Same Capitol Hill events we already ingest via CHS Blog.
- **Blocker:** `POST /api/events/GetEvents/CapitolHillSeattle` returns **junk
  when unauthenticated** — ignores the `ppid`/date params and hands back random
  events (year 4018, out-of-state venues). We work around this by parsing the
  pre-rendered `var cSparkLocals = {...}` bundle from the PortalScript endpoint
  instead (works great, ~25 events). Only relevant if we ever need CitySpark's
  *paginated future dates* beyond the bundle's ~2-day window. → Would need the
  OIDC token from `login.cityspark.com`.

---

## Dead on the free tier (404 / 403 / bot-walled feeds)

### seattle.gov / Visit Seattle / generic ICS feeds
- **Content:** Official city events, tourism-board listings.
- **Blocker:** Advertised iCal/RSS endpoints **404** or **403** (bot-walled).
  Not Capitol-Hill-specific anyway. Low priority.

---

## Wrong-vibe (integrated, but noted for tuning)

### Ticketmaster (Discovery API) — *integrated*
- **Content:** Big-room concerts, sports, comedy tours. Works via API key.
- **Caveat:** Skews to large ticketed shows, **not** the small community
  events we prioritize. Kept as a source but it's the least on-brand. → Consider
  down-weighting or filtering to small venues.
