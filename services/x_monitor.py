"""
X (Twitter) Monitor — real-time social intelligence via X API v2.

Uses app-only auth (Bearer Token) — read-only, no user OAuth needed.
Requires: X_BEARER_TOKEN env var + tweepy>=4.14.0 installed.

If the token is not configured, all functions return [] silently so the
daily briefing continues to run with Google News RSS data only.

API tier notes:
  Free  ($0/month)  : ~10 tweets per request, 1 query per 15 min
  Basic ($100/month): 100 tweets per request, 15k reads / 15 min  ← recommended
  Pro   ($5k/month) : full archive + trending topics

Trending topics are NOT available at Free or Basic tier (endpoint deprecated).
"""

import os
from datetime import datetime, timezone, timedelta


# Drop tweets older than this — real-time signal only
_MAX_TWEET_AGE_DAYS = 7


def _is_recent_tweet(tweet) -> bool:
    """Return True if tweet is within the recency window."""
    created = getattr(tweet, "created_at", None)
    if created is None:
        return False
    try:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - created) <= timedelta(days=_MAX_TWEET_AGE_DAYS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    """Return True if X_BEARER_TOKEN is present in the environment."""
    return bool(os.getenv("X_BEARER_TOKEN", "").strip())


def _get_client():
    """Return an authenticated tweepy.Client (app-only Bearer Token auth)."""
    try:
        import tweepy
    except ImportError:
        raise RuntimeError("tweepy not installed — run: pip install tweepy>=4.14.0")

    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("X_BEARER_TOKEN environment variable not set")

    return tweepy.Client(bearer_token=token, wait_on_rate_limit=False)


# ---------------------------------------------------------------------------
# Tweet → article conversion
# ---------------------------------------------------------------------------

def _tweet_to_article(tweet) -> dict:
    """
    Convert a tweepy Tweet object to the standard article dict shape used
    throughout the app (same format as news_monitor.format_article).
    """
    text = tweet.text or ""
    created = tweet.created_at
    if created is None:
        created = datetime.now(timezone.utc)

    # Use first 100 chars as headline
    title = text[:100] + ("…" if len(text) > 100 else "")

    return {
        "title": title,
        "source": {"name": "X (Twitter)"},
        "description": text,
        "url": f"https://x.com/i/web/status/{tweet.id}",
        "publishedAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
        "content": text,
    }


# ---------------------------------------------------------------------------
# Public fetch functions
# ---------------------------------------------------------------------------

def fetch_vaping_tweets(max_results: int = 20) -> list:
    """
    Search recent tweets about vaping, e-cigarettes and nicotine harm reduction.
    Returns a list of article dicts (same format as news_monitor).

    Good for surfacing consumer sentiment and viral vaping stories early —
    often 4-12 hours before mainstream news picks them up.
    """
    if not is_configured():
        return []

    # Broad vaping/nicotine search — exclude retweets and bare replies to keep quality high
    query = (
        "(#vaping OR #vape OR #disposablevape OR #ecig "
        'OR "e-cigarette" OR "nicotine pouch" OR "harm reduction vaping" '
        'OR "vape ban" OR "vape tax" OR "disposable vape" OR "vaping regulation") '
        "lang:en -is:retweet"
    )

    try:
        client = _get_client()
        # max_results: 10 on Free tier, up to 100 on Basic+
        capped = min(max_results, 100)
        resp = client.search_recent_tweets(
            query=query,
            max_results=max(10, capped),
            tweet_fields=["created_at", "text", "author_id"],
        )
        if not resp.data:
            return []
        return [_tweet_to_article(t) for t in resp.data if _is_recent_tweet(t)]
    except Exception as e:
        print(f"[X] fetch_vaping_tweets error: {e}")
        return []


def fetch_competitor_tweets(max_results: int = 10) -> list:
    """
    Search for mentions of major vape competitors.
    Surfaces competitive intelligence — if a competitor is in the news on X,
    there may be a reactive PR opportunity for Riot.
    """
    if not is_configured():
        return []

    # Main UK/global vape competitors
    query = (
        '("Elf Bar" OR "Lost Mary" OR "Geek Bar" OR "Hayati" OR "Crystal Bar" '
        'OR "Randm Tornado" OR "IVG" OR "Vampire Vape") '
        "(vape OR vaping OR e-cigarette) "
        "lang:en -is:retweet"
    )

    try:
        client = _get_client()
        capped = min(max_results, 100)
        resp = client.search_recent_tweets(
            query=query,
            max_results=max(10, capped),
            tweet_fields=["created_at", "text"],
        )
        if not resp.data:
            return []
        return [_tweet_to_article(t) for t in resp.data if _is_recent_tweet(t)]
    except Exception as e:
        print(f"[X] fetch_competitor_tweets error: {e}")
        return []


def fetch_riot_mentions(max_results: int = 10) -> list:
    """
    Monitor brand mentions of Riot Labs on X.
    Returns articles so mentions can be surfaced in the briefing and
    analysed by the AI for PR response opportunities.
    """
    if not is_configured():
        return []

    query = (
        '("Riot Labs" OR "Riot Vape" OR "Riot e-liquid" OR "Riot Squad vape" '
        'OR "@riotlabs" OR "#riotlabs" OR "#riotvape") '
        "-is:retweet"
    )

    try:
        client = _get_client()
        capped = min(max_results, 100)
        resp = client.search_recent_tweets(
            query=query,
            max_results=max(10, capped),
            tweet_fields=["created_at", "text"],
        )
        if not resp.data:
            return []
        return [_tweet_to_article(t) for t in resp.data if _is_recent_tweet(t)]
    except Exception as e:
        print(f"[X] fetch_riot_mentions error: {e}")
        return []


def fetch_nicotine_health_tweets(max_results: int = 10) -> list:
    """
    Search for health / regulation tweets about nicotine and smoking cessation.
    Often an early signal for regulatory stories that will hit mainstream news.
    """
    if not is_configured():
        return []

    query = (
        '("stop smoking" OR "quit smoking" OR "nicotine replacement" '
        'OR "vaping NHS" OR "vaping health" OR "PHE vaping" '
        'OR "MHRA vaping" OR "tobacco harm reduction") '
        "lang:en -is:retweet"
    )

    try:
        client = _get_client()
        capped = min(max_results, 100)
        resp = client.search_recent_tweets(
            query=query,
            max_results=max(10, capped),
            tweet_fields=["created_at", "text"],
        )
        if not resp.data:
            return []
        return [_tweet_to_article(t) for t in resp.data if _is_recent_tweet(t)]
    except Exception as e:
        print(f"[X] fetch_nicotine_health_tweets error: {e}")
        return []
