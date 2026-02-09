"""
Google Employee - Multi-user FastAPI application.

Access Google data (emails, chat, workspace) via OAuth and integrate with Oshaani
AI agents for automated smart work.
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from logging_config import setup_logging

logger = logging.getLogger("google_employee")

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from auth.deps import get_current_user
from auth.google_oauth import (
    credentials_to_dict,
    dict_to_credentials,
    exchange_code_for_credentials,
    get_authorization_url,
)
from config import (
    APP_BASE_URL,
    AUTOMATION_CHAT_AUTO_REPLY_ENABLED,
    AUTOMATION_ENABLED,
    AUTOMATION_INTERVAL_MINUTES,
    SECRET_KEY,
)
from mcp_server.server import router as mcp_router
from services.orchestrator import WorkflowOrchestrator
from storage import generate_api_key, load_credentials, list_users, save_credentials

app = FastAPI(
    title="Google Employee",
    description="Multi-user app: access Google data via OAuth and integrate with Oshaani AI agents.",
    version="0.2.0",
)


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions (re-raise HTTPException for proper handling)."""
    from fastapi.responses import JSONResponse

    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=14 * 24 * 3600)

# MCP server with per-user credentials
app.include_router(mcp_router)

_scheduler = None


def _run_automation_for_all_users():
    """Run all workflows for every user with credentials."""
    if not AUTOMATION_ENABLED:
        return
    include_chat = AUTOMATION_CHAT_AUTO_REPLY_ENABLED
    users = list_users()
    if not users:
        return
    logger.info("Running automation for %d user(s)", len(users))
    for user_id in users:
        try:
            cred_data = load_credentials(user_id)
            if not cred_data:
                continue
            from auth.google_oauth import dict_to_credentials
            from services.automation import run_all_workflows_for_user

            creds_obj = dict_to_credentials(cred_data)
            run_all_workflows_for_user(user_id, creds_obj, include_chat_auto_reply=include_chat)
            logger.info("Automation completed for %s", user_id)
        except Exception as e:
            logger.warning("Automation failed for %s: %s", user_id, e)


def _get_user_creds(user_id: str):
    """Load and return credentials for user."""
    data = load_credentials(user_id)
    if not data:
        logger.warning("Auth failed: no credentials for %s", user_id)
        raise HTTPException(status_code=401, detail="Not authenticated. Please complete Google OAuth first.")
    return dict_to_credentials(data)


@app.get("/")
def root():
    """Root - multi-user API. Sign in via /auth/google or use API key."""
    return {
        "message": "Google Employee API (multi-user)",
        "docs": "/docs",
        "auth": "/auth/google",
        "logout": "/auth/logout",
        "me": "/me",
        "automation": f"Enabled (every {AUTOMATION_INTERVAL_MINUTES} min)" if AUTOMATION_ENABLED else "Disabled",
        "api_key": "POST /api-key (requires auth)",
        "mcp": "/mcp (MCP server, use Authorization: Bearer <api_key>)",
        "workflows": {
            "smart-inbox": "/workflows/smart-inbox",
            "chat-assistant": "/workflows/chat-assistant",
            "chat-auto-reply": "/workflows/chat-auto-reply",
            "chat-spaces": "/workflows/chat-spaces",
            "first-email-draft": "/workflows/first-email-draft",
        },
        "tasks": "/tasks/lists",
    }


@app.get("/auth/google")
def auth_google():
    """Start Google OAuth flow."""
    try:
        url = get_authorization_url()
        logger.info("Redirecting to Google OAuth")
        return RedirectResponse(url=url)
    except ValueError as e:
        logger.error("OAuth config error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
            + " Copy .env.example to .env and add your Google OAuth credentials.",
        )


@app.get("/auth/google/callback")
def auth_google_callback(request: Request, code: str = Query(...)):
    """Handle OAuth callback - exchange code for tokens, set session, redirect."""
    import httpx

    logger.debug("Processing OAuth callback")
    creds = exchange_code_for_credentials(code)
    with httpx.Client() as client:
        resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        resp.raise_for_status()
        user_info = resp.json()
    email = user_info.get("email", "default")

    save_credentials(email, credentials_to_dict(creds))
    request.session["user_id"] = email
    logger.info("User logged in: %s", email)
    return RedirectResponse(url=f"{APP_BASE_URL}/me", status_code=302)


@app.get("/auth/logout")
def auth_logout_get(request: Request):
    """Logout URL: clear session and redirect to Google login for fresh sign-in."""
    request.session.clear()
    logger.info("User logged out")
    return RedirectResponse(url=f"{APP_BASE_URL}/auth/google", status_code=302)


@app.post("/auth/logout")
def auth_logout_post(request: Request):
    """Clear session (API). For browser logout with redirect, use GET /auth/logout."""
    request.session.clear()
    return {"message": "Logged out"}


