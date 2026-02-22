# Standard Operating Procedure (SOP): Website

**Document:** SOP – Website (Johny Sins at g.oshaani.com)  
**Purpose:** Standard procedures for operating, maintaining, and troubleshooting the live website.  
**Audience:** Operators, DevOps, and developers who maintain the site.

---

## 1. Overview

| Item | Detail |
|------|--------|
| **Site URL** | https://g.oshaani.com |
| **App** | Johny Sins – multi-user FastAPI app; Google OAuth + Oshaani AI workflows (Gmail, Chat, Drive, Tasks, Calendar). |
| **Stack** | Python 3.9+, FastAPI, uvicorn; systemd service; nginx reverse proxy; Let’s Encrypt SSL. |
| **Server** | App runs as systemd unit `johny-sins` on **port 8002** (127.0.0.1). Nginx listens on 80/443 and proxies to 8002. |
| **Repo path** | `/home/ec2-user/Johny-Sins` |

### Key URLs

| URL | Purpose |
|-----|--------|
| https://g.oshaani.com | Home |
| https://g.oshaani.com/app | Dashboard (sign in, workflows, API key) |
| https://g.oshaani.com/auth/google | Sign in with Google |
| https://g.oshaani.com/docs | API docs (Swagger UI) |
| https://g.oshaani.com/redoc | API docs (ReDoc) |
| https://g.oshaani.com/health | Health check |

---

## 2. Daily Operations

### 2.1 Check site is up

```bash
# From server
curl -s -o /dev/null -w "%{http_code}" https://g.oshaani.com/health
# Expected: 200

# Or in browser
# Open https://g.oshaani.com/health → should show {"status":"ok"}
```

### 2.2 Check service status

```bash
sudo systemctl status johny-sins
sudo systemctl status nginx
```

Both should show `Active: active (running)`.

### 2.3 View application logs

```bash
# Follow logs in real time
journalctl -u johny-sins -f

# Last 100 lines
journalctl -u johny-sins -n 100 --no-pager

# Logs since today
journalctl -u johny-sins --since today --no-pager
```

**Optional file logging:** Set `LOG_FILE` in `.env` (e.g. `LOG_FILE=logs/johny-sins.log` or `/var/log/johny-sins/app.log`) to also write logs to a file. Logs rotate at 10 MB and keep 3 backups (`LOG_FILE_MAX_BYTES`, `LOG_FILE_BACKUP_COUNT`).

### 2.4 Restart the application (after config or code change)

```bash
sudo systemctl restart johny-sins
sudo systemctl status johny-sins
```

### 2.5 Reload nginx (after nginx config change)

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Do **not** reload if `nginx -t` fails (e.g. missing SSL certs).

---

## 3. Configuration

### 3.1 Where configuration lives

| What | Location | Notes |
|------|----------|--------|
| App env (OAuth, Oshaani, app URL) | `auth/.env` or project root `.env` | systemd loads both (see unit file). |
| Systemd unit | `/etc/systemd/system/johny-sins.service` | Copied from repo `systemd/johny-sins.service`. |
| Nginx site config | `/etc/nginx/conf.d/g.oshaani.com.conf` | Copied from repo `nginx/g.oshaani.com.conf` (or `.http-only.conf` for bootstrap). |

### 3.2 Required environment variables (production)

Ensure these are set in `auth/.env` or project root `.env` (and that systemd loads that file):

| Variable | Example | Purpose |
|----------|---------|--------|
| `GOOGLE_CLIENT_ID` | `xxx.apps.googleusercontent.com` | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | `xxx` | Google OAuth |
| `GOOGLE_REDIRECT_URI` | `https://g.oshaani.com/auth/google/callback` | OAuth callback; must match Google Cloud Console |
| `APP_BASE_URL` | `https://g.oshaani.com` | Base URL for redirects and links |
| `SECRET_KEY` | Long random string | Session signing (e.g. `openssl rand -hex 32`) |
| `ENVIRONMENT` | `production` | Enables production behavior |
| `OSHAANI_AGENT_API_KEY` | (optional per user) | Default agent key; users can override in dashboard |

Optional for production:

- `ENABLE_DOCS=true` – serve `/docs` and `/redoc` (can also be set in systemd unit).
- `LOG_LEVEL=INFO` (or DEBUG for troubleshooting).

### 3.3 Google Cloud Console

- **Authorized redirect URIs** must include: `https://g.oshaani.com/auth/google/callback`.
- Required APIs: Gmail, Chat, Drive, Docs, Sheets, Tasks, People (userinfo). See README for full list.

---

## 4. Deployment & Updates

### 4.1 Deploy new code (pull and restart)

