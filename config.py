"""Central config: geo bounds and source list. No secrets here."""

# Capitol Hill bounding box (~10-min drive from Pike/Pine).
# Anything inside is tagged "Capitol Hill"; anything outside is dropped.
CAP_HILL_BBOX = {
    "min_lat": 47.60,
    "max_lat": 47.64,
    "min_lng": -122.33,
    "max_lng": -122.30,
}

# Pike/Pine-ish centroid, used as a fallback location when a source
# gives us a Capitol Hill event with no coordinates.
CAP_HILL_CENTER = (47.6145, -122.3190)

NEIGHBORHOOD_LABEL = "Capitol Hill"

# All "today/tonight" logic is Seattle-local, not UTC.
LOCAL_TZ = "America/Los_Angeles"

DB_PATH = "events.db"

# Free / self-serve sources for the spine.
# kind: "ical" | "rss" | "meetup" | "ticketmaster". scope: local|national|intl.
SOURCES = [
    {
        # Community events (trivia, board games, special interest) -- the core.
        # Centered on Pike/Pine, 5mi radius; bbox trims to Capitol Hill.
        "id": "meetup",
        "kind": "meetup",
        "scope": "local",
        "url": (
            "https://www.meetup.com/find/?location=us--wa--Seattle"
            "&source=EVENTS&distance=fiveMiles&lat=47.6145&lon=-122.3190"
        ),
    },
    {
        # Concerts / comedy / shows via the Discovery API (needs TM key).
        "id": "ticketmaster",
        "kind": "ticketmaster",
        "scope": "local",
        "url": "",
    },
    {
        # DoStuff platform JSON API (concerts, comedy, culture, food).
        "id": "do206",
        "kind": "do206",
        "scope": "local",
        "url": "https://do206.com",
    },
    {
        # Capitol Hill Seattle Blog's CHS Calendar (CitySpark bundle):
        # neighborhood trivia, drink & draw, comedy, art walks, small shows.
        "id": "chs-blog",
        "kind": "chs-blog",
        "scope": "local",
        "url": "https://portal.cityspark.com/PortalScripts/CapitolHillSeattle",
    },
]
