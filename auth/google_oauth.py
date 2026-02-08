"""Google OAuth 2.0 integration for Gmail, Chat, and Workspace APIs."""
from __future__ import annotations

from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_SCOPES,
)


def create_oauth_flow() -> Flow:
    """Create OAuth 2.0 flow for Google authorization."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError(
            "Missing required parameter: client_id (and client_secret). "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file. "
            "Get them from Google Cloud Console → APIs & Services → Credentials."
        )
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


def get_authorization_url() -> str:
    """Generate the URL for user to authorize Google access."""
    flow = create_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code_for_credentials(code: str) -> Credentials:
    """Exchange authorization code for access and refresh tokens."""
    flow = create_oauth_flow()
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_to_dict(creds: Credentials) -> dict[str, Any]:
    """Convert credentials to storable dict."""
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }


def dict_to_credentials(data: dict[str, Any]) -> Credentials:
    """Reconstruct credentials from stored dict."""
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=data.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=data.get("scopes", GOOGLE_SCOPES),
    )


def refresh_credentials_if_needed(creds: Credentials) -> Credentials:
    """Refresh token if expired."""
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def get_gmail_service(creds: Credentials):
    """Build Gmail API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("gmail", "v1", credentials=creds)


def get_chat_service(creds: Credentials):
    """Build Google Chat API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("chat", "v1", credentials=creds)


def get_drive_service(creds: Credentials):
    """Build Google Drive API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("drive", "v3", credentials=creds)


def get_docs_service(creds: Credentials):
    """Build Google Docs API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("docs", "v1", credentials=creds)


def get_sheets_service(creds: Credentials):
    """Build Google Sheets API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("sheets", "v4", credentials=creds)


def get_tasks_service(creds: Credentials):
    """Build Google Tasks API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("tasks", "v1", credentials=creds)
