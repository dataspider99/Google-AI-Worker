"""Run all workflows continuously for a user (automation)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from google.oauth2.credentials import Credentials

from services.google_data import fetch_chat_spaces
from services.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


def run_all_workflows_for_user(
    user_id: str,
    creds: Credentials,
    include_smart_inbox: bool = True,
    include_document_intelligence: bool = True,
    include_chat_auto_reply: bool = True,
    chat_spaces_limit: int = 3,
) -> dict[str, Any]:
    """
    Run all enabled workflows for a user. Returns aggregated results.
    """
    orchestrator = WorkflowOrchestrator()
    results = {"user_id": user_id, "workflows": {}, "errors": []}

    # 1. Smart Inbox
    if include_smart_inbox:
        try:
            r = orchestrator.run_smart_inbox(
                creds,
                user_request="Summarize my inbox and highlight urgent items. Suggest draft replies for the top 3 emails.",
            )
            smart_result = {"status": "ok", "response_preview": str(r.get("response", ""))[:200]}
            if r.get("tasks_created"):
                smart_result["tasks_created"] = len(r["tasks_created"])
            results["workflows"]["smart_inbox"] = smart_result
        except Exception as e:
            logger.exception("Smart inbox failed for %s", user_id)
            results["workflows"]["smart_inbox"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"smart_inbox: {e}")

    # 2. Document Intelligence
    if include_document_intelligence:
        try:
            r = orchestrator.run_document_intelligence(
                creds,
                user_request="What are the key documents in my Drive? Summarize recent activity.",
            )
            results["workflows"]["document_intelligence"] = {"status": "ok", "response_preview": str(r.get("response", ""))[:200]}
        except Exception as e:
            logger.exception("Document intelligence failed for %s", user_id)
            results["workflows"]["document_intelligence"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"document_intelligence: {e}")

    # 3. Chat Auto-Reply (for each space)
    if include_chat_auto_reply:
        try:
            spaces = fetch_chat_spaces(creds)
            chat_results = []
            for space in spaces[:chat_spaces_limit]:
                try:
                    r = orchestrator.run_chat_auto_reply(creds, space["name"], reply_to_latest=1)
                    chat_results.append({"space": space.get("displayName", space["name"]), "replies": r.get("replies", [])})
                except Exception as e:
                    logger.warning("Chat auto-reply failed for space %s: %s", space.get("name"), e)
                    chat_results.append({"space": space.get("displayName", space["name"]), "error": str(e)})
            results["workflows"]["chat_auto_reply"] = {"status": "ok", "spaces": chat_results}
        except Exception as e:
            logger.exception("Chat auto-reply failed for %s", user_id)
            results["workflows"]["chat_auto_reply"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"chat_auto_reply: {e}")

    return results