@app.get("/me")
def get_me(user_id: Annotated[str, Depends(get_current_user)]):
    """Current user info. Requires session (browser) or Authorization: Bearer <api_key>."""
    return {
        "user_id": user_id,
        "authenticated": True,
        "automation": "Active" if AUTOMATION_ENABLED else "Disabled",
        "automation_interval_minutes": AUTOMATION_INTERVAL_MINUTES,
        "chat_auto_reply": "Active" if AUTOMATION_CHAT_AUTO_REPLY_ENABLED else "Disabled",
        "api_key": "POST /api-key to generate (for scripts/cron)",
        "drive_data": "GET /me/drive-data to fetch your stored data from Drive",
    }


@app.get("/me/drive-data")
def get_drive_data(user_id: Annotated[str, Depends(get_current_user)]):
    """Fetch user data stored in the user's Google Drive (Google Employee folder)."""
    creds = _get_user_creds(user_id)
    try:
        from services.drive_storage import load_user_data_from_drive

        data = load_user_data_from_drive(creds, user_id)
        if data is None:
            return {"message": "No data in Drive yet. Complete a workflow to sync."}
        # Don't expose raw credentials/tokens
        return {
            "user_id": data.get("user_id"),
            "stored_at": "Google Drive / Google Employee / user_data.json",
            "has_credentials": "credentials" in data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api-key")
def create_api_key(user_id: Annotated[str, Depends(get_current_user)]):
    """Generate a new API key for programmatic access. Show once."""
    key = generate_api_key(user_id)
    return {"api_key": key, "message": "Save this key; it won't be shown again."}


@app.post("/workflows/smart-inbox")
def workflow_smart_inbox(
    user_id: Annotated[str, Depends(get_current_user)],
    request: Optional[str] = Query(
        None,
        description="Custom request for the agent",
    ),
    create_tasks: bool = Query(True, description="Create Google Tasks from action items in response"),
):
    """
    Run smart inbox workflow: fetch emails, send to Oshaani agent for summarization
    and draft replies. Action items output as 'TASK: title | notes' are stored in Google Tasks.
    """
    logger.info("Smart inbox workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    orchestrator = WorkflowOrchestrator()
    user_request = request or "Summarize my inbox and highlight urgent items. Suggest draft replies for the top 3 emails."
    return orchestrator.run_smart_inbox(creds, user_request=user_request, create_tasks=create_tasks, user_id=user_id)


@app.post("/workflows/chat-assistant")
def workflow_chat_assistant(
    user_id: Annotated[str, Depends(get_current_user)],
    request: str = Query(..., description="What you want the agent to do with chat data"),
    space_name: Optional[str] = Query(None),
):
    """Run chat assistant workflow: analyze Chat messages via Oshaani."""
    logger.info("Chat assistant workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    orchestrator = WorkflowOrchestrator()
    return orchestrator.run_chat_assistant(creds, request, space_name=space_name, user_id=user_id)


@app.post("/workflows/chat-auto-reply")
def workflow_chat_auto_reply(
    user_id: Annotated[str, Depends(get_current_user)],
    space_name: str = Query(..., description="Chat space name (e.g. spaces/xxx). Only one-to-one DMs supported."),
    reply_to_latest: int = Query(1, ge=1, le=5, description="Number of latest messages to reply to"),
    prompt: Optional[str] = Query(None, description="Custom system prompt for the agent"),
):
    """
    Auto-reply to Google Chat (one-to-one DMs only). Does not reply if last message is yours.
    Use GET /workflows/chat-spaces to list your spaces (filter by type=DIRECT_MESSAGE).
    """
    logger.info("Chat auto-reply workflow for %s, space %s", user_id, space_name)
    from services.google_data import get_space_type

    creds = _get_user_creds(user_id)
    space_type = get_space_type(creds, space_name)
    orchestrator = WorkflowOrchestrator()
    return orchestrator.run_chat_auto_reply(
        creds, space_name, user_id=user_id, reply_to_latest=reply_to_latest,
        system_prompt=prompt, space_type=space_type
    )


@app.get("/workflows/chat-spaces")
def list_chat_spaces(user_id: Annotated[str, Depends(get_current_user)]):
    """List Google Chat spaces (use space name in chat-auto-reply)."""
    from services.google_data import fetch_chat_spaces

    creds = _get_user_creds(user_id)
    spaces = fetch_chat_spaces(creds)
    result = {"spaces": spaces}
    if not spaces:
        result["hint"] = (
            "Chat API returned empty. Ensure: 1) Chats have at least one message, "
            "2) You have chat.spaces.readonly scope and re-authenticated, "
            "3) Google Workspace accounts have full support; consumer Gmail may have limits."
        )
    return result


@app.post("/workflows/document-intelligence")
def workflow_document_intelligence(
    user_id: Annotated[str, Depends(get_current_user)],
    request: Optional[str] = Query(None),
):
    """Run document intelligence: analyze Drive/Docs via Oshaani."""
    logger.info("Document intelligence workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    orchestrator = WorkflowOrchestrator()
    user_request = request or "What are the key documents in my Drive? Summarize recent activity."
    return orchestrator.run_document_intelligence(creds, user_request=user_request, user_id=user_id)


@app.post("/workflows/first-email-draft")
def workflow_first_email_draft(
    user_id: Annotated[str, Depends(get_current_user)],
    request: Optional[str] = Query(
        None,
        description="Custom prompt for the AI (e.g. tone, length). Default: draft a professional reply.",
    ),
    subject: Optional[str] = Query(
        None,
        description="Match email by subject (partial match). If omitted, uses first email in inbox.",
    ),
):
    """
    Read email from inbox, send to Oshaani for draft reply, create Gmail draft.
    Use subject param to target a specific email. The draft appears in Gmail Drafts.
    """
    logger.info("First email draft workflow for %s (subject=%s)", user_id, subject)
    creds = _get_user_creds(user_id)
    orchestrator = WorkflowOrchestrator()
    return orchestrator.run_first_email_draft(
        creds, user_request=request, subject_filter=subject, user_id=user_id
    )


@app.post("/workflows/custom")
def workflow_custom(
    user_id: Annotated[str, Depends(get_current_user)],
    request: str = Query(..., description="Your request for the agent"),
    include_emails: int = Query(10, ge=0, le=50),
    include_chat: bool = Query(True),
    include_drive: int = Query(10, ge=0, le=50),
):
    """Run a fully customizable workflow with your specified Google data."""
    logger.info("Custom workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    orchestrator = WorkflowOrchestrator()
    return orchestrator.run_custom(
        creds,
        request,
        include_emails=include_emails,
        include_chat=include_chat,
        include_drive=include_drive,
        user_id=user_id,
    )


@app.post("/workflows/run-all")
def run_all_workflows_now(user_id: Annotated[str, Depends(get_current_user)]):
    """
    Manually trigger all workflows (smart inbox, document intelligence, chat auto-reply).
    Also runs automatically on schedule when automation is enabled.
    """
    logger.info("Run-all workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    from services.automation import run_all_workflows_for_user

    return run_all_workflows_for_user(user_id, creds)


# --- Google Tasks ---

@app.get("/tasks/lists")
def list_task_lists(user_id: Annotated[str, Depends(get_current_user)]):
    """List Google Task lists. Tasks are stored in 'Google Employee' by default."""
    from services.tasks_service import list_task_lists as _list_task_lists

    creds = _get_user_creds(user_id)
    lists = _list_task_lists(creds)
    return {"task_lists": lists}


@app.get("/tasks/lists/{task_list_id}/tasks")
def list_tasks(
    user_id: Annotated[str, Depends(get_current_user)],
    task_list_id: str,
    show_completed: bool = Query(False, description="Include completed tasks"),
):
    """List tasks in a task list."""
    from services.tasks_service import list_tasks as _list_tasks

    creds = _get_user_creds(user_id)
    tasks = _list_tasks(creds, task_list_id, show_completed=show_completed)
    return {"tasks": tasks}


@app.post("/tasks")
def create_task(
    user_id: Annotated[str, Depends(get_current_user)],
    title: str = Query(..., description="Task title"),
    notes: Optional[str] = Query(None, description="Task notes"),
    task_list_id: Optional[str] = Query(None, description="Task list ID (default: Google Employee)"),
):
    """Create a task in Google Tasks. Uses 'Google Employee' list if not specified."""
    from services.tasks_service import create_task as _create_task

    creds = _get_user_creds(user_id)
    task = _create_task(creds, title=title, notes=notes, task_list_id=task_list_id)
    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return task


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/health/oshaani")
def health_oshaani():
    """
    Test Oshaani.com AI integration. Returns connectivity status.
    No auth required - useful to verify OSHAANI_AGENT_API_KEY is valid.
    """
    from config import OSHAANI_AGENT_API_KEY, OSHAANI_API_BASE_URL
    from services.oshaani_client import OshaaniClient

    if not OSHAANI_AGENT_API_KEY:
        return {"status": "error", "message": "OSHAANI_AGENT_API_KEY not set in .env"}
    try:
        client = OshaaniClient()
        result = client.chat_sync("Hi, reply with OK if you can read this.")
        # Oshaani may return {"response": "..."} or {"message": "..."}
        reply = result.get("response") or result.get("message") or result.get("text") or str(result)[:200]
        return {"status": "ok", "message": "Oshaani connected", "reply_preview": str(reply)[:100]}
    except Exception as e:
        logger.warning("Oshaani health check failed: %s", e)
        return {"status": "error", "message": str(e)}


@app.on_event("startup")
def startup_event():
    """Configure logging and start automation scheduler."""
    setup_logging()
    logger.info("Application starting")

    global _scheduler
    if AUTOMATION_ENABLED:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _run_automation_for_all_users,
            "interval",
            minutes=AUTOMATION_INTERVAL_MINUTES,
            id="automation",
        )
        _scheduler.start()
        logger.info("Automation scheduler started (interval: %d min)", AUTOMATION_INTERVAL_MINUTES)
        # Run once after a short delay to let app fully load
        import threading
        threading.Timer(10, _run_automation_for_all_users).start()


@app.on_event("shutdown")
def shutdown_event():
    """Stop automation scheduler on shutdown."""
    logger.info("Application shutting down")
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
