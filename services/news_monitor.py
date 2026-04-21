"""
News monitoring service — powered by Google News RSS.
Free, unlimited, no API key required. UK-biased with global coverage.
Also supports fetching article text from URLs.
"""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
from email.utils import parsedate_to_datetime


# --- Google News RSS URLs (UK edition) ---

GNEWS_BASE = "https://news.google.com/rss"
GNEWS_PARAMS = "hl=en-GB&gl=GB&ceid=GB:en"

# Topic feeds (UK edition)
GNEWS_TOPICS = {
    "Entertainment": f"{GNEWS_BASE}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pIUWlnQVAB?{GNEWS_PARAMS}",
    "Sport": f"{GNEWS_BASE}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pIUWlnQVAB?{GNEWS_PARAMS}",
    "Business": f"{GNEWS_BASE}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pIUWlnQVAB?{GNEWS_PARAMS}",
    "Health": f"{GNEWS_BASE}/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?{GNEWS_PARAMS}",
    "Science": f"{GNEWS_BASE}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pIUWlnQVAB?{GNEWS_PARAMS}",
    "Technology": f"{GNEWS_BASE}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pIUWlnQVAB?{GNEWS_PARAMS}",
}

# Vape-specific search queries
UK_VAPE_SEARCHES = [
    "vaping UK",
    "vape tax UK",
    "disposable vape ban",
    "e-cigarette regulation UK",
]

GLOBAL_VAPE_SEARCHES = [
    "vaping regulation",
    "e-cigarette",
    "nicotine harm reduction",
]

# Simple in-memory cache
_cache = {}
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _get_cache(key):
    if key in _cache:
        ts, data = _cache[key]
        if (datetime.now() - ts).total_seconds() < _CACHE_TTL_SECONDS:
            return data
    return None


def _set_cache(key, data):
    _cache[key] = (datetime.now(), data)


def is_configured():
    """Google News RSS is always available — no API key needed."""
    return True


def _fetch_rss(url, max_items=30):
    """Fetch and parse a Google News RSS feed."""
    cache_key = f"rss|{url}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Riot PR Desk)"})
        resp = urlopen(req, timeout=15)
        xml_data = resp.read()
        root = ET.fromstring(xml_data)

        articles = []
        for item in root.findall(".//item")[:max_items]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            source_el = item.find("source")
            pubdate_el = item.find("pubDate")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            # Google News appends " - Source Name" to titles — strip it for cleaner display
            source_name = source_el.text.strip() if source_el is not None and source_el.text else ""
            if source_name and title.endswith(f" - {source_name}"):
                title = title[: -(len(source_name) + 3)]

            # Parse description (HTML) to plain text
            desc_raw = desc_el.text if desc_el is not None and desc_el.text else ""
            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()

            # Parse pub date
            pub_date = ""
            if pubdate_el is not None and pubdate_el.text:
                try:
                    pub_dt = parsedate_to_datetime(pubdate_el.text)
                    pub_date = pub_dt.isoformat()
                except Exception:
                    pub_date = pubdate_el.text

            if title:
                articles.append({
                    "title": title,
                    "source": {"name": source_name},
                    "description": desc if desc else title,
                    "url": link_el.text.strip() if link_el is not None and link_el.text else "",
                    "publishedAt": pub_date,
                })

        _set_cache(cache_key, articles)
        return articles

    except Exception as e:
        try:
            from services.error_logger import log_error
            log_error("news_fetch", str(e), context=f"url={url[:100]}")
        except Exception:
            pass
        return [{"error": f"Failed to fetch news: {e}"}]


def _search_gnews(query, max_items=30):
    """Search Google News RSS for a query."""
    encoded_query = query.replace(" ", "+")
    url = f"{GNEWS_BASE}/search?q={encoded_query}&{GNEWS_PARAMS}"
    return _fetch_rss(url, max_items=max_items)


def _deduplicate(articles):
    """Remove duplicate articles by title similarity."""
    seen_titles = set()
    unique = []
    for a in articles:
        if "error" in a:
            unique.append(a)
            continue
        # Normalise title for dedup
        normalised = a.get("title", "").lower().strip()[:60]
        if normalised and normalised not in seen_titles:
            seen_titles.add(normalised)
            unique.append(a)
    return unique


def _filter_recent(articles: list, max_age_days: int = 7) -> list:
    """
    Drop articles older than `max_age_days`. Articles with no/unparseable
    publishedAt are dropped too — better to miss a story than surface stale news.
    Used by all fetch_* functions to stop Google News resurfacing old content.
    """
    from datetime import timezone as _tz
    cutoff = datetime.now(_tz.utc) - timedelta(days=max_age_days)
    kept = []
    for a in articles:
        if "error" in a:
            kept.append(a)
            continue
        raw = a.get("publishedAt", "")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            if dt >= cutoff:
                kept.append(a)
        except Exception:
            continue
    return kept


def _filter_credible(articles: list) -> list:
    """
    Drop articles from low-credibility sources (Tier 3 per source_credibility).
    Keeps errors so upstream callers can still log them.
    """
    try:
        from services.source_credibility import is_credible
    except ImportError:
        return articles

    kept = []
    for a in articles:
        if "error" in a:
            kept.append(a)
            continue
        src = a.get("source", {})
        src_name = src.get("name", "") if isinstance(src, dict) else str(src)
        if is_credible(src_name):
            kept.append(a)
    return kept


