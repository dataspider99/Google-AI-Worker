"""Oshaani.com AI Agent API client."""
from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from config import OSHAANI_AGENT_API_KEY, OSHAANI_API_BASE_URL

_REASONING_RE = re.compile(
    r"<reasoning>[\s\S]*?</reasoning>|<reasoning>[\s\S]*?</resoning>",
    re.IGNORECASE,
)


def _strip_reasoning(text: str) -> str:
    """Remove <reasoning>...</reasoning> blocks from AI response text."""
    if not isinstance(text, str):
        return text
    return _REASONING_RE.sub("", text).strip()


def _normalize_response(data: dict[str, Any]) -> dict[str, Any]:
    """Strip reasoning tags from response/message/text fields."""
    result = dict(data)
    for key in ("response", "message", "text", "content"):
        if key in result and isinstance(result[key], str):
            result[key] = _strip_reasoning(result[key])
    return result


class OshaaniClient:
    """Client for interacting with Oshaani AI agents (API key identifies the agent)."""

    def __init__(
        self,
        base_url: str = OSHAANI_API_BASE_URL,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or OSHAANI_AGENT_API_KEY

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"ApiKey {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, message: str, conversation_id: Optional[str] = None) -> dict[str, Any]:
        """
        Send a chat message to the agent (REST API v1).
        POST /api/v1/chat
        """
        async with httpx.AsyncClient() as client:
            payload = {"message": message}
            if conversation_id:
                payload["conversation_id"] = conversation_id

            resp = await client.post(
                f"{self.base_url}/api/v1/chat",
                headers=self._headers(),
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            return _normalize_response(resp.json())

    def chat_sync(self, message: str, conversation_id: Optional[str] = None) -> dict[str, Any]:
        """Synchronous chat - for use in sync contexts."""
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        with httpx.Client() as client:
            resp = client.post(
                f"{self.base_url}/api/v1/chat",
                headers=self._headers(),
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            return _normalize_response(resp.json())

    async def query_agent(
        self, agent_id: str, message: str, conversation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Query agent via agent-specific endpoint.
        POST /api/agents/{id}/query/
        """
        async with httpx.AsyncClient() as client:
            payload = {"message": message}
            if conversation_id:
                payload["conversation_id"] = conversation_id

            resp = await client.post(
                f"{self.base_url}/api/agents/{agent_id}/query/",
                headers=self._headers(),
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            return _normalize_response(resp.json())

    def query_agent_sync(
        self, agent_id: str, message: str, conversation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Synchronous query - for use in sync contexts."""
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        with httpx.Client() as client:
            resp = client.post(
                f"{self.base_url}/api/agents/{agent_id}/query/",
                headers=self._headers(),
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            return _normalize_response(resp.json())

    async def invoke_with_context(
        self,
        user_message: str,
        google_context: str,
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send a message along with Google data context for the agent to process.
        The agent receives both the user's request and the formatted Google context.
        """
        full_message = f"""**User request:** {user_message}

**Context from Google (emails, chat, workspace):**
{google_context}

Please process the above and respond accordingly. Use the context to answer questions, draft replies, summarize, or take actions as appropriate."""
        return await self.chat(full_message, conversation_id)

    def invoke_with_context_sync(
        self,
        user_message: str,
        google_context: str,
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Synchronous version of invoke_with_context."""
        full_message = f"""**User request:** {user_message}

**Context from Google (emails, chat, workspace):**
{google_context}

Please process the above and respond accordingly. Use the context to answer questions, draft replies, summarize, or take actions as appropriate."""
        return self.chat_sync(full_message, conversation_id)


def validate_oshaani_api_key(api_key: str, base_url: Optional[str] = None) -> None:
    """
    Validate an Oshaani API key by making a minimal chat request.
    Raises ValueError with a user-friendly message if the key is invalid (401/403 or API error).
    """
    if not (api_key or "").strip():
        raise ValueError("API key is empty")
    url = (base_url or OSHAANI_API_BASE_URL).rstrip("/")
    client = OshaaniClient(base_url=url, api_key=api_key.strip())
    try:
        client.chat_sync("OK")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise ValueError(
                "Invalid Oshaani API key. Check the key from your Oshaani dashboard (Agent → API Access) and try again."
            ) from e
        raise ValueError(
            f"Oshaani API error ({e.response.status_code}): {(e.response.text[:200] if e.response.text else str(e))}"
        ) from e
    except httpx.RequestError as e:
        raise ValueError(f"Cannot reach Oshaani: {e}") from e
