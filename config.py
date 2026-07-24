"""Central config: geo bounds and source list. No secrets here."""

# Search area: a bounding box over central Seattle, tuned to roughly this frame:
#   west  = Queen Anne / Interbay       north = lower Ballard / Wallingford
#   east  = Lake Washington shoreline   south = International District
# (Fremont, U-District, Montlake, Eastlake, downtown, Madrona fall in between.)
# Every event, from every source, is dropped at ingest if it falls outside this
# box (see core/geo.py in_bbox). Retune by editing the four edges.
SEARCH_BBOX = {
    "min_lat": 47.595,    # south: International District / Chinatown
    "max_lat": 47.665,    # north: lower Ballard / Wallingford / U-District
    "min_lng": -122.385,  # west:  Queen Anne / Interbay
    "max_lng": -122.275,  # east:  Lake Washington shoreline (Madrona/Leschi)
}

# Pike/Pine centroid: the map's home center, the Ticketmaster API search center,
# and the fallback location for an in-box event that arrives without coordinates
# (see core/geo.py text-hint fallback).
CAP_HILL_CENTER = (47.6145, -122.3190)

# Ticketmaster's API only supports center+radius, not a box, so we over-fetch a
# circle big enough to cover the whole box (~4.6mi max corner distance from the
# center), then in_bbox() trims it. 5mi covers it.
TM_RADIUS_MILES = 5

NEIGHBORHOOD_LABEL = "Capitol Hill"

# All "today/tonight" logic is Seattle-local, not UTC.
LOCAL_TZ = "America/Los_Angeles"

DB_PATH = "events.db"

# Free / self-serve sources for the spine.
# kind: "ical" | "rss" | "meetup" | "ticketmaster". scope: local|national|intl.
SOURCES = [
    {
        # Community events (trivia, board games, special interest) -- the core.
        # Centered on Pike/Pine, 5mi Meetup fetch; in_bbox() trims to the box.
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
