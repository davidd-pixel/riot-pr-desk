"""
Autonomous Engine — the intelligence layer that runs daily briefings,
analyses stories for Riot PR potential, auto-generates PR packs and
auto-matches journalists. Also handles the daily email digest (called
by GitHub Actions with --send-digest flag).
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BRIEFING_CACHE_FILE = os.path.join(DATA_DIR, "briefing_cache.json")
BRIEFING_CACHE_HOURS = 4


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    try:
        with open(BRIEFING_CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BRIEFING_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _cache_is_fresh() -> bool:
    cache = _load_cache()
    ts = cache.get("generated_at")
    if not ts:
        return False
    try:
        generated = datetime.fromisoformat(ts)
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - generated) < timedelta(hours=BRIEFING_CACHE_HOURS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Story analysis
# ---------------------------------------------------------------------------

def analyse_story_for_riot(article: dict) -> dict:
    """
    Ask the AI to score a news story for Riot relevance, suggest an angle,
    and classify the opportunity type.
    Returns: {relevance_score, riot_angle, suggested_position, why_it_matters, opportunity_type}
    or {"error": "..."} on failure.
    """
    from services.ai_engine import generate_json
    from config.positions import POSITIONS

    title = article.get("title", "")
    description = article.get("description", "") or article.get("content", "")
    source = article.get("source", {})
    source_name = source.get("name", "") if isinstance(source, dict) else str(source)

    if not title:
        return {"error": "No title"}

    positions_list = "\n".join(f"- {name}" for name in POSITIONS.keys())

    prompt = f"""You are Riot Labs' PR strategist. Analyse this news story for its PR potential for Riot.

STORY:
Headline: {title}
Source: {source_name}
Summary: {description[:500]}

RIOT CONTEXT:
Riot Labs is a UK-based independent vape brand (Riot Squad, Riot Bar Edition). Key angles:
- Harm reduction: vaping is 95% less harmful than smoking (PHE)
- British manufacturing: made in the UK via Fantasia Flavour House
- Anti-Big-Tobacco: independent challenger brand
- 4 million UK vapers who deserve quality products
- Regulation: supportive of sensible regulation, opposed to prohibitionist policies

