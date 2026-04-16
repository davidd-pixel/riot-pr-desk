"""
Media lists service — manage named groups of journalists for campaigns and pitching.
Stores data in data/media_lists.json.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import services.journalist_db as journalist_db

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LISTS_FILE = os.path.join(DATA_DIR, "media_lists.json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(LISTS_FILE):
        with open(LISTS_FILE, "w") as f:
            json.dump([], f)


def _load():
    _ensure_file()
    try:
        with open(LISTS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records):
    _ensure_file()
    with open(LISTS_FILE, "w") as f:
        json.dump(records, f, indent=2)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id():
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_list(name, description="", tags=None):
    """Create a new media list. Returns the new list record."""
    if tags is None:
        tags = []
    records = _load()
    now = _now_iso()
    record = {
        "id": _new_id(),
        "name": name.strip(),
        "description": description.strip(),
        "created_at": now,
        "updated_at": now,
        "journalist_ids": [],
        "tags": [t.strip() for t in tags if t.strip()],
        "last_used": None,
    }
    records.append(record)
    _save(records)
    return record


def get_all_lists():
    """Return all media lists."""
    return _load()


def get_list(list_id):
    """Return a single list by ID, or None if not found."""
    for lst in _load():
        if lst.get("id") == list_id:
            return lst
    return None


def update_list(list_id, data):
    """Update name, description, and/or tags on a list. Returns updated record."""
    records = _load()
    for i, lst in enumerate(records):
        if lst.get("id") == list_id:
            if "name" in data:
                records[i]["name"] = data["name"].strip()
            if "description" in data:
                records[i]["description"] = data["description"].strip()
            if "tags" in data:
                records[i]["tags"] = [t.strip() for t in data["tags"] if t.strip()]
            records[i]["updated_at"] = _now_iso()
            _save(records)
            return records[i]
    return None


def delete_list(list_id):
    """Delete a media list by ID."""
    records = _load()
    records = [lst for lst in records if lst.get("id") != list_id]
    _save(records)


def add_journalist_to_list(list_id, journalist_id):
    """Add a journalist to a list. No-op if already present. Returns updated list."""
    records = _load()
    for i, lst in enumerate(records):
        if lst.get("id") == list_id:
            if journalist_id not in records[i]["journalist_ids"]:
                records[i]["journalist_ids"].append(journalist_id)
                records[i]["updated_at"] = _now_iso()
                _save(records)
            return records[i]
    return None


def remove_journalist_from_list(list_id, journalist_id):
    """Remove a journalist from a list. Returns updated list."""
    records = _load()
    for i, lst in enumerate(records):
        if lst.get("id") == list_id:
            records[i]["journalist_ids"] = [
                jid for jid in records[i]["journalist_ids"] if jid != journalist_id
            ]
            records[i]["updated_at"] = _now_iso()
            _save(records)
            return records[i]
    return None


def get_journalists_in_list(list_id):
    """Return full journalist records for all journalists in a list."""
    lst = get_list(list_id)
    if not lst:
        return []
    results = []
    for jid in lst.get("journalist_ids", []):
        j = journalist_db.get_by_id(jid)
        if j:
            results.append(j)
    return results


def get_lists_for_journalist(journalist_id):
    """Return all lists that contain a given journalist ID."""
    return [lst for lst in _load() if journalist_id in lst.get("journalist_ids", [])]


def copy_list(list_id, new_name):
    """Duplicate a list under a new name with a fresh ID. Returns the new list."""
    original = get_list(list_id)
    if not original:
        return None
    records = _load()
    now = _now_iso()
    new_record = {
        "id": _new_id(),
        "name": new_name.strip(),
        "description": original.get("description", ""),
        "created_at": now,
        "updated_at": now,
        "journalist_ids": list(original.get("journalist_ids", [])),
        "tags": list(original.get("tags", [])),
        "last_used": None,
    }
    records.append(new_record)
    _save(records)
    return new_record


def mark_list_used(list_id):
    """Update last_used timestamp. Returns updated list."""
    records = _load()
    for i, lst in enumerate(records):
        if lst.get("id") == list_id:
            records[i]["last_used"] = _now_iso()
            _save(records)
            return records[i]
    return None
