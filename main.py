"""
Johny Sins - Multi-user FastAPI application.

Access Google data (emails, chat, workspace) via OAuth and integrate with Oshaani
AI agents for automated smart work.
"""
from __future__ import annotations

import html
import logging
from typing import Annotated, Optional

from logging_config import setup_logging

logger = logging.getLogger("google_employee")

from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
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
    APP_ORIGIN,
    AUTOMATION_CHAT_AUTO_REPLY_ENABLED,
    AUTOMATION_ENABLED,
    AUTOMATION_INTERVAL_MINUTES,
    CORS_ORIGINS,
    DATA_DIR,
    PRODUCTION,
    SECRET_KEY,
)
from mcp_server.server import router as mcp_router
from storage import (
    generate_api_key,
    get_user_automation_enabled,
    get_user_oshaani_key,
    get_user_workflow_toggles,
    load_credentials,
    list_users,
    save_credentials,
    set_user_automation_enabled,
    set_user_oshaani_key,
    set_user_workflow_toggles,
)

app = FastAPI(
    title="Johny Sins",
    description="Multi-user app: access Google data via OAuth and integrate with Oshaani AI agents.",
    version="0.2.0",
    docs_url="/docs" if not PRODUCTION else None,
    redoc_url="/redoc" if not PRODUCTION else None,
)


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions (re-raise HTTPException for proper handling). Return clear error detail for UI."""
    from fastapi.responses import JSONResponse

    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception: %s", exc)
    # In production return generic message; in dev return actual error so UI can show it
    detail = "Internal server error" if PRODUCTION else str(exc)
    return JSONResponse(status_code=500, content={"detail": detail})


# CORS: in production allow only APP_BASE_URL (or CORS_ORIGINS); in dev allow common origins
_cors_origins = CORS_ORIGINS if CORS_ORIGINS else ([APP_BASE_URL] if PRODUCTION else ["http://localhost:8000", "http://127.0.0.1:8000", APP_BASE_URL])
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Session: secure cookies in production (HTTPS)
_session_https_only = PRODUCTION and APP_BASE_URL.startswith("https:")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=_session_https_only,
)

# MCP server with per-user credentials
app.include_router(mcp_router)

# UI: static files and templates (Jinja2 required for /app)
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = None
if TEMPLATES_DIR.exists():
    try:
        templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    except Exception as e:
        logger.warning("Templates disabled (install jinja2 for /app UI): %s", e)

_scheduler = None


def _run_automation_for_all_users():
    """Run all workflows for every user with credentials."""
    logger.debug("Automation job started (AUTOMATION_ENABLED=%s, AUTOMATION_CHAT_AUTO_REPLY_ENABLED=%s)",
                 AUTOMATION_ENABLED, AUTOMATION_CHAT_AUTO_REPLY_ENABLED)
    if not AUTOMATION_ENABLED:
        logger.debug("Automation job skipped: AUTOMATION_ENABLED is False")
        return
    include_chat = AUTOMATION_CHAT_AUTO_REPLY_ENABLED
    users = list_users()
    logger.debug("Automation job: list_users() returned %d user(s): %s", len(users), users)
    if not users:
        logger.debug("Automation job finished: no users")
        return
    logger.info("Running automation for %d user(s)", len(users))
    processed = 0
    skipped = 0
    failed = 0
    for user_id in users:
        try:
            automation_on = get_user_automation_enabled(user_id)
            logger.debug("User %s: automation_enabled=%s", user_id, automation_on)
            if not automation_on:
                skipped += 1
                logger.debug("User %s: skipped (automation toggle off)", user_id)
                continue
            cred_data = load_credentials(user_id)
            if not cred_data:
                skipped += 1
                logger.debug("User %s: skipped (no credentials)", user_id)
                continue
            from auth.google_oauth import dict_to_credentials
            from services.automation import run_all_workflows_for_user
            from storage import get_user_oshaani_key, get_user_workflow_toggles

            creds_obj = dict_to_credentials(cred_data)
            toggles = get_user_workflow_toggles(user_id)
            include_si = toggles.get("smart_inbox", True)
            include_di = toggles.get("document_intelligence", True)
            include_car = toggles.get("chat_auto_reply", True) and include_chat
            user_key = get_user_oshaani_key(user_id)
            logger.debug("User %s: toggles smart_inbox=%s document_intelligence=%s chat_auto_reply=%s (include_chat=%s), oshaani_key_set=%s",
                         user_id, include_si, include_di, include_car, include_chat, bool(user_key))
            result = run_all_workflows_for_user(
                user_id,
                creds_obj,
                include_smart_inbox=include_si,
                include_document_intelligence=include_di,
                include_chat_auto_reply=include_car,
                oshaani_api_key=user_key,
            )
            processed += 1
            logger.debug("User %s: run_all_workflows_for_user result: workflows=%s errors=%s",
                         user_id, result.get("workflows"), result.get("errors"))
            logger.info("Automation completed for %s", user_id)
        except Exception as e:
            failed += 1
            logger.warning("Automation failed for %s: %s", user_id, e)
            logger.debug("Automation exception for %s", user_id, exc_info=True)
    logger.debug("Automation job finished: processed=%d skipped=%d failed=%d", processed, skipped, failed)


def _get_user_creds(user_id: str):
    """Load and return credentials for user."""
    data = load_credentials(user_id)
    if not data:
        logger.warning("Auth failed: no credentials for %s", user_id)
        raise HTTPException(status_code=401, detail="Not authenticated. Please complete Google OAuth first.")
    return dict_to_credentials(data)


def _get_orchestrator_for_user(user_id: str) -> "WorkflowOrchestrator":
    """Build orchestrator using the user's Oshaani API key if set, else default."""
    from services.oshaani_client import OshaaniClient
    from services.orchestrator import WorkflowOrchestrator
    user_key = get_user_oshaani_key(user_id)
    client = OshaaniClient(api_key=user_key or None)
    return WorkflowOrchestrator(oshaani_client=client)


