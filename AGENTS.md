# Article Contest Tool — Agent Context

> [!IMPORTANT]
> **Self-Updating Rule:** Every time you make a change to this project (new files, renamed files, new API endpoints, schema changes, new dependencies, new features, bug fixes, architecture changes, etc.), you **MUST** update this file to reflect the current state of the project. This file is the single source of truth for project context.

---

## Project Overview

This is a **Wiki Article Contest Management Tool** for **Bengali Wiktionary** (`bn.wiktionary.org`). It allows contest organizers to create contests, assign juries, and manage article submissions. Participants submit article titles, which are validated against the MediaWiki API to verify authorship and creation date constraints.

**Owner / Primary User:** Wiki username `R1F4T` (hardcoded as owner in auth callback).

---

## Tech Stack

| Layer    | Technology                           | Details                                         |
| -------- | ------------------------------------ | ----------------------------------------------- |
| Backend  | **FastAPI** (Python)                 | REST API, OAuth, SQLAlchemy ORM, SQLite          |
| Frontend | **Vue 3** + **Vite**                 | SPA with Vue Router, Wikimedia Codex UI library  |
| Database | **SQLite** (`backend/app.db`)        | Via SQLAlchemy, auto-created on startup          |
| Auth     | **Wikimedia OAuth 2.0**              | Via `authlib`, JWT session tokens in cookies     |
| Proxy    | Vite dev proxy                       | `/api` and `/auth` → `localhost:8000`            |
| Charts   | **Chart.js** + **vue-chartjs**       | Used for jury stats visualization                |

---

## Project Structure

```
D:\Quote Contest\article-tool\
├── app.py                      # Utility script: extracts names from data.json → names.txt
├── data.json                   # Raw article data (189 KB)
├── names.txt                   # Extracted article names
├── Procfile                    # Toolforge process command runner configuration
├── requirements.txt            # Root requirements pointing to backend requirements (Toolforge build detection)
│
├── backend\
│   ├── .env                    # Environment variables (OAuth creds, secrets)
│   ├── main.py                 # FastAPI app — all API routes (552 lines)
│   ├── models.py               # SQLAlchemy models (User, Contest, Article, Review, ContestJury)
│   ├── database.py             # DB engine & session setup (SQLite)
│   ├── requirements.txt        # Python deps: fastapi, uvicorn, sqlalchemy, httpx, authlib, PyJWT, etc.
│   ├── app.db                  # SQLite database file (auto-generated)
│   └── venv\                   # Python virtual environment
│
└── frontend-vue\
    ├── package.json            # Vue 3, Vite 8, Wikimedia Codex, Chart.js, vue-router 5
    ├── vite.config.js          # Dev server on port 3000, proxy /api & /auth → :8000
    ├── index.html              # HTML entry point
    └── src\
        ├── main.js             # Vue app bootstrap (Codex CSS imports, router)
        ├── App.vue             # Root component
        ├── router.js           # Route definitions
        ├── style.css           # Global styles
        ├── components\
        │   ├── AdminPanel.vue
        │   ├── BulkSubmit.vue
        │   ├── HelloWorld.vue
        │   └── ReviewQueue.vue
        └── views\
            ├── Home.vue            # Landing / contest list
            ├── AdminDashboard.vue  # Owner-only: manage contests & juries
            ├── ContestLayout.vue   # Wrapper layout for contest routes
            ├── ContestDashboard.vue# Contest overview page
            ├── SubmitArticles.vue  # Bulk article submission (25 KB — largest view)
            ├── ReviewQueue.vue     # Jury article review queue with article preview
            ├── ActivityLog.vue     # Full submission/review log
            ├── JuryStats.vue       # Jury performance charts
            └── UserProfile.vue     # Per-user submission & review history
```

---

## Database Models (SQLAlchemy)

| Model          | Table           | Key Fields                                                                |
| -------------- | --------------- | ------------------------------------------------------------------------- |
| **User**       | `users`         | `id`, `wiki_username` (unique), `role` (participant \| owner), `oauth_access_token`             |
| **Contest**     | `contests`      | `id`, `code` (6-char hex, unique), `name`, `start_date`, `end_date`, `rule_must_be_creator`, `min_bytes`, `min_words`, `min_refs`, `rule_no_redirect`, `rule_no_disambig`, `rule_mainspace_only`, `allow_self_review`, `add_talk_template`, `talk_template_name`, `include_talk_header` |
| **ContestJury** | `contest_jury` | `id`, `contest_id` (FK), `user_id` (FK)                                  |
| **Article**    | `articles`      | `id`, `title`, `submitter_id` (FK), `contest_id` (FK), `status` (pending/accepted/rejected/validation_failed), `validation_error`, `wiki_creation_date`, `wiki_creator`, `submitted_at` |
| **Review**     | `reviews`       | `id`, `article_id` (FK), `reviewer_id` (FK), `status` (accepted/rejected/skipped), `comment`, `timestamp` |

