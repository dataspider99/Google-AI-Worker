"""Orchestration layer: fetches Google data, sends to Oshaani, returns intelligent results."""
from __future__ import annotations

from typing import Any, Optional

from google.oauth2.credentials import Credentials

from services.google_data import (
    create_email_draft,
    fetch_chat_messages,
    fetch_chat_spaces,
    fetch_drive_files,
    fetch_emails,
    format_context_for_agent,
    post_chat_message,
    _extract_email_address,
)
from services.oshaani_client import OshaaniClient
from services.tasks_service import create_task as create_google_task


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
    ) -> dict[str, Any]:
        """
        Fetch emails, send to agent for summarization and draft replies.
        If create_tasks=True, prompts agent to output action items as 'TASK: title | notes'
        and creates them in Google Tasks.
        """
        task_instruction = (
            " At the end, list any follow-up action items. For each, output a line: TASK: [title] | [notes]"
            if create_tasks
            else ""
        )
        full_request = user_request + task_instruction

        emails = fetch_emails(creds, max_results=max_emails)
        drive = fetch_drive_files(creds, max_results=5)
        chat = []
        for space in fetch_chat_spaces(creds)[:2]:
            chat.extend(fetch_chat_messages(creds, space["name"], page_size=5))

        context = format_context_for_agent(emails, chat, drive)
        result = self.oshaani.invoke_with_context_sync(full_request, context, conversation_id)

        if create_tasks:
            created = self._create_tasks_from_response(creds, result.get("response", ""))
            if created:
                result["tasks_created"] = created

        return result

    def run_first_email_draft(
        self,
        creds: Credentials,
        user_request: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Read the first email from inbox, send to Oshaani for draft reply, create Gmail draft.
        """
        emails = fetch_emails(creds, max_results=1)
        if not emails:
            return {"status": "no_emails", "message": "Inbox is empty"}

        first = emails[0]
        context = format_context_for_agent(emails, [], [])
        prompt = user_request or (
            "Draft a professional, concise reply to this email. "
            "Keep it 1-3 short paragraphs. Output ONLY the reply body text, no greeting/signature needed."
        )
        result = self.oshaani.invoke_with_context_sync(prompt, context)

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
    ) -> dict[str, Any]:
        """
        Fetch Chat messages, send to agent for analysis/response.
        """
        if space_name:
            chat = fetch_chat_messages(creds, space_name, page_size=20)
        else:
            spaces = fetch_chat_spaces(creds)
            chat = []
            for s in spaces[:3]:
                chat.extend(fetch_chat_messages(creds, s["name"], page_size=10))

        emails = fetch_emails(creds, max_results=5)
        drive = fetch_drive_files(creds, max_results=5)
        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conversation_id)

    def run_document_intelligence(
        self,
        creds: Credentials,
        user_request: str = "What are the key documents in my Drive? Summarize recent activity.",
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Focus on Drive/Docs/Sheets context for document-related queries.
        """
        drive = fetch_drive_files(creds, max_results=20)
        emails = fetch_emails(creds, max_results=5)
        chat = []
        for space in fetch_chat_spaces(creds)[:1]:
            chat.extend(fetch_chat_messages(creds, space["name"], page_size=5))

        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conversation_id)

    def run_custom(
        self,
        creds: Credentials,
        user_request: str,
        include_emails: int = 10,
        include_chat: bool = True,
        include_drive: int = 10,
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fully customizable workflow - specify what Google data to include.
        """
        emails = fetch_emails(creds, max_results=include_emails) if include_emails else []
        drive = fetch_drive_files(creds, max_results=include_drive) if include_drive else []
        chat = []
        if include_chat:
            for space in fetch_chat_spaces(creds)[:3]:
                chat.extend(fetch_chat_messages(creds, space["name"], page_size=10))

        context = format_context_for_agent(emails, chat, drive)
        return self.oshaani.invoke_with_context_sync(user_request, context, conversation_id)

    def run_chat_auto_reply(
        self,
        creds: Credentials,
        space_name: str,
        reply_to_latest: int = 1,
        skip_empty: bool = True,
        system_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Auto-reply to Google Chat messages using Oshaani agent.
        Fetches recent messages, sends each to the agent, posts reply back to the thread.
        """
        chat = fetch_chat_messages(creds, space_name, page_size=reply_to_latest + 5)
        results = []

        default_prompt = (
            "You are a helpful assistant. Reply concisely and professionally to this chat message."
        )
        prompt = system_prompt or default_prompt

        for msg in chat[:reply_to_latest]:
            text = (msg.get("text") or "").strip()
            if skip_empty and not text:
                continue

            context = f"**Message from {msg.get('creator', 'Unknown')}:**\n{text}"
            user_request = f"{prompt}\n\nGenerate a short, appropriate reply (1-3 sentences)."
            agent_response = self.oshaani.invoke_with_context_sync(user_request, context)

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
