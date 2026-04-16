"""
Feedback service — persistent voting and learning system.
Stores votes in a JSON file and generates summaries for prompt injection.
"""

import json
import os
from datetime import datetime
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")


def _ensure_file():
    """Create data dir and feedback file if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "w") as f:
            json.dump([], f)


def _load():
    """Load all feedback entries."""
    _ensure_file()
    try:
        with open(FEEDBACK_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(entries):
    """Save feedback entries."""
    _ensure_file()
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def record_vote(content_summary, vote, context, note=""):
    """
    Record a vote.

    Args:
        content_summary: Brief description of what was voted on (article title, idea summary, etc.)
        vote: "up" or "down"
        context: Category — "news_story", "newsjack_idea", "pr_pack_section"
        note: Optional free-text reason
    """
    entries = _load()
    entries.append({
        "timestamp": datetime.now().isoformat(),
        "content": content_summary[:300],  # Cap length
        "vote": vote,
        "context": context,
        "note": note,
    })
    _save(entries)


def get_all_feedback():
    """Get all feedback entries."""
    return _load()


def get_feedback_by_context(context):
    """Get feedback filtered by context type."""
    return [e for e in _load() if e.get("context") == context]


def get_stats():
    """Get aggregate stats."""
    entries = _load()
    if not entries:
        return {"total": 0, "up": 0, "down": 0, "by_context": {}}

    up = sum(1 for e in entries if e["vote"] == "up")
    down = sum(1 for e in entries if e["vote"] == "down")

    by_context = {}
    for e in entries:
        ctx = e.get("context", "unknown")
        if ctx not in by_context:
            by_context[ctx] = {"up": 0, "down": 0}
        by_context[ctx][e["vote"]] += 1

    return {"total": len(entries), "up": up, "down": down, "by_context": by_context}


def get_feedback_summary(max_entries=30):
    """
    Generate a condensed summary of recent feedback for injection into AI prompts.
    Returns a string summary of what Riot has liked and disliked.
    """
    entries = _load()
    if not entries:
        return ""

    # Take the most recent entries
    recent = entries[-max_entries:]

    liked = [e for e in recent if e["vote"] == "up"]
    disliked = [e for e in recent if e["vote"] == "down"]

    lines = []
    lines.append("## Recent Feedback from Riot's Team")
    lines.append(f"Based on {len(recent)} recent votes ({len(liked)} liked, {len(disliked)} disliked):")

    if liked:
        lines.append("")
        lines.append("### What Riot LIKED (do more of this):")
        for e in liked[-10:]:
            note_part = f" — Reason: {e['note']}" if e.get("note") else ""
            lines.append(f"- [{e['context']}] {e['content']}{note_part}")

    if disliked:
        lines.append("")
        lines.append("### What Riot DISLIKED (avoid this):")
        for e in disliked[-10:]:
            note_part = f" — Reason: {e['note']}" if e.get("note") else ""
            lines.append(f"- [{e['context']}] {e['content']}{note_part}")

    if liked:
        # Extract common themes from liked content
        liked_words = " ".join(e["content"].lower() for e in liked)
        lines.append("")
        lines.append("Use this feedback to calibrate your outputs — lean into what was liked, avoid what was disliked.")

    return "\n".join(lines)


def clear_all():
    """Clear all feedback."""
    _save([])