---

## API Endpoints

### Auth
| Method | Path               | Description                       | Auth   |
| ------ | ------------------ | --------------------------------- | ------ |
| GET    | `/auth/login`      | Redirect to Wikimedia OAuth       | None   |
| GET    | `/auth/callback`   | OAuth callback, sets JWT cookie   | None   |
| POST   | `/auth/logout`     | Clears auth cookie                | None   |

### User
| Method | Path       | Description          | Auth     |
| ------ | ---------- | -------------------- | -------- |
| GET    | `/api/me`  | Current user info    | Required |

### Contests
| Method | Path                                    | Description                        | Auth      |
| ------ | --------------------------------------- | ---------------------------------- | --------- |
| GET    | `/api/contests`                         | List all contests                  | None      |
| GET    | `/api/contests/{code}`                  | Get single contest                 | None      |
| GET    | `/api/contests/{code}/my-role`          | Get user's role in contest         | Required  |
| GET    | `/api/contests/{code}/my-submissions`   | User's own submissions             | Required  |
| GET    | `/api/contests/{code}/log`              | Full activity log                  | Jury/Owner|
| GET    | `/api/contests/{code}/users/{username}` | User profile in contest context    | None      |

### Admin (Owner Only)
| Method | Path                                   | Description                        | Auth  |
| ------ | -------------------------------------- | ---------------------------------- | ----- |
| POST   | `/api/admin/contests`                  | Create contest with Fountain rules | Owner |
| PUT    | `/api/admin/contests/{code}`           | Update contest settings            | Owner |
| DELETE | `/api/admin/contests/{code}`           | Delete contest                     | Owner |
| POST   | `/api/admin/assign-jury`               | Assign jury members                | Owner |
| POST   | `/api/admin/unassign-jury`             | Remove jury member                 | Owner |
| GET    | `/api/admin/contests/{code}/export/csv`  | Export contest submissions CSV     | Owner |
| GET    | `/api/admin/contests/{code}/export/json` | Export contest submissions JSON    | Owner |
| GET    | `/api/admin/contests/{code}/export/wikitable` | Export contest submissions Wikitable | Owner |

### Articles & Reviews
| Method | Path                                          | Description                        | Auth       |
| ------ | --------------------------------------------- | ---------------------------------- | ---------- |
| POST   | `/api/submit-bulk`                            | Bulk submit articles               | Required   |
| GET    | `/api/articles/{contest_code}/pending/next`   | Next pending article for review    | Jury/Owner |
| POST   | `/api/articles/{article_id}/lock`             | Lock article for review            | Required   |
| POST   | `/api/articles/{article_id}/review`           | Submit review decision             | Jury/Owner |
| DELETE | `/api/articles/{article_id}`                  | Remove article from contest        | Jury/Owner |
| GET    | `/api/proxy/article/{title}`                  | Proxy bn.wiktionary article HTML   | None       |

---

## Key Business Logic

1. **Wikimedia Fountain Validation Engine:** When submitting, the backend validates articles against MediaWiki API or Wiktionary MariaDB Replica enforcing:
   - Creator constraint (`rule_must_be_creator`)
   - Creation timeframe (`start_date` to `end_date`)
   - Minimum Page Size (`min_bytes`)
   - Minimum Word Count (`min_words`)
   - Minimum Citations / References (`min_refs`)
   - Disallow Redirect pages (`rule_no_redirect`)
   - Disallow Disambiguation pages (`rule_no_disambig`)
   - Mainspace Namespace 0 requirement (`rule_mainspace_only`)
2. **Jury Governance & Self-Review:** Jury members can be configured per contest. Self-review (`allow_self_review`) is restricted by default.
3. **Privileged Users (Owner/Jury):** Can bypass validation rules and submit on behalf of others via `on_behalf_of` field.
4. **Article Locking:** In-memory lock system (`article_locks` dict) with 15-minute timeout to prevent concurrent reviews.
5. **Review Flow:** Articles go through `pending` → `accepted`/`rejected`. "Skipped" reviews don't change article status.

