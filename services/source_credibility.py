"""
Source credibility tiers — filter out low-cred news sources before they
reach AI analysis. Used by services/autonomous_engine.py._add_articles().

Edit TIER_1 / TIER_2 as you discover new sources you want to include.
Everything not listed is Tier 3 and will be blocked.
"""


# Tier 1: UK nationals, major trade press, credible international.
# These pass through with no penalty.
TIER_1 = {
    # UK nationals
    "BBC", "BBC News", "BBC.com", "BBC.co.uk",
    "The Guardian", "Guardian", "theguardian.com",
    "The Times", "Times", "thetimes.co.uk",
    "The Telegraph", "Daily Telegraph", "telegraph.co.uk",
    "Financial Times", "FT", "ft.com",
    "Daily Mail", "MailOnline", "Mail Online", "dailymail.co.uk",
    "The Sun", "thesun.co.uk",
    "Mirror", "Daily Mirror", "mirror.co.uk",
    "The Independent", "Independent", "independent.co.uk",
    "Metro", "metro.co.uk",
    "Evening Standard", "standard.co.uk",
    "Sky News", "Sky", "news.sky.com",
    "ITV News", "ITV", "itv.com",
    "LBC", "lbc.co.uk",
    "Channel 4 News", "Channel 4", "channel4.com",
    "The i", "i newspaper", "inews.co.uk",
    "HuffPost UK", "HuffPost", "Huffington Post",

    # UK vape & FMCG trade press
    "Vaping Post", "vapingpost.com",
    "ECigIntelligence", "ecigintelligence.com",
    "Vaping360", "vaping360.com",
    "Planet of the Vapes", "planetofthevapes.co.uk",
    "Convenience Store", "conveniencestore.co.uk",
    "The Grocer", "thegrocer.co.uk",
    "Better Retailing", "betterretailing.com",
    "Talking Retail", "talkingretail.com",
    "Retail Gazette", "retailgazette.co.uk",
    "Asian Trader", "asiantrader.biz",

    # Health, policy, science
    "Pulse", "pulsetoday.co.uk",
    "Nursing Times", "nursingtimes.net",
    "HSJ", "Health Service Journal", "hsj.co.uk",
    "BMJ", "The BMJ", "bmj.com",
    "The Lancet", "thelancet.com",
    "New Scientist", "newscientist.com",

    # International majors
    "Reuters", "reuters.com",
    "Bloomberg", "bloomberg.com",
    "Associated Press", "AP", "apnews.com",
    "CNN", "cnn.com",
    "CNBC", "cnbc.com",
    "The Wall Street Journal", "WSJ", "wsj.com",
    "The New York Times", "NYT", "nytimes.com",
    "The Washington Post", "washingtonpost.com",
    "Politico", "politico.eu", "politico.com",
    "Bloomberg UK",

    # Social intelligence (treated as Tier 1 — low noise filtering already
    # applied at fetch time via specific hashtags/queries)
    "X (Twitter)",
}


# Tier 2: Credible niche / specialist. Allowed but narrower remit.
TIER_2 = {
    # Vape-focused niche
    "Filter Magazine", "filtermag.org",
    "Tobacco Reporter", "tobaccoreporter.com",
    "Vaping Industry News",

    # UK parliamentary / policy
    "Politics Home", "politicshome.com",
    "Conservative Home", "conservativehome.com",
    "LabourList",
    "openDemocracy",

    # Business trade
    "City A.M.", "City AM", "cityam.com",
    "The Drum", "thedrum.com",
    "Campaign", "campaignlive.co.uk",
    "Marketing Week", "marketingweek.com",
}


# Everything else is Tier 3 — BLOCKED.
# Common Tier 3 examples (do NOT add these to Tier 1 or Tier 2):
#   - UK regional/local: Liverpool Echo, Manchester Evening News,
#     Birmingham Mail, Isle of Wight News, Yorkshire Post,
#     Cornwall Live, Leeds Live, BirminghamLive, Wales Online,
#     Chronicle Live, Gazette Live
#   - Small foreign: New Indian Express, Times of India, Hindustan Times,
#     The Hindu, local US city papers, small-state AU/NZ/CA outlets
#   - Hyperlocal / blog-style: Dorset Echo, Kent Online, Bristol Post,
#     any Reach plc regional site ("*Live")
#   - Low-cred aggregators: MSN, Yahoo News (if they're republishing
#     unidentified content)


def get_tier(source_name: str) -> int:
    """Return 1, 2, or 3 for a given source name. 3 = blocked."""
    if not source_name:
        return 3
    s = source_name.strip()

    if s in TIER_1:
        return 1
    if s in TIER_2:
        return 2

    # Case-insensitive fallback — handles "bbc news" vs "BBC News" etc.
    s_lower = s.lower()
    for src in TIER_1:
        if src.lower() == s_lower:
            return 1
    for src in TIER_2:
        if src.lower() == s_lower:
            return 2

    return 3


def is_credible(source_name: str) -> bool:
    """True if Tier 1 or 2 — safe to surface to the AI."""
    return get_tier(source_name) <= 2
