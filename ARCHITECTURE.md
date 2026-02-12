# Johny Sins - Architecture Overview

## Vision

An intelligent application that accesses Google data (emails, chat, workspace) via OAuth and integrates with **Oshaani.com** AI agents for automated smart work—acting like a virtual employee that learns and executes tasks.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOOGLE EMPLOYEE APPLICATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌─────────────────────┐    ┌──────────────────────┐   │
│  │   Web/API    │    │  Google OAuth       │    │  Oshaani Agent       │   │
│  │   Gateway    │───▶│  Integration Layer  │───▶│  Integration Layer  │   │
│  └──────────────┘    └──────────┬──────────┘    └──────────┬───────────┘   │
│         │                       │                          │               │
│         │              ┌─────────┴─────────┐       ┌────────┴────────┐     │
│         │              │                   │       │                 │     │
│         │              ▼                   ▼       ▼                 │     │
│         │     ┌──────────────┐    ┌──────────────┐ ┌──────────────┐  │     │
│         │     │   Gmail API  │    │ Google Chat  │ │ REST API     │  │     │
│         │     │   (emails)   │    │   API        │ │ /chat        │  │     │
│         │     └──────────────┘    └──────────────┘ │ /query       │  │     │
│         │              │                   │       │ /invoke      │  │     │
│         │              │                   │       └──────────────┘  │     │
│         │              └──────────┬────────┘                         │     │
│         │                         │                                  │     │
│         │                         ▼                                  │     │
│         │              ┌─────────────────────┐                       │     │
│         └─────────────▶│  Orchestration      │◀──────────────────────┘     │
│                        │  & Workflow Engine  │                              │
│                        │  (Automated Tasks)  │                              │
│                        └─────────────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL SERVICES                                                            │
│  • Google OAuth 2.0  • Gmail API  • Google Chat API  • Drive/Docs/Sheets     │
│  • Oshaani.com (https://oshaani.com) - AI Agent Platform                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Google OAuth Integration

**Purpose**: Authenticate users and obtain tokens for Google APIs.

**Google APIs & Scopes**:

| Service | API | OAuth Scopes |
|---------|-----|--------------|
| Gmail | Gmail API | `https://www.googleapis.com/auth/gmail.readonly`, `gmail.modify`, `gmail.send` |
| Google Chat | Chat API | `https://www.googleapis.com/auth/chat.messages.readonly`, `chat.messages` |
| Drive | Drive API | `https://www.googleapis.com/auth/drive.readonly`, `drive.file` |
| Docs | Docs API | `https://www.googleapis.com/auth/documents.readonly` |
| Sheets | Sheets API | `https://www.googleapis.com/auth/spreadsheets.readonly` |

**Flow**: OAuth 2.0 with refresh tokens for long-lived access.

### 2. Oshaani Agent Integration

**Purpose**: Send Google data context to Oshaani AI agents for intelligent processing.

**Oshaani Features Used**:
- **REST API**: `POST /api/v1/chat`, `POST /api/agents/{id}/query/`, `POST /api/agents/{id}/invoke/`
- **Agent API Key** authentication
- **Custom Tools**: Register Google APIs as custom HTTP tools for agents
- **MCP**: HTTP MCP server at `/mcp` with per-user credentials (Authorization: Bearer <api_key>)
- **RAG**: Train agents on your workflow patterns

**Oshaani Base URL**: `https://oshaani.com`

### 3. Orchestration Layer

**Purpose**: Automate workflows—e.g., "Check emails, summarize urgent ones, draft replies via Oshaani."

**Workflow Examples**:
1. **Email Triage**: Fetch inbox → Send to agent → Categorize/prioritize → Draft responses
2. **Chat Monitoring**: Read Chat spaces → Agent summarizes threads → Auto-respond to FAQs
3. **Document Intelligence**: Read Drive/Docs → Agent extracts insights → Generate reports
4. **Smart Scheduling**: Parse emails for meetings → Agent suggests calendar blocks

---

## Data Flow

1. **User** authorizes Google via OAuth.
2. **App** fetches data (emails, chat, workspace) using Google APIs.
3. **App** formats data and sends to **Oshaani agent** with context + instructions.
4. **Oshaani** returns intelligent response (draft, summary, action).
5. **App** optionally applies actions (send email, post to Chat) via Google APIs.

---

## Security Considerations

- Store OAuth tokens encrypted; use refresh tokens for long sessions.
- Oshaani API keys in environment variables, never in code.
- Request minimal OAuth scopes; follow principle of least privilege.
- Use HTTPS for all API calls.

---

## Setup Requirements

### Google Cloud Console
1. Create a project and enable: Gmail API, Google Chat API, Drive API, Docs API, Sheets API.
2. Configure OAuth consent screen.
3. Create OAuth 2.0 credentials (Web application).
4. Add authorized redirect URIs.

### Oshaani.com
1. Create an account at https://oshaani.com
2. Create and train an agent for your use case.
3. Publish the agent and obtain **Agent API Key**.
4. (Optional) Use Oshaani's built-in **Google Connector** if available for your Oshaani plan.

---

## Technology Stack

- **Backend**: Python 3.11+ (FastAPI)
- **Google APIs**: `google-auth`, `google-api-python-client`
- **Oshaani**: `httpx` or `requests` for REST API
- **Storage**: SQLite/PostgreSQL for tokens and job state
- **Scheduler**: APScheduler or Celery for background workflows