---

## How to Run

### Backend
```bash
cd backend
# Activate venv
.\venv\Scripts\activate      # Windows
# Install deps
pip install -r requirements.txt
# Run
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend-vue
npm install
npm run dev                  # Starts on http://localhost:3000
```

---

## Environment Variables (`backend/.env`)

| Variable                  | Description                           |
| ------------------------- | ------------------------------------- |
| `WIKIMEDIA_CLIENT_ID`     | OAuth 2.0 client ID                   |
| `WIKIMEDIA_CLIENT_SECRET` | OAuth 2.0 client secret               |
| `SESSION_SECRET`          | JWT signing key & session middleware   |
| `OAUTH_CALLBACK_URL`      | OAuth redirect URI (default: `http://localhost:3000/auth/callback`) |

---

## Change Log

| Date       | Change Description                                              |
| ---------- | --------------------------------------------------------------- |
| 2026-07-19 | Initial AGENTS.md created with full project context             |
| 2026-07-19 | Rewrote `GlobalProfile.vue` — event-based profile with tab navigation (Participated / Judged), expandable contest cards showing submitted articles or judgment info with stats bars and approval donut rings. Profile pill in header navigates to `/user/:username`. |
| 2026-07-19 | Owner jury fix — `GET /api/users/{username}/profile` now includes all contests where owner has reviews (not just explicit `ContestJury` rows). Each `judged_contests` entry now carries `role_in_contest: "owner" \| "jury"`. `GlobalProfile.vue` shows a gold ★ Owner or indigo 🛡 Jury badge on each judged event card. |
| 2026-07-19 | `ReviewQueue.vue` preview switched from `v-html` div to a sandboxed `<iframe srcdoc>`. Injected: full dark-mode CSS overrides (neutralises all inline `background: rgb(...)` / `color: rgb(...)` styles), and JS collapsible engine handling NavFrame, vsToggle (Bengali verb tables), and mw-collapsible — all three now work correctly inside the preview. |
| 2026-07-19 | `GlobalProfile.vue` updated to collapse profile events by default (removed auto-expand on first items). |
| 2026-07-19 | Added `scrollbar-gutter: stable` to global `style.css` to prevent layout shift when the scrollbar appears/disappears. |
| 2026-07-19 | Implemented smooth scrolling in `GlobalProfile.vue` using `scrollIntoView` when collapsing event cards to prevent abrupt viewport jumping. Also added `scroll-behavior: smooth` globally. |
| 2026-07-19 | Replaced `max-height` animation with a `display: grid` and `grid-template-rows: 0fr -> 1fr` approach in `GlobalProfile.vue` to ensure mathematically smooth collapsible height transitions, which prevents layout snapping without requiring excessive padding. Reverted the `80vh` padding. |
| 2026-07-19 | Injected global CSS overrides in `style.css` to force all input boxes (`cdx-text-input`, native pickers, textareas) into a unified premium dark theme with consistent focus rings and backgrounds. Set `:root { color-scheme: dark; }` to fix native checkboxes. |
| 2026-07-19 | Refactored `COLLAPSIBLE_JS` in `ReviewQueue.vue` to ensure all collapsible elements (NavFrame, vsToggle, mw-collapsible) in the preview iframe are collapsed by default and automatically injected with a `▶` toggle arrow if they lack one. |
| 2026-07-19 | Fixed duplicate Python function name in `main.py`: renamed `get_user_profile` at route `GET /api/contests/{code}/users/{username}` to `get_contest_user_profile` to avoid silent override by the global profile function. Both routes still work correctly. |
| 2026-07-19 | Expanded `style.css` with comprehensive Codex dark-mode overrides: `.cdx-menu` dropdown gets dark navy `#1a1d30` background, indigo hover/selected states, subtle borders, and a deep box-shadow. `.cdx-progress-bar` (loading animation in CdxLookup) replaced with indigo. Checkboxes get indigo checked state. Buttons tuned for dark background. All Codex text inputs get matching dark styling. |
| 2026-07-19 | Fixed Codex progress bar visual bug in `style.css` where the default black-and-white indeterminate diagonal stripes (cross pattern) overrode the custom dark-mode styling and obscured text. Forced `background-image: none !important` to apply the solid indigo theme smoothly. |
| 2026-07-19 | Fixed Codex pending loading state bug in `CdxLookup` which injected a `linear-gradient` animation into the nested `cdx-text-input__input` element. Overrode `.cdx-lookup--pending` to use a subtle indigo background instead. |
| 2026-07-19 | Fixed MediaWiki API pagination in `SubmitArticles.vue` to fetch all user articles by properly consuming the `uccontinue` token (previously limited to default limits). |
| 2026-07-19 | Updated `SubmitArticles.vue` to completely exclude already submitted articles from the fetched list view, removing them from the UI entirely to avoid duplication rather than just disabling them. Also updated empty states to handle the case where all fetched articles have been submitted. |
| 2026-07-19 | Implemented a real-time progress bar in `SubmitArticles.vue` for bulk submissions. Refactored `handleSubmit` to chunk selected articles into batches of 20 and sequentially `POST` them to `/api/submit-bulk`. The UI now displays a dynamic CSS gradient progress bar updating with the current processed count vs total count. |
| 2026-07-19 | Fixed error handling in `handleSubmit` in `SubmitArticles.vue` where 500/400 API errors caused a JavaScript TypeError, which cascaded into a catch block that injected invalid objects into the results array, masking the real error as a blank '—' row. Now gracefully catches all errors and surfaces the exact HTTP response or network error to the user interface, while reducing batch chunk size to 10 to minimize upstream Wikipedia API timeout risks. |
| 2026-07-19 | Reverted the hard exclusion of already submitted articles in `SubmitArticles.vue` and redesigned the view to display "Articles You Can Submit" and "Already Submitted" in two distinct, collapsible sections to make them easier to distinguish without losing visibility. |
| 2026-07-21 | Enforced a 50-article maximum limit on selection in `SubmitArticles.vue`, showing a `0/50` counter badge, changing "Select all" to "Select first 50", and disabling further checkbox selection once the limit is hit. Tuned SQLite in `database.py` with WAL mode, `synchronous=NORMAL`, and a 60-second timeout. Added a global `asyncio.Semaphore(15)` and dynamic personalized User-Agent headers in `main.py` to prevent rate-limit blocks and crashes under high concurrency. |
| 2026-07-21 | Optimized performance under load: introduced global, pooled `httpx.AsyncClient` to reuse TCP connections and eliminate handshake/SSL negotiation overhead. Optimized bulk submission checks to run a single batch database query (`title.in_(titles)`), reducing query count from $O(N)$ to $O(1)$. Implemented connection pool deadlock fixes by utilizing SQLAlchemy `NullPool` and executing WAL mode pragmas once at startup rather than inside the connection listener. Tuned SQLite with 64MB cache size and temp store in memory. |
| 2026-07-21 | Optimized for Wikimedia Toolforge: added support for MariaDB/MySQL connection pooling and auto-configuration from `~/replica.my.cnf` in `database.py`. Added dynamic secure cookies for HTTPS proxy compatibility on Toolforge. Fixed $N+1$ query loops in several endpoints using SQLAlchemy `joinedload` and `selectinload` to prevent timeouts under load. Enabled built-in FastAPI static files serving for built Vue SPA files and created root-level `requirements.txt` and `Procfile`. |
| 2026-07-21 | Implemented Wiktionary MariaDB Replica DB validation engine (`query_wiki_replica_batch`) in `database.py` and `main.py` querying `bnwiktionary_p` on Toolforge for instant <10ms article validation with zero rate limits. Added automatic fallback to MediaWiki HTTP API for local development. Removed the 50-article frontend limit in `SubmitArticles.vue` and increased submission chunk size to 100, allowing users to submit unlimited articles at once without rate-limit errors. |
| 2026-07-22 | Fixed critical build-breaking bug in `AdminDashboard.vue`: removed ~257 duplicate lines of template content (a second edit modal block + duplicate jury tab) that were accidentally inserted outside the owner `<template>` block during a previous edit session. Also fixed a garbled `saveEdit` function fragment (residual `};st Fountain settings updated!` text on line 337). Upgraded the edit modal Rules tab to match the create form's quality with preset chips, descriptions, and field hints for all rule inputs. Renamed "Fountain rules" → "Rules" throughout UI. |
| 2026-07-25 | Added `export_contest_wikitable` endpoint in `main.py` for exporting results as a Wikitable. Added Bengali translations for statuses in CSV, JSON, and Wikitable exports. Added a countdown timer to `ContestDashboard.vue` with Bengali text. Created a new owner-only `ContestConfig.vue` page at `/:code/config` for modifying contest settings and managing the jury directly from the contest layout. Added export buttons in `JuryStats.vue`. |
| 2026-07-27 | Fixed hardcoded white/grey color inconsistencies in `ReviewQueue.vue` (active article item highlight & copy talk button blue states) and `SubmitArticles.vue` (behalf toggle track, checked checkbox box, disabled checkbox box, and submission progress bar indigo/blue gradients). |
| 2026-07-27 | Fixed hardcoded white color inconsistencies in `ActivityLog.vue`: updated `.avatar-circle` background gradient to `#4f46e5` → `#2563eb`, and updated `.dot-accepted`, `.dot-rejected`, `.dot-pending` background colors to meaningful green (`#22c55e`), red (`#ef4444`), and amber (`#f59e0b`). |
| 2026-07-27 | Fixed hardcoded white/grey color inconsistencies across Vue views: updated save button in `ContestConfig.vue` to blue (`#2563eb`), accent bars in `ContestDashboard.vue` to green (`#22c55e`), red (`#ef4444`), and amber (`#f59e0b`), avatar conic gradient, owner role badge, accepted/rejected status pills and labels in `GlobalProfile.vue`, avatar background gradient in `UserProfile.vue`, and Wikitable export button colors in `JuryStats.vue`. |
| 2026-07-27 | Made OAuth callback URL dynamic based on request headers to support Toolforge domain automatically. Updated `database.py` to seamlessly read DB credentials from `TOOL_TOOLSDB_USER`/`TOOL_TOOLSDB_PASSWORD` for the app database and `TOOL_REPLICA_USER`/`TOOL_REPLICA_PASSWORD` for the wiki replica database directly from Toolforge environment variables, falling back to `replica.my.cnf`. |
| 2026-07-29 | Added psutil for system overload tracking in main.py, implemented backup dumping to `backup` folder in project root and process restart on high load. Added frontend warning banner in App.vue polling /api/system/status. |
| 2026-08-01 | Upgraded System Logs tab in `AdminDashboard.vue`: now filters API results to `type === 'system'` only (excludes article_submission noise), adds dynamic source filter chips (All / talk_template / backup / frontend), error/warning count banner, and click-to-expand rows that show full monospace message text. `fetchLogs` now fetches limit=200. |
| 2026-08-01 | Fixed talk page template not being added: root cause was OAuth scope `basic` only, which is "User identity verification only" and cannot use the MediaWiki write API at all. Changed scope to `basic editpage` in `main.py`. Also fixed the CSRF token validity check to detect `+\` (anonymous/unauthenticated token) and improved edit success detection to check `res_json["edit"]["result"] == "Success"` instead of just absence of `"error"` key. Added detailed `print` logging for CSRF token response and each edit result. |
| 2026-08-01 | Fixed Toolforge login (`?error=login_failed`): (1) `oauth_access_token` column was missing from MariaDB `users` table — rewrote `run_auto_migrations` in `database.py` to use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (MariaDB 10.3+ idempotent syntax). (2) Wikimedia OAuth2 JWTs exceed `VARCHAR(1000)` — widened column to `TEXT` in `models.py` and added `MODIFY COLUMN` migration. |
| 2026-07-29 | Fixed Toolforge serving bare FastAPI instead of Vue SPA. Root causes: (1) `FileResponse` and `StaticFiles` were imported nowhere in `main.py` — the entire static-serving block at the bottom was dead code. (2) `dist/` is listed in `frontend-vue/.gitignore` so the built SPA was never present on Toolforge. Fixed by adding the missing imports and updating `Procfile` to run `npm install && npm run build` in `frontend-vue/` before starting uvicorn, so the dist folder is always freshly built at startup. |
| 2026-07-30 | Fixed CdxLookup in `AdminDashboard.vue` dropping keystrokes due to delayed reactivity by binding `v-model:input-value` directly. |
| 2026-07-30 | Refactored backup system in `main.py`: extracted shared `_write_backup_files(dest_dir, label)` helper that dumps articles (with all fields), users, reviews, and contests as timestamped CSVs. Renamed overload-triggered backup to `do_emergency_backup_and_restart()` — writes to `backup/emergency/` and always creates new files (never overwrites). Added a new hourly scheduled backup via a daemon thread (`_hourly_backup_loop`) that writes to `backup/hourly/` every 60 minutes automatically on startup. |
| 2026-07-30 | Fixed bulk submission false-positive "Article does not exist" errors. Root cause: `query_wiki_replica_batch` in `database.py` stored results keyed by the original title string, but the lookup in `main.py` used the exact user-typed title — any capitalisation difference between the DB-returned page title and the submitted title caused a key miss. Fixed by keying all replica results by `orig_title.lower()` and doing the lookup with `t.lower()` in `main.py`. |
| 2026-07-30 | Fixed true root cause of bulk "Article does not exist": SQLAlchemy `text()` + `{"titles": tuple(chunk)}` does NOT expand a tuple into `IN (a, b, c)` placeholders — it binds the whole tuple as a single opaque value, so `IN :titles` matched nothing for 2+ articles (1 article accidentally worked). Fixed by adding `.bindparams(bindparam("titles", expanding=True))` to the query and passing `list(chunk)` instead of `tuple(chunk)`. |
| 2026-07-30 | Fixed MediaWiki API fallback `invalidparammix` error for multi-article submissions: MediaWiki API forbids combining `rvdir=newer` and `rvlimit=1` when `titles` contains multiple pipe-separated titles (`|`). `fetch_batch_http` in `main.py` updated to send concurrent single-title requests via `asyncio.gather`, avoiding `invalidparammix` completely. Enhanced `query_wiki_replica_batch` in `database.py` with `CONVERT(p.page_title USING utf8mb4)` character set conversion, title capitalization variants, and `p.page_first_rev_id` joins for Toolforge MariaDB replica queries. |
| 2026-07-30 | Full redesign of `ReviewQueue.vue` for mobile responsiveness and improved UX: replaced fixed-width sidebar with a full mobile tab system (Articles / Review tabs) driven by `mobileTab` ref. Added a sticky bottom nav bar on mobile. Redesigned sidebar with stats pills (Pending/Judged/Total), section dots, article cards with submitter name. Replaced flat review ribbon with a prominent sticky bottom `review-bar` that stacks vertically on mobile. Article header now shows meta chips, verdict badge, and a wiki link button. Improved bulk actions panel. All animations and transitions preserved. |
| 2026-07-30 | Subpage UI/UX & Mobile Responsiveness Polish: Color-coded all status/decision badges (accepted=green `#22c55e`, rejected=red `#ef4444`, pending=amber `#f59e0b`, skipped=grey `#94a3b8`) in `ActivityLog.vue` and `UserProfile.vue`. Colorized KPI numbers in `JuryStats.vue`. Added responsive media queries across `ContestLayout.vue` (scrollable sub-nav header), `ContestDashboard.vue` (responsive stats grid & hero actions), `ActivityLog.vue` (mobile-friendly user tables & timeline), `UserProfile.vue` (scrollable tables & vertical header), and `App.vue` (adaptive header for mobile screens). |
| 2026-07-30 | Fixed backup paths in `main.py` to use `Path.home()` (the Toolforge tool account home directory `~/`) instead of a path relative to the project source root. On startup the daemon thread now pre-creates both `~/backup/hourly/` and `~/backup/emergency/` so the folders are immediately visible alongside `logs/`, `replica.my.cnf`, and `service.manifest` in `~`. Added `from pathlib import Path` import. |
| 2026-07-30 | Backup events now written to the `SystemLog` table (`source="backup"`) on every success (level=`info`, message includes article/user/review/contest counts and dest path) and failure (level=`error`). Events appear in `GET /api/logs` and can be isolated with `?source=backup`. Fixed `status` field in the `/api/logs` response to reflect actual `level` (`info`/`error`/`warning`) instead of hardcoding `"error"` for all `SystemLog` rows. |
| 2026-07-30 | Modified _hourly_backup_loop in main.py so that it immediately performs a backup on server startup before sleeping, instead of sleeping for 1 hour first. |
| 2026-07-30 | Refactored \_write_backup_files\ to generate detailed CSV reports per contest (same format as /export/csv) instead of raw database dumps. Hourly backups overwrite \{contest_code}.csv\ while emergency backups append timestamps. |
| 2026-07-31 | Applied 12 bug fixes across backend and frontend: fixed wikitable newline export (`main.py`), replaced in-memory `article_locks` with DB-backed `ArticleLock` table for multi-worker support (`models.py`, `database.py`, `main.py`), fixed `ReviewQueue.vue` comment persistence, added error logging to bulk reviews, corrected cookie and JWT secret names in global exception handler, prevented `get_next_pending` from returning locked articles, fixed `on_behalf_of` payload construction in `SubmitArticles.vue`, fixed naive datetime comparison for article validation, removed `replica.my.cnf` fallback for app DB, fixed `title_map` overwriting issues, added `ContestUpdate` schema for PUT requests, and added monotonic fetch sequence guards to `SubmitArticles.vue`. |
| 2026-07-31 | Added Jury Members display underneath the countdown timer in `ContestDashboard.vue`. |
| 2026-07-31 | Added `oauth_access_token` column to `users` table to store MediaWiki OAuth 2.0 access token upon login. Updated `bot_edit_talk_pages` to use the submitter's (or jury's, if acting on behalf of someone) OAuth token instead of the bot account, effectively creating the talk page template on behalf of the submitter with proper attribution in the edit summary. |
| 2026-07-31 | Added `DELETE /api/articles/{article_id}` endpoint to allow contest jury or owner to completely remove articles from a contest (cascading to reviews and locks). Added "Remove" buttons (both single and bulk) in the `ReviewQueue.vue` UI. |
| 2026-07-31 | Added auto-migration in `database.py` for `oauth_access_token` column on the `users` table to fix internal server error during query execution on Toolforge. |
| 2026-08-01 | Updated Wikimedia OAuth scope in `backend/main.py` from `basic editpage` to `basic createeditmovepage`, enabling page creation, editing, and moving permissions for Feather’s talk-page edits. |
| 2026-08-01 | Fixed talk-page template formatting in `backend/main.py`: replaced the hardcoded `== Contest Submission ==` heading with the configured default `{{আলাপ পাতা}}` header so backend output matches the frontend preview. |
| 2026-08-01 | Translated the talk-page edit summary in `backend/main.py` to the exact Bengali text `প্রতিযোগিতার টেমপ্লেট যোগ করা হচ্ছে`. |
| 2026-08-01 | Removed extra leading and blank-line spacing from talk-page template output and synchronized the backend and frontend previews to render `{{আলাপ পাতা}}` immediately followed by the contest template. |
| 2026-08-01 | Fixed contest timezone handling: admin contest date/time inputs now use Bangladesh Standard Time (UTC+06:00) and convert to UTC before storage, so BST midnight matches Wikimedia revision timestamps correctly. |
| 2026-08-01 | Added an idempotent startup migration in `backend/database.py` that shifts existing contest start/end dates six hours earlier once, preserving their intended BST windows after the timezone fix. |
| 2026-08-01 | Updated `ReviewQueue.vue`: removed the talk-template ribbon from the judge view, neutralized its related colors, and added an arrow-only collapsible article sidebar control. |
| 2026-08-01 | Prevented jury members from reviewing their own submissions in both backend and queue filtering; enforced active review-lock conflicts; protected admin migration/log endpoints with owner authentication, changed forced migration to POST, and made migration execution idempotent. |
| 2026-08-01 | Adjusted the ReviewQueue sidebar arrow to use the dark panel theme instead of a bright white control. |
| 2026-08-01 | Corrected `JuryStats.vue` to count distinct articles judged per jury member, using the latest decision per article instead of counting repeated review actions. Updated table and export labels accordingly. |
| 2026-08-01 | Changed the valid bulk-submission result label in `SubmitArticles.vue` from `Accepted` to `Submitted` to avoid implying jury approval. |
| 2026-08-01 | Fixed mobile `ReviewQueue.vue` layout: kept the Articles/Review bottom navigation visible on both tabs, removed double height subtraction, and prevented review content from being clipped horizontally. |
| 2026-08-01 | Hid the desktop sidebar collapse arrow on mobile and constrained the mobile review action bar to the viewport with equal-width action buttons. |
| 2026-08-01 | Changed the desktop collapsed review sidebar to zero width, leaving only a high-contrast floating arrow instead of a thick sidebar strip. |
| 2026-08-01 | Fixed ReviewQueue layering and mobile action placement: the desktop sidebar arrow now stays above the article header, while the mobile review bar is pinned to the bottom with reserved preview space. |
| 2026-08-01 | Changed the ReviewQueue collapse control to an X/☰ hamburger toggle and fixed the mobile review bar to the viewport above the bottom navigation. |
| 2026-08-01 | Corrected the mobile ReviewQueue height calculation to prevent an oversized black container from occupying part of the screen behind the fixed bottom navigation. |
