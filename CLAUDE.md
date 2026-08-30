# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Feather ("Article Contest Tool") is a wiki article contest management tool for Bengali Wiktionary (`bn.wiktionary.org`). Organizers create contests and assign juries; participants submit article titles, which are validated against MediaWiki (via a Toolforge MariaDB replica or the public API) for authorship/date/size/reference rules. Owner is hardcoded as wiki username `R1F4T`.

**`AGENTS.md` at the repo root is the authoritative, continuously-updated project doc** — full API table, DB schema, business logic, and a dated change log going back to project inception. Read it before making non-trivial changes, and **update it (append to the Change Log table, and edit the structure/schema/endpoint sections if they changed) after every change** — file renames, new endpoints, schema changes, new deps, features, fixes. This is an existing convention in the repo, not something introduced by this file.

`docs/STYLE_GUIDE.md` is authoritative for frontend visual/CSS conventions (Feather light palette, token names, CSS file ownership, the `/jury/review*` theming exception). Read it before touching any Vue view's styling.

## Commands

Backend (from `backend/`):
```bash
.\venv\Scripts\activate          # Windows venv
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend (from `frontend-vue/`):
```bash
npm install
npm run dev       # dev server on :3000, proxies /api and /auth to :8000
npm run build     # required before verifying CSS/visual changes — see STYLE_GUIDE.md
npm run preview
```

There is no test suite (no pytest/vitest config) and no lint script configured — verify backend changes by running the server and exercising endpoints, and verify frontend changes with `npm run build` plus manual checks at both desktop and mobile widths.

Production process (Toolforge, via `Procfile`): `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`. The built `frontend-vue/dist` SPA is served by FastAPI itself (`StaticFiles`/`FileResponse` in `main.py`); it must be built and, per current workflow, committed to the repo for Toolforge to serve it (`dist/` is gitignored in `frontend-vue/.gitignore` — see STYLE_GUIDE.md step 6 and the 2026-07-29 AGENTS.md change log entry for why this matters).

## Architecture

**The deployed application is a monolith**, not the `services/` microservice split (see below):

- `backend/main.py` — single FastAPI app holding effectively all routes (auth, contests, admin, articles/reviews, jury-panel, exports, backups, SPA serving). It's large (~2100 lines); use Grep for `@app.get|post|put|delete` to jump to a route rather than reading it linearly.
- `backend/models.py` — SQLAlchemy models: `User`, `Contest`, `ContestJury`, `ContestJuryRestriction` (COI pairs), `ContestBannedUser`, `Article`, `Review`, `ArticleLock` (DB-backed review locks, not in-memory).
- `backend/database.py` — engine/session setup. Supports SQLite locally and MariaDB/MySQL on Toolforge (auto-configured from `TOOL_TOOLSDB_*` env vars or `~/replica.my.cnf`), plus a separate read path to the Wiktionary MariaDB replica (`bnwiktionary_p`) for fast article validation, with fallback to the public MediaWiki HTTP API. Runs idempotent auto-migrations on startup.
- Jury-queue assignment lives directly on `Article.assigned_to_id` (no separate projection database — an earlier design mirrored data into a second SQLite file, which was a persistent source of sync/staleness bugs and was merged away). `rebalance_pending_articles()` (places unowned articles), `redistribute_pending_articles()` (re-plans the whole pending pool to re-level the queues), `plan_scarcity_first()` (the scarcity-first allocator both use), and `backfill_reviewed_ownership()` in `backend/main.py` handle COI-aware load balancing; `review_article` sets ownership directly on decision. This is the most change-log-heavy area of the backend — read the relevant AGENTS.md entries before touching jury assignment logic.
- `frontend-vue/` — Vue 3 + Vite SPA using Wikimedia Codex components. Routes are lazy-loaded (`router.js`). `/jury/review` and `/jury/review-v2` are full-screen review workspaces with their own theme switch, isolated from the rest of the app's shared light theme (see STYLE_GUIDE.md "Review route exception"). CSS is split by ownership: `style.css` (structural only), `styles/light-theme.css` (shared tokens/theme), `styles/App.css` (shell/nav), `styles/views/*.css` (per-view, referenced via `<style scoped src>`), `ReviewQueue.css` (isolated review shell theme).

**`services/` + `shared/shared_lib`** is an unused, self-contained microservices scaffold (gateway/auth/validator/worker/jury-panel, added in a single commit) that reimplements pieces of the backend against a shared library. It is not referenced by the `Procfile`, not wired to the frontend, and not mentioned in the AGENTS.md change log — treat it as inactive/experimental unless a task explicitly directs you to work in it. Do not assume changes to `backend/` need mirroring there.

Auth is Wikimedia OAuth 2.0 (`authlib`) with JWT session cookies; the owner role is granted purely by matching wiki username, not a scope/claim.

## Local environment

`backend/.env` holds OAuth credentials, `SESSION_SECRET`, and wiki-replica DB tunnel settings. Required keys: `WIKIMEDIA_CLIENT_ID`, `WIKIMEDIA_CLIENT_SECRET`, `SESSION_SECRET`, `OAUTH_CALLBACK_URL` (`http://localhost:3000/auth/callback` locally), `WIKI_DB_HOST`/`WIKI_DB_PORT`/`WIKI_DB_USER`/`WIKI_DB_PASSWORD` for the Bengali replica (local SSH tunnel: `-L 4407:bnwiktionary.web.db.svc.wikimedia.cloud:3306`, so `WIKI_DB_HOST=127.0.0.1` and `WIKI_DB_PORT=4407`), and `ENABLE_HOURLY_BACKUP`/`ENABLE_AUTO_RECOVERY` (`0` locally, to keep expensive full exports out of request handling). `backend/.env.example` is gitignored and not in the repo, so this list is the reference for a fresh clone. Pre-migration DB snapshots are written to `backup/` (gitignored — contains credentials/session data) whenever a schema change is pending; don't delete these without checking they aren't a recent safety net.