@app.get("/")
def root(request: Request):
    """Root: redirect browsers to /app (UI), return JSON for API."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and templates:
        return RedirectResponse(url="/app", status_code=302)
    return {
        "message": "Johny Sins API (multi-user)",
        "docs": "/docs",
        "app": "/app",
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


@app.get("/app")
def app_ui(request: Request):
    """Serve the web UI: landing when logged out, dashboard when logged in."""
    if not templates:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            status_code=200,
            content="""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Johny Sins</title></head><body style="font-family:system-ui;max-width:480px;margin:3rem auto;padding:1rem;">
            <h1>Web UI not loaded</h1>
            <p>Install <code>jinja2</code> and restart the server:</p>
            <pre style="background:#eee;padding:1rem;border-radius:6px;">pip install jinja2</pre>
            <p><a href="/docs">API docs</a> · <a href="/auth/google">Sign in with Google</a></p>
            </body></html>""",
        )
    user_id = request.session.get("user_id")
    user_automation_enabled = get_user_automation_enabled(user_id) if user_id else True
    # Explicit for template: only output "checked" when True (avoids type/truthiness issues)
    automation_checked_attr = "checked" if user_automation_enabled else ""
    # Header "Chat auto-reply" badge reflects user's workflow toggle (and server allows it)
    toggles = get_user_workflow_toggles(user_id) if user_id else {}
    chat_auto_reply_on = AUTOMATION_CHAT_AUTO_REPLY_ENABLED and toggles.get("chat_auto_reply", True)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "user_id": user_id,
            "automation_enabled": AUTOMATION_ENABLED,
            "user_automation_enabled": user_automation_enabled,
            "automation_checked_attr": automation_checked_attr,
            "automation_interval": AUTOMATION_INTERVAL_MINUTES,
            "chat_auto_reply": chat_auto_reply_on,
        },
    )


@app.get("/auth/google/auth/google")
def auth_google_fix_double_path():
    """Redirect duplicated path to correct OAuth URL (e.g. from misconfigured APP_BASE_URL)."""
    return RedirectResponse(url=f"{APP_ORIGIN}/auth/google", status_code=302)


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
    from fastapi.responses import HTMLResponse, JSONResponse

    try:
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
        return RedirectResponse(url="/app", status_code=302)
    except Exception as e:
        logger.exception("OAuth callback failed: %s", e)
        err_msg = str(e)
        err_lower = err_msg.lower()
        is_scope_error = "scope" in err_lower or "invalid_grant" in err_lower
        data_path = str(DATA_DIR)
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            if is_scope_error:
                body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Re-authorize required</title></head><body style="font-family:system-ui;max-width:560px;margin:2rem auto;padding:1rem;">
                <h1>Re-authorize required</h1>
                <p>Google reported: <strong>Scope has changed</strong> or <strong>invalid_grant</strong>. This usually means the app&rsquo;s permissions were updated. You need to sign in again with the new permissions.</p>
                <p><strong>What to do:</strong></p>
                <ol>
                <li><a href="https://myaccount.google.com/permissions">Open your Google account permissions</a>, find this app, and remove access (optional but ensures a clean re-auth).</li>
                <li>Click below to <a href="/auth/google">Sign in with Google</a> again.</li>
                </ol>
                <p><a href="/auth/google" style="display:inline-block;margin-top:0.5rem;padding:0.5rem 1rem;background:#1a73e8;color:white;text-decoration:none;border-radius:4px;">Sign in with Google</a> &middot; <a href="/">Home</a></p>
                </body></html>"""
            else:
                hint = f"Data directory: {data_path} — ensure it exists and is writable. Credentials are also saved to your Google Drive."
                body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Login failed</title></head><body style="font-family:system-ui;max-width:560px;margin:2rem auto;padding:1rem;">
                <h1>Login failed</h1>
                <p><strong>Error:</strong> {html.escape(err_msg)}</p>
                <p><strong>Data directory:</strong> <code style="word-break:break-all;">{html.escape(data_path)}</code></p>
                <p>{html.escape(hint)}</p>
                <p><a href="/auth/google">Try again</a> &middot; <a href="/">Home</a></p>
                </body></html>"""
            return HTMLResponse(status_code=500, content=body)
        hint = "Re-authorize: revoke app access at myaccount.google.com/permissions then sign in again." if is_scope_error else f"Data directory: {data_path}"
        return JSONResponse(
            status_code=500,
            content={"detail": "Login failed", "error": err_msg, "hint": hint, "data_dir": data_path},
        )


@app.get("/auth/logout")
def auth_logout_get(request: Request):
    """Logout URL: clear session and redirect to Google login for fresh sign-in."""
    request.session.clear()
    logger.info("User logged out")
    return RedirectResponse(url=f"{APP_ORIGIN}/auth/google", status_code=302)


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
    """Fetch user data stored in the user's Google Drive (Johny Sins folder)."""
    creds = _get_user_creds(user_id)
    try:
        from services.drive_storage import load_user_data_from_drive

        data = load_user_data_from_drive(creds, user_id)
        if data is None:
            return {"message": "No data in Drive yet. Complete a workflow to sync."}
        # Don't expose raw credentials/tokens
        return {
            "user_id": data.get("user_id"),
            "stored_at": "Google Drive / Johny Sins / user_data.json",
            "has_credentials": "credentials" in data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api-key")
def create_api_key(user_id: Annotated[str, Depends(get_current_user)]):
    """Generate a new API key for programmatic access. Show once."""
    key = generate_api_key(user_id)
    return {"api_key": key, "message": "Save this key; it won't be shown again."}


@app.get("/me/oshaani-key")
def get_oshaani_key_status(user_id: Annotated[str, Depends(get_current_user)]):
    """Return whether the user has set their own Oshaani API key (key value not returned)."""
    key = get_user_oshaani_key(user_id)
    return {
        "set": bool(key),
        "hint": "User personal key enabled" if key else "Using default key from server config",
    }


@app.put("/me/oshaani-key")
def save_oshaani_key(
    user_id: Annotated[str, Depends(get_current_user)],
    body: dict = Body(default={}, embed=False),
):
    """Save or clear the user's Oshaani API key. Body: {"oshaani_api_key": "..."} or {"oshaani_api_key": ""} to clear. Stored in your Google Drive."""
    if not isinstance(body, dict):
        body = {}
    api_key = (body.get("oshaani_api_key") or "").strip()
    if api_key:
        try:
            from services.oshaani_client import validate_oshaani_api_key
            validate_oshaani_api_key(api_key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    try:
        set_user_oshaani_key(user_id, api_key)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("PUT /me/oshaani-key failed")
        raise HTTPException(status_code=500, detail=f"Failed to save to Drive: {e!s}")
    return {"message": "Saved to your Google Drive." if api_key else "Cleared. Using default key."}


@app.post("/me/oshaani-key/test")
def test_oshaani_key(
    user_id: Annotated[str, Depends(get_current_user)],
    body: dict = Body(default={}, embed=False),
):
    """Test an Oshaani API key without saving. Body: {"oshaani_api_key": "..."} to test that key, or omit to test the user's saved key."""
    from services.oshaani_client import validate_oshaani_api_key

    if not isinstance(body, dict):
        body = {}
    api_key = (body.get("oshaani_api_key") or "").strip()
    if not api_key:
        api_key = get_user_oshaani_key(user_id) or ""
        if not api_key:
            raise HTTPException(status_code=400, detail="No key to test. Enter a key in the box above or save one first.")
    try:
        validate_oshaani_api_key(api_key)
        return {"valid": True, "message": "Oshaani API key is valid and accepted by the server."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/me/workflow-toggles")
def get_workflow_toggles(user_id: Annotated[str, Depends(get_current_user)]):
    """Return current workflow on/off toggles (smart_inbox, document_intelligence, chat_auto_reply, first_email_draft, chat_spaces)."""
    return get_user_workflow_toggles(user_id)


@app.put("/me/workflow-toggles")
def save_workflow_toggles(
    user_id: Annotated[str, Depends(get_current_user)],
    body: dict = Body(default={}, embed=False),
):
    """Update one or more workflow toggles. Body: { \"workflow_id\": true|false, ... } (e.g. smart_inbox, document_intelligence)."""
    if not isinstance(body, dict):
        body = {}
    try:
        set_user_workflow_toggles(user_id, body)
        return {"toggles": get_user_workflow_toggles(user_id)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/me/automation")
def get_automation_status(user_id: Annotated[str, Depends(get_current_user)]):
    """Return whether scheduled Run-all automation is on for this user."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"enabled": get_user_automation_enabled(user_id)},
        headers={"Cache-Control": "no-store"},
    )


@app.put("/me/automation")
def set_automation_status(
    user_id: Annotated[str, Depends(get_current_user)],
    body: dict = Body(default={}, embed=False),
):
    """Turn scheduled Run-all automation on or off for this user. Body: { \"enabled\": true|false }."""
    if not isinstance(body, dict):
        body = {}
    raw = body.get("enabled", True)
    # Normalize: accept bool, "true"/"false", 1/0
    if isinstance(raw, bool):
        enabled = raw
    elif isinstance(raw, str):
        enabled = raw.strip().lower() in ("true", "1", "on", "yes")
    else:
        enabled = bool(raw)
    try:
        set_user_automation_enabled(user_id, enabled)
        return {"enabled": get_user_automation_enabled(user_id)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


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
    orchestrator = _get_orchestrator_for_user(user_id)
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
    orchestrator = _get_orchestrator_for_user(user_id)
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
    orchestrator = _get_orchestrator_for_user(user_id)
    return orchestrator.run_chat_auto_reply(
        creds, space_name, user_id=user_id, reply_to_latest=reply_to_latest,
        system_prompt=prompt, space_type=space_type
    )


@app.post("/workflows/chat-auto-reply-batch")
def workflow_chat_auto_reply_batch(
    user_id: Annotated[str, Depends(get_current_user)],
    limit: int = Query(5, ge=1, le=20, description="Max number of DM spaces to run (top N)"),
):
    """Run chat auto-reply for the first N DM spaces (default 5). Returns results per space."""
    from services.google_data import fetch_chat_spaces, get_space_type

    logger.info("Chat auto-reply batch for %s, limit=%d", user_id, limit)
    creds = _get_user_creds(user_id)
    orchestrator = _get_orchestrator_for_user(user_id)
    all_spaces = fetch_chat_spaces(creds)
    dm_spaces = [s for s in all_spaces if s.get("type") == "DIRECT_MESSAGE"]
    spaces_to_run = dm_spaces[:limit]
    results = []
    for space in spaces_to_run:
        try:
            space_type = get_space_type(creds, space["name"])
            r = orchestrator.run_chat_auto_reply(
                creds, space["name"], user_id=user_id, reply_to_latest=1, space_type=space_type
            )
            results.append({"space": space.get("displayName", space["name"]), "replies": r.get("replies", [])})
        except Exception as e:
            logger.warning("Chat auto-reply failed for space %s: %s", space.get("name"), e)
            results.append({"space": space.get("displayName", space["name"]), "error": str(e)})
    return {"total": len(results), "spaces": results}


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
    orchestrator = _get_orchestrator_for_user(user_id)
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
    orchestrator = _get_orchestrator_for_user(user_id)
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
    orchestrator = _get_orchestrator_for_user(user_id)
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
    Manually trigger all workflows that are toggled on (smart inbox, document intelligence, chat auto-reply).
    Also runs automatically on schedule when automation is enabled.
    """
    logger.info("Run-all workflow for %s", user_id)
    creds = _get_user_creds(user_id)
    from services.automation import run_all_workflows_for_user

    toggles = get_user_workflow_toggles(user_id)
    return run_all_workflows_for_user(
        user_id,
        creds,
        include_smart_inbox=toggles.get("smart_inbox", True),
        include_document_intelligence=toggles.get("document_intelligence", True),
        include_chat_auto_reply=toggles.get("chat_auto_reply", True),
        oshaani_api_key=get_user_oshaani_key(user_id),
    )


# --- Google Tasks ---

@app.get("/tasks/lists")
def list_task_lists(user_id: Annotated[str, Depends(get_current_user)]):
    """List Google Task lists. Tasks are stored in 'Johny Sins' by default."""
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
    task_list_id: Optional[str] = Query(None, description="Task list ID (default: Johny Sins)"),
):
    """Create a task in Google Tasks. Uses 'Johny Sins' list if not specified."""
    from services.tasks_service import create_task as _create_task

    creds = _get_user_creds(user_id)
    task = _create_task(creds, title=title, notes=notes, task_list_id=task_list_id)
    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return task


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_well_known():
    """Chrome DevTools probes this path; return empty so it does not 404."""
    from fastapi.responses import JSONResponse
    return JSONResponse(content={}, status_code=200)


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
    """Configure logging, ensure data dir is writable, and start automation scheduler."""
    setup_logging()
    logger.info("Application starting (production=%s)", PRODUCTION)
    try:
        from storage import ensure_data_dir_ready
        data_path = ensure_data_dir_ready()
        logger.info("Data directory ready: %s", data_path)
    except RuntimeError as e:
        logger.warning("Data directory check failed: %s — login may fail until DATA_DIR is writable", e)

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
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("1", "true", "yes") and not PRODUCTION
    workers = int(os.getenv("WORKERS", "1"))
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
        reload=reload,
        workers=workers,
    )
