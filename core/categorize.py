"""Coarse, keyword-based event categorizer.

The raw `category` field is a mess: some sources give clean labels
("Concerts & Live Music", "Comedy"), others hand us the *Meetup group name*
("board game girlies! [20s/30s]", "The Best Book Club in the World"). This
collapses everything into a small, human-legible taxonomy that cleanly
partitions the next ~month of Capitol Hill events for the map's filter chips.

NOTE (future work): this is deliberately dumb -- ordered keyword matching,
first hit wins. A smarter version would embed title+description and cluster
(or few-shot an LLM) so the buckets emerge from the data instead of being
hand-rolled. See source_wishlist.md / the end-of-session writeup.
"""

from __future__ import annotations

# Ordered: the FIRST bucket whose keywords appear in the haystack wins, so
# put specific buckets before generic ones (e.g. Comedy before Music).
CATEGORIES: list[tuple[str, str, tuple[str, ...]]] = [
    ("Games & Trivia", "🎲", (
        "trivia", "board game", "boardgame", "tabletop", "mahjong", "riichi",
        "backgammon", "chess", "bingo", "dungeons", "d&d", "poker", "card game",
        "quiz", "game night", "games night", "console", "cardboard",
        "magic: the gathering", "pub quiz",
    )),
    ("Books & Talks", "📚", (
        "book club", "book swap", "literature", "literary", "poetry", "poem",
        "author", "lecture", "storytelling", "writers", "writing", "zine",
        "reading group", "novel", "books",
    )),
    ("Art & Exhibits", "🎨", (
        "art exhibit", "gallery", "visual art", "drink & draw", "drink and draw",
        "painting", "arts & crafts", "craft fair", "exhibition", "museum",
        "art walk", "mural", "sculpture", "pottery", "ceramics", "art show",
    )),
    ("Comedy", "😂", (
        "comedy", "stand-up", "standup", "open mic", "improv", "sketch comedy",
        "chuckle", "cheap laughs", "roast",
    )),
    ("Film", "🎬", (
        "film", "movie", "screening", "cinema", "matinee", "documentary",
        "short films",
    )),
    ("Theatre & Dance", "🎭", (
        "theatre", "theater", "theatrical", "drag", "burlesque", "cabaret",
        "ballet", "opera", "musical", "performing arts", "recital",
        "dance performance", "play ",
    )),
    ("Food & Drink", "🍔", (
        "vegan", "tasting", "brunch", "dinner", "happy hour", "wine", "beer",
        "cocktail", "dining", "potluck", "farmers market", "coffee", "bakery",
        "pop-up", "food & drink", "booze", "supper", "menu",
    )),
    ("Music", "🎵", (
        "concert", "live music", "music", "band", "dj ", "dj:", "dance party",
        "album", "singer", "songwriter", "jazz", "rock", "hip hop", "hip-hop",
        "karaoke", "acoustic", "record release", "vinyl", "choir", "symphony",
        "orchestra", "cello", "nightlife",
    )),
    ("Community & Social", "🌈", (
        "meetup", "social", "language", "culture", "society", "networking",
        "mixer", "social club", "community", "lgbt", "queer", "pride",
        "friends", "hangout", "meet up", "speed dating", "volunteer",
        "market", "swap meet", "desi", "bipoc", "allies",
    )),
]

OTHER = ("Other", "✨")


def categorize(title: str | None, category: str | None, description: str | None) -> str:
    """Return the display bucket name (e.g. 'Games & Trivia') for an event."""
    hay = " ".join(p for p in (title, category, description) if p)[:400].lower()
    for name, _emoji, keywords in CATEGORIES:
        for kw in keywords:
            if kw in hay:
                return name
    return OTHER[0]


# name -> emoji, for the UI (includes the Other fallback).
EMOJI = {name: emoji for name, emoji, _ in CATEGORIES}
EMOJI[OTHER[0]] = OTHER[1]

# Stable display order for the filter chips.
ORDER = [name for name, _, _ in CATEGORIES] + [OTHER[0]]
