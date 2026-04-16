"""
Spokesperson profiles — real Riot Labs spokespeople.
"""

SPOKESPEOPLE = {
    "CEO": {
        "name": "Ben Johnson",
        "title": "CEO, Riot Labs",
        "bio": (
            "Founder and CEO of Riot Labs. Built Riot from the ground up into one of the UK's "
            "leading independent vape brands. Passionate about British manufacturing, helping "
            "people quit smoking and building a category that earns public trust. Known for "
            "backing bold campaigns — from sponsoring non-league football club Wroxham FC "
            "to launching Riot Activist."
        ),
        "tone": "Direct, plain-speaking, visionary. Talks like a founder who's built something real — not a corporate suit.",
        "topics": [
            "Company strategy and vision",
            "British manufacturing",
            "Industry leadership",
            "Regulatory engagement",
            "Harm reduction",
            "Brand campaigns and sponsorships",
        ],
    },
    "Head of Brand & Marketing": {
        "name": "David Donaghy",
        "title": "Head of Brand & Marketing, Riot Labs",
        "bio": (
            "Leads Riot's brand strategy, creative output, PR and marketing. Architect of "
            "Riot's comms approach across trade, consumer and regulatory channels. Drives "
            "the Riot Activist campaigning arm and oversees the creative marketing team. "
            "Background in challenger brand strategy with a bias for action over talk."
        ),
        "tone": "Strategic, commercially sharp, no-nonsense. Speaks with authority on brand, trade and comms.",
        "topics": [
            "Brand strategy and campaigns",
            "Trade and retailer comms",
            "Riot Activist",
            "Product launches",
            "Vape tax comms",
            "Industry marketing and PR",
        ],
    },
}


def get_spokesperson_names():
    return list(SPOKESPEOPLE.keys())


def get_spokesperson(name):
    return SPOKESPEOPLE.get(name)
