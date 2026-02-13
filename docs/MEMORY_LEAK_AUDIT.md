# Memory leak audit

Summary of checks and fixes for memory/disk growth in the Johny Sins app.

---

## Fixed

### 1. Default key daily usage file (storage.py)

- **Issue:** `default_key_daily_usage.json` stored one entry per user per calendar day with no pruning. Over months/years the file could grow unbounded, and `_load_default_key_usage()` loads the entire file into memory on every workflow run.
- **Fix:** Introduced `DEFAULT_KEY_USAGE_RETENTION_DAYS = 31`. `_load_default_key_usage()` and `_save_default_key_usage()` now prune dates older than 31 days via `_prune_old_default_key_usage()`. File size and per-request memory for this data stay bounded.

---

## Checked – no leak

### 2. APScheduler (main.py)

- **Checked:** `BackgroundScheduler` with a single interval job. No job history or unbounded state; one reference to `_run_automation_for_all_users`. Shutdown clears `_scheduler`.
- **Verdict:** No leak.

### 3. threading.Timer (main.py startup)

- **Checked:** `threading.Timer(10, _run_automation_for_all_users).start()` runs once after 10s. Timer object is not retained after fire.
- **Verdict:** No leak.

### 4. HTTP clients (httpx)

- **Checked:** All `httpx.Client()` and `httpx.AsyncClient()` uses are inside `with` / `async with`, so connections are closed.
- **Locations:** `auth/google_oauth.py` (token exchange), `services/oshaani_client.py` (chat, validate), `main.py` (userinfo), `services/google_data.py` (get_current_user_gaia_id).
- **Verdict:** No leak.

### 5. Sessions

- **Checked:** Starlette `SessionMiddleware` uses signed cookies by default; session data is not stored in server memory.
- **Verdict:** No leak.

### 6. Credentials and user data

- **Checked:** No in-memory cache of credentials. `load_credentials()` reads from disk/Drive each time. `list_users()` builds a list from bootstrap filenames and returns; no persistent cache.
- **Verdict:** No leak.

### 7. Per-request objects

- **Checked:** `OshaaniClient`, `WorkflowOrchestrator`, and Google API service objects (`build(...)`) are created per request or per workflow and not stored globally. They become eligible for GC after the request.
- **Verdict:** No leak.

### 8. Caching

- **Checked:** No `functools.lru_cache`, `@cache`, or custom TTL caches in the codebase.
- **Verdict:** No risk of unbounded cache growth.

---

## Recommendations

- **Monitor:** In long-running production, monitor process RSS and `default_key_daily_usage.json` size; both should stay stable after the pruning fix.
- **Google API clients:** Service objects are created per call. If needed for performance, a bounded per-user or per-process cache with TTL could be added later; not required for correctness or leak prevention.
