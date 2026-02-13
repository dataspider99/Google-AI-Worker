"""Google OAuth 2.0 integration for Gmail, Chat, and Workspace APIs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import httpx

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_SCOPES,
)

logger = logging.getLogger(__name__)


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


def _parse_token_response(data: dict) -> Credentials:
    """Build Credentials from Google token endpoint JSON (no scope validation)."""
    token = data["access_token"]
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)
    scope_str = data.get("scope", "")
    scopes = scope_str.split() if scope_str else list(GOOGLE_SCOPES)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
    return Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=scopes,
        expiry=expiry,
    )


def exchange_code_for_credentials(code: str) -> Credentials:
    """Exchange authorization code for access and refresh tokens."""
    # Do a single token exchange ourselves so we can accept any scope Google returns
    # (oauthlib raises "Scope has changed" when Google returns reordered/extra scopes).
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(data.get("error_description", data.get("error", "Unknown error")))
    return _parse_token_response(data)


def credentials_to_dict(creds: Credentials) -> dict[str, Any]:
    """Convert credentials to storable dict."""
    result: dict[str, Any] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }
    if creds.expiry is not None:
        e = creds.expiry
        if e.tzinfo is not None:
            e = e.astimezone(timezone.utc).replace(tzinfo=None)
        result["expiry"] = e.isoformat() + "Z"
    return result


def _normalize_expiry_to_naive_utc(expiry: datetime) -> datetime:
    """Return expiry as naive UTC so it matches google.auth's internal comparison."""
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(timezone.utc)
    return expiry.replace(tzinfo=None)


def dict_to_credentials(data: dict[str, Any]) -> Credentials:
    """Reconstruct credentials from stored dict."""
    expiry = None
    if data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(data["expiry"].replace("Z", "+00:00"))
            expiry = _normalize_expiry_to_naive_utc(expiry)
        except (ValueError, TypeError):
            pass
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=data.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=data.get("scopes", GOOGLE_SCOPES),
        expiry=expiry,
    )


def refresh_credentials_if_needed(creds: Credentials) -> Credentials:
    """Refresh token if expired or missing."""
    if not creds or not creds.refresh_token:
        return creds
    # Refresh when: token missing, expiry unknown (assume stale), or expired.
    # Avoid creds.expired to prevent naive/aware datetime comparison errors; check ourselves.
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    expiry_ok = False
    if creds.expiry is not None:
        if creds.expiry.tzinfo is None:
            expiry_ok = creds.expiry >= now_utc
        else:
            exp_naive_utc = creds.expiry.astimezone(timezone.utc).replace(tzinfo=None)
            expiry_ok = exp_naive_utc >= now_utc
    needs_refresh = (
        creds.token is None
        or (creds.token is not None and creds.expiry is None)
        or (creds.expiry is not None and not expiry_ok)
    )
    if needs_refresh:
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


def get_calendar_service(creds: Credentials):
    """Build Google Calendar API service."""
    creds = refresh_credentials_if_needed(creds)
    return build("calendar", "v3", credentials=creds)
