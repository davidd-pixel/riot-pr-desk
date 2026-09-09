"""
Opportunity Tracker — stores and manages PR opportunities surfaced by the
autonomous engine. Each opportunity is a news story that the AI has ranked
as relevant to Riot, with a suggested angle and position.
"""

import json
import os
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OPP_FILE = os.path.join(DATA_DIR, "opportunities.json")

STATUS_OPTIONS = ["pending", "approved", "rejected", "generating", "generated", "skipped"]

# Only the scheduled job writes opportunity records. User decisions are
# immutable events, so replacing a stale opportunity snapshot cannot undo them.
_DRIVE_RESYNC_SECONDS = 60
_last_drive_sync_at = 0.0
_lock = threading.RLock()


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _actions_dir():
    return Path(DATA_DIR) / "opportunity_actions"


def _load() -> list:
    import time
    from services import drive_persistence as drive
    global _last_drive_sync_at
    with _lock:
        directory = _actions_dir()
        directory.mkdir(parents=True, exist_ok=True)
        if drive.is_configured() and time.time() - _last_drive_sync_at > _DRIVE_RESYNC_SECONDS:
            records = drive.download_json("opportunities.json", strict=True)
            if records is not None:
                if not isinstance(records, list):
                    raise RuntimeError("Invalid opportunities in Google Drive")
                _atomic_json(OPP_FILE, records)
            events = drive.download_action_events({p.name for p in directory.glob("*.json")})
            for name, event in events.items():
                if Path(name).name != name or not isinstance(event, dict):
                    raise RuntimeError("Invalid opportunity action in Google Drive")
                _atomic_json(directory / name, event)
            _last_drive_sync_at = time.time()
        path = Path(OPP_FILE)
        records = json.loads(path.read_text()) if path.exists() else []
        by_id = {o["id"]: o for o in records}
        events = [json.loads(p.read_text()) for p in directory.glob("*.json")]
        for event in sorted(events, key=lambda e: (e["created_at"], e["id"])):
            if event["opportunity_id"] in by_id:
                by_id[event["opportunity_id"]].update(event["changes"])
        return list(by_id.values())


def force_resync_from_drive() -> None:
    global _last_drive_sync_at
    _last_drive_sync_at = 0.0
    _load()  # Report errors now, before the UI announces success.


def _save(records: list) -> None:
    from services import drive_persistence as drive
    with _lock:
        if drive.is_configured():
            drive.upload_json("opportunities.json", records, strict=True)
        _atomic_json(OPP_FILE, records)


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
    story_published_at: str = "",     # ISO timestamp of the original article (from news feed)
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
        "story_published_at": story_published_at,
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
    if status not in STATUS_OPTIONS:
        raise ValueError("Unknown opportunity status")
    from services import drive_persistence as drive
    with _lock:
        if not get_opportunity(opp_id):
            return False
        changes = {"status": status}
        if pack_id is not None:
            changes["pack_id"] = pack_id
        if custom_angle is not None:
            changes["custom_angle"] = custom_angle
        event = {"id": uuid.uuid4().hex, "opportunity_id": opp_id,
                 "created_at": datetime.now(timezone.utc).isoformat(), "changes": changes}
        name = f"opportunity_action_{event['id']}.json"
        if drive.is_configured():
            drive.upload_json(name, event, strict=True)
        _atomic_json(_actions_dir() / name, event)
        return True



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
