"""
Blog Library service — save, load and manage generated blog posts.
Stores posts in data/blog_library.json with full CRUD, search and stats.
"""

import json
import os
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LIBRARY_FILE = os.path.join(DATA_DIR, "blog_library.json")

STATUS_OPTIONS = ["draft", "ready", "published"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "w") as f:
            json.dump([], f)


def _load():
    _ensure_file()
    try:
        with open(LIBRARY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records):
    _ensure_file()
    with open(LIBRARY_FILE, "w") as f:
        json.dump(records, f, indent=2)


def _extract_title_from_seo_package(seo_package_text):
    """Extract the title tag value from the SEO Package section."""
    if not seo_package_text:
        return ""
    for line in seo_package_text.splitlines():
        line = line.strip()
        if line.lower().startswith("**title tag:**"):
            title = line[len("**title tag:**"):].strip()
            return title.strip("[]").strip()
        if line.lower().startswith("title tag:"):
            title = line[len("title tag:"):].strip()
            return title.strip("[]").strip()
    # Fall back to the first non-empty line
    for line in seo_package_text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return ""


def _count_words(text):
    """Return word count for a string."""
    if not text:
        return 0
    return len(text.split())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_blog(topic, sections, blog_type, primary_keyword,
              secondary_keywords=None, title=None, tags=None):
    """
    Save a new blog post to the library.

    Returns the saved blog record (dict).
    """
    records = _load()

    # Auto-generate title from SEO Package section if not provided
    if not title or not title.strip():
        title = _extract_title_from_seo_package(sections.get("SEO Package", ""))
    if not title or not title.strip():
        # Last resort: truncate topic
        title = topic.strip()[:80]

    word_count = _count_words(sections.get("Blog Post", ""))

    blog = {
        "id": str(uuid.uuid4())[:8],
        "title": title.strip(),
        "created_at": datetime.now().isoformat(),
        "topic": topic,
        "blog_type": blog_type,
        "primary_keyword": primary_keyword,
        "secondary_keywords": [kw.strip() for kw in secondary_keywords if kw.strip()] if secondary_keywords else [],
        "sections": sections,
        "status": "draft",
        "word_count": word_count,
        "tags": [t.strip().lower() for t in tags if t.strip()] if tags else [],
        "versions": [],
    }

    records.append(blog)
    _save(records)
    return blog


def get_all_blogs():
    """Return all blogs, newest first."""
    blogs = _load()
    return sorted(blogs, key=lambda b: b.get("created_at", ""), reverse=True)


def get_blog(blog_id):
    """Return a single blog by id, or None if not found."""
    for blog in _load():
        if blog.get("id") == blog_id:
            return blog
    return None


def search_blogs(query):
    """
    Search blogs by title, topic, blog_type, primary_keyword,
    secondary_keywords and all section content.
    Returns matching blogs, newest first.
    """
    query = query.lower().strip()
    if not query:
        return get_all_blogs()

    results = []
    for blog in _load():
        sections_text = " ".join(blog.get("sections", {}).values())
        secondary_text = " ".join(blog.get("secondary_keywords", []))
        tags_text = " ".join(blog.get("tags", []))
        searchable = " ".join([
            blog.get("title", ""),
            blog.get("topic", ""),
            blog.get("blog_type", ""),
            blog.get("primary_keyword", ""),
            secondary_text,
            sections_text,
            tags_text,
        ]).lower()
        if query in searchable:
            results.append(blog)

    return sorted(results, key=lambda b: b.get("created_at", ""), reverse=True)


def update_blog_status(blog_id, new_status):
    """
    Update the status of a blog.  Returns the updated blog record.
    """
    if new_status not in STATUS_OPTIONS:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {STATUS_OPTIONS}.")
    records = _load()
    for i, blog in enumerate(records):
        if blog.get("id") == blog_id:
            records[i]["status"] = new_status
            _save(records)
            return records[i]
    raise ValueError(f"Blog '{blog_id}' not found.")


def delete_blog(blog_id):
    """Delete a blog by id."""
    records = _load()
    records = [b for b in records if b.get("id") != blog_id]
    _save(records)


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

def add_version(blog_id: str, sections: dict, note: str = "") -> dict:
    """Save current sections as a version snapshot. Keeps last 10 versions."""
    records = _load()
    for i, b in enumerate(records):
        if b["id"] == blog_id:
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
    raise KeyError(f"Blog {blog_id} not found")


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def get_stats():
    """
    Return aggregate stats for the blog library metrics row.

    Returns dict with: total, this_month, published_count, total_words.
    """
    blogs = _load()
    total = len(blogs)

    now = datetime.now()
    this_month = sum(
        1 for b in blogs
        if b.get("created_at", "")[:7] == f"{now.year}-{now.month:02d}"
    )

    published_count = sum(1 for b in blogs if b.get("status") == "published")

    total_words = sum(b.get("word_count", 0) for b in blogs)

    return {
        "total": total,
        "this_month": this_month,
        "published_count": published_count,
        "total_words": total_words,
    }
