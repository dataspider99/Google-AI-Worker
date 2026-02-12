"""Orchestration layer: fetches Google data, sends to Oshaani, returns intelligent results."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

from services.google_data import (
    create_email_draft,
    fetch_chat_messages,
    fetch_chat_spaces,
    fetch_drive_files,
    fetch_emails,
    format_context_for_agent,
    get_current_user_gaia_id,
    get_space_type,
    post_chat_message,
    _extract_email_address,
)
from services.oshaani_client import OshaaniClient
from services.tasks_service import create_task as create_google_task


def _conversation_id_for_chat(user_id: str, space_name: str) -> str:
    """Generate a stable conversation ID per user+space so agent context is bound per chat."""
    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or ""))[:40]
    safe_space = re.sub(r"[^a-zA-Z0-9_-]", "-", (space_name or ""))[:60]
    return f"ge-chat-{safe_user}-{safe_space}"


def _conversation_id_for_workflow(user_id: str, workflow: str) -> str:
    """Generate a stable conversation ID per user+workflow."""
    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or ""))[:40]
    return f"ge-{workflow}-{safe_user}"


class WorkflowOrchestrator:
    """
    Orchestrates automated workflows:
    1. Fetch Google data (emails, chat, workspace)
    2. Send to Oshaani agent with user request
    3. Return agent response (drafts, summaries, suggestions)
    """

    def __init__(self, oshaani_client: Optional[OshaaniClient] = None):
        self.oshaani = oshaani_client or OshaaniClient()

    def run_smart_inbox(
        self,
        creds: Credentials,
        user_request: str = "Summarize my inbox and highlight urgent items. Suggest draft replies for the top 3 emails.",
        max_emails: int = 15,
        conversation_id: Optional[str] = None,
        create_tasks: bool = True,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fetch emails, send to agent for summarization and draft replies.
        If create_tasks=True, prompts agent to output action items as 'TASK: title | notes'
        and creates them in the user's Google Tasks (list "Johny Sins").
        """
        task_instruction = (
            " At the end, list follow-up action items. For each item you want created in the user's Google Tasks, "
            "output exactly one line in this format: TASK: [task title] | [optional notes]. "
            "Example: TASK: Follow up with John on proposal | Send by Friday. "
            "Only lines starting with TASK: will be created as Google Tasks for the user."
            if create_tasks
            else ""
        )
        full_request = user_request + task_instruction

        emails = fetch_emails(creds, max_results=max_emails)
        drive = fetch_drive_files(creds, max_results=5)
        chat = []
        for space in fetch_chat_spaces(creds)[:2]:
            chat.extend(fetch_chat_messages(creds, space["name"], page_size=5))

        conv_id = conversation_id or _conversation_id_for_workflow(user_id or "", "smart-inbox")
        context = format_context_for_agent(emails, chat, drive)
        result = self.oshaani.invoke_with_context_sync(full_request, context, conv_id)

        if create_tasks:
            created = self._create_tasks_from_response(creds, result.get("response", ""))
            if created:
                result["tasks_created"] = created

        return result

    def run_first_email_draft(
        self,
        creds: Credentials,
        user_request: Optional[str] = None,
        subject_filter: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Read email from inbox, send to Oshaani for draft reply, create Gmail draft.
        If subject_filter is provided, find the first email whose subject contains it.
        Otherwise use the first email in inbox. Skips emails sent by the user (user_id).
        """
        max_emails = 50 if subject_filter else 1
        emails = fetch_emails(creds, max_results=max_emails)
        if not emails:
            return {"status": "no_emails", "message": "Inbox is empty"}

        user_email_lower = (user_id or "").lower()

        if subject_filter:
            filt = subject_filter.lower()
            first = next((e for e in emails if filt in (e.get("subject") or "").lower()), None)
            if not first:
                return {"status": "not_found", "message": f"No email found for subject: {subject_filter}"}
        else:
            first = emails[0]

        # Skip own emails (don't reply to yourself)
        from_addr = _extract_email_address(first.get("from", ""))
        if user_email_lower and from_addr.lower() == user_email_lower:
            return {"status": "skipped", "message": "Will not reply to your own email", "email": first.get("subject")}
        context = format_context_for_agent([first], [], [])
        prompt = user_request or (
            "Draft a professional, concise reply to this email. "
            "Keep it 1-3 short paragraphs. Output ONLY the reply body text, no greeting/signature needed."
        )
        conv_id = _conversation_id_for_workflow(user_id or "", "email-draft")
        result = self.oshaani.invoke_with_context_sync(prompt, context, conversation_id=conv_id)

        draft_text = result.get("response", "").strip()
        if not draft_text:
            return {"status": "no_draft", "email": first, "agent_response": result}

        subject = first.get("subject", "")
        if subject and not subject.upper().startswith("RE:"):
            subject = f"Re: {subject}"

        to_addr = _extract_email_address(first.get("from", ""))
        if not to_addr:
            return {"status": "error", "message": "Could not extract recipient from email"}

        refs = first.get("references", "")
        if first.get("message_id") and first["message_id"] not in (refs or ""):
            refs = f"{refs} {first['message_id']}".strip() if refs else first["message_id"]

        draft = create_email_draft(
            creds,
            to=to_addr,
            subject=subject,
            body=draft_text,
            thread_id=first.get("thread_id"),
            in_reply_to=first.get("message_id"),
            references=refs or None,
        )
        if not draft:
            return {"status": "draft_failed", "email": first, "draft_text_preview": draft_text[:100]}

        return {
            "status": "ok",
            "email": {"id": first["id"], "subject": subject, "from": first["from"]},
            "draft": draft,
            "draft_preview": draft_text[:150],
        }

    def _create_tasks_from_response(self, creds: Credentials, response: str) -> list[dict]:
        """Parse TASK: title | notes lines from agent response and create Google Tasks."""
        created = []
        for line in (response or "").splitlines():
            line = line.strip()
            if not line.upper().startswith("TASK:"):
                continue
            rest = line[5:].strip()
            if "|" in rest:
                title, notes = rest.split("|", 1)
                title, notes = title.strip(), notes.strip()
            else:
                title, notes = rest, None
            if title:
                task = create_google_task(creds, title=title, notes=notes or None)
                if task:
                    created.append(task)
        return created

    def run_chat_assistant(
        self,
        creds: Credentials,
        user_request: str,
        space_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fetch Chat messages, send to agent for analysis/response.
        Context is bound per user+space when space_name is provided.
        """
        if space_name:
            chat = fetch_chat_messages(creds, space_name, page_size=20)
            conv_id = conversation_id or _conversation_id_for_chat(user_id or "", space_name)
        else:
            spaces = fetch_chat_spaces(creds)
            chat = []
            for s in spaces[:3]:
                chat.extend(fetch_chat_messages(creds, s["name"], page_size=10))
            conv_id = conversation_id or _conversation_id_for_workflow(user_id or "", "chat-assistant")

        emails = fetch_emails(creds, max_results=5)
        drive = fetch_drive_files(creds, max_results=5)
        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conv_id)

    def run_document_intelligence(
        self,
        creds: Credentials,
        user_request: str = "What are the key documents in my Drive? Summarize recent activity.",
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Focus on Drive/Docs/Sheets context for document-related queries.
        Context is bound per user.
        """
        conv_id = conversation_id or _conversation_id_for_workflow(user_id or "", "doc-intel")
        drive = fetch_drive_files(creds, max_results=20)
        emails = fetch_emails(creds, max_results=5)
        chat = []
        for space in fetch_chat_spaces(creds)[:1]:
            chat.extend(fetch_chat_messages(creds, space["name"], page_size=5))

        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conv_id)

    def run_custom(
        self,
        creds: Credentials,
        user_request: str,
        include_emails: int = 10,
        include_chat: bool = True,
        include_drive: int = 10,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fully customizable workflow - specify what Google data to include.
        Context is bound per user.
        """
        conv_id = conversation_id or _conversation_id_for_workflow(user_id or "", "custom")
        emails = fetch_emails(creds, max_results=include_emails) if include_emails else []
        drive = fetch_drive_files(creds, max_results=include_drive) if include_drive else []
        chat = []
        if include_chat:
            for space in fetch_chat_spaces(creds)[:3]:
                chat.extend(fetch_chat_messages(creds, space["name"], page_size=10))

        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conv_id)

    def run_chat_auto_reply(
        self,
        creds: Credentials,
        space_name: str,
        user_id: Optional[str] = None,
        reply_to_latest: int = 1,
        skip_empty: bool = True,
        system_prompt: Optional[str] = None,
        space_type: Optional[str] = None,
        dm_only: bool = True,
    ) -> dict[str, Any]:
        """
        Auto-reply to Google Chat messages using Oshaani agent.
        Only replies in one-to-one (DM) chats. Does not reply if the last message is your own.
        """
        # Only process one-to-one (direct message) spaces
        if dm_only:
            st = space_type or get_space_type(creds, space_name)
            if st != "DIRECT_MESSAGE":
                return {"space": space_name, "replies": [], "skipped": "Only one-to-one (DM) chats are supported"}

        from auth.google_oauth import refresh_credentials_if_needed

        creds = refresh_credentials_if_needed(creds)
        chat = fetch_chat_messages(creds, space_name, page_size=reply_to_latest + 10)
        results = []

        gaia_id = get_current_user_gaia_id(creds)
        user_email_lower = (user_id or "").lower()

        def _is_own(m: dict) -> bool:
            cn = m.get("creator_name") or ""
            if gaia_id and cn == f"users/{gaia_id}":
                return True
            if user_email_lower and (m.get("creator_email") or "").lower() == user_email_lower:
                return True
            if cn == "users/app":
                return True
            return False

        # Do not reply when last message is from own user (applies to DMs and all spaces)
        if chat and _is_own(chat[0]):
            logger.info("Chat auto-reply skip %s: last message is your own, not replying", space_name)
            return {"space": space_name, "replies": [], "skipped": "Last message is your own"}

        # Filter out own messages, then take latest N to reply to
        eligible = [m for m in chat if not _is_own(m)]
        if not eligible:
            logger.debug("Chat auto-reply skip %s: no messages from others", space_name)
            return {"space": space_name, "replies": [], "skipped": "No messages from others to reply to"}

        logger.info("Chat auto-reply %s: replying to %d eligible message(s)", space_name, min(len(eligible), reply_to_latest))

        default_prompt = (
            "You are a helpful assistant. Reply concisely and professionally to this chat message."
        )
        prompt = system_prompt or default_prompt

        for msg in eligible[:reply_to_latest]:
            text = (msg.get("text") or "").strip()
            if skip_empty and not text:
                continue

            context = f"**Message from {msg.get('creator', 'Unknown')}:**\n{text}"
            user_request = f"{prompt}\n\nGenerate a short, appropriate reply (1-3 sentences)."
            conv_id = _conversation_id_for_chat(user_id or "", space_name)
            agent_response = self.oshaani.invoke_with_context_sync(user_request, context, conversation_id=conv_id)

            reply_text = agent_response.get("response", "").strip()
            if not reply_text:
                results.append({"message": msg.get("name"), "reply": None, "error": "Empty agent response"})
                continue

            parent = msg.get("reply_parent") or space_name
            posted = post_chat_message(creds, parent, reply_text)
            results.append({
                "message": msg.get("name"),
                "original": text[:100],
                "reply": reply_text,
                "posted": posted is not None,
            })

        return {"space": space_name, "replies": results}
