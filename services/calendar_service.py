"""Google Calendar API integration for scheduling events from email/chat workflows."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from google.oauth2.credentials import Credentials

from auth.google_oauth import get_calendar_service
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Default timezone for parsed times when not specified (RFC3339 requires timezone; we use UTC)
DEFAULT_EVENT_TIMEZONE = "UTC"


def _log_http_error(operation: str, e: Exception) -> None:
    if isinstance(e, HttpError):
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        logger.warning("%s failed (HTTP %s): %s", operation, status, e)
    else:
        logger.warning("%s failed: %s", operation, e)


def create_event(
    creds: Credentials,
    summary: str,
    start: str,
    end: str,
    description: Optional[str] = None,
    calendar_id: str = "primary",
) -> Optional[dict[str, Any]]:
    """
    Create a calendar event.
    start/end: RFC3339 strings (e.g. 2025-02-15T14:00:00Z) or date-only (YYYY-MM-DD) for all-day.
    Returns the created event or None on failure.
    """
    if not summary or not start or not end:
        return None
    service = get_calendar_service(creds)
    body: dict[str, Any] = {"summary": summary[:1024]}
    if description:
        body["description"] = description[:8192]

    # All-day: use "date"; timed: use "dateTime" + "timeZone"
    if "T" in start and "T" in end:
        body["start"] = {"dateTime": start, "timeZone": DEFAULT_EVENT_TIMEZONE}
        body["end"] = {"dateTime": end, "timeZone": DEFAULT_EVENT_TIMEZONE}
    else:
        body["start"] = {"date": start[:10]}
        body["end"] = {"date": end[:10]}

    try:
        result = service.events().insert(
            calendarId=calendar_id,
            body=body,
        ).execute()
        return {
            "id": result.get("id", ""),
            "summary": result.get("summary", summary),
            "start": result.get("start", {}),
            "end": result.get("end", {}),
            "htmlLink": result.get("htmlLink", ""),
        }
    except HttpError as e:
        _log_http_error("Calendar events.insert", e)
        return None
    except Exception as e:
        logger.warning("Calendar events.insert failed: %s", e)
        return None


def parse_datetime_for_calendar(value: str) -> Optional[str]:
    """
    Parse a datetime string from agent output into RFC3339 for Calendar API.
    Accepts: YYYY-MM-DD HH:MM, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD (date only).
    Returns RFC3339 string (with Z) or date string YYYY-MM-DD for all-day; None if unparseable.
    """
    value = (value or "").strip()
    if not value:
        return None
    # Already RFC3339-like
    if value.endswith("Z") or "+" in value or (len(value) >= 19 and value[10] == "T"):
        if len(value) == 10:
            return value  # date only
        return value
    # YYYY-MM-DD (all-day)
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            return None
    # YYYY-MM-DD HH:MM or HH:MM:SS
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(value.replace("Z", "").strip(), fmt)
            # Emit as UTC RFC3339
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def list_calendars(creds: Credentials) -> list[dict[str, Any]]:
    """List the user's calendars (for optional calendar picker)."""
    try:
        service = get_calendar_service(creds)
        response = service.calendarList().list().execute()
        return [
            {"id": c.get("id", ""), "summary": c.get("summary", ""), "primary": c.get("primary", False)}
            for c in response.get("items", [])
        ]
    except HttpError as e:
        _log_http_error("Calendar calendarList.list", e)
        return []
    except Exception as e:
        logger.warning("Calendar list failed: %s", e)
        return []
