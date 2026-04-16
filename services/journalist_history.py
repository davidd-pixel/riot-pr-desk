"""
Journalist contact history service — lightweight CRM interaction log.
Tracks every pitch, call, meeting, email and coverage outcome per journalist.
Stores data in a JSON file alongside the journalist database.
"""

import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "journalist_history.json")

CONTACT_TYPES = ["pitch", "call", "meeting", "email", "coverage"]
OUTCOME_OPTIONS = ["", "responded", "no_response", "coverage_landed", "declined"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump([], f)


def _load() -> list:
    _ensure_file()
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records: list) -> None:
    _ensure_file()
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_contact(
    journalist_id: str,
    contact_type: str,
    subject: str,
    notes: str = "",
    outcome: str = "",
    pack_id: Optional[str] = None,
) -> dict:
    """
    Log a new interaction with a journalist.

    Args:
        journalist_id:  ID from the journalist database.
        contact_type:   One of: pitch | call | meeting | email | coverage
        subject:        Brief description / subject line.
        notes:          Optional free-text notes.
        outcome:        One of: responded | no_response | coverage_landed | declined | ""
        pack_id:        Optional ID linking to a PR pack in the library.

    Returns:
        The newly created contact record dict.
    """
    if contact_type not in CONTACT_TYPES:
        raise ValueError(
            f"Invalid contact_type '{contact_type}'. Must be one of: {CONTACT_TYPES}"
        )
    if outcome not in OUTCOME_OPTIONS:
        raise ValueError(
            f"Invalid outcome '{outcome}'. Must be one of: {OUTCOME_OPTIONS}"
        )

    records = _load()
    record = {
        "id": str(uuid.uuid4())[:8],
        "journalist_id": journalist_id,
        "contact_type": contact_type,
        "subject": subject.strip(),
        "notes": notes.strip(),
        "outcome": outcome,
        "pack_id": pack_id,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    _save(records)
    return record


def get_history(journalist_id: str) -> list:
    """
    Return all interactions for a journalist, newest first.

    Args:
        journalist_id: ID from the journalist database.

    Returns:
        List of contact record dicts sorted by logged_at descending.
    """
    records = [r for r in _load() if r.get("journalist_id") == journalist_id]
    return sorted(records, key=lambda r: r.get("logged_at", ""), reverse=True)


def get_recent_contacts(days: int = 30) -> list:
    """
    Return all interactions logged in the last N days, across all journalists.
    Results are sorted newest first.

    Args:
        days: Number of days to look back.

    Returns:
        List of contact record dicts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    for r in _load():
        logged_str = r.get("logged_at", "")
        if not logged_str:
            continue
        try:
            logged_dt = datetime.fromisoformat(logged_str)
            if logged_dt.tzinfo is None:
                logged_dt = logged_dt.replace(tzinfo=timezone.utc)
            if logged_dt >= cutoff:
                results.append(r)
        except ValueError:
            continue
    return sorted(results, key=lambda r: r.get("logged_at", ""), reverse=True)


def get_contact_summary(journalist_id: str) -> dict:
    """
    Return aggregate statistics for a journalist's contact history.

    Returns:
        {
            "total_contacts": int,
            "last_contact_date": str | None,  # ISO date string or None
            "response_rate": float,            # fraction of pitches that got a response
            "coverage_count": int,
        }
    """
    history = get_history(journalist_id)

    if not history:
        return {
            "total_contacts": 0,
            "last_contact_date": None,
            "response_rate": 0.0,
            "coverage_count": 0,
        }

    total = len(history)
    last_date = history[0].get("logged_at")  # already sorted newest first

    # Response rate = contacts with outcome "responded" / total pitches
    pitches = [r for r in history if r.get("contact_type") == "pitch"]
    responded = [r for r in pitches if r.get("outcome") == "responded"]
    response_rate = (len(responded) / len(pitches)) if pitches else 0.0

    coverage_count = len(
        [r for r in history if r.get("outcome") == "coverage_landed"]
    )

    return {
        "total_contacts": total,
        "last_contact_date": last_date,
        "response_rate": round(response_rate, 2),
        "coverage_count": coverage_count,
    }


def delete_contact(contact_id: str) -> None:
    """
    Delete a contact record by its ID.

    Args:
        contact_id: The 8-character ID of the record to delete.
    """
    records = [r for r in _load() if r.get("id") != contact_id]
    _save(records)


def get_pitch_analytics() -> dict:
    """
    Return aggregate pitch performance statistics across all journalists.

    Returns:
        {
            "total_pitches": int,
            "avg_response_rate": float,
            "coverage_count": int,
            "coverage_by_publication": {publication: count},
            "best_response_rate_journalist_ids": [journalist_id, ...],  # top 5
            "outcome_breakdown": {outcome: count},
        }
    """
    from services.journalist_db import get_by_id  # avoid circular import at module level

    records = _load()

    pitches = [r for r in records if r.get("contact_type") == "pitch"]
    total_pitches = len(pitches)

    # Outcome breakdown across all contact types
    outcome_breakdown: dict = {}
    for r in records:
        outcome = r.get("outcome", "") or "none"
        outcome_breakdown[outcome] = outcome_breakdown.get(outcome, 0) + 1

    # Coverage count and by publication
    coverage_records = [r for r in records if r.get("outcome") == "coverage_landed"]
    coverage_count = len(coverage_records)
    coverage_by_publication: dict = {}
    for r in coverage_records:
        journalist = get_by_id(r.get("journalist_id", ""))
        pub = journalist.get("publication", "Unknown") if journalist else "Unknown"
        coverage_by_publication[pub] = coverage_by_publication.get(pub, 0) + 1

    # Per-journalist response rates
    journalist_ids = list({r.get("journalist_id") for r in pitches if r.get("journalist_id")})
    journalist_rates = []
    for jid in journalist_ids:
        j_pitches = [r for r in pitches if r.get("journalist_id") == jid]
        j_responded = [r for r in j_pitches if r.get("outcome") == "responded"]
        rate = len(j_responded) / len(j_pitches) if j_pitches else 0.0
        journalist_rates.append((jid, rate))

    journalist_rates.sort(key=lambda x: x[1], reverse=True)
    best_journalists = [jid for jid, _ in journalist_rates[:5]]

    # Average response rate across all journalists who received at least one pitch
    avg_response_rate = (
        sum(rate for _, rate in journalist_rates) / len(journalist_rates)
        if journalist_rates
        else 0.0
    )

    return {
        "total_pitches": total_pitches,
        "avg_response_rate": round(avg_response_rate, 2),
        "coverage_count": coverage_count,
        "coverage_by_publication": coverage_by_publication,
        "best_response_rate_journalist_ids": best_journalists,
        "outcome_breakdown": outcome_breakdown,
    }
