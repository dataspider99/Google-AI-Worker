"""Storage: API keys (local file), user credentials (local bootstrap + Google Drive)."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR

logger = logging.getLogger(__name__)
API_KEYS_FILE = "api_keys.json"
BOOTSTRAP_PREFIX = "bootstrap_"
USER_SETTINGS_PREFIX = "user_settings_"
AUTOMATION_LOCAL_PREFIX = "automation_"


def ensure_data_dir_ready() -> Path:
    """
    Create the data directory and verify it is writable. Call at startup.
    Returns the path. Raises RuntimeError if the directory cannot be created or written to.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Cannot create data directory {DATA_DIR}: {e}") from e
    probe = DATA_DIR / ".write_check"
    try:
        probe.write_text("")
        probe.unlink(missing_ok=True)
    except OSError as e:
        raise RuntimeError(f"Data directory is not writable: {DATA_DIR} — {e}") from e
    return DATA_DIR


def _ensure_data_dir() -> Path:
    """Create data directory if needed (for use during requests)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_api_keys() -> dict[str, str]:
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
    return _load_api_keys().get(_hash_api_key(api_key))


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


def _user_settings_path(user_id: str) -> Path:
    return DATA_DIR / f"{USER_SETTINGS_PREFIX}{_safe_filename(user_id)}.json"


def _safe_filename(user_id: str) -> str:
    return user_id.replace("@", "_at_").replace(".", "_dot_")


def _make_json_safe(obj: Any) -> Any:
    """Return a copy of obj safe for json.dumps (e.g. datetime -> iso string)."""
    if hasattr(obj, "isoformat"):  # datetime
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(v) for v in obj]
    return obj


def save_credentials(user_id: str, credentials_dict: dict) -> None:
    """
    Save user credentials: minimal bootstrap locally (for server restart) and
    full data in the user's Google Drive (folder "Johny Sins", user_data.json).
    """
    try:
        _ensure_data_dir()
    except OSError as e:
        raise RuntimeError(f"Cannot create data directory {DATA_DIR}: {e}") from e
    bootstrap_path = _bootstrap_path(user_id)
    bootstrap: dict[str, Any] = {
        "refresh_token": credentials_dict.get("refresh_token"),
        "client_id": credentials_dict.get("client_id"),
        "client_secret": credentials_dict.get("client_secret"),
        "token_uri": credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": credentials_dict.get("scopes", []),
    }
    if credentials_dict.get("token") and credentials_dict.get("expiry"):
        bootstrap["token"] = credentials_dict["token"]
        bootstrap["expiry"] = credentials_dict["expiry"]
    try:
        with open(bootstrap_path, "w") as f:
            json.dump(bootstrap, f, indent=2)
    except OSError as e:
        raise RuntimeError(f"Cannot write credentials to {bootstrap_path}: {e}") from e

    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive, save_user_data_to_drive

        creds = dict_to_credentials(credentials_dict)
        existing = load_user_data_from_drive(creds, user_id) or {}
        user_data = {**existing, "credentials": credentials_dict, "user_id": user_id}
        save_user_data_to_drive(creds, user_id, user_data)
    except Exception:
        pass  # Drive sync is best-effort; local bootstrap is sufficient


def load_credentials(user_id: str) -> Optional[dict]:
    """
    Load user credentials: from local bootstrap, refresh token if needed, then
    optionally merge from Drive if bootstrap has no refresh_token (migration).
    """
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

    path = _bootstrap_path(user_id)
    if not path.exists():
        return None

    try:
        with open(path) as f:
            content = f.read().strip()
            if not content:
                logger.warning("Bootstrap file empty for %s: %s", user_id, path)
                return None
            bootstrap = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Bootstrap file invalid JSON for %s (%s): %s", user_id, path, e)
        return None
    except OSError as e:
        logger.warning("Cannot read bootstrap for %s: %s", user_id, e)
        return None

    from auth.google_oauth import credentials_to_dict, dict_to_credentials, refresh_credentials_if_needed

    credentials_dict = {
        "token": bootstrap.get("token"),
        "refresh_token": bootstrap.get("refresh_token"),
        "client_id": bootstrap.get("client_id"),
        "client_secret": bootstrap.get("client_secret"),
        "token_uri": bootstrap.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": bootstrap.get("scopes", []),
    }
    if bootstrap.get("expiry"):
        credentials_dict["expiry"] = bootstrap["expiry"]
    creds = dict_to_credentials(credentials_dict)
    try:
        creds = refresh_credentials_if_needed(creds)
    except Exception as e:
        err = str(e).lower()
        if "scope" in err or "invalid_grant" in err:
            logger.warning("Clearing stale credentials for %s (scope/invalid_grant): %s", user_id, e)
            delete_credentials(user_id)
            return None  # Force re-login with current scopes
        raise
    credentials_dict = credentials_to_dict(creds)
    if creds.token and creds.refresh_token:
        bootstrap["token"] = creds.token
        if creds.expiry:
            bootstrap["expiry"] = creds.expiry.isoformat()
        bootstrap["refresh_token"] = creds.refresh_token
        with open(_bootstrap_path(user_id), "w") as f:
            json.dump(bootstrap, f, indent=2)

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
            part = name[len(BOOTSTRAP_PREFIX):]
            users.append(part.replace("_at_", "@").replace("_dot_", "."))
    return users


def get_user_oshaani_key(user_id: str) -> Optional[str]:
    """Return the user's Oshaani API key from their Google Drive (user_data.json). None = use default from env."""
    # Migrate from legacy local file to Drive if present
    path = _user_settings_path(user_id)
    if path.exists():
        try:
            with open(path) as f:
                local_key = (json.load(f).get("oshaani_api_key") or "").strip()
            if local_key:
                cred_data = load_credentials(user_id)
                if cred_data:
                    try:
                        from auth.google_oauth import dict_to_credentials
                        from services.drive_storage import load_user_data_from_drive, save_user_data_to_drive
                        creds = dict_to_credentials(cred_data)
                        existing = load_user_data_from_drive(creds, user_id) or {}
                        existing["oshaani_api_key"] = local_key
                        save_user_data_to_drive(creds, user_id, existing)
                    except Exception:
                        pass
            path.unlink(missing_ok=True)
        except Exception:
            pass
    cred_data = load_credentials(user_id)
    if not cred_data:
        return None
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive
        creds = dict_to_credentials(cred_data)
        drive_data = load_user_data_from_drive(creds, user_id)
        if not drive_data:
            return None
        key = (drive_data.get("oshaani_api_key") or "").strip()
        return key if key else None
    except Exception:
        return None


