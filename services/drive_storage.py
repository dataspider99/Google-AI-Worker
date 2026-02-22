"""Store and fetch user data from the user's Google Drive."""
from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any, Optional

from google.oauth2.credentials import Credentials

from auth.google_oauth import get_drive_service
from googleapiclient.errors import HttpError

logger = logging.getLogger("google_employee.drive_storage")

APP_FOLDER_NAME = "Johny Sins"
USER_DATA_FILENAME = "user_data.json"


def _get_or_create_app_folder(creds: Credentials) -> Optional[str]:
    """Get or create the app folder in user's Drive. Returns folder_id or None."""
    service = get_drive_service(creds)
    try:
        # Search for existing folder
        result = (
            service.files()
            .list(
                q=f"name='{APP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="files(id, name)",
            )
            .execute()
        )
        files = result.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        folder = (
            service.files()
            .create(
                body={
                    "name": APP_FOLDER_NAME,
                    "mimeType": "application/vnd.google-apps.folder",
                },
                fields="id",
            )
            .execute()
        )
        return folder.get("id")
    except HttpError as e:
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        logger.warning(
            "Drive folder create/list failed (HTTP %s): %s - Check Drive API enabled and drive.file scope",
            status,
            e,
        )
        return None
    except Exception as e:
        logger.warning("Failed to get/create app folder: %s", e)
        return None


def _find_user_data_file(service, folder_id: str) -> Optional[str]:
    """Find user_data.json in folder. Returns file_id or None."""
    result = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and name='{USER_DATA_FILENAME}' and trashed=false",
            fields="files(id, name)",
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _find_file_in_folder(service, folder_id: str, name: str) -> Optional[str]:
    """Find a file by name in folder. Returns file_id or None."""
    result = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and name='{name}' and trashed=false",
            fields="files(id, name)",
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else None


WORKFLOW_RESULT_FILENAMES = {
    "smart-inbox": "Smart Inbox result.txt",
    "document-intelligence": "Document Intelligence result.txt",
    "first-email-draft": "First email draft result.txt",
}


def save_workflow_result_to_drive(
    creds: Credentials,
    workflow_name: str,
    content: str,
) -> Optional[str]:
    """
    Save workflow result as a text file in the user's "Johny Sins" Drive folder.
    Returns webViewLink to open the file in Drive, or None on failure.
    """
    service = get_drive_service(creds)
    folder_id = _get_or_create_app_folder(creds)
    if not folder_id:
        return None

    filename = WORKFLOW_RESULT_FILENAMES.get(workflow_name) or f"{workflow_name} result.txt"
    try:
        from googleapiclient.http import MediaIoBaseUpload

        body_content = content.encode("utf-8")
        media_body = MediaIoBaseUpload(
            BytesIO(body_content),
            mimetype="text/plain; charset=utf-8",
            resumable=False,
        )

        existing_id = _find_file_in_folder(service, folder_id, filename)
        if existing_id:
            service.files().update(
                fileId=existing_id,
                media_body=media_body,
            ).execute()
            file_id = existing_id
        else:
            created = service.files().create(
                body={
                    "name": filename,
                    "parents": [folder_id],
                    "mimeType": "text/plain",
                },
                media_body=media_body,
                fields="id, webViewLink",
            ).execute()
            file_id = created.get("id")

        meta = service.files().get(fileId=file_id, fields="webViewLink").execute()
        return meta.get("webViewLink")
    except HttpError as e:
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        logger.warning(
            "Drive workflow result save failed (HTTP %s): %s",
            status,
            e,
        )
        return None
    except Exception as e:
        logger.warning("Failed to save workflow result to Drive: %s", e)
        return None


def save_user_data_to_drive(creds: Credentials, user_id: str, data: dict[str, Any]) -> bool:
    """
    Save user data (credentials, settings, etc.) to user's Drive.
    Creates/uses folder "Johny Sins" and file user_data.json.
    """
    service = get_drive_service(creds)
    folder_id = _get_or_create_app_folder(creds)
    if not folder_id:
        return False

    try:
        from googleapiclient.http import MediaIoBaseUpload

        content = json.dumps(data, indent=2).encode("utf-8")
        media_body = MediaIoBaseUpload(
            BytesIO(content),
            mimetype="application/json",
            resumable=False,
        )

        existing_id = _find_user_data_file(service, folder_id)
        if existing_id:
            service.files().update(
                fileId=existing_id,
                media_body=media_body,
            ).execute()
        else:
            service.files().create(
                body={
                    "name": USER_DATA_FILENAME,
                    "parents": [folder_id],
                },
                media_body=media_body,
                fields="id",
            ).execute()
        logger.debug("Saved user data to Drive for %s", user_id)
        return True
    except HttpError as e:
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        logger.warning(
            "Drive save failed for %s (HTTP %s): %s - Check drive.file scope and re-auth",
            user_id,
            status,
            e,
        )
        return False
    except Exception as e:
        logger.warning("Failed to save user data to Drive for %s: %s", user_id, e)
        return False


def load_user_data_from_drive(creds: Credentials, user_id: str) -> Optional[dict[str, Any]]:
    """
    Load user data from user's Drive.
    Returns dict or None if not found.
    """
    service = get_drive_service(creds)
    folder_id = _get_or_create_app_folder(creds)
    if not folder_id:
        return None

    file_id = _find_user_data_file(service, folder_id)
    if not file_id:
        return None

    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        buf = BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        return json.loads(buf.read().decode("utf-8"))
    except HttpError as e:
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        logger.warning(
            "Drive load failed for %s (HTTP %s): %s",
            user_id,
            status,
            e,
        )
        return None
    except Exception as e:
        logger.warning("Failed to load user data from Drive for %s: %s", user_id, e)
        return None
