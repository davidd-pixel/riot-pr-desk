"""
Competitor monitoring service — powered by Google News RSS.
Tracks competitor and industry/regulatory body activity.
Free, unlimited, no API key required.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import urlopen, Request

from services.news_monitor import _fetch_rss, _search_gnews, _deduplicate, _sort_by_date

# ---------------------------------------------------------------------------
# Competitor definitions
# ---------------------------------------------------------------------------

COMPETITORS = {
    "Elf Bar / EBCREATE": "Elf Bar OR EBCREATE vape",
    "Lost Mary": '"Lost Mary" vape',
    "Vuse (BAT)": "Vuse vaping OR \"Vuse\" e-cigarette",
    "Haypp Group": "Haypp nicotine OR Haypp vape",
    "IVG (I Vape Great)": "IVG vape OR \"I Vape Great\"",
    "Totally Wicked": "\"Totally Wicked\" vape",
    "ELFA / RELX": "ELFA vape OR RELX e-cigarette",
    "88vape": "88vape",
    "Vampire Vape": "\"Vampire Vape\"",
}

REGULATORS = {
    "MHRA (Vaping)": "MHRA vaping OR MHRA e-cigarette",
    "DHSC (E-Cigarettes)": "DHSC e-cigarettes OR \"Department of Health\" vaping",
    "IBVTA": "IBVTA OR \"Independent British Vape Trade Association\"",
    "UKVIA": "UKVIA OR \"UK Vaping Industry Association\"",
    "ASA (Advertising Standards)": "ASA \"Advertising Standards\" vaping OR e-cigarette",
}

# ---------------------------------------------------------------------------
# Cache — separate from news_monitor's cache, 60-minute TTL
# ---------------------------------------------------------------------------

_cache: dict = {}
_CACHE_TTL_SECONDS = 3600  # 60 minutes


def _get_cache(key):
    if key in _cache:
        ts, data = _cache[key]
        if (datetime.now() - ts).total_seconds() < _CACHE_TTL_SECONDS:
            return data
    return None


def _set_cache(key, data):
    _cache[key] = (datetime.now(), data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_competitor_news(competitor_name: str, page_size: int = 10) -> list:
    """
    Fetch news for a single competitor by display name.
    Returns a list of article dicts (same schema as news_monitor).
    """
    query = COMPETITORS.get(competitor_name)
    if not query:
        return [{"error": f"Unknown competitor: {competitor_name}"}]

    cache_key = f"comp|{competitor_name}|{page_size}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    articles = _search_gnews(query, max_items=page_size * 2)
    results = _sort_by_date(_deduplicate([a for a in articles if "error" not in a]))[:page_size]
    _set_cache(cache_key, results)
    return results


def fetch_all_competitor_news(page_size: int = 5) -> dict:
    """
    Fetch news for every competitor.
    Returns {competitor_name: [articles]}.
    """
    return {
        name: fetch_competitor_news(name, page_size=page_size)
        for name in COMPETITORS
    }


def fetch_regulator_news(page_size: int = 8) -> dict:
    """
    Fetch news for all regulatory / industry bodies.
    Returns {body_name: [articles]}.
    """
    results = {}
    for name, query in REGULATORS.items():
        cache_key = f"reg|{name}|{page_size}"
        cached = _get_cache(cache_key)
        if cached is not None:
            results[name] = cached
            continue

        articles = _search_gnews(query, max_items=page_size * 2)
        clean = _sort_by_date(_deduplicate([a for a in articles if "error" not in a]))[:page_size]
        _set_cache(cache_key, clean)
        results[name] = clean

    return results


def get_competitor_summary_for_ai(competitor_name: str, articles: list) -> str:
    """
    Format a competitor's articles as a compact string for AI prompt injection.
    """
    if not articles:
        return f"No recent news found for {competitor_name}."

    lines = [f"Recent news for {competitor_name}:"]
    for i, a in enumerate(articles, start=1):
        if "error" in a:
            continue
        title = a.get("title", "")
        source = a.get("source", {}).get("name", "")
        published = a.get("publishedAt", "")
        desc = a.get("description", "")
        lines.append(
            f"{i}. [{source}] {title} ({published})\n   {desc}"
        )
    return "\n".join(lines)
