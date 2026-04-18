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
    Ask the AI to score a news story for Riot relevance and suggest an angle.
    Returns: {relevance_score, riot_angle, suggested_position, why_it_matters}
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

AVAILABLE POSITIONS:
{positions_list}

TASK:
1. Score this story's relevance to Riot on a scale of 1-10 (10 = Riot must respond today)
2. Suggest Riot's specific PR angle for this story (1-2 sentences, concrete and punchy)
3. Choose the single best position from the list above
4. Write one line explaining why it matters for Riot right now

Return ONLY valid JSON in this exact format:
{{
  "relevance_score": <integer 1-10>,
  "riot_angle": "<1-2 sentence PR angle>",
  "suggested_position": "<exact position name from list>",
  "why_it_matters": "<one line>"
}}"""

    try:
        result = generate_json(prompt)
        if isinstance(result, dict) and "relevance_score" in result:
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
    )

    # Return cached pending opportunities if cache is fresh
    if not force and _cache_is_fresh():
        return get_pending_opportunities()

    # Fetch news
    try:
        from services.news_monitor import fetch_trending_news
        articles = fetch_trending_news(page_size=15)
        articles = [a for a in articles if "error" not in a]
    except Exception:
        articles = []

    if not articles:
        _save_cache({"generated_at": datetime.now(timezone.utc).isoformat(), "count": 0})
        return get_pending_opportunities()

    # Dedup: don't re-analyse stories we've already seen
    existing = get_all_opportunities()
    seen_titles = {o.get("story_title", "").lower() for o in existing}

    new_count = 0
    analysed = []
    for article in articles[:12]:  # cap to keep costs low
        title = article.get("title", "")
        if not title or title.lower() in seen_titles:
            continue

        analysis = analyse_story_for_riot(article)
        if "error" in analysis:
            continue

        score = analysis.get("relevance_score", 0)
        if score < 5:  # only surface genuinely relevant stories
            continue

        source = article.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else str(source)

        save_opportunity(
            story_title=title,
            story_url=article.get("url", ""),
            story_source=source_name,
            riot_angle=analysis.get("riot_angle", ""),
            relevance_score=score,
            suggested_position=analysis.get("suggested_position", ""),
            why_it_matters=analysis.get("why_it_matters", ""),
        )
        analysed.append(analysis)
        new_count += 1

        if new_count >= 5:  # surface at most 5 new opportunities per run
            break

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

def auto_generate_pack(opportunity_id: str, custom_angle: str = None) -> str:
    """
    Generate a full PR pack from an approved opportunity.
    Returns the new pack_id.
    """
    from services.opportunity_tracker import get_opportunity, update_opportunity_status
    from services.content_generator import generate_pr_pack
    from services.pr_library import save_pack, update_pack_status

    opp = get_opportunity(opportunity_id)
    if not opp:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    update_opportunity_status(opportunity_id, "generating")

    angle = custom_angle or opp.get("riot_angle", "")
    position = opp.get("suggested_position", "Harm Reduction")

    input_content = (
        f"{opp['story_title']}\n\n"
        f"Riot angle: {angle}\n\n"
        f"Source: {opp.get('story_source', '')}\n"
        f"Original story: {opp.get('story_url', '')}"
    )

    # Default to sensible settings for autonomous generation
    sections = generate_pr_pack(
        input_content=input_content,
        position_name=position,
        spokesperson_key="CEO",
        audience_key="Trade Media",
        tone_key="Conversational",
    )

    pack = save_pack(
        input_content=input_content,
        sections=sections,
        position_name=position,
        spokesperson_key="CEO",
        audience_key="Trade Media",
        tone_key="Conversational",
        title=opp["story_title"][:80],
        tags=["auto-generated"],
    )

    # Move status to under_review (awaiting David's approval)
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

    # Build plain text body
    lines = [
        f"RIOT PR DESK — Daily Briefing",
        f"{today}",
        "",
        f"{n} opportunit{'ies' if n != 1 else 'y'} ready for your review." if n else "Quiet news day — nothing relevant surfaced today.",
        "",
        "=" * 60,
        "",
    ]
    for i, opp in enumerate(opportunities[:5], 1):
        lines += [
            f"{i}. [{opp.get('relevance_score', 0)}/10] {opp.get('story_title', '')}",
            f"   Source: {opp.get('story_source', '')}",
            f"   Riot angle: {opp.get('riot_angle', '')}",
            f"   Why it matters: {opp.get('why_it_matters', '')}",
            "",
        ]
    lines += [
        "Open the app to approve opportunities:",
        "https://riot-pr-desk.streamlit.app",
        "",
        "—",
        "Riot PR Desk · Auto-generated · Do not reply",
    ]

    # Build HTML body
    opp_html = ""
    for opp in opportunities[:5]:
        score = opp.get("relevance_score", 0)
        colour = "#E8192C" if score >= 8 else "#fbbf24" if score >= 6 else "#60a5fa"
        opp_html += f"""
        <div style="border-left:3px solid {colour};padding:10px 16px;margin-bottom:12px;background:#111;border-radius:0 4px 4px 0">
          <div style="font-size:13px;font-weight:700;color:#fff">{opp.get('story_title','')}</div>
          <div style="font-size:11px;color:#888;margin-top:2px">{opp.get('story_source','')} &middot; Relevance {score}/10</div>
          <div style="font-size:12px;color:#E0E0E0;margin-top:6px">{opp.get('riot_angle','')}</div>
          <div style="font-size:11px;color:#999;margin-top:4px;font-style:italic">{opp.get('why_it_matters','')}</div>
        </div>"""

    html_body = f"""
    <div style="font-family:Arial,sans-serif;background:#0A0A0A;color:#E0E0E0;padding:24px;max-width:600px">
      <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#E8192C;font-weight:700;margin-bottom:4px">Riot PR Desk</div>
      <div style="font-size:20px;font-weight:900;color:#fff;margin-bottom:4px">Daily Briefing</div>
      <div style="font-size:12px;color:#666;margin-bottom:20px">{today}</div>
      <div style="font-size:13px;color:#aaa;margin-bottom:16px">{len(opportunities)} opportunit{'ies' if len(opportunities) != 1 else 'y'} ready for review:</div>
      {opp_html}
      <div style="margin-top:20px">
        <a href="https://riot-pr-desk.streamlit.app" style="background:#E8192C;color:#fff;padding:10px 20px;text-decoration:none;font-weight:700;font-size:13px;border-radius:3px;display:inline-block">
          Open Inbox →
        </a>
      </div>
      <div style="margin-top:20px;font-size:10px;color:#444">Riot PR Desk · Auto-generated daily briefing</div>
    </div>"""

    msg = MIMEMultipart("alternative")
    subject_line = f"Riot PR Desk — {n} opportunit{'ies' if n != 1 else 'y'} · {today}" if n else f"Riot PR Desk — Quiet news day · {today}"
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

        print("=== Riot PR Desk — Daily Briefing ===")
        print(f"DIGEST_EMAIL_TO : {'SET' if to_email else 'MISSING'} ({to_email})")
        print(f"SMTP_USER       : {'SET' if smtp_user else 'MISSING'} ({smtp_user})")
        print(f"SMTP_PASSWORD   : {'SET' if smtp_pass else 'MISSING'}")
        print(f"NEWSCATCHER_KEY : {'SET' if news_key else 'MISSING'}")
        print(f"ANTHROPIC_KEY   : {'SET' if ai_key else 'MISSING'}")

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
