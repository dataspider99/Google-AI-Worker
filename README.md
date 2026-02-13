# Johny Sins

An intelligent application that accesses Google data (emails, chat, workspace) via OAuth and integrates with **Oshaani.com** AI agents for automated smart work—acting like a virtual employee.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-user** | Session auth (browser) + API keys (scripts/cron). Each user's data is isolated. |
| **Automation** | Workflows run continuously for all logged-in users (every 30 min by default). |
| **Drive storage** | User credentials stored in their Google Drive (folder "Johny Sins"). |
| **Task storage** | Action items from workflows stored in Google Tasks (list "Johny Sins"). |
| **Web UI** | Dashboard at `/app`: sign in with Google, run workflows, manage API key. |
| **Drive storage** | User credentials and data stored in the user's Google Drive (folder "Johny Sins"). |
| **MCP server** | HTTP MCP endpoint at `/mcp` for Cursor, Claude Desktop, and other MCP clients. |
| **Logging** | Configurable logging (DEBUG, INFO, WARNING, ERROR) to stdout. |
| **Google OAuth** | Access Gmail, Chat, Drive, Docs, Sheets, Tasks |
| **Oshaani** | Send context to AI agents for intelligent processing |

### Workflows

- **Smart Inbox** – Summarize emails, highlight urgent items, draft replies
- **Chat Assistant** – Analyze Chat spaces and respond to FAQs
- **Chat Auto-Reply** – Auto-reply to Chat messages via Oshaani agent
- **Document Intelligence** – Summarize Drive activity and key documents
- **Custom** – Fully configurable workflows with your specified data

---

## User Guide

### Step 1: Prerequisites

