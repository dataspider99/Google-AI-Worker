# Demo video: How scopes are used (Johny Sins + Oshaani.com)

Use this for an **Oshaani.com demo video**: what the user sees in the app, and which Google scope makes it possible. Script-friendly and suitable for privacy/consent screens.

**Oshaani tutorial (YouTube):** [https://www.youtube.com/watch?v=J6G7neOlAms](https://www.youtube.com/watch?v=J6G7neOlAms) — step-by-step walkthrough for creating an Agent Key and using Oshaani with Johny Sins.

---

## One-line pitch

**Johny Sins** connects your Google workspace (Gmail, Chat, Drive, Tasks, Calendar) to **Oshaani.com** AI agents. We only request the permissions needed for each feature you use.

---

## 1. Sign in with Google

**What you show:** User clicks “Sign in with Google” and lands on the dashboard.

**Scopes used:** `openid`, `userinfo.email`, `userinfo.profile`  
**Why:** We need to know who you are (email + profile) so we can keep your data isolated and link your Oshaani key and settings to your account.

**Script:** “We use your email and profile only to identify you and keep your data separate from other users.”

---

## 2. Smart Inbox (summarize emails, drafts, tasks)

**What you show:** User runs “Smart Inbox”; the app shows a summary of recent emails, urgency, and may create a Gmail draft and Google Tasks.

**Scopes used:**

| Scope | How it’s used in the demo |
|-------|---------------------------|
| `gmail.readonly` | We read your inbox (subject, sender, snippet/body) and send that context to Oshaani so the agent can summarize and suggest replies. |
| `gmail.compose` | When the agent suggests a reply, we create a **draft** in Gmail. You review and send from Gmail yourself—we never send email for you. |
| `tasks.readonly` | We list your existing task lists so we can find or create the “Johny Sins” list. |
| `tasks` | When the agent extracts action items (e.g. “TASK: Call client \| by Friday”), we create a task in Google Tasks in the “Johny Sins” list. |
| `drive.readonly` | Optional: we can include recent Drive file names/metadata in context so the agent has a fuller picture of your work. |
| `documents.readonly` | Optional: if you reference a Doc, we can read its content (read-only) so the agent can summarize or answer questions. |
| `spreadsheets.readonly` | Optional: same for Sheets—read-only, for context. |

**Script:** “Smart Inbox reads your emails and optional Drive/Docs/Sheets so Oshaani can summarize your inbox and suggest replies. Replies are created as Gmail drafts for you to send. Action items are added as tasks in Google Tasks.”

---

## 3. First email draft

**What you show:** User runs “First email draft” for a given subject; a draft appears in Gmail.

**Scopes used:** `gmail.readonly` (read the thread), `gmail.compose` (create the draft).

**Script:** “We read the email thread and use Oshaani to generate a first draft. The draft is created in your Gmail—you edit and send it when you’re ready.”

---

## 4. Chat Assistant & Chat Auto-Reply

**What you show:** User picks a Chat space (e.g. a DM), runs “Chat Assistant” or enables “Chat Auto-Reply”; the app lists messages and/or sends replies via the Oshaani agent.

**Scopes used:**

| Scope | How it’s used in the demo |
|-------|---------------------------|
| `chat.spaces.readonly` | We list your Chat spaces (including DMs) so you can choose which conversation to run the assistant or auto-reply in. |
| `chat.messages.readonly` | We read the latest messages in that space and send them to Oshaani for analysis or to decide whether to reply. |
| `chat.messages` | When the agent generates a reply (or auto-reply is on), we **send** that message in the Chat space on your behalf. |

**Script:** “We list your Chat spaces so you can pick one, read the conversation so Oshaani can understand it, and when you use Chat Assistant or Auto-Reply we send the agent’s reply in that Chat—so it looks like you replying.”

---

## 5. Document Intelligence

**What you show:** User runs “Document Intelligence”; the app summarizes recent Drive activity and key documents.

**Scopes used:** `drive.readonly`, `documents.readonly`, `spreadsheets.readonly`  
**How:** We list and read (read-only) your Drive files, Docs, and Sheets and send that context to Oshaani so the agent can summarize what’s changed and what matters.

**Script:** “Document Intelligence only reads your Drive, Docs, and Sheets. We don’t change anything—we just give Oshaani that context so it can summarize your workspace.”

---

## 6. Calendar events from workflows

**What you show:** When a workflow suggests a meeting (e.g. “EVENT: Team sync \| tomorrow 10am \| 30 min”), the app creates an event on the user’s primary Google Calendar.

**Scopes used:** `calendar.events`  
**How:** When the agent outputs something like `EVENT: summary | start | end | description`, we create that event in your primary calendar.

**Script:** “When the AI suggests a meeting, we create the event in your Google Calendar so you can accept or edit it there.”

---

## 7. Your settings and API key (Drive app folder)

**What you show:** User sets their Oshaani API key and toggles (e.g. automation, workflow toggles) in the dashboard; these are persisted.

**Scopes used:** `drive.file`  
**How:** We create and use a single **app-created** folder in your Drive (“Johny Sins”) and a file `user_data.json` inside it. We only access that folder and file—not the rest of your Drive.

**Script:** “We store your Oshaani key and app settings in a dedicated folder we create in your Drive. We don’t read or touch your other files.”

---

## Quick reference: scope → feature (for demo)

| Scope | Demo feature |
|-------|----------------|
| openid, userinfo.email, userinfo.profile | Sign in, identity |
| gmail.readonly | Read inbox (Smart Inbox, First email draft) |
| gmail.compose | Create Gmail drafts only |
| chat.spaces.readonly | List Chat spaces to choose DM/space |
| chat.messages.readonly | Read Chat messages for context |
| chat.messages | Send Chat replies (Assistant / Auto-reply) |
| tasks.readonly + tasks | List tasks, create “Johny Sins” list and TASK: items |
| drive.file | App folder + user_data.json only |
| drive.readonly | List/read Drive for Document Intelligence |
| documents.readonly | Read Docs for context |
| spreadsheets.readonly | Read Sheets for context |
| calendar.events | Create EVENT: entries in Google Calendar |

---

## Suggested demo flow (Oshaani.com video)

1. **Intro:** “Johny Sins connects your Google workspace to Oshaani AI—we only ask for the permissions we need.”
2. **Sign in:** Show consent screen; call out “email and profile to identify you.”
3. **Dashboard:** Show where Oshaani API key goes; mention “stored in a private app folder in your Drive.”
4. **Smart Inbox:** Run it; show summary, then Gmail draft and Google Tasks; say “we read mail, create drafts and tasks—we never send email for you.”
5. **First email draft:** Run it; show draft in Gmail.
6. **Chat:** List spaces, run Chat Assistant or Auto-Reply; show “we read this conversation and send the agent’s reply here.”
7. **Document Intelligence:** Run it; “we only read Drive/Docs/Sheets to summarize—no edits.”
8. **Optional:** Show automation toggle and “TASK: / EVENT:” behavior; mention calendar events created when the AI suggests a meeting.

This gives a clear, honest story for oshaani.com: **each scope is tied to a visible feature**, and we don’t request more than we need for the demo.
