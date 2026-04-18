"""
Journalist database service — lightweight CRM for managing press contacts.
Stores data in a JSON file with CRUD operations, CSV import and AI matching.
"""

import csv
import io
import json
import os
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_FILE = os.path.join(DATA_DIR, "journalists.json")

BEAT_OPTIONS = [
    "Vaping", "Health", "FMCG", "Retail", "Regulation",
    "Tobacco", "Consumer", "Lifestyle", "Politics", "Business",
    "Technology", "Science", "Environment", "Sport", "Entertainment",
    "Food & Drink", "Manufacturing", "Trade",
]

TYPE_OPTIONS = ["Trade", "National", "Regional", "Consumer", "Broadcast", "Freelance", "Online"]


_drive_synced = False  # sync from Drive once per process startup


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump([], f)


def _load():
    global _drive_synced
    _ensure_file()

    # On first load after a deploy, pull the authoritative copy from Drive
    if not _drive_synced:
        _drive_synced = True
        try:
            from services.drive_persistence import download_json, is_configured
            if is_configured():
                drive_data = download_json("journalists.json")
                if drive_data is not None:
                    with open(DB_FILE, "w") as f:
                        json.dump(drive_data, f, indent=2)
        except Exception:
            pass

    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records):
    _ensure_file()
    with open(DB_FILE, "w") as f:
        json.dump(records, f, indent=2)
    # Push to Drive so data survives the next redeploy
    try:
        from services.drive_persistence import upload_json
        upload_json("journalists.json", records)
    except Exception:
        pass


def get_all():
    """Get all journalist records."""
    return _load()


def get_journalist_count():
    """Get total number of journalists."""
    return len(_load())


def get_by_id(journalist_id):
    """Get a single journalist by ID."""
    for j in _load():
        if j.get("id") == journalist_id:
            return j
    return None


def add_journalist(data):
    """Add a new journalist. Returns the new record."""
    records = _load()
    record = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip(),
        "phone": data.get("phone", "").strip(),
        "publication": data.get("publication", "").strip(),
        "job_title": data.get("job_title", "").strip(),
        "beats": [b.strip().title() for b in data.get("beats", [])],
        "location": data.get("location", "").strip(),
        "type": data.get("type", "Trade"),
        "notes": data.get("notes", "").strip(),
        "linkedin": data.get("linkedin", "").strip(),
        "last_contacted": data.get("last_contacted", ""),
        "relationship_score": data.get("relationship_score", 3),
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "tags": data.get("tags", []),
    }
    records.append(record)
    _save(records)
    return record


def update_journalist(journalist_id, data):
    """Update an existing journalist record."""
    records = _load()
    for i, j in enumerate(records):
        if j.get("id") == journalist_id:
            records[i].update(data)
            _save(records)
            return records[i]
    return None


def delete_journalist(journalist_id):
    """Delete a journalist by ID."""
    records = _load()
    records = [j for j in records if j.get("id") != journalist_id]
    _save(records)


def search(query):
    """Search journalists by name, publication, beats or tags."""
    query = query.lower()
    results = []
    for j in _load():
        searchable = " ".join([
            j.get("name", ""),
            j.get("publication", ""),
            j.get("job_title", ""),
            j.get("location", ""),
            " ".join(j.get("beats", [])),
            " ".join(j.get("tags", [])),
            j.get("notes", ""),
        ]).lower()
        if query in searchable:
            results.append(j)
    return results


def filter_by(type_filter=None, beat_filter=None, publication_filter=None):
    """Filter journalists by type, beat or publication."""
    records = _load()
    if type_filter:
        records = [j for j in records if j.get("type", "").lower() == type_filter.lower()]
    if beat_filter:
        records = [j for j in records if beat_filter.lower() in [b.lower() for b in j.get("beats", [])]]
    if publication_filter:
        records = [j for j in records if publication_filter.lower() in j.get("publication", "").lower()]
    return records


def import_csv(csv_content):
    """
    Import journalists from CSV content string.
    Returns (imported_count, skipped_count, errors).
    Only 'name' and 'publication' are required.
    """
    imported = 0
    skipped = 0
    errors = []

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        for row_num, row in enumerate(reader, start=2):
            # Normalise column names (strip whitespace, lowercase)
            row = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}

            name = row.get("name", "")
            publication = row.get("publication", "")

            if not name or not publication:
                skipped += 1
                errors.append(f"Row {row_num}: Missing name or publication")
                continue

            # Parse beats and tags from comma-separated strings
            beats = [b.strip() for b in row.get("beats", "").split(",") if b.strip()]
            tags = [t.strip() for t in row.get("tags", "").split(",") if t.strip()]

            # Parse relationship score
            try:
                rel_score = int(row.get("relationship_score", 3))
                rel_score = max(1, min(5, rel_score))
            except (ValueError, TypeError):
                rel_score = 3

            add_journalist({
                "name": name,
                "email": row.get("email", ""),
                "phone": row.get("phone", ""),
                "publication": publication,
                "job_title": row.get("job_title", ""),
                "beats": beats,
                "location": row.get("location", ""),
                "type": row.get("type", "Trade"),
                "notes": row.get("notes", ""),
                "linkedin": row.get("linkedin", ""),
                "relationship_score": rel_score,
                "tags": tags,
            })
            imported += 1

    except Exception as e:
        errors.append(f"CSV parse error: {e}")

    return imported, skipped, errors


def get_database_summary_for_ai():
    """Format the journalist database for AI prompt injection."""
    records = _load()
    if not records:
        return "No journalists in the database yet."

    lines = []
    for j in records:
        beats = ", ".join(j.get("beats", []))
        lines.append(
            f"- {j['name']} | {j.get('publication', '')} | {j.get('job_title', '')} | "
            f"Beats: {beats} | Type: {j.get('type', '')} | "
            f"Relationship: {j.get('relationship_score', '?')}/5"
        )
    return "\n".join(lines)


def clear_all():
    """Delete all journalists."""
    _save([])
