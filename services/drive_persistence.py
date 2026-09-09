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


def _materialise_service_account_from_env() -> None:
    """
    GitHub Actions and Streamlit Cloud only expose secrets as env vars, not
    files. If GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT is set (raw JSON content)
    but GOOGLE_SERVICE_ACCOUNT_JSON (file path) is not, write the content to
    a tempfile and point the path env var at it. Idempotent — once the path
    env var is set, this is a no-op.

    This previously only ran in app.py, which broke Drive sync for any
    process that started directly from CLI (e.g. the GitHub Actions
    autonomous_engine briefing runner). Doing it here guarantees both
    Streamlit Cloud and the briefing runner have working Drive auth.
    """
    sa_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
    if not sa_content:
        return
    if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return
    import tempfile
    try:
        sa_data = json.loads(sa_content)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(sa_data, tmp)
        tmp.close()
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = tmp.name
    except Exception:
        pass


# Run on import — covers every process that imports this module.
_materialise_service_account_from_env()


def is_configured() -> bool:
    # Re-run materialisation in case env was set after module import
    _materialise_service_account_from_env()
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
    result = drive.files().list(q=q, fields="files(id)", pageSize=2).execute()
    files = result.get("files", [])
    if len(files) > 1:
        raise RuntimeError(f"Duplicate Drive records for {filename}; reconcile them before continuing")
    return files[0]["id"] if files else None


def download_json(filename: str, *, strict: bool = False):
    """
    Download riot_db_<filename> from Drive and return parsed JSON.
    Strict callers distinguish missing files from configuration/transport failures.
    """
    if not is_configured():
        if strict:
            raise RuntimeError("Google Drive persistence is not configured")
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
    except Exception as exc:
        if strict:
            raise RuntimeError(f"Could not read {filename} from Google Drive") from exc
        return None


def upload_json(filename: str, data, *, strict: bool = False) -> None:
    """
    Upload data as riot_db_<filename> to Drive.  Creates or overwrites.
    Strict callers receive failures before acknowledging a successful save.
    """
    if not is_configured():
        if strict:
            raise RuntimeError("Google Drive persistence is not configured")
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
    except Exception as exc:
        if strict:
            raise RuntimeError(f"Could not save {filename} to Google Drive") from exc


def download_action_events(known_names: set[str]) -> dict:
    """Read new immutable user actions, paginating without re-downloading old ones.

    The scheduled writer never updates these files. Concurrent app actions use
    distinct UUID filenames; listing failures are fatal rather than an empty log.
    """
    if not is_configured():
        raise RuntimeError("Google Drive persistence is not configured")
    drive = _get_drive()
    result = {}
    page_token = None
    prefix = "riot_db_opportunity_action_"
    while True:
        page = drive.files().list(
            q=f"'{_folder_id()}' in parents and trashed=false and name contains '{prefix}'",
            fields="nextPageToken,files(id,name)", pageSize=1000,
            pageToken=page_token,
        ).execute()
        for file in page.get("files", []):
            name = file["name"].removeprefix("riot_db_")
            if not file["name"].startswith(prefix) or name in known_names:
                continue
            raw = drive.files().get_media(fileId=file["id"]).execute()
            event = json.loads(raw.decode("utf-8"))
            result[name] = event
        page_token = page.get("nextPageToken")
        if not page_token:
            return result
