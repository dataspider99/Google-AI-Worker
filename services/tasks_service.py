"""Google Tasks API integration for storing action items from workflows."""
from __future__ import annotations

import logging
from typing import Any, Optional

from google.oauth2.credentials import Credentials

from auth.google_oauth import get_tasks_service
from googleapiclient.errors import HttpError

logger = logging.getLogger("google_employee.tasks")

TASKS_DEFAULT_LIST_NAME = "Google Employee"


def _log_http_error(operation: str, e: Exception) -> None:
    """Log 403/API errors with full details from Google."""
    if isinstance(e, HttpError):
        status = getattr(e.resp, "status", "?") if hasattr(e, "resp") else "?"
        reason = str(e)
        hint = " | Check: Tasks API enabled, OAuth scopes" if status == 403 else ""
        logger.warning("%s failed (HTTP %s): %s%s", operation, status, reason, hint)
    else:
        logger.warning("%s failed: %s", operation, e)


def list_task_lists(creds: Credentials) -> list[dict[str, Any]]:
    """List all task lists for the user."""
    service = get_tasks_service(creds)
    try:
        response = service.tasklists().list(maxResults=100).execute()
        return [
            {
                "id": tl.get("id", ""),
                "title": tl.get("title", ""),
                "updated": tl.get("updated", ""),
            }
            for tl in response.get("items", [])
        ]
    except HttpError as e:
        _log_http_error("Tasks tasklists.list", e)
        raise
    except Exception as e:
        logger.warning("Tasks tasklists.list failed: %s", e)
        return []


def get_or_create_task_list(creds: Credentials, name: str = TASKS_DEFAULT_LIST_NAME) -> Optional[str]:
    """
    Get or create a task list by name. Returns the task list ID.
    """
    service = get_tasks_service(creds)
    try:
        response = service.tasklists().list(maxResults=100).execute()
        for tl in response.get("items", []):
            if tl.get("title") == name:
                return tl.get("id")
        # Create if not found
        created = service.tasklists().insert(body={"title": name}).execute()
        return created.get("id")
    except HttpError as e:
        _log_http_error("Tasks tasklists", e)
        return None
    except Exception as e:
        logger.warning("Tasks get_or_create_task_list failed: %s", e)
        return None


def list_tasks(
    creds: Credentials,
    task_list_id: str,
    show_completed: bool = False,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """List tasks in a task list."""
    service = get_tasks_service(creds)
    try:
        response = service.tasks().list(
            tasklist=task_list_id,
            showCompleted=show_completed,
            maxResults=max_results,
        ).execute()
        return [
            {
                "id": t.get("id", ""),
                "title": t.get("title", ""),
                "notes": t.get("notes", ""),
                "status": t.get("status", "needsAction"),
                "due": t.get("due", ""),
                "completed": t.get("completed", ""),
                "updated": t.get("updated", ""),
            }
            for t in response.get("items", [])
        ]
    except HttpError as e:
        _log_http_error("Tasks tasks.list", e)
        raise
    except Exception as e:
        logger.warning("Tasks tasks.list failed: %s", e)
        return []


def create_task(
    creds: Credentials,
    title: str,
    notes: Optional[str] = None,
    task_list_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Create a task. Uses "Google Employee" list if task_list_id not provided.
    Returns the created task or None on failure.
    """
    if not task_list_id:
        task_list_id = get_or_create_task_list(creds)
    if not task_list_id:
        return None

    service = get_tasks_service(creds)
    body: dict[str, Any] = {"title": title}
    if notes:
        body["notes"] = notes

    try:
        result = service.tasks().insert(
            tasklist=task_list_id,
            body=body,
        ).execute()
        return {
            "id": result.get("id", ""),
            "title": result.get("title", ""),
            "notes": result.get("notes", ""),
            "status": result.get("status", "needsAction"),
            "task_list_id": task_list_id,
        }
    except HttpError as e:
        _log_http_error("Tasks tasks.insert", e)
        return None
    except Exception as e:
        logger.warning("Tasks tasks.insert failed: %s", e)
        return None
