"""
Content generation service — orchestrates prompt building and AI calls
to produce PR packs and triage assessments.
"""

from services.ai_engine import generate, generate_json
from utils.prompts import PR_PACK_PROMPT, TRIAGE_PROMPT, ANGLE_SUGGESTION_PROMPT, NEWSJACK_PROMPT
from config.positions import POSITIONS, get_position
from config.spokespeople import get_spokesperson
from config.settings import TONES, AUDIENCES


def triage_news(news_content):
    """Assess a news story and return a triage recommendation."""
    positions_context = "\n".join(
        f"- {name}: {p['stance']}" for name, p in POSITIONS.items()
    )
    prompt = TRIAGE_PROMPT.format(
        news_content=news_content,
        positions_context=positions_context,
    )
    return generate_json(prompt)


def _build_pr_pack_prompt(input_content, position_name, spokesperson_key, audience_key, tone_key, tone_dial=None, length_dial=None):
    """Build the PR pack prompt string (separated so streaming can use it directly)."""
    position = get_position(position_name)
    spokesperson = get_spokesperson(spokesperson_key)
    tone_desc = TONES.get(tone_key, tone_key)
    audience_desc = AUDIENCES.get(audience_key, audience_key)

    position_context = (
        f"Position: {position_name}\n"
        f"Headline: {position['headline']}\n"
        f"Stance: {position['stance']}\n"
        f"Key messages:\n" + "\n".join(f"  - {m}" for m in position["key_messages"])
    )

    tone_str = f"{tone_key}: {tone_desc}"
    if tone_dial:
        tone_str += f" | Tone dial: {tone_dial}"
    if length_dial:
        tone_str += f" | Length: {length_dial}"

    return PR_PACK_PROMPT.format(
        input_content=input_content,
        position_context=position_context,
        spokesperson_name=spokesperson["name"],
        spokesperson_title=spokesperson["title"],
        spokesperson_bio=spokesperson["bio"],
        spokesperson_tone=spokesperson["tone"],
        audience=f"{audience_key}: {audience_desc}",
        tone=tone_str,
    )


def generate_pr_pack(input_content, position_name, spokesperson_key, audience_key, tone_key, tone_dial=None, length_dial=None):
    """Generate a complete PR response pack."""
    prompt = _build_pr_pack_prompt(input_content, position_name, spokesperson_key, audience_key, tone_key, tone_dial, length_dial)
    raw_response = generate(prompt)
    return _parse_pr_pack(raw_response)


def suggest_angles(input_content):
    """Suggest PR angles for a given input."""
    positions_context = "\n".join(
        f"- {name}: {p['headline']}" for name, p in POSITIONS.items()
    )
    prompt = ANGLE_SUGGESTION_PROMPT.format(
        input_content=input_content,
        positions_context=positions_context,
    )
    return generate(prompt)


def suggest_newsjack(story_content):
    """Suggest creative news-jacking ideas for a trending story."""
    prompt = NEWSJACK_PROMPT.format(story_content=story_content)
    return generate(prompt)


def _parse_pr_pack(raw_response):
    """Parse the AI response into labelled sections."""
    sections = {}
    current_section = None
    current_content = []

    section_markers = {
        "1. PRESS RELEASE": "Press Release",
        "2. JOURNALIST PITCH": "Journalist Pitch Email",
        "3. LINKEDIN POST": "LinkedIn Post",
        "4. RETAILER WHATSAPP": "Retailer WhatsApp Comms",
        "5. CONSUMER SOCIAL": "Consumer Social Media Comms",
        "6. INTERNAL BRIEFING": "Internal Briefing",
        "7. CREATIVE BRIEF": "Creative Brief",
    }

    for line in raw_response.split("\n"):
        matched = False
        for marker, label in section_markers.items():
            if marker.lower() in line.lower().replace("#", "").strip().replace("*", ""):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = label
                current_content = []
                matched = True
                break
        if not matched and current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # If parsing failed, return the raw response
    if not sections:
        sections["Full Response"] = raw_response

    return sections
