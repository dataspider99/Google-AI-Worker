"""
MCP HTTP server with per-user credentials (multi-user).

Implements MCP protocol over HTTP. Requires Authorization: Bearer <api_key>.
Each request uses the authenticated user's Google credentials.
"""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("google_employee.mcp")

# Per-request user ID (set by auth middleware)
_current_user: ContextVar[Optional[str]] = ContextVar("mcp_user_id", default=None)

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "Google Employee"


def get_current_mcp_user() -> str:
    """Get user ID for current MCP request. Raises if not authenticated."""
    user_id = _current_user.get()
    if not user_id:
        raise HTTPException(status_code=401, detail="MCP requires Authorization: Bearer <api_key>")
    return user_id


def _get_creds(user_id: str):
    """Load credentials for user."""
    from auth.google_oauth import dict_to_credentials
    from storage import load_credentials

    data = load_credentials(user_id)
    if not data:
        raise HTTPException(status_code=401, detail="User not authenticated. Complete OAuth at /auth/google")
    return dict_to_credentials(data)


def _handle_initialize(params: dict) -> dict:
    """MCP initialize handshake."""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
    }


def _handle_tools_list() -> dict:
    """Return list of available tools."""
    return {
        "tools": [
            {
                "name": "smart_inbox",
                "description": "Summarize Gmail inbox and suggest draft replies via Oshaani agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "Custom request (optional)",
                            "default": "Summarize my inbox and highlight urgent items.",
                        },
                    },
                },
            },
            {
                "name": "first_email_draft",
                "description": "Read first email from inbox, send to Oshaani for draft reply, create Gmail draft",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "Custom prompt for the AI (optional)",
                        },
                    },
                },
            },
            {
                "name": "chat_spaces",
                "description": "List Google Chat spaces for the user",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "document_intelligence",
                "description": "Summarize Drive documents and activity via Oshaani",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "string",
                            "description": "Custom request (optional)",
                        },
                    },
                },
            },
            {
                "name": "chat_auto_reply",
                "description": "Auto-reply to latest Chat message using Oshaani agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Chat space name (e.g. spaces/xxx)"},
                    },
                    "required": ["space_name"],
                },
            },
            {
                "name": "run_all_workflows",
                "description": "Run all workflows (smart inbox, document intelligence, chat auto-reply)",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "list_task_lists",
                "description": "List Google Task lists for the user",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "list_tasks",
                "description": "List tasks in a task list (use task_list_id from list_task_lists)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_list_id": {
                            "type": "string",
                            "description": "Task list ID (from list_task_lists)",
                        },
                        "show_completed": {
                            "type": "boolean",
                            "description": "Include completed tasks",
                            "default": False,
                        },
                    },
                    "required": ["task_list_id"],
                },
            },
            {
                "name": "create_task",
                "description": "Create a task in Google Tasks (stores in 'Google Employee' list by default)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "notes": {"type": "string", "description": "Task notes (optional)"},
                        "task_list_id": {
                            "type": "string",
                            "description": "Task list ID (optional, default: Google Employee)",
                        },
                    },
                    "required": ["title"],
                },
            },
        ],
    }