```bash
cd /home/ec2-user/Johny-Sins
git pull
# If dependencies changed:
# /home/ec2-user/Johny-Sins/venv/bin/pip install -r requirements.txt
sudo systemctl restart johny-sins
```

### 4.2 Update systemd unit (after editing repo file)

```bash
sudo cp /home/ec2-user/Johny-Sins/systemd/johny-sins.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart johny-sins
```

### 4.3 Update nginx config (after editing repo file)

```bash
sudo cp /home/ec2-user/Johny-Sins/nginx/g.oshaani.com.conf /etc/nginx/conf.d/g.oshaani.com.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 4.4 SSL certificate renewal

Renewal is automatic via certbot timer. To test:

```bash
sudo certbot renew --dry-run
```

If certs were missing and you fixed them, reload nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Troubleshooting

### 5.1 Site returns 502 / connection refused

- **Check app is running:** `sudo systemctl status johny-sins`
- **Start if stopped:** `sudo systemctl start johny-sins`
- **Check port:** `curl -s http://127.0.0.1:8002/health` → should return `{"status":"ok"}`

### 5.2 /auth/google returns 500

- **Cause:** Missing Google OAuth credentials.
- **Log message:** `OAuth config error: Missing required parameter: client_id (and client_secret)`
- **Fix:** Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in `auth/.env` (or root `.env`) and that the systemd unit loads that file (`EnvironmentFile=-/home/ec2-user/Johny-Sins/auth/.env`). Then restart: `sudo systemctl restart johny-sins`.

### 5.3 /docs returns 404

- **Cause:** Docs are disabled in production by default.
- **Fix:** Set `ENABLE_DOCS=true` in the systemd unit or in `.env`, then restart the service. (The repo systemd file already sets `Environment=ENABLE_DOCS=true` for this site.)

### 5.4 nginx -t fails (SSL certificate missing)

- **Cause:** Nginx config references Let’s Encrypt certs that don’t exist yet.
- **Fix:** Use HTTP-only config first, then run certbot. See `nginx/README.md`:
  ```bash
  sudo cp /home/ec2-user/Johny-Sins/nginx/g.oshaani.com.http-only.conf /etc/nginx/conf.d/g.oshaani.com.conf
  sudo nginx -t && sudo systemctl reload nginx
  sudo certbot --nginx -d g.oshaani.com
  # Then optionally copy full HTTPS config from repo and reload nginx again.
  ```

### 5.5 OAuth redirect goes to localhost after sign-in

- **Cause:** `GOOGLE_REDIRECT_URI` or `APP_BASE_URL` not set for production.
- **Fix:** In `auth/.env` set:
  - `GOOGLE_REDIRECT_URI=https://g.oshaani.com/auth/google/callback`
  - `APP_BASE_URL=https://g.oshaani.com`
  Add the same redirect URI in Google Cloud Console → Credentials → OAuth client. Restart: `sudo systemctl restart johny-sins`.

### 5.6 High CPU / memory or app crashes

- Check logs: `journalctl -u johny-sins -n 200 --no-pager`
- Restart: `sudo systemctl restart johny-sins`
- Service is set to `Restart=on-failure` with `RestartSec=5`, so it will auto-restart on crash.

---

## 6. Security & Access

- App binds to **127.0.0.1:8002** (not exposed directly). Only nginx should connect to it.
- HTTPS and redirect are handled by nginx; keep SSL config and certs up to date.
- Do not commit `auth/.env` or any `.env` containing secrets (they are in `.gitignore`).
- Use a strong `SECRET_KEY` in production.

---

## 7. Reference

| Document | Path | Content |
|----------|------|--------|
| Main README | `README.md` | Features, setup, Google/Oshaani config |
| Systemd | `systemd/README.md` | Service install and commands |
| Nginx | `nginx/README.md` | Nginx and SSL setup |
| OAuth scopes | `docs/SCOPES.md` | Which scopes are used |
| Demo (scopes) | `docs/DEMO_VIDEO_SCOPES.md` | How to explain scopes for demos |
| Oshaani tutorial | [YouTube](https://www.youtube.com/watch?v=J6G7neOlAms) | Step-by-step Oshaani Agent Key and Johny Sins walkthrough |

---

## 8. Quick command reference

| Task | Command |
|------|--------|
| Site health | `curl -s https://g.oshaani.com/health` |
| App status | `sudo systemctl status johny-sins` |
| Nginx status | `sudo systemctl status nginx` |
| Restart app | `sudo systemctl restart johny-sins` |
| Reload nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| Follow app logs | `journalctl -u johny-sins -f` |
| Deploy code | `cd /home/ec2-user/Johny-Sins && git pull && sudo systemctl restart johny-sins` |

---

*Last updated: 2026-02-13. Keep this SOP in sync with deployment and config changes.*
