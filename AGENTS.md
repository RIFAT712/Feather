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
├── Procfile                    # Toolforge process command runner configuration
├── requirements.txt            # Root requirements pointing to backend requirements (Toolforge build detection)
│
├── backend\
│   ├── .env                    # Environment variables (OAuth creds, secrets)
│   ├── main.py                 # FastAPI app — all API routes
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
        │   └── ui\
        │       ├── NumberRuleInput.vue  # Reusable numeric rule input
        │       └── RuleToggleCard.vue   # Reusable rule toggle card
        └── views\
            ├── Home.vue            # Landing / contest list
            ├── AdminDashboard.vue  # Owner-only: manage contests & juries
            ├── ContestLayout.vue   # Wrapper layout for contest routes
            ├── ContestDashboard.vue# Contest overview page
            ├── ContestConfig.vue   # Owner-only contest settings & jury management
            ├── ContestResult.vue   # Public contest results page
            ├── SubmitArticles.vue  # Bulk article submission
            ├── ReviewQueue.vue     # Jury article review queue with article preview
            ├── ActivityLog.vue     # Full submission/review log
            ├── JuryStats.vue       # Jury performance charts & article moderation
            ├── GlobalProfile.vue   # Cross-contest user profile (/user/:username)
            └── UserProfile.vue     # Per-user submission & review history (contest-scoped)
