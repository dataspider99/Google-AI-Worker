"""Application configuration."""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _resolve_data_dir() -> Path:
    """Resolve DATA_DIR: use env if set and writable, else default, else temp fallback."""
    env_val = os.getenv("DATA_DIR", "").strip()
    candidates = []
    if env_val:
        candidates.append(Path(env_val).resolve())
    candidates.append(Path(__file__).resolve().parent / "data")
    candidates.append(Path(tempfile.gettempdir()) / "google_employee_data")
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_check"
            probe.write_text("")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    return candidates[-1]  # last resort: temp (may still fail later)

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# Google API Scopes (openid required when using userinfo - Google adds it automatically)
# Gmail + Chat scopes for full AI automation; Drive/Docs/Sheets for workspace
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    # Gmail - full automation
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.insert",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    # gmail.metadata removed - it conflicts with format=full; gmail.readonly is sufficient
    # Chat - full automation
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/chat.memberships",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.messages.reactions.readonly",
    "https://www.googleapis.com/auth/chat.messages.reactions",
    # Tasks - store action items from workflows
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/tasks.readonly",
    # Workspace
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# Oshaani (Agent API Key identifies the agent)
OSHAANI_API_BASE_URL = os.getenv("OSHAANI_API_BASE_URL", "https://oshaani.com")
OSHAANI_AGENT_API_KEY = os.getenv("OSHAANI_AGENT_API_KEY", "")

# App
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
PRODUCTION = ENVIRONMENT == "production"
DEBUG = not PRODUCTION and os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
if PRODUCTION and (not SECRET_KEY or SECRET_KEY == "change-me-in-production"):
    import warnings
    warnings.warn(
        "SECRET_KEY is default or empty in production. Set SECRET_KEY in .env to a long random string.",
        UserWarning,
        stacklevel=2,
    )

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
# Origin only (scheme + netloc) for redirects - avoids /auth/google/auth/google if APP_BASE_URL had a path
_parsed = urlparse(APP_BASE_URL)
APP_ORIGIN = f"{_parsed.scheme}://{_parsed.netloc}" if _parsed.netloc else APP_BASE_URL
# Comma-separated origins for CORS (empty = same as APP_BASE_URL only in production)
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()] if CORS_ORIGINS_STR else []

# Data dir: writable path (project data/, or temp fallback if not writable)
DATA_DIR = _resolve_data_dir()

# Automation (run workflows continuously for logged-in users)
AUTOMATION_ENABLED = os.getenv("AUTOMATION_ENABLED", "true").lower() == "true"
AUTOMATION_INTERVAL_MINUTES = int(os.getenv("AUTOMATION_INTERVAL_MINUTES", "30"))
AUTOMATION_CHAT_AUTO_REPLY_ENABLED = os.getenv("AUTOMATION_CHAT_AUTO_REPLY_ENABLED", "true").lower() == "true"

# Default key limit: max workflow runs per day when user has no Oshaani API key (manual/API only; scheduler is unlimited)
DEFAULT_KEY_WORKFLOW_LIMIT_PER_DAY = int(os.getenv("DEFAULT_KEY_WORKFLOW_LIMIT_PER_DAY", "10"))

# Logging (in production default to INFO; DEBUG only when not production)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if PRODUCTION else "DEBUG")