def set_user_oshaani_key(user_id: str, api_key: str) -> None:
    """Save the user's Oshaani API key to their Google Drive (user_data.json). Pass empty string to clear."""
    cred_data = load_credentials(user_id)
    if not cred_data:
        raise RuntimeError("User not logged in; cannot save Oshaani key to Drive")
    path = _user_settings_path(user_id)
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive, save_user_data_to_drive
        creds = dict_to_credentials(cred_data)
        existing = load_user_data_from_drive(creds, user_id) or {}
        key = (api_key or "").strip()
        if key:
            existing["oshaani_api_key"] = key
        else:
            existing.pop("oshaani_api_key", None)
        # Ensure JSON-serializable: credentials dict may have datetime from in-memory state
        existing = _make_json_safe(existing)
        if not save_user_data_to_drive(creds, user_id, existing):
            raise RuntimeError("Could not save to Google Drive (check Drive access and try reconnecting).")
    finally:
        if path.exists():
            path.unlink(missing_ok=True)


# Default workflow toggles (all on). Keys: smart_inbox, document_intelligence, chat_auto_reply, first_email_draft, chat_spaces.
DEFAULT_WORKFLOW_TOGGLES = {
    "smart_inbox": True,
    "document_intelligence": True,
    "chat_auto_reply": True,
    "first_email_draft": True,
    "chat_spaces": True,
}


