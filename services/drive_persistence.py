"""
Drive persistence — keeps app data files (journalists, PR library, blog library,
media lists) alive across Streamlit Cloud redeploys.

On every process startup each service syncs ONCE from Drive (fast — one API call
per file, per server restart).  Every write also pushes to Drive so the cloud
copy is always up to date.

Folder used: GOOGLE_DRIVE_FOLDER_ID (same service account as doc exports).
Files are stored with a "riot_db_" prefix to distinguish them from exported docs.
"""

import io
import json
import os

from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)


def is_configured() -> bool:
    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not sa_path or not folder_id:
        return False
    if not os.path.isabs(sa_path):
        sa_path = os.path.join(_project_root, sa_path)
    return os.path.exists(sa_path)


def _get_drive():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not os.path.isabs(sa_path):
        sa_path = os.path.join(_project_root, sa_path)

    creds = service_account.Credentials.from_service_account_file(
        sa_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    owner = os.getenv("GOOGLE_DRIVE_OWNER_EMAIL", "")
    if owner:
        creds = creds.with_subject(owner)
    return build("drive", "v3", credentials=creds)


def _folder_id() -> str:
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")


def _find_file_id(drive, filename: str) -> str | None:
    """Return the Drive file ID for riot_db_<filename>, or None if not found."""
    drive_name = f"riot_db_{filename}"
    fid = _folder_id()
    q = f"name='{drive_name}' and '{fid}' in parents and trashed=false"
    result = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def download_json(filename: str):
    """
    Download riot_db_<filename> from Drive and return parsed JSON.
    Returns None if not configured, file not found, or any error.
    """
    if not is_configured():
        return None
    try:
        drive = _get_drive()
        file_id = _find_file_id(drive, filename)
        if not file_id:
            return None
        from googleapiclient.http import MediaIoBaseDownload
        request = drive.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        return json.loads(buf.read().decode("utf-8"))
    except Exception:
        return None


def upload_json(filename: str, data) -> None:
    """
    Upload data as riot_db_<filename> to Drive.  Creates or overwrites.
    Silent fail — never raises, never crashes the app.
    """
    if not is_configured():
        return
    try:
        from googleapiclient.http import MediaIoBaseUpload

        drive = _get_drive()
        drive_name = f"riot_db_{filename}"
        content = json.dumps(data, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")

        file_id = _find_file_id(drive, filename)
        if file_id:
            drive.files().update(fileId=file_id, media_body=media).execute()
        else:
            metadata = {"name": drive_name, "parents": [_folder_id()]}
            drive.files().create(body=metadata, media_body=media, fields="id").execute()
    except Exception:
        pass
