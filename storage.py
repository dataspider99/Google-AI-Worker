"""Storage: API keys (local), user credentials/data (Drive + local bootstrap)."""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR

API_KEYS_FILE = "api_keys.json"
BOOTSTRAP_PREFIX = "bootstrap_"


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_api_keys() -> dict[str, str]:
    """Load api_key_hash -> user_id mapping."""
    path = DATA_DIR / API_KEYS_FILE
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_api_keys(data: dict[str, str]) -> None:
    _ensure_data_dir()
    with open(DATA_DIR / API_KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key(user_id: str) -> str:
    """Generate a new API key for user. Returns the raw key (show once)."""
    key = f"ge_{secrets.token_urlsafe(32)}"
    data = _load_api_keys()
    data[_hash_api_key(key)] = user_id
    _save_api_keys(data)
    return key


def get_user_by_api_key(api_key: str) -> str | None:
    """Look up user_id by API key. Returns None if invalid."""
    data = _load_api_keys()
    return data.get(_hash_api_key(api_key))


def revoke_api_key(user_id: str) -> bool:
    """Revoke all API keys for a user."""
    data = _load_api_keys()
    original_len = len(data)
    data = {h: u for h, u in data.items() if u != user_id}
    if len(data) < original_len:
        _save_api_keys(data)
        return True
    return False


def _bootstrap_path(user_id: str) -> Path:
    return DATA_DIR / f"{BOOTSTRAP_PREFIX}{_safe_filename(user_id)}.json"


def _safe_filename(user_id: str) -> str:
    """Safe filename from user_id (email). Reversible."""
    return user_id.replace("@", "_at_").replace(".", "_dot_")


def save_credentials(user_id: str, credentials_dict: dict) -> None:
    """
    Save user credentials: to Drive (primary) and local bootstrap (for server restart).
    """
    # 1. Save bootstrap locally (required for load_credentials when server restarts)
    _ensure_data_dir()
    bootstrap = {
        "refresh_token": credentials_dict.get("refresh_token"),
        "client_id": credentials_dict.get("client_id"),
        "client_secret": credentials_dict.get("client_secret"),
        "token_uri": credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": credentials_dict.get("scopes", []),
    }
    with open(_bootstrap_path(user_id), "w") as f:
        json.dump(bootstrap, f, indent=2)

    # 2. Save to Drive (requires Credentials to call Drive API)
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import save_user_data_to_drive

        creds = dict_to_credentials(credentials_dict)
        user_data = {"credentials": credentials_dict, "user_id": user_id}
        save_user_data_to_drive(creds, user_id, user_data)
    except Exception:
        pass  # Drive sync is best-effort; bootstrap is sufficient


def load_credentials(user_id: str) -> Optional[dict]:
    """
    Load user credentials: from Drive if available, else from local bootstrap.
    """
    # 0. Migration: if old creds_ file exists, migrate to bootstrap + Drive
    old_path = DATA_DIR / f"creds_{user_id}.json"
    if old_path.exists():
        with open(old_path) as f:
            old_data = json.load(f)
        save_credentials(user_id, old_data)
        try:
            old_path.unlink()
        except Exception:
            pass
        return old_data

    # 1. Load bootstrap (required to get Credentials for Drive access)
    path = _bootstrap_path(user_id)
    if not path.exists():
        return None

    with open(path) as f:
        bootstrap = json.load(f)

    # Bootstrap has refresh_token but not token; we need to refresh to get token
    from auth.google_oauth import dict_to_credentials, refresh_credentials_if_needed

    credentials_dict = {
        "token": None,
        "refresh_token": bootstrap.get("refresh_token"),
        "client_id": bootstrap.get("client_id"),
        "client_secret": bootstrap.get("client_secret"),
        "token_uri": bootstrap.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": bootstrap.get("scopes", []),
    }
    creds = dict_to_credentials(credentials_dict)
    creds = refresh_credentials_if_needed(creds)
    credentials_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "token_uri": creds.token_uri,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }

    # 2. Prefer bootstrap credentials (updated on every login). Only use Drive when
    # bootstrap has no refresh_token. Drive credentials can be stale (e.g. before
    # chat.spaces scope was added), causing workflows to get empty chat spaces.
    if not credentials_dict.get("refresh_token"):
        try:
            from services.drive_storage import load_user_data_from_drive

            drive_data = load_user_data_from_drive(creds, user_id)
            if drive_data and "credentials" in drive_data:
                return drive_data["credentials"]
        except Exception:
            pass
    return credentials_dict


def delete_credentials(user_id: str) -> bool:
    """Remove stored credentials (local bootstrap only; Drive file remains)."""
    path = _bootstrap_path(user_id)
    if path.exists():
        path.unlink()
        return True
    return False


def list_users() -> list[str]:
    """List user_ids that have stored credentials (from local bootstrap)."""
    users = []
    for p in DATA_DIR.glob(f"{BOOTSTRAP_PREFIX}*.json"):
        name = p.stem
        if name.startswith(BOOTSTRAP_PREFIX):
            part = name[len(BOOTSTRAP_PREFIX) :]
            users.append(part.replace("_at_", "@").replace("_dot_", "."))
    return users
