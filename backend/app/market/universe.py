"""The curated asset universe the scanner watches.

"Curated" per the build spec means a deliberately small, editable list of
established, liquid names — not "every ticker on the market." This is a
starting list; add/remove symbols here as the humans running this system
decide which assets they actually want watched.
"""

DEFAULT_UNIVERSE: list[str] = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
    "COST",
    "JPM",
    "V",
    "UNH",
    "XOM",
]
