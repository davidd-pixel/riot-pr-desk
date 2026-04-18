"""
PR Library service — save, load and manage generated PR packs.
Stores packs in data/pr_library.json with full CRUD, search and coverage tracking.
"""

import json
import os
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LIBRARY_FILE = os.path.join(DATA_DIR, "pr_library.json")

STATUS_OPTIONS = ["draft", "under_review", "approved", "declined", "pitched", "covered"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "w") as f:
            json.dump([], f)


_drive_synced = False


def _load():
    global _drive_synced
    _ensure_file()

    if not _drive_synced:
        _drive_synced = True
        try:
            from services.drive_persistence import download_json, is_configured
            if is_configured():
                drive_data = download_json("pr_library.json")
                if drive_data is not None:
                    with open(LIBRARY_FILE, "w") as f:
                        json.dump(drive_data, f, indent=2)
        except Exception:
            pass

    try:
        with open(LIBRARY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records):
    _ensure_file()
    with open(LIBRARY_FILE, "w") as f:
        json.dump(records, f, indent=2)
    try:
        from services.drive_persistence import upload_json
        upload_json("pr_library.json", records)
    except Exception:
        pass


def _auto_title(input_content):
    """Generate a title from the first 80 characters of input_content."""
    text = input_content.strip()
    if len(text) <= 80:
        return text
    # Try to break at a word boundary
    truncated = text[:80]
    last_space = truncated.rfind(" ")
    if last_space > 50:
        return truncated[:last_space] + "…"
    return truncated + "…"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_pack(input_content, sections, position_name, spokesperson_key,
              audience_key, tone_key, title=None, tags: list = None):
    """
    Save a new PR pack to the library.

    Returns the saved pack record (dict).
    """
    records = _load()

    pack = {
        "id": str(uuid.uuid4())[:8],
        "title": title.strip() if title and title.strip() else _auto_title(input_content),
        "created_at": datetime.now().isoformat(),
        "input_content": input_content,
        "position_name": position_name,
        "spokesperson_key": spokesperson_key,
        "audience_key": audience_key,
        "tone_key": tone_key,
        "sections": sections,
        "votes": {},
        "coverage": [],
        "status": "draft",
        "tags": [t.strip().lower() for t in tags if t.strip()] if tags else [],
        "reviewer": "",
        "comments": [],
        "versions": [],
        "suggested_journalists": [],   # populated by autonomous_engine.auto_match_journalists()
        "pitches_sent": False,         # set True once user has sent pitches
    }

    records.append(pack)
    _save(records)
    return pack


def get_all_packs():
    """Return all packs, newest first."""
    packs = _load()
    return sorted(packs, key=lambda p: p.get("created_at", ""), reverse=True)


def get_pack(pack_id):
    """Return a single pack by id, or None if not found."""
    for pack in _load():
        if pack.get("id") == pack_id:
            return pack
    return None


def delete_pack(pack_id):
    """Delete a pack by id."""
    records = _load()
    records = [p for p in records if p.get("id") != pack_id]
    _save(records)


def duplicate_pack(pack_id):
    """
    Create a copy of an existing pack with a new id, new timestamp,
    and a 'Copy of …' title prefix.

    Returns the new pack record.
    """
    original = get_pack(pack_id)
    if original is None:
        raise ValueError(f"Pack '{pack_id}' not found.")

    records = _load()

    new_pack = dict(original)
    new_pack["id"] = str(uuid.uuid4())[:8]
    new_pack["title"] = f"Copy of {original['title']}"
    new_pack["created_at"] = datetime.now().isoformat()
    new_pack["status"] = "draft"
    new_pack["votes"] = {}
    new_pack["coverage"] = list(original.get("coverage", []))
    new_pack["tags"] = list(original.get("tags", []))
    new_pack["reviewer"] = ""
    new_pack["comments"] = []
    new_pack["versions"] = []

    records.append(new_pack)
    _save(records)
    return new_pack


def search_packs(query):
    """
    Search packs by title, input_content and all sections text.
    Returns matching packs, newest first.
    """
    query = query.lower().strip()
    if not query:
        return get_all_packs()

    results = []
    for pack in _load():
        sections_text = " ".join(pack.get("sections", {}).values())
        tags_text = " ".join(pack.get("tags", []))
        searchable = " ".join([
            pack.get("title", ""),
            pack.get("input_content", ""),
            pack.get("position_name", ""),
            pack.get("spokesperson_key", ""),
            pack.get("audience_key", ""),
            pack.get("tone_key", ""),
            sections_text,
            tags_text,
        ]).lower()
        if query in searchable:
            results.append(pack)

    return sorted(results, key=lambda p: p.get("created_at", ""), reverse=True)


def update_pack_title(pack_id, new_title):
    """
    Rename a pack.  Returns the updated pack record.
    """
    records = _load()
    for i, pack in enumerate(records):
        if pack.get("id") == pack_id:
            records[i]["title"] = new_title.strip()
            _save(records)
            return records[i]
    raise ValueError(f"Pack '{pack_id}' not found.")


def update_pack_status(pack_id, new_status):
    """
    Update the status of a pack.  Returns the updated pack record.
    """
    if new_status not in STATUS_OPTIONS:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {STATUS_OPTIONS}.")
    records = _load()
    for i, pack in enumerate(records):
        if pack.get("id") == pack_id:
            records[i]["status"] = new_status
            _save(records)
            return records[i]
    raise ValueError(f"Pack '{pack_id}' not found.")


