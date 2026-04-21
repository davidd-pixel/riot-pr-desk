"""
Opportunity Tracker — stores and manages PR opportunities surfaced by the
autonomous engine. Each opportunity is a news story that the AI has ranked
as relevant to Riot, with a suggested angle and position.
"""

import json
import os
import uuid
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OPP_FILE = os.path.join(DATA_DIR, "opportunities.json")

STATUS_OPTIONS = ["pending", "approved", "rejected", "generating", "generated", "skipped"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(OPP_FILE):
        with open(OPP_FILE, "w") as f:
            json.dump([], f)


def _load() -> list:
    _ensure_file()
    try:
        with open(OPP_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records: list) -> None:
    _ensure_file()
    with open(OPP_FILE, "w") as f:
        json.dump(records, f, indent=2)
    # Sync to Google Drive if configured
    try:
        from services.drive_persistence import upload_json
        upload_json("opportunities.json", records)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_opportunity(
    story_title: str,
    story_url: str,
    story_source: str,
    riot_angle: str,
    relevance_score: int,
    suggested_position: str,
    why_it_matters: str = "",
    opportunity_type: str = "pr_commentary",  # pr_commentary | newsjacking | blog
    # Newsjacking creative brief fields (only populated when opportunity_type == "newsjacking")
    newsjacking_concept: str = "",    # one-line title for the idea
    newsjacking_hook: str = "",       # 1-2 sentence creative connection
    newsjacking_execution: str = "",  # 2-3 sentence specific execution
    newsjacking_format: str = "",     # format (press quote, stunt, data piece etc)
    newsjacking_speed: str = "",      # urgency tier
) -> dict:
    """Save a new opportunity. Returns the saved record."""
    records = _load()
    now = datetime.now(timezone.utc)
    opp = {
        "id": str(uuid.uuid4())[:8],
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=48)).isoformat(),
        "story_title": story_title,
        "story_url": story_url,
        "story_source": story_source,
        "riot_angle": riot_angle,
        "relevance_score": relevance_score,
        "suggested_position": suggested_position,
        "why_it_matters": why_it_matters,
        "opportunity_type": opportunity_type,
        "newsjacking_concept": newsjacking_concept,
        "newsjacking_hook": newsjacking_hook,
        "newsjacking_execution": newsjacking_execution,
        "newsjacking_format": newsjacking_format,
        "newsjacking_speed": newsjacking_speed,
        "status": "pending",
        "pack_id": None,
        "custom_angle": None,  # set when user edits the angle before approving
    }
    records.append(opp)
    _save(records)
    return opp


def get_all_opportunities() -> list:
    """Return all opportunities, newest first."""
    return sorted(_load(), key=lambda o: o.get("created_at", ""), reverse=True)


def get_pending_opportunities() -> list:
    """Return pending (not yet actioned) opportunities, highest relevance first."""
    expire_old_opportunities()
    all_opps = _load()
    pending = [o for o in all_opps if o.get("status") == "pending"]
    return sorted(pending, key=lambda o: o.get("relevance_score", 0), reverse=True)


def get_opportunity(opp_id: str) -> dict | None:
    for o in _load():
        if o.get("id") == opp_id:
            return o
    return None


def update_opportunity_status(opp_id: str, status: str, pack_id: str = None, custom_angle: str = None) -> bool:
    """Update the status (and optionally pack_id / custom_angle) of an opportunity."""
    records = _load()
    for o in records:
        if o.get("id") == opp_id:
            o["status"] = status
            if pack_id is not None:
                o["pack_id"] = pack_id
            if custom_angle is not None:
                o["custom_angle"] = custom_angle
            _save(records)
            return True
    return False


def expire_old_opportunities() -> int:
    """Mark expired pending opportunities as skipped. Returns count expired."""
    records = _load()
    now = datetime.now(timezone.utc)
    expired = 0
    for o in records:
        if o.get("status") == "pending":
            expires = o.get("expires_at", "")
            try:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now > exp_dt:
                    o["status"] = "skipped"
                    expired += 1
            except Exception:
                pass
    if expired:
        _save(records)
    return expired


def trim_pending_to_top_n_per_type(n: int = 5) -> int:
    """
    Clean up pending opportunities so the inbox + email only show a focused
    top-N per type. Does three things in order:

    1. Marks pending opps from low-credibility sources as 'skipped'
       (retroactively applies services.source_credibility — catches opps
       that were created before the credibility filter existed).
    2. Marks pending newsjacking opps with no newsjacking_hook as 'skipped'
       (they were created before the richer prompt — we'd rather regenerate).
    3. For each remaining pending opportunity_type, keeps the top N by
       relevance_score and marks the rest as 'skipped'.

    Returns the total count trimmed.
    """
    try:
        from services.source_credibility import is_credible
    except ImportError:
        def is_credible(_):  # type: ignore
            return True

    records = _load()
    trimmed = 0

    # Pass 1 — drop low-credibility sources retroactively
    for o in records:
        if o.get("status") != "pending":
            continue
        if not is_credible(o.get("story_source", "")):
            o["status"] = "skipped"
            trimmed += 1

    # Pass 2 — drop pre-prompt-upgrade newsjacking opps missing the richer hook
    for o in records:
        if o.get("status") != "pending":
            continue
        if o.get("opportunity_type") == "newsjacking" and not o.get("newsjacking_hook"):
            o["status"] = "skipped"
            trimmed += 1

    # Pass 3 — cap each type at top-N by relevance score
    pending_by_type: dict = {}
    for o in records:
        if o.get("status") != "pending":
            continue
        t = o.get("opportunity_type", "pr_commentary")
        pending_by_type.setdefault(t, []).append(o)

    for opp_type, opps in pending_by_type.items():
        opps.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        for overflow in opps[n:]:
            overflow["status"] = "skipped"
            trimmed += 1

    if trimmed:
        _save(records)
    return trimmed


def get_inbox_count() -> int:
    """Return total number of items across all inbox sections requiring attention."""
    from services.pr_library import get_all_packs
    pending_opps = len(get_pending_opportunities())
    packs = get_all_packs()
    under_review = sum(1 for p in packs if p.get("status") == "under_review")
    needs_media = sum(
        1 for p in packs
        if p.get("status") == "approved" and p.get("suggested_journalists")
        and not p.get("pitches_sent")
    )
    return pending_opps + under_review + needs_media
