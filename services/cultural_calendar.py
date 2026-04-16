"""
Cultural calendar service — manages upcoming events and AI opportunity scanning.
"""

import json
import os
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CALENDAR_FILE = os.path.join(DATA_DIR, "cultural_calendar.json")

CATEGORIES = [
    "Sport", "Music & Festivals", "Entertainment",
    "UK Calendar", "Awareness Days", "Riot-Specific",
]


def _load():
    try:
        with open(CALENDAR_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(events):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(events, f, indent=2)


def get_all_events():
    """Get all events sorted by date."""
    events = _load()
    events.sort(key=lambda e: e.get("date", "9999"))
    return events


def get_upcoming_events(days_ahead=60):
    """Get events happening in the next N days."""
    today = datetime.now().date()
    cutoff = today + timedelta(days=days_ahead)

    upcoming = []
    for event in _load():
        try:
            event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
            end_date = event_date
            if event.get("end_date"):
                end_date = datetime.strptime(event["end_date"], "%Y-%m-%d").date()

            # Include if it's upcoming or currently happening
            if event_date <= cutoff and end_date >= today:
                # Calculate days until
                days_until = (event_date - today).days
                event["_days_until"] = days_until
                event["_status"] = "happening now" if event_date <= today <= end_date else f"in {days_until} days"
                upcoming.append(event)
        except (ValueError, KeyError):
            continue

    upcoming.sort(key=lambda e: e.get("date", "9999"))
    return upcoming


def get_events_by_category(category):
    """Filter events by category."""
    return [e for e in get_all_events() if e.get("category") == category]


def add_event(name, date, category, description="", relevance="", end_date=None):
    """Add a custom event to the calendar."""
    events = _load()
    events.append({
        "name": name,
        "date": date,
        "end_date": end_date,
        "category": category,
        "description": description,
        "relevance_to_riot": relevance,
        "custom": True,
    })
    _save(events)


def delete_event(event_name):
    """Delete a custom event by name."""
    events = _load()
    events = [e for e in events if not (e.get("name") == event_name and e.get("custom"))]
    _save(events)


def format_events_for_ai(events):
    """Format a list of events for AI prompt injection."""
    lines = []
    for e in events:
        date_str = e.get("date", "?")
        if e.get("end_date"):
            date_str += f" to {e['end_date']}"
        status = e.get("_status", "")
        lines.append(
            f"- **{e['name']}** ({date_str}) [{e.get('category', '')}] — "
            f"{e.get('description', '')} "
            f"Riot relevance: {e.get('relevance_to_riot', 'Not assessed')} "
            f"({status})"
        )
    return "\n".join(lines)
