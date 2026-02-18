# How Google OAuth scopes are used

The app requests the scopes defined in `config.GOOGLE_SCOPES`. Below is how each scope is used in the codebase.

---

## Identity

| Scope | Where used | Purpose |
|-------|------------|---------|
| `openid` | OAuth flow | Required when using OpenID Connect / userinfo. |
| `userinfo.email` | `main.py` (OAuth callback) | Fetch user email from `oauth2/v2/userinfo` after login; stored as session `user_id` and used to identify the user and load their credentials. |
| `userinfo.profile` | OAuth / userinfo | Optional profile info; requested with email for a complete user identity. |

---

## Gmail

| Scope | Where used | Purpose |
|-------|------------|---------|
| `gmail.readonly` | `services/google_data.py`: `fetch_emails()` | List inbox messages (`messages.list`) and get full message content (`messages.get` with `format="full"`) for Smart Inbox and First email draft. |
| `gmail.compose` | `services/google_data.py`: `create_email_draft()` | Create Gmail drafts (`drafts.create`) for the First email draft workflow so the user can review and send from Gmail. |
| `gmail.send` | Reserved | For sending email directly (e.g. “send now”); currently the app only creates drafts. |
| `gmail.insert` | Reserved | For inserting messages (e.g. sent/draft); drafts are created via Drafts API. |
| `gmail.modify` | Reserved | For modifying messages/labels; could be used for marking read or applying labels. |
| `gmail.labels` | Reserved | For reading or applying labels; enables label-based filtering or organization. |

---

## Google Chat

| Scope | Where used | Purpose |
|-------|------------|---------|
| `chat.spaces.readonly` | `services/google_data.py`: `fetch_chat_spaces()` | List spaces (`spaces.list`) so the user can pick a DM for Chat auto-reply and to list spaces in the Chat assistant workflow. |
| `chat.spaces` | Chat API usage | Broader access to spaces when needed. |
| `chat.memberships.readonly` | Chat API | List members in spaces. |
| `chat.memberships` | Chat API | Manage memberships if the app ever adds membership operations. |
| `chat.messages.readonly` | `services/google_data.py`: `fetch_chat_messages()` | List messages in a space for Smart Inbox context, Chat assistant, and Chat auto-reply (read latest message to decide whether to reply). |
| `chat.messages` | `services/orchestrator.py` (Chat auto-reply) | Send replies in Chat (create messages in a space). |
| `chat.messages.reactions.readonly` | Chat API | Read reactions; can be used for context in workflows. |
| `chat.messages.reactions` | Chat API | Add reactions if the app supports them later. |

---

## Google Tasks

| Scope | Where used | Purpose |
|-------|------------|---------|
| `tasks.readonly` | `services/tasks_service.py`: `list_task_lists()`, `list_tasks()` | List task lists and tasks for the Tasks API endpoints and for finding the “Johny Sins” list. |
| `tasks` | `services/tasks_service.py`: `get_or_create_task_list()`, `create_task()` | Create the “Johny Sins” task list if missing (`tasklists().insert`) and create tasks (`tasks().insert`) when Smart Inbox (or other workflows) output action items as `TASK: title \| notes`. |

---

## Google Drive

| Scope | Where used | Purpose |
|-------|------------|---------|
| `drive.file` | `services/drive_storage.py` | Create and update only the app-created files: folder “Johny Sins” and `user_data.json` (credentials, Oshaani key, workflow toggles, automation setting). `files().list` (in app folder), `files().create`, `files().update`, and upload/download of `user_data.json`. |
| `drive.readonly` | `services/google_data.py`: `fetch_drive_files()` | List and read Drive files (metadata and export) for Document intelligence and custom workflows. |

---

## Google Docs

| Scope | Where used | Purpose |
|-------|------------|---------|
| `documents.readonly` | `services/google_data.py` (Document intelligence / custom) | Read Google Docs content (e.g. export or get body) to summarize documents and include in agent context. |

---

## Google Sheets

| Scope | Where used | Purpose |
|-------|------------|---------|
| `spreadsheets.readonly` | `services/google_data.py` (Document intelligence / custom) | Read spreadsheet data to include Sheets in workspace context for the agent. |

---

## Summary by feature

- **Sign-in and identity:** `openid`, `userinfo.email`, `userinfo.profile`
- **Smart Inbox:** Gmail read, Tasks create, Drive/Docs/Sheets read for context
- **First email draft:** Gmail read + compose (drafts)
- **Document intelligence:** Drive, Docs, Sheets read
- **Chat auto-reply / Chat assistant:** Chat spaces list, messages read and send
- **User settings and storage:** Drive (app folder + `user_data.json`) via `drive.file` and `drive_storage`
- **Action items (TASK: …):** Tasks create + Tasks list read

Scopes not yet used in code (e.g. `gmail.send`, `gmail.modify`, `gmail.labels`) are requested so the app can support sending email, labels, or other features without asking users to re-authorize later.

---

## Minimum scopes (least permission)

To run without issues, the app only needs the scopes that are **actually used** in code. The list below is the minimal set; removing any of these can break login, storage, or a feature.

| Scope | Purpose |
|-------|--------|
| `openid` | Required for OpenID Connect / userinfo. |
| `userinfo.email` | User identity after login (session `user_id`). |
| `userinfo.profile` | User identity (profile with email). |
| `gmail.readonly` | List and read emails (Smart Inbox, First email draft). |
| `gmail.compose` | Create Gmail drafts (First email draft). |
| `chat.spaces.readonly` | List Chat spaces (pick DM, Chat assistant). |
| `chat.messages.readonly` | Read Chat messages (Smart Inbox, auto-reply context). |
| `chat.messages` | Send Chat replies (auto-reply, Chat assistant). |
| `tasks.readonly` | List task lists and tasks. |
| `tasks` | Create “Johny Sins” list and create tasks (TASK: …). |
| `drive.file` | App-created files only: “Johny Sins” folder and `user_data.json`. |
| `drive.readonly` | List/read Drive files (Document intelligence). |
| `documents.readonly` | Read Google Docs content. |
| `spreadsheets.readonly` | Read Google Sheets data. |
| `calendar.events` | Create Calendar events (EVENT: … from workflows). |

**Not required for current features:** `gmail.send`, `gmail.insert`, `gmail.modify`, `gmail.labels`, `chat.spaces`, `chat.memberships.readonly`, `chat.memberships`, `chat.messages.reactions.readonly`, `chat.messages.reactions`. These can be omitted if you want the least permission set; add them back if you add features that need them.
