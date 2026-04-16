"""
Error logging service — captures AI failures, API errors and unexpected exceptions
to a rotating log file for debugging and monitoring.
"""

import os
import json
import traceback
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LOG_FILE = os.path.join(LOG_DIR, "error_log.json")
MAX_LOG_ENTRIES = 500  # Keep last 500 errors


def log_error(error_type: str, message: str, context: str = "", exception=None):
    """
    Log an error to the error log file.

    Args:
        error_type: Category e.g. 'ai_generation', 'news_fetch', 'library_save', 'journalist_fetch'
        message: Human-readable error message
        context: What was happening when the error occurred
        exception: Optional Exception object for traceback
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": error_type,
        "message": str(message),
        "context": context,
        "traceback": traceback.format_exc() if exception else None,
    }

    # Load existing log
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    # Prepend (newest first) and trim
    logs.insert(0, entry)
    logs = logs[:MAX_LOG_ENTRIES]

    try:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception:
        pass  # Silent fail — logging must never crash the app


def get_recent_errors(n=50):
    """Get the n most recent error log entries."""
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
        return logs[:n]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def get_error_summary():
    """Return a summary dict of recent errors for the dashboard."""
    errors = get_recent_errors(100)
    if not errors:
        return {"total": 0, "by_type": {}, "last_error": None}

    by_type = {}
    for e in errors:
        t = e.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": len(errors),
        "by_type": by_type,
        "last_error": errors[0]["timestamp"][:19].replace("T", " ") if errors else None,
    }


def clear_errors():
    """Clear all error logs."""
    try:
        with open(LOG_FILE, "w") as f:
            json.dump([], f)
    except Exception:
        pass
