"""
Regulator & Trade Body monitoring service — powered by Google News RSS.
Tracks UK regulatory and trade body activity relevant to Riot and the vaping industry.
Free, unlimited, no API key required.
"""

from datetime import datetime

from services.news_monitor import _search_gnews, _deduplicate, _sort_by_date

# ---------------------------------------------------------------------------
# Regulatory body definitions
# body display name → Google News search query
# ---------------------------------------------------------------------------

REGULATORS = {
    "MHRA": "MHRA vaping OR MHRA e-cigarette OR MHRA nicotine",
    "DHSC": 'DHSC vaping OR "Department of Health and Social Care" e-cigarette OR vape',
    "IBVTA": 'IBVTA OR "Independent British Vape Trade Association"',
    "UKVIA": 'UKVIA OR "UK Vaping Industry Association"',
    "ASA": '"Advertising Standards" vaping OR "Advertising Standards" e-cigarette OR "ASA" vape ruling',
    "HMRC": "HMRC vape tax OR HMRC \"excise duty\" vaping OR HMRC nicotine pouches",
    "Trading Standards": '"Trading Standards" vaping OR "Trading Standards" e-cigarette OR "Trading Standards" vape',
    "WHO": 'WHO tobacco nicotine OR "World Health Organization" vaping OR WHO e-cigarette policy',
}

# Human-readable descriptions for each body (shown in the UI)
REGULATOR_DESCRIPTIONS = {
    "MHRA": "Medicines & Healthcare products Regulatory Agency",
    "DHSC": "Department of Health and Social Care",
    "IBVTA": "Independent British Vape Trade Association",
    "UKVIA": "UK Vaping Industry Association",
    "ASA": "Advertising Standards Authority — vaping/tobacco rulings",
    "HMRC": "HM Revenue & Customs — vape tax & excise duty",
    "Trading Standards": "Trading Standards — product compliance & enforcement",
    "WHO": "World Health Organization — tobacco/nicotine policy",
}

# ---------------------------------------------------------------------------
# Cache — 30-minute TTL (regulators refresh more often than competitor news)
# ---------------------------------------------------------------------------

_cache: dict = {}
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _get_cache(key):
    if key in _cache:
        ts, data = _cache[key]
        if (datetime.now() - ts).total_seconds() < _CACHE_TTL_SECONDS:
            return data
    return None


def _set_cache(key, data):
    _cache[key] = (datetime.now(), data)


def _fetch_for_body(body_name: str, page_size: int = 8) -> list:
    """Internal: fetch and cache articles for a single regulatory body."""
    query = REGULATORS.get(body_name)
    if not query:
        return [{"error": f"Unknown regulatory body: {body_name}"}]

    cache_key = f"reg|{body_name}|{page_size}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    articles = _search_gnews(query, max_items=page_size * 2)
    results = _sort_by_date(_deduplicate([a for a in articles if "error" not in a]))[:page_size]
    _set_cache(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    """Always returns True — the service uses Google News RSS (no API key needed)."""
    return True


def get_all_regulator_news(page_size: int = 8) -> dict:
    """
    Fetch news for every tracked regulatory body.
    Returns {body_name: [article_dicts]}.
    Article schema: {title, url, source: {name}, description, publishedAt}
    """
    return {
        name: _fetch_for_body(name, page_size=page_size)
        for name in REGULATORS
    }


def get_news_for_body(body_name: str, page_size: int = 8) -> list:
    """
    Fetch news for a single regulatory body by display name.
    Returns a list of article dicts.
    """
    return _fetch_for_body(body_name, page_size=page_size)


def get_latest_alerts() -> dict:
    """
    Returns the single most recent article per regulatory body.
    Returns {body_name: article_dict_or_None}.
    """
    alerts = {}
    for name in REGULATORS:
        articles = _fetch_for_body(name, page_size=5)
        valid = [a for a in articles if "error" not in a]
        alerts[name] = valid[0] if valid else None
    return alerts


def triage_article(article_dict: dict) -> dict:
    """
    Use AI to triage a regulatory article for Riot's PR team.

    Returns a dict with:
        relevance_score: int 1–5 (5 = most relevant to Riot)
        why_it_matters:  str — brief note on what this means for Riot
        suggested_action: str — recommended immediate action

    Falls back to {"error": str} if AI is unavailable or returns unexpected JSON.
    """
    from services.ai_engine import generate_json

    title = article_dict.get("title", "")
    description = article_dict.get("description", "")
    source = article_dict.get("source", {}).get("name", "")
    published = article_dict.get("publishedAt", "")

    prompt = (
        "You are Riot's PR intelligence analyst. Riot is a UK vaping brand focused on "
        "harm reduction, adult smokers switching to vaping, and responsible marketing.\n\n"
        "Triage this regulatory/trade body news article for relevance to Riot:\n\n"
        f"Title: {title}\n"
        f"Source: {source}\n"
        f"Published: {published}\n"
        f"Summary: {description}\n\n"
        "Return a JSON object with exactly these keys:\n"
        "  relevance_score: integer 1–5 (1 = not relevant, 5 = urgent/critical for Riot)\n"
        "  why_it_matters: string — one or two sentences explaining the direct impact on Riot\n"
        "  suggested_action: string — one concrete recommended action for Riot's PR team\n\n"
        "Return valid JSON only. No markdown, no preamble."
    )

    try:
        result = generate_json(prompt)
        # Validate and normalise the expected keys
        return {
            "relevance_score": int(result.get("relevance_score", 1)),
            "why_it_matters": result.get("why_it_matters", result.get("raw_response", "")),
            "suggested_action": result.get("suggested_action", ""),
        }
    except Exception as e:
        return {"error": f"Triage failed: {e}"}
