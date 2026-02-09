"""Application configuration."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

# Automation (run workflows continuously for logged-in users)
AUTOMATION_ENABLED = os.getenv("AUTOMATION_ENABLED", "true").lower() == "true"
AUTOMATION_INTERVAL_MINUTES = int(os.getenv("AUTOMATION_INTERVAL_MINUTES", "30"))
AUTOMATION_CHAT_AUTO_REPLY_ENABLED = os.getenv("AUTOMATION_CHAT_AUTO_REPLY_ENABLED", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