def get_user_workflow_toggles(user_id: str) -> dict[str, bool]:
    """Return user's workflow on/off toggles from Drive. Missing keys = True (on)."""
    cred_data = load_credentials(user_id)
    if not cred_data:
        return dict(DEFAULT_WORKFLOW_TOGGLES)
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive
        creds = dict_to_credentials(cred_data)
        drive_data = load_user_data_from_drive(creds, user_id)
        if not drive_data or "workflow_toggles" not in drive_data:
            return dict(DEFAULT_WORKFLOW_TOGGLES)
        toggles = dict(DEFAULT_WORKFLOW_TOGGLES)
        for k, v in drive_data["workflow_toggles"].items():
            if k in toggles and isinstance(v, bool):
                toggles[k] = v
        return toggles
    except Exception:
        return dict(DEFAULT_WORKFLOW_TOGGLES)


def set_user_workflow_toggles(user_id: str, toggles: dict[str, bool]) -> None:
    """Save workflow toggles to user's Google Drive. Merges with existing; only known keys are stored."""
    cred_data = load_credentials(user_id)
    if not cred_data:
        raise RuntimeError("User not logged in; cannot save toggles to Drive")
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive, save_user_data_to_drive
        creds = dict_to_credentials(cred_data)
        existing = load_user_data_from_drive(creds, user_id) or {}
        current = existing.get("workflow_toggles") or {}
        if not isinstance(current, dict):
            current = {}
        for k in DEFAULT_WORKFLOW_TOGGLES:
            if k in toggles:
                current[k] = bool(toggles[k])
        existing["workflow_toggles"] = current
        existing = _make_json_safe(existing)
        if not save_user_data_to_drive(creds, user_id, existing):
            raise RuntimeError("Could not save toggles to Drive")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Could not save toggles: {e}") from e


def _automation_local_path(user_id: str) -> Path:
    return DATA_DIR / f"{AUTOMATION_LOCAL_PREFIX}{_safe_filename(user_id)}.json"


def _parse_enabled_value(val: Any) -> bool:
    """Parse enabled flag from JSON (bool or string 'true'/'false')."""
    if val is None:
        return True
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "on", "yes")
    return bool(val)


def get_user_automation_enabled(user_id: str) -> bool:
    """Return whether the user has scheduled Run-all automation enabled. Default True.
    Reads from local file first (so preference persists even when Drive fails), then Drive."""
    # Local file takes precedence so we never lose the user's choice
    local_path = _automation_local_path(user_id)
    if local_path.exists():
        try:
            with open(local_path) as f:
                data = json.load(f)
            if "enabled" in data:
                return _parse_enabled_value(data["enabled"])
        except (json.JSONDecodeError, OSError):
            pass
    cred_data = load_credentials(user_id)
    if not cred_data:
        return True
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive
        creds = dict_to_credentials(cred_data)
        drive_data = load_user_data_from_drive(creds, user_id)
        if not drive_data or "automation_enabled" not in drive_data:
            return True
        return _parse_enabled_value(drive_data["automation_enabled"])
    except Exception:
        return True


def set_user_automation_enabled(user_id: str, enabled: bool) -> None:
    """Save user's automation on/off. Always persists locally first; then syncs to Drive when possible."""
    local_path = _automation_local_path(user_id)
    try:
        _ensure_data_dir()
        with open(local_path, "w") as f:
            json.dump({"enabled": bool(enabled)}, f)
    except OSError as e:
        raise RuntimeError(f"Cannot save automation preference: {e}") from e
    # Sync to Drive when possible; do not fail the request if Drive fails
    cred_data = load_credentials(user_id)
    if not cred_data:
        return
    try:
        from auth.google_oauth import dict_to_credentials
        from services.drive_storage import load_user_data_from_drive, save_user_data_to_drive
        creds = dict_to_credentials(cred_data)
        existing = load_user_data_from_drive(creds, user_id) or {}
        existing["automation_enabled"] = bool(enabled)
        existing = _make_json_safe(existing)
        if not save_user_data_to_drive(creds, user_id, existing):
            logger.warning("Could not sync automation_enabled to Drive for %s", user_id)
    except Exception as e:
        logger.warning("Drive sync for automation_enabled failed: %s", e)
