# App verification details (Johny Sins)

Use this document when submitting the app for verification (e.g. Google OAuth consent screen verification). Fill in the placeholders and share it with the verifier as needed.

---

## 1. App summary

| Field | Value |
|-------|--------|
| **App name** | Johny Sins |
| **Purpose** | Multi-user web app that connects a user’s Google Workspace (Gmail, Chat, Drive, Tasks, Calendar) to **Oshaani.com** AI agents for workflows: inbox summarization, email draft suggestions, document intelligence, and Chat auto-reply. |
| **Live URL** | https://g.oshaani.com |
| **Privacy policy** | https://g.oshaani.com/privacy |
| **Terms of service** | https://g.oshaani.com/terms |

---

## 2. Google OAuth (for verification)

| Item | Value |
|------|--------|
| **Authorized redirect URI** | `https://g.oshaani.com/auth/google/callback` |
| **OAuth client type** | Web application |
| **Google Cloud project ID** | *[Fill in: your Google Cloud project ID from Cloud Console → Home / IAM & Admin → Settings]* |
| **Other projects using this OAuth client** | *[Fill in: list any other Google Cloud project IDs that use the same OAuth client ID, or “None”]* |

---

## 3. Test user credentials (for reviewer testing)

Provide a **test Google account** that reviewers can use to sign in and exercise the app. Do **not** use a personal or production account; create a dedicated test account.

| Field | Value |
|-------|--------|
| **Test user email** | *[Fill in: e.g. johny-sins-test@yourdomain.com]* |
| **Test user password** | *[Fill in: or state “We will provide via secure channel”]* |
| **Notes** | Sign in at https://g.oshaani.com → “Sign in with Google” using the test account. After sign-in, the dashboard shows workflows (Smart Inbox, First email draft, Chat auto-reply, etc.). An optional Oshaani API key can be added in the dashboard for unlimited runs; without it, the app uses a shared key with a daily limit. |

---

## 4. OAuth scopes requested

The app requests the following scopes. Each is tied to a visible feature (see `docs/SCOPES.md` and `docs/DEMO_VIDEO_SCOPES.md` for mapping).

**Identity**

- `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/userinfo.profile`

**Gmail**

- `gmail.readonly`, `gmail.compose`, `gmail.send`, `gmail.insert`, `gmail.modify`, `gmail.labels`

**Google Chat**

- `chat.spaces.readonly`, `chat.spaces`, `chat.memberships.readonly`, `chat.memberships`, `chat.messages.readonly`, `chat.messages`, `chat.messages.reactions.readonly`, `chat.messages.reactions`

**Google Tasks**

- `tasks`, `tasks.readonly`

**Google Calendar**

- `calendar.events`

**Google Drive & Workspace**

- `drive.readonly`, `drive.file`, `documents.readonly`, `spreadsheets.readonly`

Scope-to-feature mapping and a demo script are in:

- `docs/SCOPES.md` — which scope is used where in code
- `docs/DEMO_VIDEO_SCOPES.md` — script-friendly explanation for demos and consent screens

---

## 5. Demo / screen recording

- **Oshaani tutorial (walkthrough):** https://www.youtube.com/watch?v=J6G7neOlAms  
- *[Optional: add a short screen recording showing sign-in, dashboard, and one workflow run.]*

---

## 6. Support and contact

| Field | Value |
|-------|--------|
| **Support URL or email** | *[Fill in: e.g. support@oshaani.com or your support page]* |
| **Developer / organization** | *[Fill in: your company or name]* |

---

## 7. Technical notes (optional for verifier)

- **Backend:** FastAPI on port 8002 (behind nginx); session-based auth after Google OAuth.
- **Token storage:** User tokens are stored in the user’s own Google Drive in an app-created folder (“Johny Sins”), not on our servers.
- **APIs used:** Gmail, Google Chat, Drive, Docs, Sheets, Tasks, People (userinfo), Calendar. All enabled in the same Google Cloud project as the OAuth client.

---

*Update the placeholders above before sharing with the verifier. Do not commit real test-account passwords; share those through a secure channel if needed.*
