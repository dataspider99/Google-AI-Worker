"""Run all workflows continuously for a user (automation)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from google.oauth2.credentials import Credentials

from services.google_data import fetch_chat_spaces
from services.oshaani_client import OshaaniClient
from services.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


def run_all_workflows_for_user(
    user_id: str,
    creds: Credentials,
    include_smart_inbox: bool = True,
    include_document_intelligence: bool = True,
    include_chat_auto_reply: bool = True,
    chat_spaces_limit: int = 10,
    oshaani_api_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run all enabled workflows for a user. Returns aggregated results.
    Uses oshaani_api_key if provided, else default from env.
    """
    logger.debug("run_all_workflows_for_user entry: user_id=%s include_smart_inbox=%s include_document_intelligence=%s "
                 "include_chat_auto_reply=%s chat_spaces_limit=%s", user_id, include_smart_inbox,
                 include_document_intelligence, include_chat_auto_reply, chat_spaces_limit)
    client = OshaaniClient(api_key=oshaani_api_key or None)
    orchestrator = WorkflowOrchestrator(oshaani_client=client)
    results = {"user_id": user_id, "workflows": {}, "errors": []}

    # 1. Smart Inbox
    if include_smart_inbox:
        try:
            logger.debug("User %s: starting workflow smart_inbox", user_id)
            r = orchestrator.run_smart_inbox(
                creds,
                user_request="Summarize my inbox and highlight urgent items. Suggest draft replies for the top 3 emails.",
                user_id=user_id,
            )
            smart_result = {"status": "ok", "response_preview": str(r.get("response", ""))[:200]}
            if r.get("tasks_created"):
                smart_result["tasks_created"] = len(r["tasks_created"])
            results["workflows"]["smart_inbox"] = smart_result
            logger.debug("User %s: smart_inbox completed: tasks_created=%s preview=%s",
                         user_id, smart_result.get("tasks_created"), smart_result.get("response_preview", "")[:80])
        except Exception as e:
            logger.exception("Smart inbox failed for %s", user_id)
            results["workflows"]["smart_inbox"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"smart_inbox: {e}")
            logger.debug("User %s: smart_inbox error: %s", user_id, e)

    # 2. Document Intelligence
    if include_document_intelligence:
        try:
            logger.debug("User %s: starting workflow document_intelligence", user_id)
            r = orchestrator.run_document_intelligence(
                creds,
                user_request="What are the key documents in my Drive? Summarize recent activity.",
                user_id=user_id,
            )
            results["workflows"]["document_intelligence"] = {"status": "ok", "response_preview": str(r.get("response", ""))[:200]}
            logger.debug("User %s: document_intelligence completed", user_id)
        except Exception as e:
            logger.exception("Document intelligence failed for %s", user_id)
            results["workflows"]["document_intelligence"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"document_intelligence: {e}")
            logger.debug("User %s: document_intelligence error: %s", user_id, e)

    # 3. Chat Auto-Reply (one-to-one DMs only)
    if include_chat_auto_reply:
        try:
            logger.debug("User %s: starting workflow chat_auto_reply (fetching spaces)", user_id)
            all_spaces = fetch_chat_spaces(creds)
            spaces = [s for s in all_spaces if s.get("type") == "DIRECT_MESSAGE"]
            logger.info("Chat auto-reply: %d DM spaces (of %d total)", len(spaces), len(all_spaces))
            logger.debug("User %s: chat_auto_reply DM space names: %s", user_id, [s.get("displayName", s.get("name")) for s in spaces[:chat_spaces_limit]])
            chat_results = []
            for space in spaces[:chat_spaces_limit]:
                try:
                    r = orchestrator.run_chat_auto_reply(
                        creds, space["name"], user_id=user_id, reply_to_latest=1, space_type=space.get("type")
                    )
                    chat_results.append({"space": space.get("displayName", space["name"]), "replies": r.get("replies", [])})
                    logger.debug("User %s: chat_auto_reply space %s: replies=%s", user_id, space.get("name"), r.get("replies"))
                except Exception as e:
                    logger.warning("Chat auto-reply failed for space %s: %s", space.get("name"), e)
                    chat_results.append({"space": space.get("displayName", space["name"]), "error": str(e)})
            results["workflows"]["chat_auto_reply"] = {"status": "ok", "spaces": chat_results}
            logger.debug("User %s: chat_auto_reply completed: %d spaces processed", user_id, len(chat_results))
        except Exception as e:
            logger.exception("Chat auto-reply failed for %s", user_id)
            results["workflows"]["chat_auto_reply"] = {"status": "error", "error": str(e)}
            results["errors"].append(f"chat_auto_reply: {e}")
            logger.debug("User %s: chat_auto_reply error: %s", user_id, e)

    logger.debug("run_all_workflows_for_user exit: user_id=%s workflows=%s errors=%s",
                 user_id, list(results["workflows"].keys()), results["errors"])
    return results