def _handle_tools_call(name: str, arguments: dict) -> dict:
    """Execute a tool with the current user's credentials."""
    user_id = get_current_mcp_user()
    creds = _get_creds(user_id)

    from services.orchestrator import WorkflowOrchestrator
    from services.google_data import fetch_chat_spaces

    orchestrator = WorkflowOrchestrator()

    if name == "smart_inbox":
        req = (arguments or {}).get("request") or "Summarize my inbox and highlight urgent items. Suggest draft replies for the top 3 emails."
        result = orchestrator.run_smart_inbox(creds, user_request=req)
        return {"content": [{"type": "text", "text": str(result.get("response", result))}]}

    elif name == "first_email_draft":
        req = (arguments or {}).get("request")
        result = orchestrator.run_first_email_draft(creds, user_request=req)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif name == "chat_spaces":
        spaces = fetch_chat_spaces(creds)
        return {"content": [{"type": "text", "text": json.dumps(spaces, indent=2)}]}

    elif name == "document_intelligence":
        req = (arguments or {}).get("request") or "What are the key documents in my Drive? Summarize recent activity."
        result = orchestrator.run_document_intelligence(creds, user_request=req)
        return {"content": [{"type": "text", "text": str(result.get("response", result))}]}

    elif name == "chat_auto_reply":
        space_name = (arguments or {}).get("space_name")
        if not space_name:
            return {"content": [{"type": "text", "text": "Error: space_name is required"}]}
        result = orchestrator.run_chat_auto_reply(creds, space_name, reply_to_latest=1)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif name == "run_all_workflows":
        from services.automation import run_all_workflows_for_user

        result = run_all_workflows_for_user(user_id, creds)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif name == "list_task_lists":
        from services.tasks_service import list_task_lists as _list_task_lists

        lists = _list_task_lists(creds)
        return {"content": [{"type": "text", "text": json.dumps(lists, indent=2)}]}

    elif name == "list_tasks":
        task_list_id = (arguments or {}).get("task_list_id")
        if not task_list_id:
            return {"content": [{"type": "text", "text": "Error: task_list_id is required"}]}
        from services.tasks_service import list_tasks as _list_tasks

        show_completed = (arguments or {}).get("show_completed", False)
        tasks = _list_tasks(creds, task_list_id, show_completed=show_completed)
        return {"content": [{"type": "text", "text": json.dumps(tasks, indent=2)}]}

    elif name == "create_task":
        title = (arguments or {}).get("title")
        if not title:
            return {"content": [{"type": "text", "text": "Error: title is required"}]}
        from services.tasks_service import create_task as _create_task

        notes = (arguments or {}).get("notes")
        task_list_id = (arguments or {}).get("task_list_id")
        task = _create_task(creds, title=title, notes=notes, task_list_id=task_list_id)
        if not task:
            return {"content": [{"type": "text", "text": "Failed to create task"}]}
        return {"content": [{"type": "text", "text": json.dumps(task, indent=2)}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def _dispatch_method(method: str, params: Optional[dict]) -> dict:
    """Dispatch MCP JSON-RPC method."""
    if method == "initialize":
        return _handle_initialize(params or {})
    elif method == "tools/list":
        return _handle_tools_list()
    elif method == "tools/call":
        name = (params or {}).get("name", "")
        arguments = (params or {}).get("arguments") or {}
        return _handle_tools_call(name, arguments)
    elif method == "initialized":
        return {}
    else:
        raise ValueError(f"Unknown method: {method}")


router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("")
@router.get("/")
async def mcp_info():
    """MCP endpoint info. Use POST with JSON-RPC and Authorization: Bearer <api_key>."""
    return {
        "protocol": "MCP",
        "transport": "HTTP JSON-RPC",
        "auth": "Authorization: Bearer <api_key>",
        "methods": ["initialize", "tools/list", "tools/call"],
        "tools": ["smart_inbox", "first_email_draft", "chat_spaces", "document_intelligence", "chat_auto_reply", "run_all_workflows", "list_task_lists", "list_tasks", "create_task"],
    }


async def _resolve_user(request: Request) -> Optional[str]:
    """Extract user_id from Authorization header (API key)."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    api_key = auth[7:].strip()
    if not api_key:
        return None
    from storage import get_user_by_api_key

    return get_user_by_api_key(api_key)


@router.post("")
@router.post("/")
async def mcp_handler(request: Request):
    """
    MCP JSON-RPC endpoint. Requires Authorization: Bearer <api_key>.

    Supports: initialize, tools/list, tools/call
    """
    user_id = await _resolve_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="MCP requires Authorization: Bearer <api_key>. Get key from POST /api-key")

    _current_user.set(user_id)
    body = {}
    try:
        payload = await request.json()
        # Support batch (array) or single request
        if isinstance(payload, list):
            results = []
            for req in payload:
                body = req
                req_id = body.get("id")
                method = body.get("method")
                params = body.get("params")
                if method:
                    result = _dispatch_method(method, params)
                    results.append({"jsonrpc": "2.0", "id": req_id, "result": result})
            return results if len(results) > 1 else (results[0] if results else {})
        body = payload
        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params")

        if not method:
            raise HTTPException(status_code=400, detail="Missing method")

        result = _dispatch_method(method, params)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    except ValueError as e:
        return {"jsonrpc": "2.0", "id": body.get("id", 0), "error": {"code": -32601, "message": str(e)}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("MCP error: %s", e)
        return {"jsonrpc": "2.0", "id": body.get("id", 0), "error": {"code": -32603, "message": str(e)}}
    finally:
        _current_user.set(None)
