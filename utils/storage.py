"""
Storage Manager — Google Drive (15GB free) + local fallback
Handles upload/download of generated media
"""
import os
import json
from pathlib import Path
from typing import Optional
from utils.logger import get_logger
from utils.rate_limiter import get_limiter

log = get_logger("storage")
limiter = get_limiter()

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "")
GDRIVE_CREDENTIALS_FILE = os.getenv("GDRIVE_CREDENTIALS_FILE", "gdrive_credentials.json")


def _get_drive_service():
    """Lazy-load Google Drive service"""
    try:
        from google.oauth2.credentials import Credentials
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if Path(GDRIVE_CREDENTIALS_FILE).exists():
            creds = service_account.Credentials.from_service_account_file(
                GDRIVE_CREDENTIALS_FILE,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            return build("drive", "v3", credentials=creds)
    except Exception as e:
        log.warning(f"Google Drive unavailable: {e}. Using local storage only.")
    return None


def save_locally(content: bytes, filename: str, subfolder: str = "images") -> Path:
    """Save content to local output directory"""
    dest = OUTPUT_DIR / subfolder
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / filename
    filepath.write_bytes(content)
    log.info(f"Saved locally: {filepath}")
    return filepath


def upload_to_drive(local_path: Path, mime_type: str = "image/jpeg") -> Optional[str]:
    """Upload file to Google Drive, return shareable link"""
    if not limiter.acquire("gdrive"):
        log.error("Google Drive daily limit reached")
        return None

    service = _get_drive_service()
    if service is None:
        log.info("Drive unavailable — using local path")
        return str(local_path)

    try:
        from googleapiclient.http import MediaFileUpload

        file_metadata = {
            "name": local_path.name,
            "parents": [GDRIVE_FOLDER_ID] if GDRIVE_FOLDER_ID else []
        }
        media = MediaFileUpload(str(local_path), mimetype=mime_type)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        link = file.get("webViewLink", "")
        log.success(f"Uploaded to Drive: {link}")
        return link

    except Exception as e:
        log.error(f"Drive upload failed: {e}")
        return str(local_path)


def save_media(content: bytes, filename: str, subfolder: str = "images",
               upload: bool = True) -> dict:
    """
    Save media locally and optionally upload to Drive.
    Returns dict with local_path and drive_link.
    """
    local_path = save_locally(content, filename, subfolder)
    drive_link = None

    if upload and GDRIVE_FOLDER_ID:
        mime = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
        drive_link = upload_to_drive(local_path, mime)

    return {
        "local_path": str(local_path),
        "drive_link": drive_link,
        "filename": filename
    }


def save_json(data: dict, filename: str, subfolder: str = "data") -> Path:
    """Save JSON metadata"""
    dest = Path(subfolder)
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / filename
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return filepath


def load_json(filepath: str) -> dict:
    """Load JSON file"""
    p = Path(filepath)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}