def _sort_by_date(articles: list) -> list:
    """Sort articles newest-first by publishedAt. Articles with no/unparseable date go last."""
    def _parse_dt(article):
        raw = article.get("publishedAt", "")
        if not raw:
            return datetime.min
        try:
            # Handle ISO format (with or without timezone offset)
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            # Strip timezone info for comparison (convert to naive UTC)
            if dt.tzinfo is not None:
                from datetime import timezone
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return datetime.min

    errors = [a for a in articles if "error" in a]
    valid  = [a for a in articles if "error" not in a]
    return sorted(valid, key=_parse_dt, reverse=True) + errors


def fetch_uk_vape_news(page_size=20, max_age_days: int = 7):
    """Fetch UK vaping news via Google News search. Free and unlimited."""
    all_articles = []
    for query in UK_VAPE_SEARCHES:
        articles = _search_gnews(query, max_items=15)
        all_articles.extend([a for a in articles if "error" not in a])
    filtered = _filter_credible(_filter_recent(all_articles, max_age_days=max_age_days))
    return _sort_by_date(_deduplicate(filtered))[:page_size]


def fetch_global_vape_news(page_size=20, max_age_days: int = 7):
    """Fetch global vaping news via Google News search."""
    all_articles = []
    for query in GLOBAL_VAPE_SEARCHES:
        articles = _search_gnews(query, max_items=15)
        all_articles.extend([a for a in articles if "error" not in a])
    filtered = _filter_credible(_filter_recent(all_articles, max_age_days=max_age_days))
    return _sort_by_date(_deduplicate(filtered))[:page_size]


def fetch_trending_news(page_size=30, days_back=None, max_age_days: int = 7):
    """
    Fetch trending UK stories across entertainment, sport, business, health, science, tech.
    Free and unlimited via Google News RSS topic feeds.
    """
    all_articles = []

    # Top UK stories
    top_stories = _fetch_rss(f"{GNEWS_BASE}?{GNEWS_PARAMS}", max_items=10)
    for a in top_stories:
        if "error" not in a:
            a["_category"] = "Top Stories"
    all_articles.extend([a for a in top_stories if "error" not in a])

    # Topic feeds
    for topic_name, topic_url in GNEWS_TOPICS.items():
        articles = _fetch_rss(topic_url, max_items=8)
        for a in articles:
            if "error" not in a:
                a["_category"] = topic_name
        all_articles.extend([a for a in articles if "error" not in a])

    filtered = _filter_credible(_filter_recent(all_articles, max_age_days=max_age_days))
    return _sort_by_date(_deduplicate(filtered))[:page_size]


# Social/viral search queries — stories originating from Reddit, TikTok, social media
SOCIAL_VIRAL_SEARCHES = {
    "Reddit Vaping": '"reddit" vaping OR vape',
    "Social Media Vaping": '"social media" vaping OR vape',
    "TikTok / Viral Vaping": '"tiktok" OR "viral" vaping OR vape',
    "Weird Vape News": '"weird news" OR "bizarre" vaping OR vape',
    "Viral UK Trends": '"reddit" OR "viral" OR "tiktok" UK trending',
}


def fetch_social_viral_news(page_size=25, max_age_days: int = 7):
    """
    Fetch stories originating from Reddit, TikTok and social media.
    Captures viral content that has crossed into mainstream news —
    exactly the kind of stories Riot can news-jack or add comment to.
    """
    all_articles = []

    for category, query in SOCIAL_VIRAL_SEARCHES.items():
        articles = _search_gnews(query, max_items=10)
        for a in articles:
            if "error" not in a:
                a["_category"] = category
        all_articles.extend([a for a in articles if "error" not in a])

    filtered = _filter_credible(_filter_recent(all_articles, max_age_days=max_age_days))
    return _sort_by_date(_deduplicate(filtered))[:page_size]


def _format_uk_date(iso_str: str) -> str:
    """Convert an ISO datetime string to UK date format — e.g. '18 April 2026'."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%-d %B %Y")
    except Exception:
        # Fallback: strip time portion if present and reformat
        try:
            date_part = iso_str[:10]  # "YYYY-MM-DD"
            dt = datetime.strptime(date_part, "%Y-%m-%d")
            return dt.strftime("%-d %B %Y")
        except Exception:
            return iso_str[:10]  # Return raw date portion as last resort


def format_article(article):
    """Format an article dict for display."""
    return {
        "title": article.get("title", "No title"),
        "source": article.get("source", {}).get("name", "Unknown"),
        "description": article.get("description", ""),
        "url": article.get("url", ""),
        "published": _format_uk_date(article.get("publishedAt", "")),
        "content": article.get("description", ""),
        "category": article.get("_category", ""),
    }


def is_url(text):
    """Check if text looks like a URL."""
    return bool(re.match(r"https?://\S+", text.strip()))


def fetch_article_text(url):
    """Fetch a URL and extract readable text content."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Riot PR Desk)"})
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > 3000:
            text = text[:3000] + "..."

        if title:
            return f"{title}\n\n{text}"
        return text

    except (URLError, Exception):
        return None


# Legacy compatibility — these are no longer needed but kept so existing page code doesn't break
SEARCH_PRESETS = {}


def fetch_news_multi(**kwargs):
    return fetch_trending_news()