SCORE THESE LOW (1-3):
Riot does NOT respond to tabloid horror stories. Score LOW when the story is:
- A personal horror / medical terror tale
  (e.g. "Vaping gave me black teeth", "Woman, 22, given 18 months to live
   after vaping since 15", "My lungs collapsed from vaping")
- About illicit, spiked, or counterfeit vapes
  (e.g. "Thieves handing out vapes spiked with drugs", "Child hospitalised
   by fake vape", "Drug-laced disposables seized")
- A teen/underage scare narrative without wider policy context
- Individual anecdotal injury claims without scientific or regulatory grounding
- Sensationalist single-victim stories with no systemic or regulatory angle

These stories are too frequent, too sensational, and conflate illicit products
with the regulated market Riot operates in. Never score them above 3. Riot
does not comment on individual horror stories.

AVAILABLE POSITIONS:
{positions_list}

TASK:
1. Score this story's relevance to Riot on a scale of 1-10 (10 = Riot must respond today)
2. Suggest Riot's specific PR angle for this story (1-2 sentences, concrete and punchy)
3. Choose the single best position from the list above
4. Write one line explaining why it matters for Riot right now
5. Identify ALL opportunity types this story could generate for Riot (can be more than one):
   - "pr_commentary" — story demands a press release or formal Riot statement (regulation, product safety, tax, science)
   - "newsjacking" — trending story Riot can piggyback with a reactive quote or comment (celebrity, viral, mainstream news)
   - "blog" — story could fuel a longer-form blog post (education, harm reduction explainer, consumer trend, myth-busting, how-to)
6. If "newsjacking" is one of the types, you MUST provide a bold, specific creative brief — not a generic "post about it on social" suggestion. Riot has a strong news-jacking track record:
     - **Heat Map** — data-led map of UK illegal vape hotspots (Daily Mail, regional press)
     - **Ibiza Final Boss** — summer festival culture hijack (Mirror, Indy100)
     - **Chief Misinformation Officer** — activist stunt responding to vaping junk science
     - **Rishi's Vape Shop** — political satire tied to government policy
     - **Welcome to Wroxham** — non-league football sponsorship (300k+ social views)
     - **Countdown Vape Party** — disposable ban deadline stunt (Evening Standard, Daily Star)
     - **Merry Quitmas** — Christmas campaign with East 17

   Think Paddy Power meets Riot activist. Provide:
   - newsjacking_hook: the creative connection between this story and Riot (1-2 sentences — what's the surprising, funny or sharp link?)
   - newsjacking_execution: what Riot would actually DO. Be specific and concrete — a stunt? a data piece? a satirical product tie-in? a fake shopfront? a sponsored video? Describe the asset/activation in 2-3 sentences.
   - newsjacking_format: one of "Reactive press quote", "Social stunt / activation", "Data piece / map", "Satirical product tie-in", "Reactive video", "CEO comment to media", "Full creative campaign"
   - newsjacking_speed: one of "Immediate (24h)", "This week", "Can plan (2+ weeks)"
   - newsjacking_concept: one-line title for the idea (e.g. "Riot's Disposable Ban Funeral", "The Big Vape Price Tracker")

   NEVER output generic suggestions like "post a social comment" or "issue a CEO quote" — if that's all you can think of, this isn't a newsjacking opp; re-classify as pr_commentary instead.

Be generous with "blog" — most vaping/health/regulation stories have blog potential.
If a story is strong enough for PR commentary it almost certainly also warrants a blog post.

Return ONLY valid JSON in this exact format:
{{
  "relevance_score": <integer 1-10>,
  "riot_angle": "<1-2 sentence PR angle>",
  "suggested_position": "<exact position name from list>",
  "why_it_matters": "<one line>",
  "opportunity_types": ["pr_commentary", "blog"],
  "newsjacking_concept": "<one-line title — only if newsjacking in opportunity_types>",
  "newsjacking_hook": "<1-2 sentence creative connection — only if newsjacking>",
  "newsjacking_execution": "<2-3 sentence specific execution — only if newsjacking>",
  "newsjacking_format": "<format — only if newsjacking>",
  "newsjacking_speed": "<Immediate (24h) / This week / Can plan (2+ weeks) — only if newsjacking>"
}}

opportunity_types must be a JSON array containing one or more of: "pr_commentary", "newsjacking", "blog"."""

    try:
        result = generate_json(prompt)
        if isinstance(result, dict) and "relevance_score" in result:
            # Normalise to list
            valid_types = {"pr_commentary", "newsjacking", "blog"}
            raw_types = result.get("opportunity_types") or result.get("opportunity_type")
            if isinstance(raw_types, str):
                raw_types = [raw_types]
            if not isinstance(raw_types, list):
                raw_types = ["pr_commentary"]
            result["opportunity_types"] = [t for t in raw_types if t in valid_types] or ["pr_commentary"]
            return result
        return {"error": "Invalid AI response format"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Daily briefing
# ---------------------------------------------------------------------------

def run_daily_briefing(force: bool = False) -> list:
    """
    Fetch today's top news, analyse each story for Riot relevance, save new
    opportunities (deduped against existing pending ones) and return the list.
    Uses a 4-hour cache — pass force=True to bypass.
    Returns list of opportunity dicts (from opportunity_tracker).
    """
    from services.opportunity_tracker import (
        save_opportunity, get_all_opportunities, get_pending_opportunities,
        update_opportunity_status,
    )

    # Return cached pending opportunities if cache is fresh
    if not force and _cache_is_fresh():
        return get_pending_opportunities()

    # On a forced run (GitHub Actions / manual), clear old pending opps so
    # inbox count matches the email exactly
    if force:
        for old in get_pending_opportunities():
            update_opportunity_status(old["id"], "skipped")

    # Fetch news — all feeds: vape-specific, trending, social, competitors, regulatory
    articles = []
    seen_titles: set = set()
    _credibility_skipped = 0

    from services.source_credibility import is_credible

    def _add_articles(feed: list):
        nonlocal _credibility_skipped
        for a in feed:
            if "error" in a:
                continue
            # Skip low-credibility sources before AI ever sees them
            src = a.get("source", {})
            src_name = src.get("name", "") if isinstance(src, dict) else str(src)
            if not is_credible(src_name):
                _credibility_skipped += 1
                continue
            t = a.get("title", "").lower()[:60]
            if t and t not in seen_titles:
                seen_titles.add(t)
                articles.append(a)

    try:
        from services.news_monitor import (
            fetch_uk_vape_news, fetch_global_vape_news,
            fetch_trending_news,
        )
        _add_articles(fetch_uk_vape_news(page_size=10))
        _add_articles(fetch_global_vape_news(page_size=10))
        _add_articles(fetch_trending_news(page_size=15))
    except Exception as e:
        print(f"News feed error: {e}")

    # Real X / Twitter data (if X_BEARER_TOKEN is configured)
    try:
        from services.x_monitor import (
            fetch_vaping_tweets, fetch_competitor_tweets,
            fetch_riot_mentions, fetch_nicotine_health_tweets,
            is_configured as x_is_configured,
        )
        if x_is_configured():
            _add_articles(fetch_vaping_tweets(max_results=15))
            _add_articles(fetch_competitor_tweets(max_results=10))
            _add_articles(fetch_riot_mentions(max_results=10))
            _add_articles(fetch_nicotine_health_tweets(max_results=10))
            print("[X] Social data fetched from X API")
        else:
            print("[X] X_BEARER_TOKEN not set — skipping X social feed")
    except Exception as e:
        print(f"[X] fetch error: {e}")

    try:
        from services.competitor_monitor import fetch_all_competitor_news
        comp_data = fetch_all_competitor_news(page_size=5)
        for comp_name, comp_articles in comp_data.items():
            for a in comp_articles:
                a.setdefault("source", {})
                if isinstance(a.get("source"), dict):
                    a["source"]["name"] = a["source"].get("name") or comp_name
                _add_articles([a])
    except Exception as e:
        print(f"Competitor feed error: {e}")

    try:
        from services.regulator_monitor import get_all_regulator_news
        reg_data = get_all_regulator_news(page_size=5)
        for reg_name, reg_articles in reg_data.items():
            for a in reg_articles:
                a.setdefault("source", {})
                if isinstance(a.get("source"), dict):
                    a["source"]["name"] = a["source"].get("name") or reg_name
                _add_articles([a])
    except Exception as e:
        print(f"Regulatory feed error: {e}")

    print(f"Fetched {len(articles)} articles across all feeds "
          f"({_credibility_skipped} skipped as low-credibility sources)")

    if not articles:
        _save_cache({"generated_at": datetime.now(timezone.utc).isoformat(), "count": 0})
        return get_pending_opportunities()

    # Dedup: don't re-analyse stories we've already seen
    existing = get_all_opportunities()
    seen_titles = {o.get("story_title", "").lower() for o in existing}

    # Analyse up to 20 credible articles — we'll trim to 5-per-type afterwards
    new_count = 0
    analysed = []
    for article in articles[:20]:
        title = article.get("title", "")
        if not title or title.lower() in seen_titles:
            continue

        print(f"  Analysing: {title[:80]}")
        analysis = analyse_story_for_riot(article)
        if "error" in analysis:
            print(f"    → Error: {analysis['error']}")
            continue

        score = analysis.get("relevance_score", 0)
        print(f"    → Score: {score}/10 types={analysis.get('opportunity_types')} — {analysis.get('riot_angle','')[:50]}")
        if score < 4:  # only surface genuinely relevant stories
            continue

        source = article.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else str(source)

        # Create a separate opportunity for each type the AI identified
        for opp_type in analysis.get("opportunity_types", ["pr_commentary"]):
            is_nj = opp_type == "newsjacking"
            save_opportunity(
                story_title=title,
                story_url=article.get("url", ""),
                story_source=source_name,
                riot_angle=analysis.get("riot_angle", ""),
                relevance_score=score,
                suggested_position=analysis.get("suggested_position", ""),
                why_it_matters=analysis.get("why_it_matters", ""),
                opportunity_type=opp_type,
                newsjacking_concept=analysis.get("newsjacking_concept", "") if is_nj else "",
                newsjacking_hook=analysis.get("newsjacking_hook", "") if is_nj else "",
                newsjacking_execution=analysis.get("newsjacking_execution", "") if is_nj else "",
                newsjacking_format=analysis.get("newsjacking_format", "") if is_nj else "",
                newsjacking_speed=analysis.get("newsjacking_speed", "") if is_nj else "",
                story_published_at=article.get("publishedAt", ""),
            )
        analysed.append(analysis)
        new_count += 1

        # 15 analyses gives plenty of candidates for 5-per-type cap (5×3=15)
        if new_count >= 15:
            break

    # Trim to top-5-per-type so inbox + email see the same focused set
    from services.opportunity_tracker import trim_pending_to_top_n_per_type
    trimmed = trim_pending_to_top_n_per_type(n=5)
    if trimmed:
        print(f"Trimmed {trimmed} lower-ranked opportunities to keep top-5 per type")

    _save_cache({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": new_count,
    })

    return get_pending_opportunities()


def get_briefing_meta() -> dict:
    """Return metadata about the last briefing run (timestamp, count)."""
    cache = _load_cache()
    return {
        "generated_at": cache.get("generated_at", ""),
        "count": cache.get("count", 0),
        "is_fresh": _cache_is_fresh(),
    }


# ---------------------------------------------------------------------------
# Auto pack generation
# ---------------------------------------------------------------------------

def auto_generate_blog(opportunity_id: str, custom_angle: str = None) -> str:
    """
    Generate a blog post from an approved blog opportunity.
    Saves to blog_library with status 'draft'. Returns blog_id.
    """
    from services.opportunity_tracker import get_opportunity, update_opportunity_status
    from services.ai_engine import generate
    from services.blog_library import save_blog
    from utils.prompts import BLOG_PROMPT

    opp = get_opportunity(opportunity_id)
    if not opp:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    update_opportunity_status(opportunity_id, "generating")

    angle = custom_angle or opp.get("riot_angle", "")
    topic = f"{opp['story_title']} — {angle}"

    prompt = BLOG_PROMPT.format(
        topic=topic,
        blog_type="News Response / Commentary",
        primary_keyword="vaping",
        secondary_keywords="vape tax, harm reduction, UK vapers, e-cigarettes, quit smoking",
        word_count="700-900 words",
        tone_dial="Confident and direct — Riot's challenger brand voice",
    )

    try:
        content = generate(prompt)
    except Exception as e:
        update_opportunity_status(opportunity_id, "pending")
        raise RuntimeError(f"Blog generation failed: {e}")

    # Parse into sections using the numbered headers
    import re
    section_map = {
        "SEO Package": "",
        "Blog Post": "",
        "Image Suggestions": "",
        "External Links": "",
        "Social Promotion": "",
    }
    current = None
    buffer = []
    for line in content.splitlines():
        header_match = re.match(r"###\s*\d+\.\s*(.*)", line)
        if header_match:
            if current and buffer:
                section_map[current] = "\n".join(buffer).strip()
            raw = header_match.group(1).strip().upper()
            for key in section_map:
                if key.upper() in raw:
                    current = key
                    buffer = []
                    break
        elif current:
            buffer.append(line)
    if current and buffer:
        section_map[current] = "\n".join(buffer).strip()

    blog = save_blog(
        topic=opp["story_title"][:120],
        sections=section_map,
        blog_type="news_response",
        primary_keyword="vaping",
        secondary_keywords=["vape tax", "harm reduction", "UK vapers"],
        title=opp["story_title"][:80],
        tags=["auto-generated", "news-response"],
    )

    update_opportunity_status(opportunity_id, "generated", pack_id=blog["id"])
    return blog["id"]


def auto_generate_pack(opportunity_id: str, custom_angle: str = None) -> str:
    """
    Generate a PR pack (or blog for blog-type ops) from an approved opportunity.
    Routes to auto_generate_blog() for blog opportunities.
    Returns the new pack_id / blog_id.
    """
    from services.opportunity_tracker import get_opportunity, update_opportunity_status
    from services.content_generator import generate_pr_pack
    from services.pr_library import save_pack, update_pack_status

    opp = get_opportunity(opportunity_id)
    if not opp:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    # Route blog opportunities to the blog generator
    if opp.get("opportunity_type") == "blog":
        return auto_generate_blog(opportunity_id, custom_angle=custom_angle)

    update_opportunity_status(opportunity_id, "generating")

    angle = custom_angle or opp.get("riot_angle", "")
    position = opp.get("suggested_position", "Harm Reduction")
    opp_type = opp.get("opportunity_type", "pr_commentary")

    # Newsjacking gets a more reactive tone and audience
    tone = "Conversational" if opp_type == "newsjacking" else "Professional"
    audience = "National Media" if opp_type == "newsjacking" else "Trade Media"

    input_content = (
        f"{opp['story_title']}\n\n"
        f"Riot angle: {angle}\n\n"
        f"Source: {opp.get('story_source', '')}\n"
        f"Original story: {opp.get('story_url', '')}"
    )

    sections = generate_pr_pack(
        input_content=input_content,
        position_name=position,
        spokesperson_key="CEO",
        audience_key=audience,
        tone_key=tone,
    )

    pack = save_pack(
        input_content=input_content,
        sections=sections,
        position_name=position,
        spokesperson_key="CEO",
        audience_key=audience,
        tone_key=tone,
        title=opp["story_title"][:80],
        tags=["auto-generated", opp_type],
    )

    update_pack_status(pack["id"], "under_review")
    update_opportunity_status(opportunity_id, "generated", pack_id=pack["id"])

    return pack["id"]


# ---------------------------------------------------------------------------
# Auto journalist matching
# ---------------------------------------------------------------------------

def auto_match_journalists(pack_id: str) -> list:
    """
    Run AI journalist matching for an approved pack.
    Stores top 5 on the pack and returns the list.
    Each item: {id, name, publication, beat, relationship_score, reasoning}
    """
    from services.pr_library import get_pack, update_suggested_journalists
    from services.journalist_db import get_all
    from services.ai_engine import generate_json

    pack = get_pack(pack_id)
    if not pack:
        return []

    journalists = get_all()
    if not journalists:
        return []

    # Build journalist context
    j_lines = []
    for j in journalists[:80]:  # cap to manage prompt size
        beats = ", ".join(j.get("beats", []))
        j_lines.append(
            f"ID:{j['id']} | {j['name']} | {j.get('publication','')} | "
            f"Type:{j.get('type','')} | Beats:{beats} | "
            f"Relationship:{j.get('relationship_score',3)}/5"
        )
    journalist_context = "\n".join(j_lines)

    press_release = pack.get("sections", {}).get("Press Release", "")[:800]
    position = pack.get("position_name", "")

    prompt = f"""You are Riot Labs' PR director choosing which journalists to pitch for a story.

PR PACK SUMMARY:
Position: {position}
Story angle: {pack.get('input_content','')[:300]}

PRESS RELEASE EXCERPT:
{press_release}

JOURNALIST DATABASE:
{journalist_context}

Select the top 5 journalists most likely to cover this story. Consider:
1. Beat relevance (Vaping, Health, FMCG, Regulation beats are most valuable)
2. Publication type (Trade for trade stories, National for big moments)
3. Relationship score (higher = easier win)
4. Avoid pitching the same journalist twice for similar stories

Return ONLY a JSON array of exactly 5 objects:
[
  {{
    "journalist_id": "<id from database>",
    "name": "<name>",
    "publication": "<publication>",
    "reasoning": "<one sentence why this journalist for this story>"
  }}
]"""

    try:
        result = generate_json(prompt)
        if not isinstance(result, list):
            return []

        # Enrich with full journalist data
        from services.journalist_db import get_by_id
        enriched = []
        for item in result[:5]:
            jid = item.get("journalist_id", "")
            j = get_by_id(jid)
            if j:
                enriched.append({
                    "id": jid,
                    "name": j.get("name", item.get("name", "")),
                    "publication": j.get("publication", item.get("publication", "")),
                    "email": j.get("email", ""),
                    "beats": j.get("beats", []),
                    "relationship_score": j.get("relationship_score", 3),
                    "reasoning": item.get("reasoning", ""),
                })

        if enriched:
            update_suggested_journalists(pack_id, enriched)

        return enriched

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Pitch email builder
# ---------------------------------------------------------------------------

def build_mailto_link(journalist: dict, pack: dict) -> str:
    """
    Build a mailto: link pre-filled with journalist email, subject and pitch body.
    """
    import urllib.parse

    email = journalist.get("email", "")
    if not email:
        return ""

    # Extract subject from pitch email section
    pitch_section = pack.get("sections", {}).get("Journalist Pitch Email", "")
    subject = ""
    body = pitch_section

    # Try to parse Subject: line from the pitch
    for line in pitch_section.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("subject:"):
            subject = stripped[len("subject:"):].strip()
            # Remove the subject line from the body
            body = pitch_section.replace(line, "").strip()
            break

    if not subject:
        subject = f"Story pitch: {pack.get('title', 'Riot Labs')}"

    # Append journalist-specific note if present
    note = journalist.get("pitch_note", "")
    if note:
        body = body + f"\n\n[Note for this journalist: {note}]"

    params = urllib.parse.urlencode({"subject": subject, "body": body})
    return f"mailto:{urllib.parse.quote(email)}?{params}"


# ---------------------------------------------------------------------------
# Email digest (called by GitHub Actions)
# ---------------------------------------------------------------------------

def send_digest_email(opportunities: list, to_email: str) -> bool:
    """
    Send the daily PR briefing email digest via Gmail SMTP.
    Requires env vars: SMTP_USER, SMTP_PASSWORD.
    Returns True on success.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        print("SMTP credentials not configured — skipping email digest")
        return False

    today = datetime.now().strftime("%A %d %B %Y")
    n = len(opportunities)

    # Split by type
    pr_opps   = [o for o in opportunities if o.get("opportunity_type") == "pr_commentary"]
    nj_opps   = [o for o in opportunities if o.get("opportunity_type") == "newsjacking"]
    blog_opps = [o for o in opportunities if o.get("opportunity_type") == "blog"]

    from services.news_monitor import _format_uk_date as _fmt_uk

    def _opp_cards_html(opps):
        html = ""
        for opp in opps:
            score = opp.get("relevance_score", 0)
            colour = "#E8192C" if score >= 8 else "#fbbf24" if score >= 6 else "#60a5fa"
            opp_type = opp.get("opportunity_type", "pr_commentary")
            nj_concept = opp.get("newsjacking_concept", "")
            nj_format = opp.get("newsjacking_format", "")
            try:
                pub_uk = _fmt_uk(opp.get("story_published_at", ""))
            except Exception:
                pub_uk = ""
            meta_suffix = f" &middot; {pub_uk}" if pub_uk else ""

            # Newsjacking cards get the full creative brief panel to match inbox
            nj_hook = opp.get("newsjacking_hook", "")
            nj_execution = opp.get("newsjacking_execution", "")
            nj_speed = opp.get("newsjacking_speed", "")
            if opp_type == "newsjacking" and (nj_hook or nj_concept):
                meta_badges = ""
                if nj_format:
                    meta_badges += (
                        f'<span style="background:#fbbf2422;border:1px solid #fbbf2466;color:#fbbf24;'
                        f'font-size:10px;font-weight:700;padding:1px 7px;border-radius:2px;'
                        f'text-transform:uppercase;letter-spacing:0.06em;margin-right:4px">{nj_format}</span>'
                    )
                if nj_speed:
                    speed_col = "#E8192C" if "Immediate" in nj_speed else "#fbbf24" if "This week" in nj_speed else "#60a5fa"
                    meta_badges += (
                        f'<span style="background:{speed_col}22;border:1px solid {speed_col}66;color:{speed_col};'
                        f'font-size:10px;font-weight:700;padding:1px 7px;border-radius:2px;'
                        f'text-transform:uppercase;letter-spacing:0.06em">{nj_speed}</span>'
                    )
                idea_title = (
                    f'<div style="font-weight:900;font-size:14px;color:#fbbf24;margin-bottom:6px">{nj_concept}</div>'
                ) if nj_concept else ""
                hook_block = (
                    f'<div style="margin-bottom:6px"><div style="font-size:10px;font-weight:700;'
                    f'letter-spacing:0.1em;text-transform:uppercase;color:#fbbf24;margin-bottom:2px">The Hook</div>'
                    f'<div style="font-size:12px;color:#F0E0A0;line-height:1.5">{nj_hook}</div></div>'
                ) if nj_hook else ""
                exec_block = (
                    f'<div><div style="font-size:10px;font-weight:700;letter-spacing:0.1em;'
                    f'text-transform:uppercase;color:#fbbf24;margin-bottom:2px">The Execution</div>'
                    f'<div style="font-size:12px;color:#F0E0A0;line-height:1.5">{nj_execution}</div></div>'
                ) if nj_execution else ""
                body = (
                    f'<div style="background:#1A1400;border:1px solid #fbbf2433;border-radius:3px;'
                    f'padding:10px 12px;margin-top:6px;margin-bottom:6px">'
                    f'{idea_title}'
                    f'<div style="margin-bottom:6px">{meta_badges}</div>'
                    f'{hook_block}'
                    f'{exec_block}'
                    f'</div>'
                    f'<div style="font-size:11px;color:#888;margin-top:4px">'
                    f'<strong style="color:#666">Message:</strong> {opp.get("riot_angle","")}</div>'
                    f'<div style="font-size:11px;color:#999;margin-top:4px;font-style:italic">{opp.get("why_it_matters","")}</div>'
                )
            else:
                body = (
                    f'<div style="font-size:12px;color:#E0E0E0;margin-top:6px">{opp.get("riot_angle","")}</div>'
                    f'<div style="font-size:11px;color:#999;margin-top:4px;font-style:italic">{opp.get("why_it_matters","")}</div>'
                )

            html += (
                f'<div style="border-left:3px solid {colour};padding:10px 16px;'
                f'margin-bottom:10px;background:#111;border-radius:0 4px 4px 0">'
                f'<div style="font-size:13px;font-weight:700;color:#fff">{opp.get("story_title","")}</div>'
                f'<div style="font-size:11px;color:#888;margin-top:2px">'
                f'{opp.get("story_source","")}{meta_suffix} &middot; Relevance {score}/10</div>'
                f'{body}'
                f'</div>'
            )
        return html

    def _section_html(label, colour, opps):
        if not opps:
            return ""
        count = len(opps)
        return (
            f'<div style="margin-bottom:20px">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;'
            f'color:{colour};border-bottom:1px solid #222;padding-bottom:6px;margin-bottom:10px">'
            f'{label} &nbsp;·&nbsp; {count} stor{"ies" if count != 1 else "y"}</div>'
            f'{_opp_cards_html(opps)}'
            f'</div>'
        )

    section_html = (
        _section_html("PR / News Commentary", "#E8192C", pr_opps) +
        _section_html("News-Jacking", "#fbbf24", nj_opps) +
        _section_html("Blog Opportunities", "#60a5fa", blog_opps)
    )

    summary = f"{n} opportunit{'ies' if n != 1 else 'y'} ready for review" if n else "Quiet news day"
    if n:
        parts = []
        if pr_opps:   parts.append(f"{len(pr_opps)} PR")
        if nj_opps:   parts.append(f"{len(nj_opps)} newsjacking")
        if blog_opps: parts.append(f"{len(blog_opps)} blog")
        summary += f" ({', '.join(parts)})"

    html_body = (
        f'<div style="font-family:Arial,sans-serif;background:#0A0A0A;color:#E0E0E0;padding:24px;max-width:600px">'
        f'<div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#E8192C;font-weight:700;margin-bottom:4px">Riot PR Desk</div>'
        f'<div style="font-size:20px;font-weight:900;color:#fff;margin-bottom:4px">Daily Briefing</div>'
        f'<div style="font-size:12px;color:#666;margin-bottom:4px">{today}</div>'
        f'<div style="font-size:13px;color:#aaa;margin-bottom:20px">{summary}</div>'
        f'{section_html}'
        f'<div style="margin-top:20px">'
        f'<a href="https://riot-pr-desk-5k9kicamlm6rxkugrrymxq.streamlit.app/inbox" '
        f'style="background:#E8192C;color:#fff;padding:10px 20px;text-decoration:none;'
        f'font-weight:700;font-size:13px;border-radius:3px;display:inline-block">Open Inbox →</a>'
        f'</div>'
        f'<div style="margin-top:16px;font-size:10px;color:#444">Riot PR Desk · Auto-generated daily briefing</div>'
        f'</div>'
    )

    # Plain text fallback
    lines = ["RIOT PR DESK — Daily Briefing", today, "", summary, ""]
    for label, opps in [("PR / NEWS COMMENTARY", pr_opps), ("NEWS-JACKING", nj_opps), ("BLOG", blog_opps)]:
        if opps:
            lines += [f"── {label} ──", ""]
            for opp in opps:
                is_nj = opp.get("opportunity_type") == "newsjacking"
                try:
                    pub_uk = _fmt_uk(opp.get("story_published_at", ""))
                except Exception:
                    pub_uk = ""
                source_line = opp.get('story_source','')
                if pub_uk:
                    source_line = f"{source_line} · {pub_uk}"
                entry = [
                    f"[{opp.get('relevance_score',0)}/10] {opp.get('story_title','')}",
                    f"  {source_line}",
                ]
                if is_nj and (opp.get("newsjacking_hook") or opp.get("newsjacking_concept")):
                    if opp.get("newsjacking_concept"):
                        entry.append(f"  IDEA: {opp['newsjacking_concept']}")
                    meta_parts = []
                    if opp.get("newsjacking_format"): meta_parts.append(opp["newsjacking_format"])
                    if opp.get("newsjacking_speed"):  meta_parts.append(opp["newsjacking_speed"])
                    if meta_parts:
                        entry.append(f"  ({' · '.join(meta_parts)})")
                    if opp.get("newsjacking_hook"):
                        entry.append(f"  Hook: {opp['newsjacking_hook']}")
                    if opp.get("newsjacking_execution"):
                        entry.append(f"  Execution: {opp['newsjacking_execution']}")
                    entry.append(f"  Message: {opp.get('riot_angle','')}")
                else:
                    entry.append(f"  Angle: {opp.get('riot_angle','')}")
                entry.append("")
                lines += entry
    lines += ["Open Inbox: https://riot-pr-desk-5k9kicamlm6rxkugrrymxq.streamlit.app/inbox", "", "—", "Riot PR Desk · Auto-generated"]

    msg = MIMEMultipart("alternative")
    subject_line = f"Riot PR Desk — {summary} · {today}"
    msg["Subject"] = subject_line
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText("\n".join(lines), "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
        print(f"Digest sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send digest: {e}")
        return False


# ---------------------------------------------------------------------------
# CLI entry point — called by GitHub Actions
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Riot PR Desk Autonomous Engine")
    parser.add_argument("--send-digest", action="store_true", help="Run briefing and send email digest")
    parser.add_argument("--force", action="store_true", help="Bypass 4-hour cache")
    args = parser.parse_args()

    if args.send_digest:
        to_email = os.getenv("DIGEST_EMAIL_TO", "")
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASSWORD", "")
        news_key = os.getenv("NEWSCATCHER_API_KEY", "")
        ai_key = os.getenv("ANTHROPIC_API_KEY", "")
        x_token = os.getenv("X_BEARER_TOKEN", "")

        print("=== Riot PR Desk — Daily Briefing ===")
        print(f"DIGEST_EMAIL_TO : {'SET' if to_email else 'MISSING'} ({to_email})")
        print(f"SMTP_USER       : {'SET' if smtp_user else 'MISSING'} ({smtp_user})")
        print(f"SMTP_PASSWORD   : {'SET' if smtp_pass else 'MISSING'}")
        print(f"NEWSCATCHER_KEY : {'SET' if news_key else 'MISSING'}")
        print(f"ANTHROPIC_KEY   : {'SET' if ai_key else 'MISSING'}")
        print(f"X_BEARER_TOKEN  : {'SET (X social feed active)' if x_token else 'MISSING (social feed disabled — Google News only)'}")

        if not to_email:
            print("ERROR: DIGEST_EMAIL_TO not set")
            sys.exit(1)
        if not smtp_user or not smtp_pass:
            print("ERROR: SMTP_USER or SMTP_PASSWORD not set")
            sys.exit(1)

        print("\nFetching and analysing news...")
        try:
            opps = run_daily_briefing(force=True)
            print(f"Found {len(opps)} opportunities")
        except Exception as e:
            print(f"Briefing failed: {e}")
            opps = []

        # Always send — even on a quiet news day
        print(f"\nSending digest to {to_email}...")
        success = send_digest_email(opps, to_email)
        if success:
            print("Digest sent successfully.")
            sys.exit(0)
        else:
            print("ERROR: Failed to send digest email.")
            sys.exit(1)