- Python 3.9+
- Google Cloud project with OAuth credentials
- [Oshaani.com](https://oshaani.com) account and Agent API Key

### Step 2: Installation

```bash
# Clone or navigate to project
cd "Johny Sins"

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select existing)
3. Enable APIs: **APIs & Services → Library**
   - Gmail API
   - Google Chat API
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Tasks API
4. **Configure the Chat app** (required – fixes 404 "Chat app not found"):
   - Go to [Chat API Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat)
   - Under **Application info** set: **App name** (e.g. "Johny Sins"), **Avatar URL** (optional, HTTPS image), **Description** (e.g. "AI automation for Gmail and Chat")
   - Turn **Interactive features** OFF (optional for API-only usage)
   - Click **Save**
6. Configure OAuth consent screen: **APIs & Services → OAuth consent screen**
   - User type: External (or Internal for Workspace)
   - Add scopes: gmail, chat, drive, docs, sheets, userinfo
7. Create credentials: **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
8. Copy **Client ID** and **Client Secret**

### Step 4: Oshaani Setup

1. Sign up at [oshaani.com](https://oshaani.com)
2. Create an agent and train it for your use case
3. Publish the agent
4. Copy the **Agent API Key** (Agent → API Access)

### Step 5: Configure

```bash
cp .env.example .env
# Edit .env with your values
```

**.env:**

```
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Oshaani
OSHAANI_API_BASE_URL=https://oshaani.com
OSHAANI_AGENT_API_KEY=your-agent-api-key

# App
SECRET_KEY=your-secret-key
APP_BASE_URL=http://localhost:8000

# Optional
AUTOMATION_ENABLED=true
AUTOMATION_INTERVAL_MINUTES=30
# Set to false to disable auto-replies in Google Chat (stops new threads being created)
AUTOMATION_CHAT_AUTO_REPLY_ENABLED=true
# Max workflow runs per day when using server default Oshaani key (manual/API only; scheduler unlimited)
DEFAULT_KEY_WORKFLOW_LIMIT_PER_DAY=10
LOG_LEVEL=INFO
```

### Step 6: Run

**Local (development):**

```bash
uvicorn main:app --reload --port 8000
```

**Web UI:** Open [http://localhost:8000](http://localhost:8000) in a browser. You’ll see the landing page; click **Sign in with Google** to reach the dashboard. From the dashboard you can run workflows and generate API keys.

**Storage:** User data (credentials) is saved to the user's Google Drive in a folder **Johny Sins** (file `user_data.json`). A minimal bootstrap is kept locally so the app can refresh tokens after a restart.

---

### Run with Docker

You can set up and run the application using Docker so you don’t need to install Python or dependencies on the host.

#### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (and optionally [Docker Compose](https://docs.docker.com/compose/install/))
- A `.env` file with the same variables as in **Step 5: Configure** (Google OAuth, Oshaani, `APP_BASE_URL`, `SECRET_KEY`, etc.)

#### Option A: Docker Compose (recommended)

1. **Configure:** Copy and edit `.env` in the project root (see Step 5 above).

2. **Build and run:**

   ```bash
   cd "Johny Sins"
   docker compose up -d
   ```

   This builds the image, loads variables from `.env`, mounts `./data` for persistence, and runs the app in the background. The web UI and MCP are at **http://localhost:8000**.

3. **Useful commands:**

   ```bash
   docker compose logs -f    # Follow logs
   docker compose down      # Stop and remove containers
   docker compose up -d --build   # Rebuild and start after code changes
   ```

#### Option B: Build and run with `docker run`

1. **Configure:** Ensure `.env` exists in the project root with all required variables.

2. **Build the image:**

   ```bash
   cd "Johny Sins"
   docker build -t johny-sins .
   ```

3. **Run the container:**

   ```bash
   docker run -d \
     --name johny-sins \
     -p 8000:8000 \
     --env-file .env \
     -v "$(pwd)/data:/app/data" \
     johny-sins
   ```

   - `-p 8000:8000` — exposes the app on port 8000.
   - `--env-file .env` — loads environment variables from `.env`.
   - `-v "$(pwd)/data:/app/data"` — persists bootstrap credentials and API keys; ensure `./data` is writable (container runs as UID 1000).

4. **Useful commands:**

   ```bash
   docker logs -f johny-sins    # Follow logs
   docker stop johny-sins      # Stop
   docker start johny-sins     # Start again
   docker rm -f johny-sins     # Remove container (data in ./data is kept)
   ```

#### Option C: Use a pre-built image from a registry

If you have the image in a registry (Docker Hub, GHCR, etc.):

```bash
# Pull (replace with your registry path)
docker pull YOUR_REGISTRY/johny-sins:latest

# Run with your .env and data volume
docker run -d \
  --name johny-sins \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  YOUR_REGISTRY/johny-sins:latest
```

#### Docker image details

- **Base:** `python:3.11-slim`
- **Runs as:** non-root user (UID 1000)
- **Healthcheck:** `GET /health` every 30s (used by orchestrators)
- **Data:** Mount a volume at `/app/data` so credentials and API keys survive restarts. If you use a host directory, ensure it is writable by UID 1000: `chown 1000:1000 ./data`

---

## Production deployment

For production, set the following and run behind HTTPS (reverse proxy recommended).

### Environment variables

| Variable | Production value |
|---------|------------------|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Long random string (e.g. `openssl rand -hex 32`) |
| `APP_BASE_URL` | Your public URL, e.g. `https://your-domain.com` |
| `GOOGLE_REDIRECT_URI` | `https://your-domain.com/auth/google/callback` |
| `CORS_ORIGINS` | Optional; comma-separated allowed origins (default: `APP_BASE_URL` only) |
| `DATA_DIR` | Persistent volume path, e.g. `/var/lib/johny-sins/data` (default in container: `/app/data`) |
| `LOG_LEVEL` | `INFO` (default in production) |

### Production behavior

- **Session cookies**: When `APP_BASE_URL` is HTTPS, session cookies are set with `Secure` and `SameSite=Lax`.
- **CORS**: Only `APP_BASE_URL` (or `CORS_ORIGINS`) are allowed; credentials supported.
- **API docs**: `/docs` and `/redoc` are disabled when `ENVIRONMENT=production` to reduce exposure.
- **Startup**: App logs `production=True` and warns if `SECRET_KEY` is still the default.

### Run with Uvicorn (single process)

```bash
export ENVIRONMENT=production
export PORT=8000
uvicorn main:app --host 0.0.0.0 --port 8000
# Or: python main.py  (uses PORT and HOST from env; no reload in production)
```

### Docker (production)

The Dockerfile sets `ENVIRONMENT=production`, runs as non-root user (UID 1000), and includes a healthcheck on `/health`. Use a production `.env` or pass variables explicitly:

```bash
docker build -t johny-sins .
docker run -d -p 8000:8000 \
  --env-file .env \
  -v /var/lib/johny-sins/data:/app/data \
  --name johny-sins \
  johny-sins
```

Or with inline env vars:

```bash
docker run -d -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e APP_BASE_URL=https://your-domain.com \
  -e GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback \
  -v /var/lib/johny-sins/data:/app/data \
  --name johny-sins \
  johny-sins
```

Mount a persistent volume for `/app/data` so credentials and data survive restarts. If you use a host directory (e.g. `-v ./data:/app/data`), ensure it is writable by UID 1000: `chown 1000:1000 ./data`.

### Reverse proxy (HTTPS)

Run the app on localhost and put **nginx**, **Caddy**, or **Traefik** in front with TLS:

- Terminate SSL at the proxy.
- Proxy `https://your-domain.com` → `http://127.0.0.1:8000`.
- Set `APP_BASE_URL=https://your-domain.com` and `GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback` so OAuth and cookies work.

### Google Cloud Console (production)

1. In **APIs & Services → Credentials**, add the production redirect URI: `https://your-domain.com/auth/google/callback`.
2. If the app is public, complete OAuth consent screen verification as required by Google.

---

### Step 7: First-Time Login

1. Open **http://localhost:8000/auth/google**
2. Sign in with your Google account
3. Approve the requested permissions
4. You’ll be redirected to `/me` when done

### Step 8: Use the App

**Browser (session):**

- Visit **http://localhost:8000/docs** for the Swagger UI
- Endpoints use your session automatically
- Try workflows such as Smart Inbox, Document Intelligence, etc.

**API key (scripts/cron):**

1. While logged in, call `POST /api-key`
2. Copy the returned API key (shown only once)
3. Use it in requests: `Authorization: Bearer <api_key>`

**Logout:**

- **http://localhost:8000/auth/logout** – clears session and redirects to login

---

## API Reference

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/auth/google` | No | Start Google OAuth |
| GET | `/auth/logout` | No | Logout, redirect to login |
| POST | `/auth/logout` | No | Logout (JSON) |
| GET | `/me` | Yes | Current user info |
| POST | `/api-key` | Yes | Generate API key |
| GET | `/me/drive-data` | Yes | View Drive-stored data |

### Workflows

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/workflows/smart-inbox` | Yes | Summarize inbox + draft replies; creates Google Tasks from action items |
| POST | `/workflows/first-email-draft` | Yes | Read first email, AI drafts reply, create Gmail draft |
| POST | `/workflows/chat-assistant` | Yes | Analyze Chat messages |
| POST | `/workflows/chat-auto-reply` | Yes | Auto-reply to Chat via Oshaani |
| GET | `/workflows/chat-spaces` | Yes | List Chat spaces |
| POST | `/workflows/document-intelligence` | Yes | Analyze Drive/Docs |
| POST | `/workflows/custom` | Yes | Custom workflow |
| POST | `/workflows/run-all` | Yes | Run all workflows manually |

### Tasks

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/tasks/lists` | Yes | List Google Task lists |
| GET | `/tasks/lists/{id}/tasks` | Yes | List tasks in a list |
| POST | `/tasks` | Yes | Create task (title, notes; uses "Johny Sins" list by default) |

### MCP

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/mcp` | No | MCP endpoint info |
| GET | `/mcp/validate` | No | Validate MCP server is running |
| GET | `/mcp/validate` | Yes (API key) | Validate API key and list tools |
| POST | `/mcp` | Yes (API key) | MCP JSON-RPC (tools/list, tools/call) |

---

## Usage Examples

### Browser (session)

```bash
# 1. Sign in at http://localhost:8000/auth/google
# 2. Use Swagger UI at http://localhost:8000/docs
# Or with curl (cookies from browser):
curl -X POST "http://localhost:8000/workflows/smart-inbox" -b cookies.txt -c cookies.txt
```

### API key (scripts / cron)

```bash
# Generate key first (while logged in):
curl -X POST "http://localhost:8000/api-key" -b cookies.txt -c cookies.txt

# Use the key:
curl -X POST "http://localhost:8000/workflows/smart-inbox" \
  -H "Authorization: Bearer ge_your_api_key"

# Chat auto-reply (need space name from /workflows/chat-spaces):
curl -X POST "http://localhost:8000/workflows/chat-auto-reply?space_name=spaces/xxx" \
  -H "Authorization: Bearer ge_your_api_key"
```

### MCP (Cursor / Claude)

```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer ge_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Call smart_inbox
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer ge_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"smart_inbox","arguments":{}}}'
```

---

## Automation

After login, workflows run automatically for all users with credentials:

- **Smart Inbox** – Summarize emails, suggest replies
- **Document Intelligence** – Summarize Drive activity
- **Chat Auto-Reply** – Reply to latest messages in each Chat space

**Configuration (`.env`):**

- `AUTOMATION_ENABLED=true` (default)
- `AUTOMATION_INTERVAL_MINUTES=30`
- `AUTOMATION_CHAT_AUTO_REPLY_ENABLED=true` (default) – set to `false` to disable Chat auto-replies

**Manual trigger:** `POST /workflows/run-all`

---

## Drive Storage

User data is stored in the user’s Google Drive:

- **Folder:** `Johny Sins` (in Drive root)
- **File:** `user_data.json` (credentials and settings)
- **Local bootstrap:** Minimal refresh token kept locally for server restarts

Users who signed in before Drive storage may need to re-auth to grant `drive.file` scope.

---

## MCP Server

HTTP MCP server at `/mcp` for Cursor, Claude Desktop, and other MCP clients.

**Auth:** `Authorization: Bearer <api_key>`

### Validate MCP server

```bash
# Check server is up (no auth)
curl -s http://localhost:8000/mcp/validate

# Validate your API key and list tools
curl -s http://localhost:8000/mcp/validate -H "Authorization: Bearer ge_your_api_key"
```

With a valid key, the response includes `"auth": "valid"`, `user_id`, `tools_count`, and `tools` list.

**Tools:**

| Tool | Description |
|------|-------------|
| `smart_inbox` | Summarize Gmail and suggest replies (creates Tasks from action items) |
| `first_email_draft` | Read first email, AI drafts reply, create Gmail draft |
| `chat_spaces` | List Google Chat spaces |
| `document_intelligence` | Summarize Drive activity |
| `chat_auto_reply` | Auto-reply to Chat (requires `space_name`) |
| `run_all_workflows` | Run all workflows |
| `list_task_lists` | List Google Task lists |
| `list_tasks` | List tasks in a list (requires `task_list_id`) |
| `create_task` | Create task in Google Tasks (requires `title`) |

---

## Logging

Logs go to stdout. Set `LOG_LEVEL` in `.env`: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Default: `INFO`.

```
2026-02-08 23:19:37 | INFO     | google_employee | User logged in: user@example.com
```

---

## Project Structure

```
├── main.py                 # FastAPI app
├── config.py               # Configuration
├── storage.py              # Credentials + API keys
├── logging_config.py      # Logging setup
├── auth/
│   ├── deps.py             # Auth dependencies (get_current_user)
│   └── google_oauth.py     # Google OAuth
├── services/
│   ├── google_data.py      # Fetch Gmail, Chat, Drive
│   ├── oshaani_client.py   # Oshaani API client
│   ├── orchestrator.py     # Workflow orchestration
│   ├── automation.py      # Automation runner
│   └── drive_storage.py   # Drive read/write
├── mcp_server/
│   └── server.py          # MCP HTTP server
├── ARCHITECTURE.md
└── requirements.txt
```

---

## Troubleshooting

### 404 "Google Chat app not found"

Configure the Chat app in Google Cloud: [Chat API Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat) → set **App name**, **Avatar URL**, **Description** → **Save**.

### 403 PERMISSION_DENIED

1. **Google Cloud** – Enable Gmail, Chat, Drive, Docs, Sheets APIs
2. **OAuth scopes** – Re-auth via `/auth/logout` then `/auth/google`
3. **Workspace** – Chat API may need admin approval for `chat.messages` scopes
4. **Unverified app** – Use "Advanced" → "Go to app (unsafe)" if needed

### Missing client_id

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` from Google Cloud Console.

### MCP 401

Ensure `Authorization: Bearer <api_key>` is sent. Generate an API key via `POST /api-key`.

---

## Security

- Store tokens and API keys securely
- Use environment variables for secrets
- Request minimal OAuth scopes
- Rotate API keys regularly
- Use HTTPS in production

---

## License

MIT
