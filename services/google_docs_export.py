"""
Google Docs export service — creates formatted Google Docs from PR packs.
Uses a service account for authentication; docs land in the configured Drive folder.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)


def _get_credentials(impersonate=True):
    """
    Load service account credentials.
    If GOOGLE_DRIVE_OWNER_EMAIL is set and impersonate=True, uses domain-wide
    delegation to act as that user (fixes service account storage quota issues).
    Requires domain-wide delegation to be enabled in Google Admin Console first.
    """
    from google.oauth2 import service_account

    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not os.path.isabs(json_path):
        json_path = os.path.join(_project_root, json_path)

    scopes = [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = service_account.Credentials.from_service_account_file(json_path, scopes=scopes)

    owner_email = os.getenv("GOOGLE_DRIVE_OWNER_EMAIL", "")
    if impersonate and owner_email:
        creds = creds.with_subject(owner_email)

    return creds


def _get_docs_service():
    from googleapiclient.discovery import build
    return build("docs", "v1", credentials=_get_credentials())


def _get_drive_service():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_get_credentials())


def is_configured():
    """Check if Google Docs export is configured."""
    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not json_path or not folder_id:
        return False
    if not os.path.isabs(json_path):
        json_path = os.path.join(_project_root, json_path)
    return os.path.exists(json_path)


def export_pr_pack_to_docs(pack: dict) -> dict:
    """
    Export a PR pack dict to a formatted Google Doc.

    Returns:
        dict with keys: 'doc_id', 'doc_url', 'title'
    """
    docs_service = _get_docs_service()
    drive_service = _get_drive_service()
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    title = pack.get("title", "PR Pack")
    created = pack.get("created_at", "")[:10]
    doc_title = f"[DRAFT] {title} — {created}"

    # --- Create the document in Drive ---
    file_metadata = {
        "name": doc_title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id] if folder_id else [],
    }
    doc_file = drive_service.files().create(body=file_metadata, fields="id,webViewLink").execute()
    doc_id = doc_file["id"]
    doc_url = doc_file["webViewLink"]

    # --- Build the document content via batchUpdate ---
    requests = _build_doc_requests(pack)
    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

    return {"doc_id": doc_id, "doc_url": doc_url, "title": doc_title}


def export_blog_to_docs(blog: dict) -> dict:
    """
    Export a blog library record to a formatted Google Doc.

    Returns:
        dict with keys: 'doc_id', 'doc_url', 'title'
    """
    docs_service = _get_docs_service()
    drive_service = _get_drive_service()
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    title = blog.get("title", "Blog Post")
    created_raw = blog.get("created_at", "")[:10]
    try:
        y, m, d = created_raw.split("-")
        created_display = f"{d}/{m}/{y}"
    except Exception:
        created_display = created_raw

    doc_title = f"[BLOG DRAFT] {title} — {created_display}"

    file_metadata = {
        "name": doc_title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id] if folder_id else [],
    }
    doc_file = drive_service.files().create(body=file_metadata, fields="id,webViewLink").execute()
    doc_id = doc_file["id"]
    doc_url = doc_file["webViewLink"]

    requests = _build_blog_doc_requests(blog)
    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

    return {"doc_id": doc_id, "doc_url": doc_url, "title": doc_title}


def _build_blog_doc_requests(blog: dict) -> list:
    """Build Google Docs API requests to populate a blog document."""
    requests = []

    title = blog.get("title", "Blog Post")
    created_raw = blog.get("created_at", "")[:10]
    try:
        y, m, d = created_raw.split("-")
        created_display = f"{d}/{m}/{y}"
    except Exception:
        created_display = created_raw

    blog_type = blog.get("blog_type", "")
    primary_kw = blog.get("primary_keyword", "")
    status = blog.get("status", "draft").upper()
    sections = blog.get("sections", {})

    insert_ops = []

    insert_ops.append(("RIOT PR DESK — BLOG WRITER\n", "title"))
    insert_ops.append((f"{title}\n", "heading1"))
    insert_ops.append((
        f"Created: {created_display}  |  Type: {blog_type}  |  "
        f"Keyword: {primary_kw}  |  Status: {status}\n\n",
        "normal_small",
    ))

    section_order = ["SEO Package", "Blog Post", "Image Suggestions", "External Links", "Social Promotion"]
    ordered_keys = [k for k in section_order if k in sections]
    ordered_keys += [k for k in sections if k not in section_order]

    for section_name in ordered_keys:
        content = sections.get(section_name, "").strip()
        if not content:
            continue
        insert_ops.append((f"{section_name}\n", "heading2"))
        if section_name == "Blog Post":
            insert_ops.append(("⚠️ DRAFT — Requires approval before publishing\n", "normal_small"))
        insert_ops.append((f"{content}\n\n", "normal"))

    current_index = 1
    text_ranges = []

    for text, style_hint in insert_ops:
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": text,
            }
        })
        text_ranges.append((current_index, current_index + len(text), style_hint))
        current_index += len(text)

    for start, end, style_hint in text_ranges:
        if style_hint == "title":
            requests.append({"updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": "TITLE"},
                "fields": "namedStyleType",
            }})
        elif style_hint == "heading1":
            requests.append({"updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": "HEADING_1"},
                "fields": "namedStyleType",
            }})
        elif style_hint == "heading2":
            requests.append({"updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": "HEADING_2"},
                "fields": "namedStyleType",
            }})
        elif style_hint == "normal_small":
            requests.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "textStyle": {
                    "fontSize": {"magnitude": 9, "unit": "PT"},
                    "foregroundColor": {"color": {"rgbColor": {
                        "red": 0.5, "green": 0.5, "blue": 0.5,
                    }}},
                },
                "fields": "fontSize,foregroundColor",
            }})

    return requests


def _build_doc_requests(pack: dict) -> list:
    """Build the list of Google Docs API requests to populate the document."""
    requests = []

    title = pack.get("title", "PR Pack")
    created = pack.get("created_at", "")[:19].replace("T", " ")
    position = pack.get("position_name", "")
    spokesperson = pack.get("spokesperson_key", "")
    status = pack.get("status", "draft").upper()
    sections = pack.get("sections", {})

    # We build the content as a series of insertText + updateParagraphStyle/updateTextStyle requests.
    # Google Docs API inserts at an index; we track the current end index.
    # Start at index 1 (after the implicit newline at position 0).

    index = 1
    insert_ops = []  # list of (text, style_hint)

    # --- Title block ---
    insert_ops.append((f"RIOT PR DESK — DRAFT\n", "title"))
    insert_ops.append((f"{title}\n", "heading1"))
    insert_ops.append((
        f"Generated: {created}  |  Position: {position}  |  Spokesperson: {spokesperson}  |  Status: {status}\n\n",
        "normal_small"
    ))

    # --- Coverage summary if any ---
    coverage = pack.get("coverage", [])
    if coverage:
        insert_ops.append(("Coverage Logged\n", "heading2"))
        for c in coverage:
            insert_ops.append((
                f"• {c.get('publication', '?')} — {c.get('journalist', '')} — {c.get('sentiment', '').title()} — reach: {c.get('reach_estimate', '?'):,}\n",
                "normal"
            ))
        insert_ops.append(("\n", "normal"))

    # --- PR sections ---
    section_order = [
        "Press Release",
        "Journalist Pitch Email",
        "LinkedIn Post",
        "Retailer WhatsApp Comms",
        "Consumer Social Media Comms",
        "Internal Briefing",
        "Creative Brief",
    ]
    # Use section_order to sort, then append any extras
    ordered_keys = [k for k in section_order if k in sections]
    ordered_keys += [k for k in sections if k not in section_order]

    for section_name in ordered_keys:
        content = sections.get(section_name, "")
        insert_ops.append((f"{section_name}\n", "heading2"))
        # Add a DRAFT watermark line
        insert_ops.append(("⚠️ DRAFT — Requires approval before external use\n", "normal_small"))
        insert_ops.append((f"{content}\n\n", "normal"))

    # --- Build actual API requests from insert_ops ---
    # First pass: insert all text in reverse order so indices don't shift
    # Actually, easiest: insert all text sequentially from index 1, tracking position

    current_index = 1
    text_ranges = []  # (start, end, style_hint) for styling pass

    for text, style_hint in insert_ops:
        requests.append({
            "insertText": {
                "location": {"index": current_index},
                "text": text,
            }
        })
        text_ranges.append((current_index, current_index + len(text), style_hint))
        current_index += len(text)

    # Second pass: apply paragraph styles
    for start, end, style_hint in text_ranges:
        if style_hint == "title":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "TITLE"},
                    "fields": "namedStyleType",
                }
            })
        elif style_hint == "heading1":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            })
        elif style_hint == "heading2":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType",
                }
            })
        elif style_hint == "normal_small":
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {
                        "fontSize": {"magnitude": 9, "unit": "PT"},
                        "foregroundColor": {"color": {"rgbColor": {"red": 0.5, "green": 0.5, "blue": 0.5}}},
                    },
                    "fields": "fontSize,foregroundColor",
                }
            })

    return requests
