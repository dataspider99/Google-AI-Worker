"""Authentication dependencies for multi-user support."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from storage import get_user_by_api_key

# API key via Bearer token (for programmatic access)
api_key_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(api_key_scheme),
) -> str:
    """
    Resolve current user from session (browser) or API key (programmatic).
    Raises 401 if not authenticated.
    """
    # 1. Check API key (Authorization: Bearer <key>)
    if credentials and credentials.credentials:
        user_id = get_user_by_api_key(credentials.credentials)
        if user_id:
            return user_id

    # 2. Check session (set after Google OAuth)
    user_id = request.session.get("user_id")
    if user_id:
        return user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Sign in via /auth/google or use Authorization: Bearer <api_key>.",
    )
