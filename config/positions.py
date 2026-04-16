"""
Riot position bank — key stances on industry topics.
Built from real Riot comms, strategy docs and brand materials.
"""

POSITIONS = {
    "British Manufacturing": {
        "headline": "Proudly made in Great Britain",
        "stance": (
            "Riot is one of the few major vape brands that manufactures in the UK. "
            "Our e-liquids are developed and produced through Fantasia Flavour House, "
            "our in-house flavour operation. This means British jobs, rigorous quality control "
            "and full supply chain traceability. We believe British manufacturing should be "
            "championed — not undermined by cheap imports that cut corners on safety and compliance."
        ),
        "key_messages": [
            "Riot products are manufactured in Great Britain to the highest standards",
            "Fantasia Flavour House develops and produces our e-liquids in-house in the UK",
            "British manufacturing supports local jobs and economic growth",
            "UK production ensures full regulatory compliance and traceability",
            "Consumers deserve to know where their products are made",
        ],
        "keywords": ["manufacturing", "made in britain", "UK production", "factory", "jobs", "fantasia"],
    },
    "Harm Reduction": {
        "headline": "Vaping saves lives — the science is clear",
        "stance": (
            "Riot exists to help people quit smoking. Vaping is significantly less harmful "
            "than smoking, and millions of adults have used vapes to quit cigarettes. "
            "We're not just selling products — we're liberating people from the choking grasp "
            "of cigarettes. Regulation should protect consumers while preserving access to "
            "less harmful alternatives."
        ),
        "key_messages": [
            "Vaping is at least 95% less harmful than smoking according to Public Health England",
            "Over 4 million adults in the UK have used vapes to quit smoking",
            "Harm reduction policy must be grounded in science, not moral panic",
            "Riot supports responsible regulation that protects both adults and young people",
            "Riot Rehab and smoking cessation initiatives demonstrate our commitment to helping people quit",
        ],
        "keywords": ["harm reduction", "quit smoking", "health", "PHE", "less harmful", "cessation"],
    },
    "Flavour Protection": {
        "headline": "Flavours help adults quit — banning them helps no one",
        "stance": (
            "Flavoured vapes are a critical tool in helping adult smokers switch. "
            "Evidence shows that restricting flavours pushes people back to cigarettes "
            "or towards unregulated black market products. Riot advocates for sensible "
            "regulation that keeps flavours available to adults. Our flavours are developed "
            "by scientists who replicate molecular profiles of ingredients with extraordinary "
            "accuracy — it's the difference between an e-liquid that tastes of blueberry "
            "and one that tastes like blueberry's synthetic cousin."
        ),
        "key_messages": [
            "Flavoured vapes are the most effective quitting aid for adult smokers",
            "Flavour bans increase black market activity and reduce consumer safety",
            "Adult consumer choice must be protected alongside youth prevention",
            "Riot supports age-gated access, not blanket flavour bans",
            "Our in-house flavour scientists develop products to the highest standards",
        ],
        "keywords": ["flavour", "flavor", "ban", "restriction", "taste", "fruit"],
    },
    "Retailer Support": {
        "headline": "We back the retailers who back their communities",
        "stance": (
            "Independent retailers are the backbone of the UK vaping market. "
            "Riot invests in retailer education, compliance support, category management "
            "and direct communication through our WhatsApp retailer channel. We help shops "
            "grow their vape business responsibly — because a well-informed retailer "
            "is the best gatekeeper against underage sales."
        ),
        "key_messages": [
            "Riot provides compliance training, POS materials and category management support",
            "Our WhatsApp retailer channel delivers trade news, product updates and support directly",
            "Independent retailers are essential to responsible vape distribution",
            "A well-informed retailer is the best gatekeeper against underage sales",
            "Riot's trade team works on the ground with shops across the UK",
        ],
        "keywords": ["retailer", "shop", "store", "trade", "wholesale", "independent", "whatsapp"],
    },
    "Vape Tax": {
        "headline": "Tax vapes proportionally — don't punish smokers trying to quit",
        "stance": (
            "Vaping Products Duty starts 1 October 2026 at £2.20 per 10ml, with full "
            "duty-stamped shelf compliance required by 1 April 2027. Riot accepts taxation "
            "is coming but it must be proportionate. The government has committed to a "
            "tobacco duty increase alongside VPD to maintain the price incentive to switch. "
            "If vapes become too expensive, smokers will stay on cigarettes or turn to the "
            "black market. Riot is working to be fully tax-stamp ready and supporting "
            "retailers through the transition."
        ),
        "key_messages": [
            "VPD starts 1 October 2026 at £2.20 per 10ml — duty stamps required on all retail packaging",
            "Full shelf compliance required by 1 April 2027 — unstamped products become illegal to sell",
            "Vape tax must maintain a clear price gap between vapes and cigarettes",
            "Excessive taxation drives consumers to unregulated black market products",
            "Riot is supporting retailers through the transition with clear timelines and practical guidance",
            "Riot aims to be fully tax-stamp ready ahead of the October 2026 deadline",
        ],
        "keywords": ["tax", "duty", "price", "excise", "fiscal", "budget", "HMRC", "VPD", "stamp"],
    },
    "Compliance & Standards": {
        "headline": "Compliance isn't optional — it's how we protect consumers",
        "stance": (
            "Riot meets and exceeds all UK regulatory requirements including TRPR and MHRA "
            "notification. We believe the industry must self-regulate to the highest standard "
            "or face losing the right to exist. Non-compliant products — overwhelmingly "
            "imported — endanger consumers and damage the reputation of legitimate manufacturers."
        ),
        "key_messages": [
            "All Riot products are fully TRPR compliant and MHRA notified",
            "Riot voluntarily exceeds minimum regulatory requirements",
            "Industry self-regulation is essential to maintaining public trust",
            "Non-compliant products endanger consumers and the entire category",
            "UK-manufactured products offer the highest compliance standards",
        ],
        "keywords": ["compliance", "regulation", "TRPR", "MHRA", "standards", "legal"],
    },
    "Chinese Disposables": {
        "headline": "The disposable crisis is an import problem, not a vaping problem",
        "stance": (
            "The flood of non-compliant Chinese disposable vapes has damaged the industry's "
            "reputation and put consumers at risk. These products often fail basic safety tests "
            "and contain nicotine levels above the legal limit. Riot calls for stronger border "
            "enforcement, stricter import controls and meaningful penalties for non-compliant "
            "distributors. The disposable problem is distinct from the regulated UK vaping industry."
        ),
        "key_messages": [
            "Non-compliant disposables are overwhelmingly imported, not UK-manufactured",
            "Stronger border enforcement is needed to stop illegal products entering the UK",
            "Riot supports tougher penalties for distributors of non-compliant products",
            "The disposable problem is distinct from the regulated UK vaping industry",
            "British-manufactured products like Riot's meet the highest safety and compliance standards",
        ],
        "keywords": ["disposable", "chinese", "import", "illegal", "non-compliant", "safety"],
    },
    "Riot Activist": {
        "headline": "We don't just make vapes — we fight for vapers",
        "stance": (
            "Riot Activist is our campaigning arm. We mobilise vapers, retailers and "
            "industry partners to push back against misinformation, disproportionate regulation "
            "and policies that would harm adult smokers' right to switch. From tackling "
            "junk science headlines to running bold public campaigns, Riot Activist gives "
            "vapers a voice in the debates that affect their lives."
        ),
        "key_messages": [
            "Riot Activist gives vapers a voice in policy debates",
            "We campaign against misinformation and junk science on vaping",
            "Riot Activist partners with retailers and trade bodies for collective action",
            "Every vaper has a stake in the regulatory outcome — and a right to be heard",
            "Bold campaigns like Welcome to Wroxham and Chief Misinformation Officer demonstrate our activist approach",
        ],
        "keywords": ["activist", "campaign", "advocacy", "policy", "misinformation", "stunt"],
    },
    "Product Launch": {
        "headline": "Innovation that moves the category forward",
        "stance": (
            "Riot continuously develops new products across e-liquids, closed-pod systems "
            "and next-generation devices. Every launch is backed by in-house R&D through "
            "Fantasia Flavour House and designed to meet real consumer needs — whether that's "
            "the convenience retail channel (RIOT CONNEX), premium 10ml formats (KURO) "
            "or core e-liquid ranges (Riot Bar Edtn). We launch with full trade support, "
            "POS materials and retailer comms."
        ),
        "key_messages": [
            "All new products are developed in-house and manufactured in the UK",
            "Product launches are supported with full trade comms, POS and retailer toolkits",
            "Riot CONNEX brings a fully compliant closed-pod system to convenience retail",
            "KURO is the first brand born from Fantasia Flavour House — a premium 10ml concept",
            "Every product is TRPR compliant and MHRA notified before launch",
        ],
        "keywords": ["launch", "new product", "connex", "kuro", "bar edtn", "device", "pod"],
    },
}


def get_position_names():
    return list(POSITIONS.keys())


def get_position(name):
    return POSITIONS.get(name)


def get_all_keywords():
    keywords = []
    for pos in POSITIONS.values():
        keywords.extend(pos["keywords"])
    return list(set(keywords))