```

---

## Database Models (SQLAlchemy)

| Model          | Table           | Key Fields                                                                |
| -------------- | --------------- | ------------------------------------------------------------------------- |
| **User**       | `users`         | `id`, `wiki_username` (unique), `role` (participant \| owner), `oauth_access_token`             |
| **Contest**     | `contests`      | `id`, `code` (6-char hex, unique), `name`, `start_date`, `end_date`, `rule_must_be_creator`, `min_bytes`, `min_words`, `min_refs`, `rule_no_redirect`, `rule_no_disambig`, `rule_mainspace_only`, `allow_self_review`, `add_talk_template`, `talk_template_name`, `include_talk_header` |
| **ContestJury** | `contest_jury` | `id`, `contest_id` (FK), `user_id` (FK)                                  |
| **ContestJuryRestriction** | `contest_jury_restrictions` | `id`, `contest_id` (FK), `jury_user_id` (FK), `submitter_user_id` (FK), unique contest/jury/submitter pair |
| **ContestBannedUser** | `contest_banned_users` | `id`, `contest_id` (FK), `user_id` (FK), unique contest/user pair; hides submitter articles from review-v2 |
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
| GET    | `/api/admin/contests/{code}/jury-restrictions` | List jury/submitter COI restrictions | Owner |
| POST   | `/api/admin/contests/{code}/jury-restrictions` | Add jury/submitter COI restriction | Owner |
| DELETE | `/api/admin/contests/{code}/jury-restrictions/{restriction_id}` | Remove COI restriction | Owner |
| GET    | `/api/admin/contests/{code}/banned-users` | List review-v2 exclusions | Owner |
| POST   | `/api/admin/contests/{code}/banned-users` | Hide a submitter from review-v2 | Owner |
| DELETE | `/api/admin/contests/{code}/banned-users/{ban_id}` | Restore a submitter to review-v2 | Owner |
| GET    | `/api/admin/contests/{code}/export/csv`  | Export contest submissions CSV     | Owner |
| GET    | `/api/admin/contests/{code}/export/json` | Export contest submissions JSON    | Owner |
| GET    | `/api/admin/contests/{code}/export/wikitable` | Export contest submissions Wikitable | Owner |
| GET    | `/api/admin/backup/download`          | Download current SQLite database or MariaDB dump | Owner |

### Articles & Reviews
| Method | Path                                          | Description                        | Auth       |
| ------ | --------------------------------------------- | ---------------------------------- | ---------- |
| POST   | `/api/submit-bulk`                            | Bulk submit articles               | Required   |
| GET    | `/api/articles/{contest_code}/pending/next`   | Next pending article for review    | Jury/Owner |
| POST   | `/api/articles/{article_id}/lock`             | Lock article for review            | Required   |
| POST   | `/api/articles/{article_id}/review`           | Submit review decision             | Jury/Owner |
| POST   | `/api/articles/bulk-review`                   | Review up to 500 articles in one request | Jury/Owner |
| DELETE | `/api/articles/{article_id}`                  | Remove article from contest        | Jury/Owner |
| POST   | `/api/articles/bulk-delete`                   | Remove up to 500 articles in one request | Jury/Owner |
| GET    | `/api/jury-panel/contests/{code}/articles/page` | Paginated assigned jury queue with counts | Jury/Owner |
| GET    | `/api/jury-panel/contests/{code}/progress`     | Assigned/judged jury progress      | Jury/Owner |
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
| `ENABLE_HOURLY_BACKUP`    | Optional hourly full export; disabled by default so startup and request handling stay responsive |
| `ENABLE_AUTO_RECOVERY`    | Optional overload-triggered backup/restart; disabled by default |

Before schema migrations run, the backend writes a rollback snapshot under `backup/pre_migration/` in the project codebase (or under `BACKUP_ROOT/backup/pre_migration/` when `BACKUP_ROOT` is set). SQLite uses exact database-file copies. Toolforge MariaDB uses `mysqldump` when available and otherwise stores every application table, column, and row in JSON; any local SQLite projection databases are copied too. These snapshots contain credentials/tokens and should be kept private.

---

## Change Log

| 2026-08-28 | Switched the local application and jury projection SQLite databases from TRUNCATE journaling to WAL mode with 60-second busy timeouts and pooled connections, allowing API reads to continue during submissions, projection refreshes, and maintenance writes. |

| 2026-08-28 | Jury projection rebuilds now recover reviewed-page ownership from the latest non-skipped reviewer, keep those pages assigned to that jury, count them in the jury load, and distribute only pending pages evenly across eligible juries; the assignment fingerprint version forces a one-time repair of existing projections. |

| 2026-08-28 | Removed startup and health-probe-triggered full database dumps; pre-migration snapshots now run only when metadata detects a pending schema change, hourly backups are opt-in and delayed until after the first hour, and contest counts use indexed aggregated SQL queries to keep API responses responsive on large databases. |

| 2026-08-28 | Optimized the public contest list endpoint to use grouped SQL counts instead of loading every article relationship, preventing the home page refresh from blocking the Toolforge app on large contests. |

| 2026-08-28 | Optimized the first jury-panel projection rebuild with 500-row batches and serialized concurrent syncs; existing pending articles are now rebalanced across eligible juries during the rebuild, preventing duplicate metadata inserts and overlapping MariaDB reads on fresh Toolforge containers. |

| 2026-08-28 | Fixed Jury Progress loading by moving its initial API request into `onMounted`, so `/jury` no longer reports “No jury assignment data available yet” on first render. |
| 2026-08-28 | Added bounded jury queue pagination with server-side totals/status counts and bulk review/delete endpoints (up to 500 IDs per request); Review v2 now requests 250-item pages and appends additional server pages on demand. |
| 2026-08-28 | Added recoverable article deletion snapshots with a five-minute, permission-checked undo token; single and bulk deletion responses now expose restore metadata, and Review v2/Jury Stats show an Undo action. The duplicate Pending Review count was removed from the queue group header because the pending total is already shown in the compact stats strip. |
| 2026-08-28 | Fixed Undo to retain multiple recent deletion tokens and restore them together; bulk deletion reconciliation in Review v2 now refreshes silently without showing the full-screen queue loader. |
| 2026-08-28 | Removed the optional article-deletion Undo feature at the user’s request; deletion snapshots, restore endpoint, undo UI, and related migration were removed. Bulk deletion remains available without recovery prompts. |
| 2026-08-28 | Closed `/api/submit-bulk` outside the contest start/end window, including before-start protection; Submit Articles also disables fetching and submitting with a clear contest-closed message, while backend enforcement remains authoritative. |
| 2026-08-28 | Simplified incremental loading controls by removing misleading client-side “remaining” counts; progress-table Remaining values are unchanged because they represent jury assignment data. |
| 2026-08-28 | Removed the unnecessary mobile preview bottom margin that created a visible gap before the fixed review decision panel. |
| 2026-08-28 | Made mobile review decisions a single four-button inline row with compact colored icons and labels: Accept, Reject, Skip, and Delete; desktop action layout is unchanged. |
| 2026-08-28 | Added a compact mobile review workspace for `/jury/review`: tightened queue rows/groups, owner controls, statistics, article header, decision dock, action buttons, mobile navigation, and review top-bar spacing while preserving desktop behavior. |
| 2026-08-28 | Added the missing light-mode review top-bar theme so `/jury/review-v2` switches its Back to Jury control, contest title, borders, and background to the shared light palette. |
| 2026-08-28 | Redesigned the full-screen review top bar with a slate-blue gradient shell, compact elevated Back to Jury control, readable contest title, active-status accent, focus state, and improved responsive spacing. |
| 2026-08-28 | Fixed empty Jury Progress data by moving the progress API request into `JuryStats.vue` initial loading; article deletion handlers no longer own the initial progress fetch. |
| 2026-08-28 | Updated Jury Progress rows to show each member’s judged/assigned count directly beside the completion bar, such as `1,245 / 3,319`. |
| 2026-08-28 | Kept the original Jury Activity Breakdown table and added Jury Progress as a separate section at the end of `/:code/jury`, showing assigned, judged, remaining, and completion percentage. |
| 2026-08-28 | Added the missing contest `/progress` route as an alias to the Jury Progress/Statistics view, fixing the blank `/:code/progress` page while preserving the existing `/jury` route. |
| 2026-08-28 | Restricted the ReviewQueue “Other Judges” article section to owners, added owner/current-jury scoped `/api/jury-panel/contests/{code}/progress`, and replaced Jury Statistics activity rows with assigned/judged/remaining progress and completion percentage. |
| 2026-08-28 | Improved jury-panel distribution after COI/self-review changes: assignment metadata now fingerprints the actual restrictions and self-review setting, pending work is balanced against each jury’s existing reviewed load, and self-review eligibility follows `allow_self_review`. |
| 2026-08-28 | Fixed bulk review preview state: when the currently previewed article is included in a successful bulk Accept/Reject, the old preview is cleared before advancing; preview request IDs prevent stale article responses from overwriting the next article. |
| 2026-08-28 | Fixed bulk Accept/Reject to refresh the review queue silently with `fetchArticles(false)` and added explicit non-submit behavior to bulk action buttons, preventing the loading screen from replacing the workspace. |
| 2026-08-28 | Made the post-review background queue reconciliation silent by calling `fetchArticles(false)`, preventing the full “Loading review queue…” state from replacing the workspace after Accept/Reject. |
| 2026-08-28 | Changed ReviewQueue Accept/Reject handling to update the local article queue optimistically, advance immediately without waiting for a full refetch, reconcile server data in the background, and explicitly prevent native button submission/navigation. |
| 2026-08-28 | Simplified the ReviewQueue bulk comment placeholder to `Add comment`. |
| 2026-08-28 | Compacted the ReviewQueue owner View as controls and Total/Pending/OK/Rejected statistics strip to reduce left-panel height and preserve article navigation space. |
| 2026-08-28 | Compacted the ReviewQueue bulk-review comment panel with tighter padding, inline truncated helper text, and a smaller resizable textarea so the left article queue retains more navigation space when multiple articles are selected. |
| 2026-08-28 | Optimized `/jury/review-v2` sidebar expansion by unmounting collapsed queue lists, rendering each expanded section in 100-item batches with Load more controls, and replacing the expensive grid-height transition; corrected group arrows to point right when collapsed and down when expanded. |
| 2026-08-28 | Removed the unintended white backing from the grouped Jury submissions section so the page uses one continuous blue-gray canvas while retaining elevated white header and user cards. |
| 2026-08-28 | Refined the grouped Jury submission header with a dedicated contest-submissions label, article/user/selection summary pills, clearer action grouping, improved button hierarchy, and responsive mobile behavior. |
| 2026-08-28 | Updated the Jury Statistics submission workspace to group all submitted articles by submitter in collapsed user cards, with per-article selection, per-user select-all, global select-all, and bulk deletion through the existing article removal endpoint. |
| 2026-08-28 | Added contest-scoped submitter bans: owners can hide users from the `/review-v2` jury panel through Contest Configuration; banned articles remain in contest records and exports, while the jury projection removes them and rebuilds when bans change. Added `ContestBannedUser`, migration, and owner-only ban management APIs. |
| 2026-08-28 | Redesigned the owner Admin Management Suite styling around the shared light Feather palette with clearer command navigation, calmer surfaces, readable tables/forms, responsive controls, and a review-exclusion KPI; admin contest-list and stats responses now include ban counts. |
| 2026-08-28 | Replaced the Admin Management Suite's prominent emoji-only KPI and navigation indicators with local Heroicons-style SVG assets under `frontend-vue/src/assets/admin-icons/`; CSS masks keep the icons scalable and CDN-independent. |
| 2026-08-28 | Improved non-review page text contrast by normalizing legacy gray supporting-text selectors to the readable `--feather-muted` token in `light-theme.css`; the ReviewQueue theme remains isolated. |
| 2026-08-28 | Fixed light-theme activity-log count badges so values such as per-user submission counts use navy text on a readable blue-gray surface with a defined border. |
| 2026-08-28 | Added a final light-theme contrast pass for legacy button and label classes across all non-review stylesheets, including `.preset-chip`, rule badges, jury chips, tabs, secondary actions, and slate utility text. |
| 2026-08-28 | Paired remaining legacy non-review dark panels with light surfaces and readable foreground tokens, preventing navy text from appearing on dark backgrounds across logs, stats, submissions, profiles, results, admin, and configuration views. |
| 2026-08-28 | Corrected the Activity Log view switch so `.toggle-bar` remains a quiet wrapper and only the segmented control receives the tinted control surface, avoiding an oversized white block. |
| 2026-08-28 | Completed the Activity Log component contrast audit: restored semantic surfaces and readable dark text for Total, Accepted, Rejected, Pending, and Errors stat chips instead of applying the generic white-panel rule. |
| 2026-08-28 | Completed a component-level Jury Stats light-theme audit, pairing its scoped hero, KPI, chart, table, submission, and moderation surfaces with readable Feather foreground colors and updated chart labels/ticks. |
| 2026-08-28 | Rebuilt the Jury Stats route from a fresh `JuryStatsFresh.css` canvas instead of layering overrides over its dark legacy stylesheet; the existing workflow now uses a clean command-center composition with responsive analytics and moderation sections. |
| 2026-08-28 | Strengthened the Activity Log active `Per-User Table` tab override with explicit white text and text-fill color so the selected control cannot inherit a dark foreground. |
| 2026-08-28 | Enhanced the Admin Dashboard Create New Contest wizard with a live setup summary, date-duration readout, core-rule/jury/template counters, connected step navigation, and responsive wizard footer guidance while preserving the existing form payload and API flow. |
| 2026-08-28 | Redesigned `/:code/config` with an owner-controls header, contest code and live summary strip, clearer tab navigation, lighter form/rule surfaces, two-column jury management layout, and responsive mobile behavior. |
| 2026-08-28 | Made the contest configuration route a full-width continuous Feather canvas so centered content no longer creates mismatched left/right background bands. |
| 2026-08-28 | Fixed the normal contest shell background split by changing `.contest-content` from a white fill to the shared Feather canvas; configuration content now grows uniformly without blue-center/white-side bands. |
| 2026-08-28 | Restyled contest configuration COI restriction rows as readable light cards with emphasized jury/submitter names, distinct remove actions, and mobile stacking. |
| 2026-08-28 | Fixed Activity Log segmented tabs such as `Per-User Table` so inactive labels remain readable and the active tab uses the Feather accent with white text and a clear selected state. |

| 2026-08-28 | Completed a second light-theme audit: added explicit overrides for remaining dark admin, contest, profile, log, results, jury, and article-submission panels, including their inputs, lists, tables, modal layers, and action states; the full-screen review workspace remains independently themed. |
| 2026-08-28 | Fixed the normal contest shell used by `/:code`: explicitly overrides the scoped dark layout, header, content, navigation, active-link, and date-chip styles while leaving `/jury/review` and `/jury/review-v2` untouched. |
| 2026-08-28 | Extracted every Vue view’s embedded scoped stylesheet into `frontend-vue/src/styles/views/*.css` and switched the views to external `<style scoped src>` files; shared application styling remains in `src/style.css`, making the light theme and per-view CSS maintainable without changing selector scoping. |
| 2026-08-28 | Removed duplicate global dark/light CSS layers and the unused Codex dark-mode import; `src/style.css` now contains only structural defaults, while `src/styles/light-theme.css` is the single shared application theme. |
| 2026-08-28 | Redesigned `ContestDashboard.vue` hero into a light contest overview layout with a clear title/date area, dedicated countdown and jury panel, stronger action hierarchy, responsive spacing, and light statistic cards; removed inline hero styles. |
| 2026-08-28 | Restored shared form, focus, Codex menu/progress, button, and document-color behavior removed during the CSS deduplication pass; these are now maintained once in `styles/light-theme.css` using light tokens. |
| 2026-08-28 | Redesigned the `/` home page in `Home.css` with a light editorial hero, restrained ambient decoration, clearer contest cards, accessible status colors, improved spacing, and mobile-specific layout behavior while preserving existing content and navigation. |
| 2026-08-28 | Unified the home page into one continuous light surface by removing the hero wave divider and separate section boundary; welcome content and contest discovery now share the same visual canvas and spacing rhythm. |
| 2026-08-28 | Redesigned the bottom cookie-consent panel for the light theme with a white elevated surface, readable navy/muted text, light secondary action, and consistent border/shadow treatment. |
| 2026-08-28 | Fixed the remaining black strip beneath the home page by overriding the dark `App.vue` `.app-layout` and `.app-main` wrappers with the shared light background. |
| 2026-08-28 | Simplified the home hero by removing the grid texture and section-divider styling that created a distracting white line above the Contests heading; the page now uses a quieter continuous light background. |
| 2026-08-28 | Made the home page `.section-header` transparent so the Contests label no longer receives the shared alternate-surface background and the unified page canvas remains visually continuous. |
| 2026-08-28 | Redesigned the app-wide navbar in extracted `styles/App.css` with a light glass shell, clearer active navigation, refined brand/account controls, and a compact mobile layout; extracted the remaining `App.vue` stylesheet from the component. |
| 2026-08-28 | Added `docs/STYLE_GUIDE.md` documenting the light palette, component rules, CSS ownership, review-route exception, maintenance workflow, and the `frontend-app-builder` and `human-writing-style` skills used for the visual work. |
| 2026-08-28 | Applied the Review v2 slate/navy light palette across all non-review routes via a scoped global theme layer; `/review-v2` retains its independent dark/light switch. Updated surfaces, typography, forms, Codex controls, tables, navigation, and scrollbars. |
| 2026-08-28 | Changed the ReviewQueue default theme from dark to light so the entire application opens in the shared light palette; an explicitly saved dark preference and the manual theme switch remain supported. |
| 2026-08-28 | Extended pre-migration snapshots to preserve every local SQLite database, including `jury_panel.db`, alongside the primary application database. |
| 2026-08-28 | Excluded runtime `backup/` snapshots from version control because pre-migration backups contain private database/session data; backups remain stored on the deployed Toolforge filesystem. |
| 2026-08-28 | Added a mandatory pre-migration database snapshot: SQLite databases are copied exactly, while Toolforge MariaDB uses `mysqldump` with a complete table/row JSON fallback; migrations stop if an existing database cannot be backed up. |
| 2026-08-28 | Added an owner-only Admin Dashboard `Download Backup` button and `/api/admin/backup/download`; SQLite downloads the live DB file, while Toolforge downloads a freshly generated SQL/JSON database dump. |
| 2026-08-28 | Added an explicit idempotent `contest_jury_restrictions` table migration for Toolforge upgrades; existing database tables and rows are preserved, and the SQLite jury projection now has a busy timeout for concurrent access. |
| 2026-08-28 | Made contest configuration loading aggregate article counts and submitters in SQL instead of loading every article, and added a 30-second SQLite busy timeout to the jury projection for concurrent refresh safety. |
| 2026-08-28 | Added conflict-of-interest-aware jury distribution: juries cannot receive their own articles or configured submitter conflicts; pending assignments are balanced across eligible juries, and backend review endpoints enforce the same restrictions. Added owner controls in Contest Configuration to add/remove jury-versus-submitter restrictions. |
| 2026-08-28 | Added a projection-count recovery check so queues previously emptied by the refresh regression automatically rebuild once after deployment. |
| 2026-08-28 | Fixed a jury-panel refresh regression that rebuilt/deleted the projection on unchanged polls; also replaced per-article projection lookups with a single preload query to reduce initial sync latency. |
| 2026-08-28 | Fixed the ReviewQueue light theme for the left article-list scrollbar and bulk-selection checkboxes, including native light control rendering and scrollbar track/thumb colors. |
| 2026-08-28 | Prevented aborted ReviewQueue refreshes from incorrectly clearing the loading state of a newer request. |
| 2026-08-28 | Optimized ReviewQueue refreshes by caching the contest role, aborting superseded article requests, and cancelling in-flight polling on unmount to prevent overlapping network work. |
| 2026-08-28 | Optimized jury-panel refreshes with a per-contest projection fingerprint; unchanged queues skip full article/review mirroring while still preserving persistent assignments and detecting new submissions or reviews. |
| 2026-08-28 | Added a bulk review comment panel to `ReviewQueue.vue` when multiple articles are selected; the entered comment is submitted with each bulk accept/reject decision and clears when the selection drops below two. |
| 2026-08-28 | Fixed remaining ReviewQueue light-mode surfaces: the article sidebar scroll container and comment textarea now override global dark native-form styling, including focus and placeholder states. |
| 2026-08-28 | Fixed jury-panel projection freshness: article statuses, validation metadata, and non-skipped review history are synchronized on each queue read, and deleted legacy articles are removed from the projection. Assignment ownership remains persistent. |
| 2026-08-28 | Updated `ReviewQueue.vue` with a slate/navy color palette and a persistent Light/Dark mode switch stored in `localStorage`; existing review behavior remains unchanged. |
| 2026-08-28 | Completed ReviewQueue theme switching: light/dark variables now cover the full review shell, and the wiki article iframe rebuilds with a matching light or dark stylesheet when the theme changes. |
| 2026-08-28 | Reworked the wiki preview dark stylesheet to use the slate/navy review palette instead of pure black, white, and grey surfaces. |
| 2026-08-28 | Applied the provided HSL/OKLCH color palette to ReviewQueue dark and light theme tokens, with HSL fallbacks and OKLCH overrides. |
| 2026-08-28 | Aligned the outer article preview container, review input, and preview error state with the new theme palette instead of the remaining hardcoded dark-blue/black values. |
| 2026-08-28 | Added a dedicated Errored tab to `JuryStats.vue` for validation-failed submissions, with select-all, multi-select, and bulk deletion using the existing article-delete API. |
| 2026-08-28 | Optimized `/api/jury-panel/contests/{code}/articles`: owner Judge mode now filters server-side with `view_as`, and the review database skips full 10k-article mirroring when its article count is already current. |
| 2026-08-28 | Fixed local wiki-replica configuration loading by loading `backend/.env` before importing `database.py`; configured the Bengali replica tunnel to use local port `4407` instead of the English replica port. |
| 2026-08-28 | Added article selection ranges of 10, 100, 1,000, and 2,000 in `SubmitArticles.vue`; unavailable ranges are disabled and manual selection is capped at the chosen range. |
| 2026-08-28 | Restored the original `Select all` behavior as an explicit selection-range option alongside the numeric ranges. |
| 2026-08-28 | Changed submission ranges to auto-apply on dropdown changes and added a Custom article-count input; numeric and custom limits are enforced for manual checkbox selection. |
| 2026-08-28 | Made the submission range selector start with an unset `—` placeholder so no articles are selected until the user explicitly chooses a range. |
| 2026-08-28 | Improved large submission-list performance by rendering available articles in batches of 200 and already-submitted articles in batches of 100 with Load more controls; selection still operates on the complete in-memory data set. |
| 2026-08-28 | Added `/jury/review-v2`, reusing the existing review interface with `GET /api/jury-panel/contests/{code}/articles`; the original `/jury/review` remains the all-articles fallback queue. |
| 2026-08-28 | Updated the Jury Stats Start Judging action to open `/jury/review-v2`; the contest layout now treats both review routes as full-screen review pages. |
| 2026-08-28 | Fixed `/jury/review-v2` document overflow by making `App.vue` hide the app header on the new full-screen review route; internal queue and preview areas retain scrolling. |
| 2026-08-28 | Added sanitized `backend/.env.example` and expanded `services/jury-panel/.env.example` with required local configuration placeholders; no secret values were copied. |
| 2026-08-28 | Added `backend/jury_panel_store.py` and `GET /api/jury-panel/contests/{code}/articles`; the new endpoint mirrors read-only article data into `backend/jury_panel.db` and assigns pending articles across juries while leaving the legacy queue endpoint unchanged. |

| Date       | Change Description                                              |
| 2026-08-07 | Removed both navigation bars (app-level header and contest header) from the `/jury/review` route. `App.vue` now conditionally hides `<header>` when `route.path` ends with `/jury/review`. `ContestLayout.vue` replaces the contest header with a slim `review-topbar` containing a `← Back to Jury` button that navigates to `/{code}/jury`. The review layout uses `100dvh` (full viewport) since the app header is absent. |
| 2026-08-28 | Updated the embedded wiki preview dark theme to use the configured OKLCH palette for its page, tables, infoboxes, navigation frames, headings, and inline-style overrides, preventing the preview iframe from remaining black while the review shell uses the selected theme. |
| 2026-08-28 | Fixed ReviewQueue Codex icons inheriting incompatible dark/light colors by explicitly binding icon SVGs to the review theme and defining readable hover and action-button states. |
| 2026-08-28 | Improved ReviewQueue sidebar toggling with a shorter width-only transition to reduce layout reflow lag, and added light-mode overrides for remaining dark status chips, wiki link, error message, inputs, and borders. |
| 2026-08-07 | Fixed mobile scroll issues across the tool: (1) `ContestLayout.vue` switched from `100vh` to `100dvh` so content is no longer clipped behind the mobile browser address bar; (2) on mobile, non-review pages (Submit, Dashboard, Results) now use `overflow-y:auto` instead of `overflow:hidden` so they are scrollable; only the review shell stays locked; (3) `ReviewQueue.vue` mobile `.review-area` switched from `overflow:hidden` to `overflow-y:auto` + `-webkit-overflow-scrolling:touch` + `padding-bottom:174px` so the article preview is fully scrollable above the fixed review bar; (4) `style.css` disables `scrollbar-gutter:stable` on mobile (overlay scrollbars need no gutter) and adds `overscroll-behavior-y:none` to prevent accidental pull-to-refresh. |
| 2026-08-07 | Fixed two `ReviewQueue.vue` bugs: (1) Preview iframe link colors restored to Wikipedia standard — blue (#3366cc) for unvisited, purple (#795cb2) for visited, and red (#d33) for missing-page red-links (`.new` class); previously all links were overridden to gray (#d1d5db). (2) Removed random article selection on mount and after bulk actions — the queue now always advances serially to `availableNewArticles[0]` so articles are reviewed in submission order. |
| 2026-08-06 | Removed unused files and components: deleted root-level utility scripts (`app.py`, `recolor.py`, `data.json`, `names.txt`), the `benchmark/` directory and `benchmark_results.json`, the Vite starter assets (`assets/hero.png`, `assets/vite.svg`, `assets/vue.svg`), and the four obsolete starter components (`components/HelloWorld.vue`, `AdminPanel.vue`, `BulkSubmit.vue`, `ReviewQueue.vue`). Removed the duplicate `jury-stats` route alias from `router.js` and updated `ContestDashboard.vue` to link to `/jury` instead. |
| 2026-08-06 | Fixed login-related bugs: (1) `delete_cookie` in logout now passes matching `httponly/secure/samesite/path` attributes so browsers actually clear it; (2) `jwt.ExpiredSignatureError` is now caught separately from generic `PyJWTError` for clearer 401 messages; (3) cookie consent banner now only shows when the user is logged in; (4) `?error=login_failed` query param is now detected and displayed as a red error box on the login page, then cleaned from the URL; (5) auth callback now logs full traceback on failure. |
| 2026-08-06 | Added persistent auth cookie (`max_age=604800`) so the JWT survives browser restarts (previously a session cookie). Added a cookie consent banner (`App.vue`) that appears on first login, slides up from the bottom, and stores the user's Accept/Decline choice in `localStorage` under `cookie_consent`. |
| 2026-08-02 | Fixed `ReviewQueue.vue` showing non-pending articles as reviewable, which caused expected backend `409 Conflict` responses; the queue now filters to pending articles and displays the backend conflict detail. |
| 2026-08-02 | Synchronized dashboard and review-queue accepted, rejected, pending, and total article counts using article statuses from the contest log; both views now refresh live every five seconds. |
| 2026-08-02 | Added a read-only ReviewQueue section showing finalized articles reviewed by other judges, while preserving backend protection against duplicate decisions. |
| 2026-08-02 | Added a Jury Comment column to the ActivityLog Per-User Table, rendering all non-empty comments left by reviewers for each submitted article. |
| 2026-08-02 | Fixed HTTP validation failures for usernames containing accented or non-ASCII characters by percent-encoding the username in the MediaWiki API `User-Agent` header. |
| 2026-08-02 | Allowed jurors to reopen and update their own review decision and comment, while keeping other jurors blocked from reviewing finalized articles. |
| 2026-08-02 | Made the other-judge review section collapsible and placed it after My Judged; removed redundant reviewer names from the Jury Comment column because the reviewer is already shown separately. |
| 2026-08-02 | Preloaded the juror's previous comment when reopening an article from My Judged, allowing the comment to be edited and resubmitted. |
| 2026-08-02 | Redesigned ReviewQueue with a monochrome black-and-gray dark theme, clearer desktop/mobile hierarchy, neutral containers, and color limited to action buttons and warnings. |
| 2026-08-02 | Switched the dark ReviewQueue surfaces, borders, text, and Codex controls to WikimediaUI Codex dark-mode design tokens instead of standalone theme values. |
| 2026-08-02 | Replaced review workflow emojis with Codex icons in ReviewQueue, ActivityLog, and JuryStats. |
| 2026-08-02 | Rebuilt the ReviewQueue desktop layout around a persistent article queue, central preview, and dedicated right-side decision panel; retained the mobile tab workflow. |
| 2026-08-02 | Added an all-submitted-articles moderation list to ReviewQueue so jury members can remove pending, accepted, rejected, or validation-failed submissions directly. |
| 2026-08-02 | Restored the ReviewQueue bottom action bar and compacted the sidebar, article header, and review controls to reduce thick ribbon-like layout panels. |
| 2026-08-02 | Moved all-submitted-article moderation into a dedicated `JuryStats.vue` tab with refresh and removal controls. Simplified `ReviewQueue.vue` to one scrollable sidebar, removed its collapse rail, and keeps My Judged before other juries' reviews. |
| 2026-08-02 | Rebuilt and committed `frontend-vue/dist` deployment assets after confirming Toolforge serves the committed SPA bundle directly through FastAPI. |
| 2026-08-02 | Added a collapsible review decision sidebar, standardized queue section arrows with Codex icons, and reduced the article header height and spacing. |
| 2026-08-02 | Restored a separate collapsible left article sidebar control with Codex expand/collapse icons while keeping the mobile queue navigation unchanged. |
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
| 2026-08-01 | Fixed review lock lifecycle: added an authenticated lock-release endpoint; Skip and leaving an undecided article release its lock, while Accept/Reject retain the lock permanently and finalized articles are rejected from further reviews to prevent double judging. |
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
| 2026-08-01 | Kept a transparent 28px desktop sidebar rail so the hamburger control remains visible after collapsing instead of being clipped by the zero-width panel. |
| 2026-08-01 | Removed the artificial mobile preview bottom padding and fixed-position review bar that created a large black block; the review bar now stays in normal flex flow at the bottom of the review panel. |
| 2026-08-01 | Restored a definite mobile contest viewport height so the ReviewQueue flex chain can size the preview iframe instead of collapsing it to zero height. |
| 2026-08-01 | Redesigned the ReviewQueue mobile experience as a dedicated Articles/Review two-screen workflow with card-based article lists, compact stats, a stable preview viewport, compact review actions, safe-area-aware bottom navigation, and no desktop sidebar controls on mobile. |
| 2026-08-01 | On mobile jury review, removed the contest title/navigation header and locked the page shell against scrolling; only the wiki preview iframe remains scrollable. |
| 2026-08-01 | Fixed the remaining mobile review black-space issue by removing competing 100% flex heights from `.main-layout` and `.review-area`; the preview now uses only the available flexible height above the review bar and bottom navigation. |
| 2026-08-01 | Made mobile review tools a fixed bottom dock directly above the Articles/Review navigation, with reserved panel space so the dock never covers the wiki preview. |
| 2026-08-09 | Redesigned the review panel interactions in `ReviewQueue.vue` using design engineering principles (scale on press, custom `cubic-bezier` easings, and CSS grid transitions instead of v-show) to improve UI polish and perceived performance. |
| 2026-08-09 | Executed a full UI redesign of `ReviewQueue.vue`. Upgraded the desktop layout from a drawer-based 1-column view to a modern 3-column grid (Queue on left, Preview in center, Decision Panel on right). Introduced a glassmorphic dark theme (Zinc 950 base with semi-transparent surfaces and blur filters), replaced single-line input with a text area for comments, and added rich gradient buttons for primary actions, fulfilling design engineering directives for a premium feel. |
| 2026-08-09 | Adjusted `ReviewQueue.vue` layout based on feedback: reverted from 3-column grid to a 2-column view with a collapsible left panel and the decision panel placed at the bottom. Removed glassmorphic transparency in favor of solid dark colors (Zinc 900) for better readability while retaining design engineering scaling interactions. |
