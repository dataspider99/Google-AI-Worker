"""Fetch and format Google data (Gmail, Chat, Workspace) for agent context."""
from __future__ import annotations

import base64
import logging
import re
from email.message import EmailMessage
from typing import Any, Optional

from auth.google_oauth import (
    get_chat_service,
    get_docs_service,
    get_drive_service,
    get_gmail_service,
    get_sheets_service,
)
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

logger = logging.getLogger("google_employee.google_data")


def _log_http_error(operation: str, e: Exception) -> None:
    """Log 403/API errors with actionable details."""
    if isinstance(e, HttpError):
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        reason = str(e)
        if status == 403 or "PERMISSION_DENIED" in reason:
            reason = "PERMISSION_DENIED - Check: 1) API enabled in Google Cloud 2) OAuth scopes 3) Workspace admin approval (Chat API)"
        logger.warning(
            "%s failed (HTTP %s): %s",
            operation,
            status,
            reason,
        )
    else:
        logger.warning("%s failed: %s", operation, e)


def _decode_body(payload: dict) -> str:
    """Decode Gmail message body from payload."""
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    return ""


def fetch_emails(creds: Credentials, max_results: int = 10) -> list[dict[str, Any]]:
    """Fetch recent emails from Gmail inbox."""
    try:
        service = get_gmail_service(creds)
        results = service.users().messages().list(userId="me", maxResults=max_results).execute()
    except HttpError as e:
        _log_http_error("Gmail messages.list", e)
        raise
    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        payload = full.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        snippet = full.get("snippet", "")
        body = _decode_body(payload) or snippet

        emails.append({
            "id": msg["id"],
            "thread_id": full.get("threadId", ""),
            "subject": headers.get("Subject", "(No subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "message_id": headers.get("Message-ID", ""),
            "references": headers.get("References", ""),
            "snippet": snippet[:200],
            "body_preview": body[:500] if body else snippet[:500],
        })

    return emails


def _extract_email_address(header_value: str) -> str:
    """Extract email from 'Name <email@domain.com>' or 'email@domain.com'."""
    match = re.search(r"<([^>]+)>", header_value)
    return match.group(1).strip() if match else header_value.strip()


def create_email_draft(
    creds: Credentials,
    to: str,
    subject: str,
    body: str,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Create a Gmail draft. For replies, pass thread_id, in_reply_to, references.
    """
    service = get_gmail_service(creds)
    msg = EmailMessage()
    msg.set_content(body)
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    message_obj: dict[str, Any] = {"raw": encoded}
    if thread_id:
        message_obj["threadId"] = thread_id
    draft_body = {"message": message_obj}

    try:
        result = service.users().drafts().create(userId="me", body=draft_body).execute()
        return {"id": result.get("id"), "message_id": result.get("message", {}).get("id")}
    except HttpError as e:
        _log_http_error("Gmail drafts.create", e)
        return None
    except Exception as e:
        logger.warning("Gmail drafts.create failed: %s", e)
        return None


def fetch_chat_spaces(creds: Credentials) -> list[dict[str, Any]]:
    """
    List Google Chat spaces the user is in.
    Includes SPACE (named spaces), GROUP_CHAT, and DIRECT_MESSAGE.
    """
    service = get_chat_service(creds)
    spaces = []
    response = None

    def _parse_spaces(resp: dict) -> list[dict[str, Any]]:
        out = []
        for space in resp.get("spaces") or []:
            out.append({
                "name": space.get("name", ""),
                "displayName": space.get("displayName", ""),
                "type": space.get("type", ""),
            })
        return out

    try:
        page_token = None
        while True:
            params: dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            response = service.spaces().list(**params).execute()
            spaces.extend(_parse_spaces(response))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        # If empty, try with explicit filter for all space types
        if not spaces and response:
            filter_expr = 'spaceType = "SPACE" OR spaceType = "GROUP_CHAT" OR spaceType = "DIRECT_MESSAGE"'
            try:
                resp2 = service.spaces().list(pageSize=100, filter=filter_expr).execute()
                spaces = _parse_spaces(resp2)
            except HttpError:
                pass  # Filter may not be supported in all environments
    except HttpError as e:
        _log_http_error("Google Chat spaces.list", e)
    except Exception as e:
        logger.warning("Chat spaces.list failed: %s", e)

    if not spaces and response is not None:
        logger.info(
            "Chat spaces.list returned 0 spaces. Response keys: %s",
            list(response.keys()),
        )
    return spaces


def fetch_chat_messages(creds: Credentials, space_name: str, page_size: int = 20) -> list[dict[str, Any]]:
    """Fetch messages from a Google Chat space."""
    service = get_chat_service(creds)
    messages = []
    try:
        response = service.spaces().messages().list(
            parent=space_name,
            pageSize=page_size,
        ).execute()
        for msg in response.get("messages", []):
            text = msg.get("text", "") or (msg.get("cards", [{}])[0].get("sections", [{}])[0].get("widgets", [{}])[0].get("textParagraph", {}).get("text", "") if msg.get("cards") else "")
            thread = msg.get("thread") or {}
            thread_name = thread.get("name", "")
            parent = thread_name if thread_name else space_name
            messages.append({
                "name": msg.get("name", ""),
                "text": text,
                "creator": msg.get("creator", {}).get("displayName", ""),
                "createTime": msg.get("createTime", ""),
                "thread_name": thread_name,
                "reply_parent": parent,
            })
    except HttpError as e:
        _log_http_error("Google Chat messages.list", e)
    except Exception as e:
        logger.warning("Chat messages.list failed: %s", e)
    return messages


def post_chat_message(creds: Credentials, parent: str, text: str) -> dict[str, Any] | None:
    """
    Post a message to Google Chat.
    parent: space name (e.g. spaces/xxx) or thread name (e.g. spaces/xxx/threads/yyy) for replies.
    """
    service = get_chat_service(creds)
    try:
        result = service.spaces().messages().create(
            parent=parent,
            body={"text": text},
        ).execute()
        return result
    except HttpError as e:
        _log_http_error("Google Chat messages.create", e)
        return None
    except Exception as e:
        logger.warning("Chat messages.create failed: %s", e)
        return None


def fetch_drive_files(creds: Credentials, max_results: int = 10) -> list[dict[str, Any]]:
    """Fetch recent Drive files."""
    try:
        service = get_drive_service(creds)
        results = (
            service.files()
            .list(pageSize=max_results, fields="files(id,name,mimeType,modifiedTime,webViewLink)")
            .execute()
        )
    except HttpError as e:
        _log_http_error("Google Drive files.list", e)
        raise
    return [
        {
            "id": f["id"],
            "name": f.get("name", ""),
            "mimeType": f.get("mimeType", ""),
            "modifiedTime": f.get("modifiedTime", ""),
            "webViewLink": f.get("webViewLink", ""),
        }
        for f in results.get("files", [])
    ]


def format_context_for_agent(emails: list, chat: list, drive: list) -> str:
    """Format Google data into a concise context string for the Oshaani agent."""
    parts = []

    if emails:
        parts.append("## Recent Emails\n")
        for e in emails[:5]:
            parts.append(f"- **From:** {e['from']}\n- **Subject:** {e['subject']}\n- **Preview:** {e['body_preview'][:300]}...\n")

    if chat:
        parts.append("\n## Chat Messages\n")
        for m in chat[:10]:
            parts.append(f"- **{m.get('creator', '')}:** {m.get('text', '')[:150]}\n")

    if drive:
        parts.append("\n## Recent Drive Files\n")
        for f in drive[:5]:
            parts.append(f"- {f['name']} ({f['mimeType']})\n")

    return "\n".join(parts) if parts else "No Google data available."