def update_suggested_journalists(pack_id: str, journalists: list) -> dict:
    """Store AI-matched journalists on a pack. Returns updated pack."""
    records = _load()
    for i, pack in enumerate(records):
        if pack.get("id") == pack_id:
            records[i]["suggested_journalists"] = journalists
            _save(records)
            return records[i]
    raise ValueError(f"Pack '{pack_id}' not found.")


def mark_pitches_sent(pack_id: str) -> dict:
    """Mark that pitches have been sent for this pack."""
    records = _load()
    for i, pack in enumerate(records):
        if pack.get("id") == pack_id:
            records[i]["pitches_sent"] = True
            records[i]["status"] = "pitched"
            _save(records)
            return records[i]
    raise ValueError(f"Pack '{pack_id}' not found.")


def add_coverage(pack_id, publication, journalist, reach_estimate, sentiment, notes):
    """
    Append a coverage record to a pack.

    Returns the updated pack record.
    """
    records = _load()
    for i, pack in enumerate(records):
        if pack.get("id") == pack_id:
            coverage_record = {
                "publication": publication.strip(),
                "journalist": journalist.strip(),
                "reach": reach_estimate,
                "sentiment": sentiment,
                "notes": notes.strip(),
                "logged_at": datetime.now().isoformat(),
            }
            records[i].setdefault("coverage", []).append(coverage_record)
            # Auto-promote status to "covered" if it isn't already
            if records[i].get("status") not in ("covered",):
                records[i]["status"] = "covered"
            _save(records)
            return records[i]
    raise ValueError(f"Pack '{pack_id}' not found.")


def get_recent_packs(n=5):
    """Return the n most recently created packs."""
    return get_all_packs()[:n]


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

def add_version(pack_id: str, sections: dict, note: str = "") -> dict:
    """Save current sections as a version snapshot before overwriting."""
    records = _load()
    for i, p in enumerate(records):
        if p["id"] == pack_id:
            if "versions" not in records[i]:
                records[i]["versions"] = []
            snapshot = {
                "version_id": uuid.uuid4().hex[:8],
                "saved_at": datetime.now().isoformat(),
                "note": note,
                "sections": sections,
            }
            records[i]["versions"].insert(0, snapshot)
            records[i]["versions"] = records[i]["versions"][:10]  # keep last 10
            _save(records)
            return records[i]
    raise KeyError(f"Pack {pack_id} not found")


def get_versions(pack_id: str) -> list:
    """Return version history for a pack, newest first."""
    pack = get_pack(pack_id)
    if not pack:
        return []
    return pack.get("versions", [])


def restore_version(pack_id: str, version_id: str) -> dict:
    """Restore a pack's sections from a version snapshot."""
    records = _load()
    for i, p in enumerate(records):
        if p["id"] == pack_id:
            versions = p.get("versions", [])
            version = next((v for v in versions if v["version_id"] == version_id), None)
            if not version:
                raise KeyError(f"Version {version_id} not found")
            # Save current as a version before restoring
            snapshot = {
                "version_id": uuid.uuid4().hex[:8],
                "saved_at": datetime.now().isoformat(),
                "note": "Auto-saved before restore",
                "sections": p.get("sections", {}),
            }
            records[i]["versions"].insert(0, snapshot)
            records[i]["sections"] = version["sections"]
            _save(records)
            return records[i]
    raise KeyError(f"Pack {pack_id} not found")


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def add_comment(pack_id: str, author: str, text: str, comment_type: str = "note") -> dict:
    """Add a comment to a pack. comment_type: 'note' | 'approval' | 'change_request'"""
    records = _load()
    for i, p in enumerate(records):
        if p["id"] == pack_id:
            if "comments" not in records[i]:
                records[i]["comments"] = []
            comment = {
                "comment_id": uuid.uuid4().hex[:8],
                "author": author,
                "text": text,
                "type": comment_type,
                "created_at": datetime.now().isoformat(),
            }
            records[i]["comments"].insert(0, comment)
            _save(records)
            return records[i]
    raise KeyError(f"Pack {pack_id} not found")


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def update_pack_tags(pack_id: str, tags: list) -> dict:
    """Update the tags on a pack."""
    records = _load()
    for i, p in enumerate(records):
        if p["id"] == pack_id:
            records[i]["tags"] = [t.strip().lower() for t in tags if t.strip()]
            _save(records)
            return records[i]
    raise KeyError(f"Pack {pack_id} not found")


def get_all_tags() -> list:
    """Return all unique tags across all packs, sorted alphabetically."""
    packs = _load()
    tags = set()
    for p in packs:
        for t in p.get("tags", []):
            tags.add(t)
    return sorted(tags)


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def get_stats():
    """
    Return aggregate stats for the library metrics row.

    Returns dict with: total, this_month, total_coverage, avg_vote_score, total_tags.
    """
    packs = _load()
    total = len(packs)

    now = datetime.now()
    this_month = sum(
        1 for p in packs
        if p.get("created_at", "")[:7] == f"{now.year}-{now.month:02d}"
    )

    total_coverage = sum(len(p.get("coverage", [])) for p in packs)

    # avg vote score: votes dict maps section_name → "up"/"down"
    all_votes = []
    for p in packs:
        for v in p.get("votes", {}).values():
            all_votes.append(1 if v == "up" else 0)

    avg_vote = round(sum(all_votes) / len(all_votes) * 100) if all_votes else None

    # count unique tags
    all_tag_set = set()
    for p in packs:
        for t in p.get("tags", []):
            all_tag_set.add(t)
    total_tags = len(all_tag_set)

    return {
        "total": total,
        "this_month": this_month,
        "total_coverage": total_coverage,
        "avg_vote_pct": avg_vote,
        "total_tags": total_tags,
    }
