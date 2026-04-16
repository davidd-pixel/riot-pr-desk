"""
App configuration — tones, audiences, output types.
"""

TONES = {
    "Corporate": "Professional, authoritative, measured. Suitable for regulatory bodies, investors and national media.",
    "Conversational": "Warm, approachable, human. Suitable for trade press, retailer comms and LinkedIn.",
    "Campaigning": "Bold, urgent, activist. Suitable for Riot Activist content and advocacy messaging.",
    "Trade": "Commercial, practical, benefit-led. Suitable for retailer updates, sales briefings and trade media.",
}

AUDIENCES = {
    "Trade Media": "Vaping industry press, FMCG trade publications (e.g. The Grocer, Talking Retail, Vape Business)",
    "National Press": "National newspapers, broadcast media, general news outlets",
    "Retailers": "Independent vape shops, convenience stores, wholesale partners",
    "Consumers": "Adult vapers and smokers considering switching",
    "Internal / Sales Team": "Riot's internal teams including sales, marketing and customer service",
}

OUTPUT_TYPES = [
    "Press Release",
    "Journalist Pitch Email",
    "LinkedIn Post",
    "Retailer WhatsApp Comms",
    "Consumer Social Media Comms",
    "Internal Briefing",
]

NEWS_KEYWORDS = [
    "vaping", "vape", "e-cigarette", "e-liquid",
    "tobacco regulation", "smoking cessation", "nicotine",
    "disposable vape", "vape tax", "MHRA",
    "public health vaping", "harm reduction",
    "FMCG retail UK", "convenience retail",
]

TRIAGE_CATEGORIES = {
    "respond": "Riot should issue a public response — high relevance, strong angle available.",
    "monitor": "Worth watching — could develop into an opportunity or threat.",
    "ignore": "Low relevance to Riot or no clear angle.",
    "campaign": "Could be turned into a proactive Riot Activist campaign angle.",
}
