import os
import jwt
import asyncio
import uuid
import csv
import io
import re
import unicodedata
import psutil
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks, Query
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from dotenv import load_dotenv

# Load local replica credentials before importing database.py, because the
# database module creates the wiki replica engine during import.
load_dotenv()

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import case, exists, func, or_, text
from database import get_db, engine, query_wiki_replica_batch, query_wiki_replica_user_creations, _pre_migration_backup
from timeutils import utcnow
import models

try:
    import talk_queue_worker
except ImportError as e:
    # The worker needs APScheduler, which arrived with the talk-page queue.
    # A Toolforge deploy that restarts the webservice without rebuilding the
    # image has the new code but not the new dependency -- and since this is
    # a module-level import in the file that *is* the application, that would
    # take the whole tool down (SPA included) over a background job. Degrade
    # to "no queue draining" instead: submissions still record their jobs,
    # and they drain as soon as the image is rebuilt.
    talk_queue_worker = None
    print(f"[talk-queue] Worker unavailable, queue will not drain: {e}")

models.Base.metadata.create_all(bind=engine)

is_prod = os.getenv("OAUTH_CALLBACK_URL", "").startswith("https://")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Replaces the deprecated @app.on_event("shutdown") hook, which FastAPI
    has scheduled for removal -- once it goes, the handler would silently stop
    running and the shared httpx client (and its connection pool) would leak
    on every restart.

    It also owns the talk-page queue worker: registering it here means the
    drain starts with the app and is torn down with it, instead of being a
    loose asyncio task nobody cancels."""
    if talk_queue_worker is not None:
        try:
            talk_queue_worker.requeue_stale_processing_jobs()
            talk_queue_worker.start_talk_queue_worker()
        except Exception as e:
            # A queue that fails to start must not take the whole app down
            # with it -- submissions still work, the edits just wait.
            print(f"[talk-queue] Failed to start worker: {e}")
    yield
    if talk_queue_worker is not None:
        talk_queue_worker.shutdown_talk_queue_worker()
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


app = FastAPI(lifespan=lifespan)

# Nothing was compressing responses -- not the app, and Toolforge's ingress
# can't be relied on for it either. Measured against the real 11k-article dev
# contest: /log?page_size=500 is 130 KB raw / 9.8 KB gzipped (13.2x), and the
# dashboard's full activity-log crawl moves ~2.7 MB uncompressed vs ~0.2 MB
# gzipped. A user profile drops from 898 KB to 82 KB. JSON of repeated keys
# compresses extremely well, and the app's users are mostly on Bangladeshi
# mobile connections, so this is the single largest latency win available.
# minimum_size skips the many tiny JSON replies where framing would cost more
# than it saves.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "super-secret"),
    https_only=is_prod
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Total time spent inside this app for the request (DB + Python
    processing + response encoding), excluding network/TLS/ingress time
    before the request reaches here. Compare against curl's total time for
    the same request to see how much of the delay is inside this app at all
    vs. purely network/infra -- the diagnostics endpoint's per-query timings
    don't cover response-building or JSON serialization, so this fills that
    gap without needing another round of guessing."""
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}"
    return response

# Bumped manually with each deploy-relevant change. Buildpacks-produced
# runtime images don't reliably include .git, so this is a guaranteed-simple
# way to confirm what's actually running vs. what's on GitHub, instead of
# inferring it from behavior after every redeploy.
APP_BUILD_MARKER = "2026-08-30-delete-cascade-talk-jobs"

@app.get("/api/version")
def get_version():
    return {"build": APP_BUILD_MARKER}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb_str = traceback.format_exc()
    from database import SessionLocal
    db = SessionLocal()
    log_id = None
    try:
        username = None
        token = request.cookies.get("auth_token")
        if token:
            try:
                payload_data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                username = payload_data.get("sub")
            except Exception:
                pass
        log_entry = models.SystemLog(
            level="error",
            source="backend",
            message=f"HTTP 500: {str(exc)}"[:2000],
            stack_trace=tb_str[:4000],
            url=str(request.url)[:500],
            user_agent=request.headers.get("user-agent", "")[:500],
            username=username,
            timestamp=utcnow()
        )
        db.add(log_entry)
        db.commit()
        log_id = log_entry.id
    except Exception as e:
        print(f"[ErrorLog] Failed saving exception log: {e}")
    finally:
        db.close()

    # The body used to be assembled with an f-string, which produced invalid
    # JSON the moment an exception message contained a quote, backslash, or
    # newline -- exactly what SQLAlchemy and httpx errors are full of, so the
    # client saw a JSON parse failure instead of the error. It also echoed the
    # raw exception text (DSNs, credentials, internal paths) straight to the
    # browser. JSONResponse encodes properly; the full message and traceback
    # stay in system_logs, reachable by id via /api/logs.
    detail = "Internal Server Error"
    if log_id is not None:
        detail = f"{detail} (log #{log_id})"
    return JSONResponse(status_code=500, content={"detail": detail, "log_id": log_id})

WIKI_DB_USER = os.getenv("WIKI_DB_USER", "")
WIKI_DB_PASSWORD = os.getenv("WIKI_DB_PASSWORD", "")
# ---------------------------------------------------------------------------
# Talk-page template editing
#
# The per-title edit used to live inline in add_talk_pages. It is split out
# here because talk_queue_worker.py performs the same edit one job at a time,
# and two copies of the MediaWiki edit request would drift apart.
# ---------------------------------------------------------------------------

WIKI_USER_AGENT = "QuoteContestArticleTool/1.0 (https://github.com/RIFAT712/Feather)"
TALK_HEADER_TEMPLATE = "{{আলাপ পাতা}}"
TALK_TEMPLATE_EDIT_SUMMARY = "প্রতিযোগিতার টেমপ্লেট যোগ করা হচ্ছে"

# MediaWiki bot best practice: refuse the edit when the replicas are lagging
# more than this many seconds instead of adding to the pile. A maxlag refusal
# is a "come back later", not a failed edit -- callers treat it as transient.
WIKI_MAXLAG_SECONDS = 5

# What MediaWiki returns instead of a real CSRF token when the request is not
# authenticated -- an edit sent with it would be rejected.
ANONYMOUS_CSRF_TOKEN = "+\\"

# API error codes that mean "this would have worked at a different moment".
TRANSIENT_WIKI_ERROR_CODES = frozenset({
    "maxlag", "readonly", "ratelimited", "editconflict", "badtoken",
})


def wiki_auth_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": WIKI_USER_AGENT,
    }


def build_talk_template_text(template_name: str) -> str:
    """`Foo` -> `{{Foo}}`; an already-braced name is left alone."""
    template_text = (template_name or "").strip()
    if not template_text.startswith('{{'):
        template_text = f"{{{{{template_text}}}}}"
    return template_text


def build_talk_append_text(template_name: str, include_header: bool) -> str:
    template_text = build_talk_template_text(template_name)
    if include_header:
        return f"{TALK_HEADER_TEMPLATE}\n{template_text}"
    return template_text


def talk_page_title(title: str) -> str:
    return title if title.startswith("Talk:") else f"Talk:{title}"


async def fetch_csrf_token(client: httpx.AsyncClient, headers: dict):
    """Return (token, raw response body). Token is None when OAuth is not
    usable -- MediaWiki hands out the anonymous edit token in that case."""
    res = await wiki_api_request(
        "GET",
        MEDIAWIKI_API_URL,
        client=client,
        params={"action": "query", "meta": "tokens", "type": "csrf", "format": "json"},
        headers=headers
    )
    token_data = res.json()
    csrf_token = token_data.get("query", {}).get("tokens", {}).get("csrftoken")
    if not csrf_token or csrf_token == ANONYMOUS_CSRF_TOKEN:
        return None, token_data
    return csrf_token, token_data


async def edit_talk_page(
    client: httpx.AsyncClient,
    headers: dict,
    csrf_token: str,
    title: str,
    append_text: str,
    template_text: str,
):
    """Append the contest template to one article's talk page.

    Returns (outcome, detail) where outcome is one of:
      "done"      -- the edit was saved
      "skipped"   -- the template is already on the page, nothing to do
      "transient" -- lag/rate-limit/conflict; worth retrying later
      "failed"    -- the wiki rejected it for a reason retrying won't fix

    The edit reads the current wikitext and re-posts it with the template
    appended, rather than using `appendtext`. That costs one extra read but
    makes the write safe to retry: `wiki_api_request` retries transient
    statuses, and a retried `appendtext` whose first response was merely lost
    would have added the template a second time. `basetimestamp` makes the
    wiki reject a write racing another edit, and the already-present check
    turns a re-queued job into a no-op instead of a duplicate.
    """
    page_title = talk_page_title(title)
    read_res = await wiki_api_request(
        "GET",
        MEDIAWIKI_API_URL,
        client=client,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": page_title,
            "rvprop": "content|timestamp",
            "rvslots": "main",
            "rvlimit": 1,
            "curtimestamp": 1,
            "format": "json",
            "formatversion": 2,
        },
        headers=headers,
    )
    read_data = read_res.json()
    if "error" in read_data:
        code = read_data["error"].get("code", "")
        detail = read_data["error"].get("info", code)
        return ("transient" if code in TRANSIENT_WIKI_ERROR_CODES else "failed"), detail

    pages = read_data.get("query", {}).get("pages", [])
    page = pages[0] if pages else {}
    existing_text = ""
    base_timestamp = None
    if not page.get("missing"):
        revisions = page.get("revisions", [])
        if revisions:
            existing_text = revisions[0].get("slots", {}).get("main", {}).get("content", "") or ""
            base_timestamp = revisions[0].get("timestamp")
    if template_text and template_text in existing_text:
        return "skipped", "template already present"

    edit_data = {
        "action": "edit",
        "title": page_title,
        "text": existing_text + append_text,
        "token": csrf_token,
        "format": "json",
        "summary": TALK_TEMPLATE_EDIT_SUMMARY,
        "maxlag": WIKI_MAXLAG_SECONDS,
    }
    start_timestamp = read_data.get("curtimestamp")
    if base_timestamp:
        edit_data["basetimestamp"] = base_timestamp
    if start_timestamp:
        edit_data["starttimestamp"] = start_timestamp

    edit_res = await wiki_api_request("POST", MEDIAWIKI_API_URL, client=client, data=edit_data, headers=headers)
    try:
        res_json = edit_res.json()
    except Exception:
        res_json = {}
    print(f"[talk-template] Edit result for '{page_title}': status={edit_res.status_code} body={edit_res.text[:500]}")
    if edit_res.status_code == 200 and res_json.get("edit", {}).get("result") == "Success":
        return "done", None

    error = res_json.get("error", {})
    code = error.get("code", "")
    detail = error.get("info", edit_res.text[:300])
    if code in TRANSIENT_WIKI_ERROR_CODES or edit_res.status_code in RETRYABLE_WIKI_STATUS:
        return "transient", detail
    return "failed", detail


def log_talk_template_event(level: str, message: str):
    """Talk-page work happens outside a request, so it opens its own session
    rather than depending on a request-scoped one."""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            db.add(models.SystemLog(
                level=level,
                source="talk_template",
                message=message[:2000],
                timestamp=utcnow()
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[talk-template] Error writing to SystemLog: {e}")


async def add_talk_pages(titles: list[str], template_name: str, include_header: bool, access_token: str = None, submitter: str = None):
    """Edit a whole batch of talk pages in one pass.

    Superseded by the talk_page_jobs queue for live submissions (see
    enqueue_talk_page_jobs) -- kept as the direct, unqueued path.
    """
    if not access_token:
        print(f"[add_talk_pages] Skipped — no OAuth access token stored for user. They need to log out and back in.")
        return

    template_text = build_talk_template_text(template_name)
    append_text = build_talk_append_text(template_name, include_header)

    async with httpx.AsyncClient() as client:
        headers = wiki_auth_headers(access_token)
        csrf_token, token_data = await fetch_csrf_token(client, headers)
        print(f"[add_talk_pages] CSRF token response: {token_data}")
        if not csrf_token:
            msg = ("Failed to get CSRF token. OAuth may have insufficient scope or the token is "
                   f"invalid. Full response: {token_data}")
            print(f"[add_talk_pages] {msg}")
            log_talk_template_event("error", msg)
            return

        successes = []
        failures = []
        for title in titles:
            try:
                outcome, detail = await edit_talk_page(client, headers, csrf_token, title, append_text, template_text)
            except Exception as e:
                outcome, detail = "failed", str(e)
            if outcome in ("done", "skipped"):
                successes.append(title)
            else:
                failures.append(f"{title}: {detail}")

        msg = f"Talk page template added for {len(successes)} articles."
        if failures:
            msg += f" Failures ({len(failures)}): " + ", ".join(failures)[:1500]
        log_talk_template_event("info" if not failures else "warning", msg)


def enqueue_talk_page_jobs(db: Session, contest, titles: list[str], access_token: str, submitted_by: str) -> int:
    """Queue one talk-page edit per title for talk_queue_worker to drain.

    Nothing is sent to MediaWiki here: the caller is inside a user request,
    and the whole point of the queue is that the edits outlive it.
    """
    if not titles:
        return 0
    if not access_token:
        msg = (f"Talk page templates skipped for {len(titles)} article(s) submitted by "
               f"{submitted_by}: no OAuth access token stored. They need to log out and back in.")
        print(f"[talk-queue] {msg}")
        log_talk_template_event("warning", msg)
        return 0

    articles = db.query(models.Article).filter(
        models.Article.contest_id == contest.id,
        models.Article.title.in_(titles)
    ).all()
    # Keyed case-insensitively for the same reason submit_bulk's own
    # existing-article map is: the stored title is the wiki's canonical form,
    # which may differ in case from what was typed into the submission box.
    articles_by_title = {a.title.lower(): a for a in articles}

    # A title re-submitted while its first job is still waiting must not get
    # the template twice.
    pending_article_ids = {
        row[0] for row in db.query(models.TalkPageJob.article_id).filter(
            models.TalkPageJob.contest_id == contest.id,
            models.TalkPageJob.status.in_(("queued", "processing")),
        ).all()
    }

    queued = 0
    for title in titles:
        article = articles_by_title.get(title.lower())
        if not article or article.id in pending_article_ids:
            continue
        db.add(models.TalkPageJob(
            article_id=article.id,
            contest_id=contest.id,
            title=article.title,
            status="queued",
            attempts=0,
            access_token=access_token,
            submitted_by=submitted_by,
            created_at=utcnow(),
        ))
        pending_article_ids.add(article.id)
        queued += 1
    db.commit()
    return queued


oauth = OAuth()
oauth.register(
    name='wikimedia',
    client_id=os.getenv("WIKIMEDIA_CLIENT_ID", ""),
    client_secret=os.getenv("WIKIMEDIA_CLIENT_SECRET", ""),
    access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
    authorize_url='https://meta.wikimedia.org/w/rest.php/oauth2/authorize',
    api_base_url='https://meta.wikimedia.org/w/rest.php/oauth2/resource/',
    client_kwargs={'scope': 'basic createeditmovepage'}
)

MEDIAWIKI_API_URL = os.getenv("MEDIAWIKI_API_URL", "https://bn.wiktionary.org/w/api.php")
JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret") + "_v2"
JWT_ALGORITHM = "HS256"

_global_semaphore = None
_http_client = None

def get_global_semaphore():
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(15)
    return _global_semaphore

def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_keepalive_connections=30, max_connections=100)
        )
    return _http_client


# MediaWiki's API sheds load with 429s and the Wikimedia edge returns 502/503
# during deploys, and a bulk submission of a few hundred titles reliably hits
# at least one of those. Without a retry, that single blip was recorded as a
# permanent per-article "API Error" validation failure in the database -- a
# transient network condition turned into what looked to the submitter like a
# rejected article. tenacity handles the backoff/jitter/attempt bookkeeping
# instead of a hand-rolled loop.
def _normalize_wiki_name(name: str) -> str:
    """Normalize a wiki username for comparison.

    MediaWiki treats underscores and spaces as equivalent in names, and the
    same Bengali/Devanagari string can arrive in different Unicode
    normalization forms depending on whether it came from the replica, the API,
    or a browser -- so a raw == would report a false author mismatch. This was
    duplicated inline in both branches of process_articles_batch; the integrity
    check needs the same comparison.
    """
    return unicodedata.normalize("NFC", name or "").replace("_", " ").strip()


RETRYABLE_WIKI_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryableWikiStatus(Exception):
    """A MediaWiki response worth retrying (rate limit / transient 5xx)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, RetryableWikiStatus)),
    reraise=True,
)
async def wiki_api_request(method: str, url: str, *, client: httpx.AsyncClient = None, **kwargs) -> httpx.Response:
    """Issue a MediaWiki API request, retrying transport errors and transient
    HTTP statuses with exponential backoff.

    Safe for idempotent requests only. That used to rule out page edits
    entirely, because the talk-page edit used `appendtext` -- a retry after an
    edit that had actually succeeded but whose response was lost would append
    the template twice. `edit_talk_page` now writes the full page text with a
    `basetimestamp`, which the wiki rejects if the page moved underneath it,
    so that edit is safe to retry here. Any *new* edit path has to make itself
    idempotent the same way before using this wrapper.
    """
    http = client or get_http_client()
    response = await http.request(method, url, **kwargs)
    if response.status_code in RETRYABLE_WIKI_STATUS:
        raise RetryableWikiStatus(f"{response.status_code} from {url}")
    return response


class ContestCreate(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime
    rule_must_be_creator: bool = True
    min_bytes: int = 0
    min_words: int = 0
    min_refs: int = 0
    rule_no_redirect: bool = True
    rule_no_disambig: bool = True
    rule_mainspace_only: bool = True
    allow_self_review: bool = False
    add_talk_template: bool = False
    talk_template_name: Optional[str] = None
    include_talk_header: bool = True

class ContestUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rule_must_be_creator: Optional[bool] = None
    min_bytes: Optional[int] = None
    min_words: Optional[int] = None
    min_refs: Optional[int] = None
    rule_no_redirect: Optional[bool] = None
    rule_no_disambig: Optional[bool] = None
    rule_mainspace_only: Optional[bool] = None
    allow_self_review: Optional[bool] = None
    add_talk_template: Optional[bool] = None
    talk_template_name: Optional[str] = None
    include_talk_header: Optional[bool] = None

class AssignJury(BaseModel):
    contest_code: str
    wiki_usernames: List[str]

class UnassignJury(BaseModel):
    contest_code: str
    wiki_username: str

class JuryRestriction(BaseModel):
    contest_code: str
    jury_username: str
    submitter_username: str

class ContestBan(BaseModel):
    contest_code: str
    username: str

class BulkSubmitRequest(BaseModel):
    contest_code: str
    titles: List[str]
    on_behalf_of: Optional[str] = None

class ValidationResult(BaseModel):
    title: str
    is_valid: bool
    error: Optional[str] = None
    wiki_creator: Optional[str] = None
    wiki_creation_date: Optional[str] = None
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("auth_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = db.query(models.User).filter(models.User.wiki_username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_owner_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.owner:
        raise HTTPException(status_code=403, detail="Owner privileges required")
    return current_user

@app.get("/api/admin/db-diagnostics")
def db_diagnostics(code: Optional[str] = Query(default=None), _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    """One-shot diagnostic: what indexes actually exist on `articles`, how big
    the table really is, the query plan MariaDB picks for the exact /log
    query shape (MariaDB only), and -- most importantly -- server-side wall
    time for each individual query /log actually runs, measured on the same
    connection/network path as the real endpoint. EXPLAIN shows the plan, not
    execution time, and a simplified EXPLAIN query can miss what a join
    actually costs; timing the real query shapes directly removes the
    guessing entirely."""
    from sqlalchemy import inspect as sa_inspect
    import time as _time
    inspector = sa_inspect(engine)
    is_mysql = "mysql" in str(engine.url)

    total_articles = db.query(func.count(models.Article.id)).scalar()
    contest_article_count = None
    explain_rows = []
    timings = {}
    if code:
        t0 = _time.perf_counter()
        contest = db.query(models.Contest).filter_by(code=code).first()
        timings["contest_lookup"] = _time.perf_counter() - t0
        if contest:
            t0 = _time.perf_counter()
            contest_article_count = db.query(func.count(models.Article.id)).filter_by(contest_id=contest.id).scalar()
            timings["count_query"] = _time.perf_counter() - t0

            t0 = _time.perf_counter()
            articles = db.query(models.Article).options(joinedload(models.Article.submitter)) \
                .filter_by(contest_id=contest.id).order_by(models.Article.id.desc()).limit(500).all()
            timings["main_select_with_submitter_join"] = _time.perf_counter() - t0

            t0 = _time.perf_counter()
            article_ids = [a.id for a in articles]
            _ = db.query(models.Review).filter(models.Review.article_id.in_(article_ids)) \
                .options(joinedload(models.Review.reviewer)).all()
            timings["reviews_selectin_equivalent"] = _time.perf_counter() - t0

            t0 = _time.perf_counter()
            _ = db.query(models.ArticleLock).filter(models.ArticleLock.article_id.in_(article_ids)).all()
            timings["locks_query"] = _time.perf_counter() - t0

            if is_mysql:
                result = db.execute(text(
                    "EXPLAIN SELECT id FROM articles WHERE contest_id = :cid ORDER BY id DESC LIMIT 500"
                ), {"cid": contest.id})
                explain_rows = [dict(row._mapping) for row in result]

    return {
        "is_mysql": is_mysql,
        "articles_indexes": inspector.get_indexes("articles"),
        "total_articles_all_contests": total_articles,
        "contest_article_count": contest_article_count,
        "explain": explain_rows,
        "server_side_timings_seconds": timings,
    }

# --- Jury queue assignment -------------------------------------------------
# Jury ownership of a pending article lives directly on Article.assigned_to_id
# (there used to be a second, separately-synced SQLite projection database for
# this; it was a persistent source of drift/staleness bugs and has been
# removed in favor of a single source of truth).

REBALANCE_BATCH_LIMIT = 8000

def get_eligible_juries(contest):
    """{user_id: wiki_username} for this contest's current jury members."""
    return {j.user_id: j.user.wiki_username for j in contest.juries if j.user}

def jury_map_username_to_id(jury_map: dict) -> dict:
    return {username: uid for uid, username in jury_map.items()}

def backfill_reviewed_ownership(db: Session, contest: models.Contest, jury_ids: set):
    """Give already-decided articles their assigned_to_id back (whoever made
    the final decision) when it's missing -- covers articles decided before
    this column existed. review_article sets this directly going forward, so
    this is a one-time-per-contest catch-up, bounded and cheap once caught up."""
    if not jury_ids:
        return
    candidate_ids = [row[0] for row in db.query(models.Article.id).filter(
        models.Article.contest_id == contest.id,
        models.Article.status.in_([models.ArticleStatus.accepted, models.ArticleStatus.rejected]),
        models.Article.assigned_to_id.is_(None),
    ).limit(REBALANCE_BATCH_LIMIT).all()]
    if not candidate_ids:
        return

    latest_review = db.query(
        models.Review.article_id, func.max(models.Review.id).label("latest_id")
    ).filter(
        models.Review.article_id.in_(candidate_ids),
        models.Review.status != models.ReviewStatus.skipped,
    ).group_by(models.Review.article_id).subquery()

    updates = [
        {"id": article_id, "assigned_to_id": reviewer_id}
        for article_id, reviewer_id in db.query(models.Review.article_id, models.Review.reviewer_id)
        .join(latest_review, models.Review.id == latest_review.c.latest_id).all()
        if reviewer_id in jury_ids
    ]
    if updates:
        db.bulk_update_mappings(models.Article, updates)
        db.commit()
        print(f"[Jury Assignment] Backfilled ownership for {len(updates)} decided article(s) in {contest.code}")

def clear_all_pending_assignments(db: Session, contest: models.Contest):
    """Force a full rebalance of every pending article's queue ownership --
    call this when the eligible-jury roster or COI/self-review rules change,
    so the new rules apply fairly across the whole pool immediately, instead
    of only catching newly-submitted articles going forward. An ordinary new
    submission should NOT call this -- it would needlessly reshuffle queues
    jury members are already working through."""
    db.query(models.Article).filter(
        models.Article.contest_id == contest.id,
        models.Article.status == models.ArticleStatus.pending,
    ).update({"assigned_to_id": None}, synchronize_session=False)
    db.commit()

_rebalance_lock = threading.Lock()

def rebalance_pending_articles(db: Session, contest: models.Contest, jury_map: dict = None):
    """Assign every pending article that has no valid, current jury owner to
    the least-loaded eligible jury, and backfill ownership for already-decided
    articles that predate the assigned_to_id column. Cheap no-op when nothing
    needs it, and safe to call from both write endpoints (proactively) and
    read endpoints (as a self-heal safety net).

    Serialized process-wide: concurrent requests (e.g. several jury members
    loading the panel at once) would otherwise all read the same "who's
    least loaded" snapshot before any of them commit, redo the same backfill
    work, and hand out assignments that don't account for each other."""
    with _rebalance_lock:
        _rebalance_pending_articles_locked(db, contest, jury_map)

def _rebalance_pending_articles_locked(db: Session, contest: models.Contest, jury_map: dict = None):
    if jury_map is None:
        jury_map = get_eligible_juries(contest)
    jury_ids = set(jury_map.keys())
    if not jury_ids:
        return
    backfill_reviewed_ownership(db, contest, jury_ids)

    restrictions = {
        (r.jury_user_id, r.submitter_user_id)
        for r in db.query(models.ContestJuryRestriction).filter_by(contest_id=contest.id).all()
    }
    banned_ids = {b.user_id for b in db.query(models.ContestBannedUser).filter_by(contest_id=contest.id).all()}

    base_filters = [models.Article.contest_id == contest.id]
    if banned_ids:
        base_filters.append(~models.Article.submitter_id.in_(banned_ids))

    # Current load: everything each jury currently owns (pending + already
    # reviewed by them), so a jury who has judged a lot doesn't also get
    # piled up with new pending work.
    loads = {uid: 0 for uid in jury_ids}
    for uid, count in db.query(models.Article.assigned_to_id, func.count(models.Article.id)).filter(
        *base_filters, models.Article.assigned_to_id.in_(jury_ids)
    ).group_by(models.Article.assigned_to_id).all():
        loads[uid] = count

    candidates = db.query(models.Article.id, models.Article.submitter_id).filter(
        *base_filters,
        models.Article.status == models.ArticleStatus.pending,
        or_(models.Article.assigned_to_id.is_(None), ~models.Article.assigned_to_id.in_(jury_ids)),
    ).order_by(models.Article.id.asc()).limit(REBALANCE_BATCH_LIMIT).all()

    if not candidates:
        return

    updates = []
    for article_id, submitter_id in candidates:
        choices = [uid for uid in jury_ids
                   if (contest.allow_self_review or uid != submitter_id)
                   and (uid, submitter_id) not in restrictions]
        if not choices:
            continue
        chosen = min(choices, key=lambda uid: (loads[uid], uid))
        updates.append({"id": article_id, "assigned_to_id": chosen})
        loads[chosen] += 1

    if updates:
        db.bulk_update_mappings(models.Article, updates)
        db.commit()
        print(f"[Jury Assignment] Rebalanced {len(updates)} pending article(s) for {contest.code}")

def serialize_jury_article(article: models.Article, jury_map: dict) -> dict:
    """Same item shape the old jury-panel projection returned, built live
    from the article/review rows directly."""
    non_skipped = sorted(
        (r for r in article.reviews if r.status.value != "skipped"),
        key=lambda r: r.timestamp or datetime.min,
    )
    return {
        "article_id": article.id,
        "title": article.title,
        "submitted_by": article.submitter.wiki_username if article.submitter else "",
        "submitted_at": article.submitted_at.isoformat() if article.submitted_at else None,
        "status": article.status.value,
        "validation_error": article.validation_error,
        "wiki_creator": article.wiki_creator,
        "wiki_creation_date": article.wiki_creation_date.isoformat() if article.wiki_creation_date else None,
        "reviewed_by": non_skipped[-1].reviewer.wiki_username if non_skipped and non_skipped[-1].reviewer else None,
        "reviews": [
            {
                "reviewer": r.reviewer.wiki_username,
                "decision": r.status.value,
                "comment": r.comment,
                "reviewed_at": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in non_skipped
        ],
        "assigned_to": jury_map.get(article.assigned_to_id),
    }

@app.get("/auth/login")
async def login(request: Request, next: Optional[str] = None):
    host = request.headers.get("x-forwarded-host", request.url.hostname)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    
    if next:
        request.session['next_url'] = next
    if host and "toolforge.org" in host:
        redirect_uri = f"https://{host}/auth/callback"
    else:
        redirect_uri = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:3000/auth/callback")
        
    return await oauth.wikimedia.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        token = await oauth.wikimedia.authorize_access_token(request)
        resp = await oauth.wikimedia.get('profile', token=token)
        profile = resp.json()
        username = profile.get('username')
        
        user = db.query(models.User).filter(models.User.wiki_username == username).first()
        if not user:
            role = models.RoleEnum.owner if username == "R1F4T" else models.RoleEnum.participant
            user = models.User(wiki_username=username, role=role, oauth_access_token=token.get('access_token'))
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if username == "R1F4T" and user.role != models.RoleEnum.owner:
                user.role = models.RoleEnum.owner
            user.oauth_access_token = token.get('access_token')
            db.commit()
                
        expire = utcnow() + timedelta(days=7)
        jwt_payload = {"sub": user.wiki_username, "role": user.role.value, "exp": expire}
        auth_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        is_secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
        next_url = request.session.pop('next_url', '/')
        redirect_res = RedirectResponse(url=next_url)
        redirect_res.set_cookie(
            key="auth_token",
            value=auth_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days — matches JWT expiry
        )
        return redirect_res
        
    except Exception as e:
        import traceback
        print(f"Login failed: {e}\n{traceback.format_exc()}")
        return RedirectResponse(url="/?error=login_failed")

@app.post("/auth/logout")
async def logout(request: Request):
    is_secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response = Response(status_code=200)
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )
    return response

@app.get("/api/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"wiki_username": current_user.wiki_username, "role": current_user.role.value}

_is_restarting = False
def _write_backup_files(dest_dir: str, label: str):
    """Dump articles per contest, users, and contests to CSV files in dest_dir.
    Also writes a SystemLog entry so the event appears in /api/logs.
    """
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = utcnow().strftime('%Y%m%d_%H%M%S')
    db = next(get_db())
    try:
        def translate_status(s):
            if s == "accepted": return "গৃহীত"
            if s == "rejected": return "প্রত্যাখ্যাত"
            if s == "pending": return "অপেক্ষমাণ"
            if s == "validation_failed": return "যাচাইকরণ ব্যর্থ"
            return s

        contests = db.query(models.Contest).all()
        total_articles = 0
        for c in contests:
            articles = db.query(models.Article).options(
                joinedload(models.Article.submitter),
                selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
            ).filter_by(contest_id=c.id).order_by(models.Article.submitted_at.desc()).all()
            
            total_articles += len(articles)
            
            if label == "EMERGENCY":
                filename = f"{c.code}_articles_{timestamp}.csv"
            else:
                filename = f"{c.code}_articles.csv"
                
            filepath = os.path.join(dest_dir, filename)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Article ID", "Title", "Submitter", "Status", "Validation Error",
                    "Wiki Creator", "Wiki Creation Date", "Submitted At", "Reviews Count", "Last Review Decision", "Last Reviewer", "Last Review Comment"
                ])
                for a in articles:
                    reviews = sorted(a.reviews, key=lambda r: r.timestamp or datetime.min)
                    last_rev = reviews[-1] if reviews else None
                    writer.writerow([
                        a.id, a.title, a.submitter.wiki_username if a.submitter else "",
                        translate_status(a.status.value), a.validation_error or "",
                        a.wiki_creator or "", a.wiki_creation_date.isoformat() if a.wiki_creation_date else "",
                        a.submitted_at.isoformat() if a.submitted_at else "", len(reviews),
                        translate_status(last_rev.status.value) if last_rev else "",
                        last_rev.reviewer.wiki_username if last_rev and last_rev.reviewer else "",
                        last_rev.comment or "" if last_rev else ""
                    ])
        users = db.query(models.User).all()
        users_file = f'users_{timestamp}.csv' if label == "EMERGENCY" else 'users.csv'
        with open(os.path.join(dest_dir, users_file), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'wiki_username', 'role'])
            for u in users:
                writer.writerow([u.id, u.wiki_username, u.role.value])
        contests_file = f'contests_{timestamp}.csv' if label == "EMERGENCY" else 'contests.csv'
        with open(os.path.join(dest_dir, contests_file), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'code', 'name', 'start_date', 'end_date'])
            for c in contests:
                writer.writerow([c.id, c.code, c.name, c.start_date, c.end_date])

        msg = (
            f"{label} backup completed — {total_articles} articles across {len(contests)} contests, {len(users)} users "
            f"→ {dest_dir} [{timestamp}]"
        )
        print(f"[Backup] {msg}")
        db.add(models.SystemLog(
            level="info",
            source="backup",
            message=msg,
            timestamp=utcnow(),
        ))
        db.commit()
    except Exception as e:
        err_msg = f"{label} backup FAILED: {e} (dest={dest_dir})"
        print(f"[Backup] {err_msg}")
        try:
            db.add(models.SystemLog(
                level="error",
                source="backup",
                message=err_msg[:2000],
                timestamp=utcnow(),
            ))
            db.commit()
        except Exception:
            pass  # Don't let a logging failure mask the original error
    finally:
        db.close()
def _resolve_backup_root() -> str:
    """
    Resolve where ~/backup/ should live.
    Priority:
      1. BACKUP_ROOT env var (explicit override)
      2. Path.home()  — works on Toolforge Kubernetes (HOME=/data/project/<tool>/)
      3. Fallback: directory two levels above main.py (project root)
    Always verifies the chosen path is writable before returning it.
    """
    candidates = []
    if os.environ.get("BACKUP_ROOT"):
        candidates.append(("BACKUP_ROOT env var", os.environ["BACKUP_ROOT"]))
    try:
        candidates.append(("Path.home()", str(Path.home())))
    except Exception:
        pass
    candidates.append(("project root fallback", os.path.dirname(os.path.dirname(__file__))))

    for label, base in candidates:
        probe = os.path.join(base, "backup")
        try:
            os.makedirs(probe, exist_ok=True)
            test_file = os.path.join(probe, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            print(f"[Backup] Using backup root via {label}: {base}")
            return base
        except Exception as e:
            print(f"[Backup] Cannot write to {probe} ({label}): {e} — trying next candidate")

    raise RuntimeError("[Backup] No writable backup root found!")
def do_emergency_backup_and_restart():
    global _is_restarting
    if _is_restarting:
        return
    _is_restarting = True

    home = _resolve_backup_root()
    emergency_dir = os.path.join(home, 'backup', 'emergency')
    _write_backup_files(emergency_dir, "EMERGENCY")

    time.sleep(2)   # Give FastAPI time to send the response
    os._exit(1)     # Restart via process manager (Procfile / systemd)
HOURLY_BACKUP_INTERVAL_SECONDS = 3600  # 1 hour
ENABLE_HOURLY_BACKUP = os.getenv("ENABLE_HOURLY_BACKUP", "0").lower() in {"1", "true", "yes"}

def _hourly_backup_loop():
    """Take an optional backup hourly, after the app has been serving for an hour."""
    home = _resolve_backup_root()
    os.makedirs(os.path.join(home, 'backup', 'hourly'), exist_ok=True)
    os.makedirs(os.path.join(home, 'backup', 'emergency'), exist_ok=True)
    print(f"[Backup] Directories ready: {home}/backup/{{hourly,emergency}}/")
    # Never make the first request wait behind a full export.
    time.sleep(HOURLY_BACKUP_INTERVAL_SECONDS)
    while ENABLE_HOURLY_BACKUP:
        hourly_dir = os.path.join(home, 'backup', 'hourly')
        _write_backup_files(hourly_dir, "HOURLY")
        time.sleep(HOURLY_BACKUP_INTERVAL_SECONDS)
if ENABLE_HOURLY_BACKUP:
    _hourly_thread = threading.Thread(target=_hourly_backup_loop, daemon=True, name="hourly-backup")
    _hourly_thread.start()
@app.get("/api/system/status")
def system_status(background_tasks: BackgroundTasks):
    global _is_restarting
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent

    overloaded = cpu > 90 or mem > 90 or _is_restarting

    # A health probe must remain read-only. Automatic full backups during an
    # overload caused a feedback loop that could stall every API endpoint.
    if overloaded and os.getenv("ENABLE_AUTO_RECOVERY", "0").lower() in {"1", "true", "yes"} and not _is_restarting:
        background_tasks.add_task(do_emergency_backup_and_restart)

    return {
        "cpu_percent": cpu,
        "mem_percent": mem,
        "overloaded": overloaded,
        "restarting": _is_restarting
    }

@app.get("/api/contests")
def list_contests(db: Session = Depends(get_db)):
    contests = db.query(models.Contest).options(
        selectinload(models.Contest.juries).joinedload(models.ContestJury.user)
    ).all()
    # The home page only needs counts. Loading every Article relationship here
    # made a remote Toolforge database read the entire contest dataset on each
    # refresh, blocking otherwise unrelated API requests.
    article_stats = {
        contest_id: (int(total or 0), int(accepted or 0))
        for contest_id, total, accepted in db.query(
            models.Article.contest_id,
            func.count(models.Article.id),
            func.sum(case(
                (models.Article.status == models.ArticleStatus.accepted, 1),
                else_=0,
            )),
        ).group_by(models.Article.contest_id).all()
    }
    banned_counts = dict(db.query(
        models.ContestBannedUser.contest_id, func.count(models.ContestBannedUser.id)
    ).group_by(models.ContestBannedUser.contest_id).all())
    res = []
    for c in contests:
        jury_list = [j.user.wiki_username for j in c.juries if j.user]
        res.append({
            "id": c.id,
            "code": c.code, 
            "name": c.name,
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat(),
            "rule_must_be_creator": getattr(c, 'rule_must_be_creator', True),
            "min_bytes": getattr(c, 'min_bytes', 0),
            "min_words": getattr(c, 'min_words', 0),
            "min_refs": getattr(c, 'min_refs', 0),
            "rule_no_redirect": getattr(c, 'rule_no_redirect', True),
            "rule_no_disambig": getattr(c, 'rule_no_disambig', True),
            "rule_mainspace_only": getattr(c, 'rule_mainspace_only', True),
            "allow_self_review": getattr(c, 'allow_self_review', False),
            "add_talk_template": getattr(c, 'add_talk_template', False),
            "talk_template_name": getattr(c, 'talk_template_name', None),
            "include_talk_header": getattr(c, 'include_talk_header', True),
            "articles_count": article_stats.get(c.id, (0, 0))[0],
            "accepted_count": article_stats.get(c.id, (0, 0))[1],
            "juries_count": len(jury_list),
            "juries": jury_list,
            "banned_count": banned_counts.get(c.id, 0)
        })
    return res

@app.get("/api/contests/{code}")
def get_contest(code: str, db: Session = Depends(get_db)):
    c = db.query(models.Contest).options(
        selectinload(models.Contest.juries).joinedload(models.ContestJury.user),
        selectinload(models.Contest.jury_restrictions).joinedload(models.ContestJuryRestriction.jury_user),
        selectinload(models.Contest.jury_restrictions).joinedload(models.ContestJuryRestriction.submitter_user)
        ,selectinload(models.Contest.banned_users).joinedload(models.ContestBannedUser.user)
    ).filter_by(code=code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contest not found")
    jury_list = [j.user.wiki_username for j in c.juries if j.user]
    article_count, accepted = db.query(
        func.count(models.Article.id),
        func.sum(case(
            (models.Article.status == models.ArticleStatus.accepted, 1),
            else_=0,
        )),
    ).filter(models.Article.contest_id == c.id).one()
    accepted = int(accepted or 0)
    submitters = [name for (name,) in db.query(models.User.wiki_username)
                  .join(models.Article, models.Article.submitter_id == models.User.id)
                  .filter(models.Article.contest_id == c.id)
                  .distinct().order_by(models.User.wiki_username).all()]
    return {
        "id": c.id,
        "code": c.code, 
        "name": c.name, 
        "start_date": c.start_date.isoformat() if hasattr(c.start_date, 'isoformat') else str(c.start_date), 
        "end_date": c.end_date.isoformat() if hasattr(c.end_date, 'isoformat') else str(c.end_date), 
        "rule_must_be_creator": getattr(c, 'rule_must_be_creator', True),
        "min_bytes": getattr(c, 'min_bytes', 0),
        "min_words": getattr(c, 'min_words', 0),
        "min_refs": getattr(c, 'min_refs', 0),
        "rule_no_redirect": getattr(c, 'rule_no_redirect', True),
        "rule_no_disambig": getattr(c, 'rule_no_disambig', True),
        "rule_mainspace_only": getattr(c, 'rule_mainspace_only', True),
        "allow_self_review": getattr(c, 'allow_self_review', False),
        "add_talk_template": getattr(c, 'add_talk_template', False),
        "talk_template_name": getattr(c, 'talk_template_name', None),
        "include_talk_header": getattr(c, 'include_talk_header', True),
        "articles_count": article_count,
        "accepted_count": accepted,
        "juries_count": len(jury_list),
        "juries": jury_list,
        "submitters": submitters,
        "jury_restrictions": [
            {"id": item.id, "jury_username": item.jury_user.wiki_username,
             "submitter_username": item.submitter_user.wiki_username}
            for item in c.jury_restrictions
        ],
        "banned_users": [item.user.wiki_username for item in c.banned_users if item.user]
    }

@app.get("/api/admin/stats")
def get_admin_stats(_: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    total_contests = db.query(models.Contest).count()
    now = utcnow()
    active_contests = db.query(models.Contest).filter(
        models.Contest.start_date <= now,
        models.Contest.end_date >= now
    ).count()
    total_articles = db.query(models.Article).count()
    accepted_articles = db.query(models.Article).filter(models.Article.status == models.ArticleStatus.accepted).count()
    total_users = db.query(models.User).count()
    total_juries = db.query(models.ContestJury).count()
    total_banned_users = db.query(models.ContestBannedUser).count()
    
    return {
        "total_contests": total_contests,
        "active_contests": active_contests,
        "total_articles": total_articles,
        "accepted_articles": accepted_articles,
        "total_users": total_users,
        "total_juries": total_juries
        ,"total_banned_users": total_banned_users
    }

@app.get("/api/admin/backup/download")
def download_database_backup(_: models.User = Depends(get_owner_user)):
    """Download the current app DB (SQLite) or create a current DB dump (MariaDB)."""
    if "mysql" in str(engine.url):
        backup_path = _pre_migration_backup(engine)
        if backup_path.suffix == ".sql":
            media_type = "application/sql"
        else:
            media_type = "application/json"
        return FileResponse(
            str(backup_path), media_type=media_type,
            filename=f"feather_database_backup{backup_path.suffix}"
        )

    database_path = Path(engine.url.database or "app.db")
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    if not database_path.exists():
        raise HTTPException(status_code=404, detail="Application database file not found")
    return FileResponse(
        str(database_path), media_type="application/x-sqlite3",
        filename="feather_app.db"
    )

@app.post("/api/admin/contests")
def create_contest(data: ContestCreate, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    c = models.Contest(
        name=data.name, 
        start_date=data.start_date, 
        end_date=data.end_date,
        rule_must_be_creator=data.rule_must_be_creator,
        min_bytes=data.min_bytes,
        min_words=data.min_words,
        min_refs=data.min_refs,
        rule_no_redirect=data.rule_no_redirect,
        rule_no_disambig=data.rule_no_disambig,
        rule_mainspace_only=data.rule_mainspace_only,
        allow_self_review=data.allow_self_review,
        add_talk_template=data.add_talk_template,
        talk_template_name=data.talk_template_name,
        include_talk_header=data.include_talk_header
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"code": c.code, "name": c.name}

@app.put("/api/admin/contests/{code}")
def update_contest(code: str, data: ContestUpdate, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    c = db.query(models.Contest).filter_by(code=code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    self_review_changed = data.allow_self_review is not None and data.allow_self_review != c.allow_self_review
    if data.name is not None: c.name = data.name
    if data.start_date is not None: c.start_date = data.start_date
    if data.end_date is not None: c.end_date = data.end_date
    if data.rule_must_be_creator is not None: c.rule_must_be_creator = data.rule_must_be_creator
    if data.min_bytes is not None: c.min_bytes = data.min_bytes
    if data.min_words is not None: c.min_words = data.min_words
    if data.min_refs is not None: c.min_refs = data.min_refs
    if data.rule_no_redirect is not None: c.rule_no_redirect = data.rule_no_redirect
    if data.rule_no_disambig is not None: c.rule_no_disambig = data.rule_no_disambig
    if data.rule_mainspace_only is not None: c.rule_mainspace_only = data.rule_mainspace_only
    if data.allow_self_review is not None: c.allow_self_review = data.allow_self_review
    if data.add_talk_template is not None: c.add_talk_template = data.add_talk_template
    if data.talk_template_name is not None: c.talk_template_name = data.talk_template_name
    if data.include_talk_header is not None: c.include_talk_header = data.include_talk_header
    db.commit()
    if self_review_changed:
        clear_all_pending_assignments(db, c)
        rebalance_pending_articles(db, c)
    return {"status": "success"}

@app.delete("/api/admin/contests/{code}")
def delete_contest(code: str, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    c = db.query(models.Contest).filter_by(code=code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    db.query(models.ContestJury).filter_by(contest_id=c.id).delete(synchronize_session=False)
    article_ids = db.query(models.Article.id).filter_by(contest_id=c.id).subquery()
    db.query(models.Review).filter(models.Review.article_id.in_(article_ids)).delete(synchronize_session=False)
    db.query(models.Article).filter_by(contest_id=c.id).delete(synchronize_session=False)
    db.delete(c)
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/assign-jury")
def assign_jury(data: AssignJury, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=data.contest_code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    added = []
    for username in data.wiki_usernames:
        user = db.query(models.User).filter(models.User.wiki_username == username).first()
        if not user:
            user = models.User(wiki_username=username, role=models.RoleEnum.participant)
            db.add(user)
            db.commit()
            db.refresh(user)

        exists = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=user.id).first()
        if not exists:
            jury = models.ContestJury(contest_id=contest.id, user_id=user.id)
            db.add(jury)
            added.append(username)

    db.commit()
    if added:
        db.refresh(contest)
        clear_all_pending_assignments(db, contest)
        rebalance_pending_articles(db, contest)
    return {"status": "success", "added": added}

@app.post("/api/admin/unassign-jury")
def unassign_jury(data: UnassignJury, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=data.contest_code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    user = db.query(models.User).filter_by(wiki_username=data.wiki_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=user.id).delete()
    db.query(models.ContestJuryRestriction).filter_by(contest_id=contest.id, jury_user_id=user.id).delete()
    db.commit()
    db.refresh(contest)
    clear_all_pending_assignments(db, contest)
    rebalance_pending_articles(db, contest)
    return {"status": "success", "removed": data.wiki_username}

@app.get("/api/admin/contests/{code}/jury-restrictions")
def get_jury_restrictions(code: str, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    return [{"id": item.id, "jury_username": item.jury_user.wiki_username,
             "submitter_username": item.submitter_user.wiki_username}
            for item in contest.jury_restrictions]

@app.post("/api/admin/contests/{code}/jury-restrictions")
def add_jury_restriction(code: str, data: JuryRestriction, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest or data.contest_code != code:
        raise HTTPException(status_code=404, detail="Contest not found")
    jury = db.query(models.User).filter_by(wiki_username=data.jury_username).first()
    submitter = db.query(models.User).filter_by(wiki_username=data.submitter_username).first()
    if not jury or not db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=jury.id).first():
        raise HTTPException(status_code=400, detail="Jury member is not assigned to this contest")
    if not submitter:
        submitter = models.User(wiki_username=data.submitter_username, role=models.RoleEnum.participant)
        db.add(submitter)
        db.flush()
    exists = db.query(models.ContestJuryRestriction).filter_by(
        contest_id=contest.id, jury_user_id=jury.id, submitter_user_id=submitter.id).first()
    if exists:
        return {"status": "success", "id": exists.id, "already_exists": True}
    item = models.ContestJuryRestriction(contest_id=contest.id, jury_user_id=jury.id, submitter_user_id=submitter.id)
    db.add(item)
    db.commit()
    clear_all_pending_assignments(db, contest)
    rebalance_pending_articles(db, contest)
    return {"status": "success", "id": item.id}

@app.delete("/api/admin/contests/{code}/jury-restrictions/{restriction_id}")
def delete_jury_restriction(code: str, restriction_id: int, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    item = db.query(models.ContestJuryRestriction).filter_by(id=restriction_id, contest_id=contest.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Restriction not found")
    db.delete(item)
    db.commit()
    return {"status": "success", "removed": restriction_id}

@app.get("/api/admin/contests/{code}/banned-users")
def get_banned_users(code: str, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    return [{"id": item.id, "username": item.user.wiki_username}
            for item in contest.banned_users if item.user]

@app.post("/api/admin/contests/{code}/banned-users")
def ban_contest_user(code: str, data: ContestBan, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest or data.contest_code != code:
        raise HTTPException(status_code=404, detail="Contest not found")
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    user = db.query(models.User).filter_by(wiki_username=username).first()
    if not user:
        user = models.User(wiki_username=username, role=models.RoleEnum.participant)
        db.add(user)
        db.flush()
    existing = db.query(models.ContestBannedUser).filter_by(contest_id=contest.id, user_id=user.id).first()
    if existing:
        return {"status": "success", "id": existing.id, "already_exists": True}
    item = models.ContestBannedUser(contest_id=contest.id, user_id=user.id)
    db.add(item)
    db.commit()
    return {"status": "success", "id": item.id, "username": username}

@app.delete("/api/admin/contests/{code}/banned-users/{ban_id}")
def unban_contest_user(code: str, ban_id: int, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    item = db.query(models.ContestBannedUser).filter_by(id=ban_id, contest_id=contest.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ban not found")
    db.delete(item)
    db.commit()
    return {"status": "success", "removed": ban_id}

# ---------------------------------------------------------------------------
# Talk-page queue administration
# ---------------------------------------------------------------------------

# Feather's OAuth consumer tags every edit it makes on bn.wiktionary.org with
# this change tag -- confirmed against
# Special:RecentChanges?tagfilter=OAuth+CID:+18851. It is the wiki's own record
# of what this tool has edited, which beats anything the app logs about itself.
# Both the consumer id and the wiki are single-project assumptions: if contests
# ever run on another project, this has to come from per-contest config.
FEATHER_OAUTH_CHANGE_TAG = "OAuth CID: 18851"
TALK_NAMESPACE = 1

# recentchanges is retention-limited (roughly 30-90 days), so submissions
# older than that need checking against the pages themselves. The check reads
# talk-page wikitext 50 titles at a time (the API's limit for normal users)
# instead of one page per request, which is what makes a contest with five
# figures of articles checkable inside a single request.
BACKFILL_TITLES_PER_QUERY = 50
BACKFILL_MAX_RC_PAGES = 20

# Deliberately far lower than the global semaphore (15) used for article
# validation. Validation runs against a few hundred titles; a backfill on an
# 11k-article contest is a couple of hundred back-to-back batch reads, which
# is a sustained burst rather than a spike. Measured against the real 11k
# contest: at 15-way concurrency bn.wiktionary starts answering 429 partway
# through and ~5,600 titles came back unverified, at 4 it was 600, at 2 it is
# zero (a full 4,000-title call takes ~15s).
BACKFILL_READ_CONCURRENCY = 2

# How many articles one call will examine. The reads are fast and run
# concurrently, but an unbounded call on a huge contest would sit past the
# ingress timeout -- so it works through the contest in chunks and reports
# what is left for the next call.
BACKFILL_DEFAULT_LIMIT = 4000

# Statuses that mean "this submission was accepted into the contest", i.e. the
# same set submit_bulk would have queued a template for.
TALK_TEMPLATE_ARTICLE_STATUSES = (models.ArticleStatus.pending, models.ArticleStatus.accepted)


@app.get("/api/admin/contests/{code}/talk-queue")
def get_talk_queue_status(code: str, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    """Counts by status plus the failures, so a stalled queue is visible
    without opening the database."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    counts = {"queued": 0, "processing": 0, "done": 0, "failed": 0}
    rows = db.query(models.TalkPageJob.status, func.count(models.TalkPageJob.id)).filter(
        models.TalkPageJob.contest_id == contest.id
    ).group_by(models.TalkPageJob.status).all()
    for status, count in rows:
        counts[status] = counts.get(status, 0) + count

    failed = db.query(models.TalkPageJob).filter(
        models.TalkPageJob.contest_id == contest.id,
        models.TalkPageJob.status == "failed"
    ).order_by(models.TalkPageJob.id).all()

    return {
        "contest_code": contest.code,
        "counts": counts,
        "total": sum(counts.values()),
        "failed": [
            {
                "id": job.id,
                "title": job.title,
                "error": job.error,
                "attempts": job.attempts,
                "submitted_by": job.submitted_by,
                "created_at": job.created_at,
                "processed_at": job.processed_at,
            }
            for job in failed
        ],
    }


@app.post("/api/admin/contests/{code}/talk-queue/retry-failed")
def retry_failed_talk_jobs(code: str, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    requeued = db.query(models.TalkPageJob).filter(
        models.TalkPageJob.contest_id == contest.id,
        models.TalkPageJob.status == "failed"
    ).update({"status": "queued", "attempts": 0, "error": None}, synchronize_session=False)
    db.commit()
    return {"status": "success", "requeued": requeued}


def _titles_logged_as_failed(db: Session, contest) -> set:
    """Best-effort read of past `add_talk_pages` log lines.

    The log message only ever named the *failures* ("Failures (M): title:
    error, ..."); successes were recorded as a bare count, so this can never
    tell us a title succeeded. It is used only to skip the per-page live check
    for titles already known to have failed -- it narrows API work and is
    never treated as ground truth in either direction. The text is free-form,
    truncated at ~1500 chars, and titles containing commas or colons break the
    split, so a miss here is expected and harmless.
    """
    logged_failures = set()
    logs = db.query(models.SystemLog).filter(
        models.SystemLog.source == "talk_template",
        models.SystemLog.timestamp >= contest.start_date,
    ).all()
    for log in logs:
        message = log.message or ""
        marker = message.find("Failures (")
        if marker == -1:
            continue
        tail = message[message.find(":", marker) + 1:]
        for chunk in tail.split(","):
            title, sep, _error = chunk.partition(":")
            if sep and title.strip():
                logged_failures.add(title.strip())
    return logged_failures


def _bare_talk_title(page_title: str) -> str:
    """Strip the talk namespace prefix and normalize for comparison.

    bn.wiktionary returns talk pages under the localized prefix (`আলাপ:`),
    not the canonical `Talk:`, so these cannot be compared against a
    locally-built "Talk:" + title string. Everything from `rcnamespace=1` is
    a talk page by construction, so dropping the segment before the first
    colon leaves the article title -- and only the *first* colon, since the
    article title may legitimately contain one.
    """
    _prefix, _sep, rest = page_title.partition(":")
    return _normalize_wiki_name(rest if _sep else page_title)


async def _fetch_feather_tagged_talk_titles(client: httpx.AsyncClient, since: datetime) -> set:
    """Article titles whose talk page Feather has already edited, per the
    wiki's own recentchanges feed. Authoritative but retention-limited."""
    titles = set()
    rccontinue = None
    for _ in range(BACKFILL_MAX_RC_PAGES):
        params = {
            "action": "query",
            "list": "recentchanges",
            "rctag": FEATHER_OAUTH_CHANGE_TAG,
            "rcnamespace": TALK_NAMESPACE,
            "rcprop": "title",
            "rclimit": "max",
            "rcdir": "newer",
            "rcstart": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "format": "json",
            "formatversion": 2,
        }
        if rccontinue:
            params["rccontinue"] = rccontinue
        response = await wiki_api_request(
            "GET", MEDIAWIKI_API_URL, client=client,
            params=params, headers={"User-Agent": WIKI_USER_AGENT}
        )
        data = response.json()
        for change in data.get("query", {}).get("recentchanges", []):
            if change.get("title"):
                titles.add(_bare_talk_title(change["title"]))
        rccontinue = data.get("continue", {}).get("rccontinue")
        if not rccontinue:
            break
    return titles


async def _talk_pages_already_templated(client: httpx.AsyncClient, titles: list, template_text: str) -> set:
    """Of these article titles, which already carry the template on their talk page?

    Returns (set of titles that already carry it, count of titles whose check
    could not be completed).

    Reads current talk-page wikitext in batches of 50. A per-page
    revision-tag check would answer the narrower question "has Feather ever
    edited this page", but it costs one request per page -- unusable on a
    contest with thousands of articles -- and it is also the wrong question
    here: what decides whether an edit is needed is whether the template is
    on the page right now. The one case the two disagree on is a template
    that Feather added and a human later removed; recentchanges catches that
    for recent edits, and older ones would be re-added.
    """
    templated = set()
    unverified = 0
    sem = asyncio.Semaphore(BACKFILL_READ_CONCURRENCY)

    async def check_chunk(chunk: list):
        params = {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(talk_page_title(t) for t in chunk),
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": 2,
        }
        async with sem:
            response = await wiki_api_request(
                "POST", MEDIAWIKI_API_URL, client=client,
                data=params, headers={"User-Agent": WIKI_USER_AGENT}
            )
        data = response.json()
        found = set()
        for page in data.get("query", {}).get("pages", []):
            if page.get("missing"):
                continue
            revisions = page.get("revisions", [])
            if not revisions:
                continue
            content = revisions[0].get("slots", {}).get("main", {}).get("content", "") or ""
            if template_text in content:
                found.add(_bare_talk_title(page.get("title", "")))
        return found

    chunks = [titles[i:i + BACKFILL_TITLES_PER_QUERY]
              for i in range(0, len(titles), BACKFILL_TITLES_PER_QUERY)]
    for result, chunk in zip(
        await asyncio.gather(*(check_chunk(c) for c in chunks), return_exceptions=True), chunks
    ):
        if isinstance(result, set):
            templated |= result
        else:
            # A failed chunk means "not verified", not "not templated". Those
            # titles get enqueued, which is safe -- the worker re-reads every
            # page and skips the edit if the template is already there -- but
            # it is wasted queue time, so the count is reported back.
            unverified += len(chunk)
            print(f"[talk-backfill] Chunk check failed ({len(chunk)} titles): {result}")
    return templated, unverified


@app.post("/api/admin/contests/{code}/talk-queue/backfill")
async def backfill_talk_queue(
    code: str,
    limit: int = Query(default=BACKFILL_DEFAULT_LIMIT, ge=1, le=20000),
    dry_run: bool = Query(default=False),
    current_user: models.User = Depends(get_owner_user),
    db: Session = Depends(get_db)
):
    """Queue talk-page templates for articles submitted before this queue existed.

    Only enqueues -- the reads below check what the wiki already has; every
    actual edit still goes through the worker at the global pace. Call it
    again while `remaining` is above zero to work through a large contest.

    `dry_run=true` runs exactly the same checks and reports the same counts
    without writing a single job row. How many articles a real contest still
    needs is not something you can predict from another database, and the
    button otherwise commits thousands of edits before telling you how many
    it was -- so the preview exists to be run first.
    """
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    if not contest.talk_template_name:
        raise HTTPException(status_code=400, detail="This contest has no talk template configured")

    # Fallback for the many submitters with no stored token (see the enqueue
    # loop below). Checked up front so the owner is told to re-login before
    # the wiki reads run, not after.
    owner_token = current_user.oauth_access_token
    if not owner_token:
        raise HTTPException(
            status_code=400,
            detail="Your account has no stored OAuth token — log out and back in before running a backfill."
        )

    articles = db.query(models.Article).options(joinedload(models.Article.submitter)).filter(
        models.Article.contest_id == contest.id,
        models.Article.status.in_(TALK_TEMPLATE_ARTICLE_STATUSES)
    ).order_by(models.Article.id).all()

    # A job this queue already ran is the one internal record that is
    # trustworthy, so those articles never reach the live check.
    #
    # `failed` counts as handled too, even though its edit never landed: a
    # second job row for the same article would not fix anything the first
    # one could not, it just hides the failure behind a duplicate and inflates
    # the counts. Retrying those is what /talk-queue/retry-failed is for.
    handled_article_ids = {
        row[0] for row in db.query(models.TalkPageJob.article_id).filter(
            models.TalkPageJob.contest_id == contest.id,
            models.TalkPageJob.status.in_(("queued", "processing", "done", "failed")),
        ).all()
    }

    already_done = len([a for a in articles if a.id in handled_article_ids])
    pending_articles = [a for a in articles if a.id not in handled_article_ids]
    candidates = pending_articles[:limit]
    remaining = len(pending_articles) - len(candidates)

    logged_failures = _titles_logged_as_failed(db, contest)

    to_enqueue = []
    unverified = 0
    if candidates:
        client = get_http_client()
        since = contest.start_date or (utcnow() - timedelta(days=90))
        try:
            tagged_talk_titles = await _fetch_feather_tagged_talk_titles(client, since)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not read recent changes from the wiki: {e}")

        # First pass: the wiki's own record of what Feather edited. Free
        # (one paged list query) but only covers the retention window.
        needs_page_check = []
        for article in candidates:
            if _normalize_wiki_name(article.title) in tagged_talk_titles:
                already_done += 1
            elif article.title in logged_failures:
                # The log says this one failed, so skip straight to enqueueing
                # rather than spending a check on it.
                to_enqueue.append(article)
            else:
                needs_page_check.append(article)

        # Second pass: read the talk pages themselves for everything older
        # than the retention window.
        if needs_page_check:
            template_text = build_talk_template_text(contest.talk_template_name)
            try:
                templated, unverified = await _talk_pages_already_templated(
                    client, [a.title for a in needs_page_check], template_text
                )
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Could not read talk pages from the wiki: {e}")
            for article in needs_page_check:
                if _normalize_wiki_name(article.title) in templated:
                    already_done += 1
                else:
                    to_enqueue.append(article)

    skipped_no_token = []
    enqueued = 0
    used_owner_token = 0
    for article in to_enqueue:
        submitter = article.submitter
        access_token = submitter.oauth_access_token if submitter else None
        if not access_token:
            # Most of a long-running contest's submitters have no stored
            # token: they last logged in before the column existed, or the
            # article came in through "submit on behalf of", which creates a
            # bare user row and records nothing about who ran it. Without a
            # fallback the backfill would skip the large majority of the
            # contest, so the edit is made by the owner running the backfill
            # instead. It is attributed to their wiki account; `submitted_by`
            # still names the participant the article belongs to.
            access_token = owner_token
            used_owner_token += 1
        if not access_token:
            skipped_no_token.append(article.title)
            continue
        enqueued += 1
        if dry_run:
            continue
        db.add(models.TalkPageJob(
            article_id=article.id,
            contest_id=contest.id,
            title=article.title,
            status="queued",
            attempts=0,
            access_token=access_token,
            submitted_by=submitter.wiki_username if submitter else "unknown",
            created_at=utcnow(),
        ))
    if dry_run:
        # Nothing was added, but the session still read rows -- roll back so
        # a preview can never leave anything behind.
        db.rollback()
    else:
        db.commit()

    return {
        "dry_run": dry_run,
        "enqueued": 0 if dry_run else enqueued,
        "would_enqueue": enqueued,
        "already_done": already_done,
        "skipped_no_token": skipped_no_token,
        "considered": len(articles),
        "examined": len(candidates),
        "remaining": remaining,
        "enqueued_unverified": unverified,
        "used_owner_token": used_owner_token,
    }

async def process_articles_batch(
    titles: List[str],
    submitter_username: str,
    contest,
    db: Session,
    bypass_rules: bool = False
) -> List[ValidationResult]:
    results = []
    
    existing = db.query(models.Article).filter(
        models.Article.contest_id == contest.id,
        models.Article.title.in_(titles)
    ).all()
    existing_titles = {a.title.lower() for a in existing if a.status != models.ArticleStatus.validation_failed}
    
    titles_to_check = []
    for t in titles:
        if t.lower() in existing_titles:
            results.append(ValidationResult(title=t, is_valid=False, error="Already submitted"))
        else:
            titles_to_check.append(t)
            
    if not titles_to_check:
        return results
    db_replica_results = query_wiki_replica_batch(titles_to_check)
    if db_replica_results is not None:
        for t in titles_to_check:
            info = db_replica_results.get(t.lower())  # keys are lowercased in query_wiki_replica_batch
            if not info:
                results.append(ValidationResult(title=t, is_valid=False, error="Article does not exist"))
                continue
                
            creator = info.get("wiki_creator")
            wiki_date = info.get("wiki_creation_date")
            timestamp_str = info.get("timestamp_str")
            page_ns = info.get("page_namespace", 0)
            is_redirect = info.get("page_is_redirect", False)
            page_len = info.get("page_len", 0)
            
            if not bypass_rules:
                if getattr(contest, 'rule_mainspace_only', True) and page_ns != 0:
                    results.append(ValidationResult(title=t, is_valid=False, error="Must be in Mainspace (Namespace 0)"))
                    continue
                if getattr(contest, 'rule_no_redirect', True) and is_redirect:
                    results.append(ValidationResult(title=t, is_valid=False, error="Article is a redirect page"))
                    continue
                min_b = getattr(contest, 'min_bytes', 0)
                if min_b > 0 and page_len < min_b:
                    results.append(ValidationResult(title=t, is_valid=False, error=f"Article size too small ({page_len} B < min {min_b} B)"))
                    continue
                if contest.rule_must_be_creator and _normalize_wiki_name(creator) != _normalize_wiki_name(submitter_username):
                    results.append(ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'"))
                    continue
                if wiki_date:
                    wd = wiki_date.replace(tzinfo=None) if hasattr(wiki_date, 'tzinfo') else wiki_date
                    cs = contest.start_date.replace(tzinfo=None) if contest.start_date else None
                    ce = contest.end_date.replace(tzinfo=None) if contest.end_date else None
                    if cs and ce and not (cs <= wd <= ce):
                        results.append(ValidationResult(title=t, is_valid=False, error="Created outside contest timeframe"))
                        continue
                    
            results.append(ValidationResult(title=t, is_valid=True, wiki_creator=creator, wiki_creation_date=timestamp_str))
        return results
    unique_id = uuid.uuid4().hex[:8]
    contact_email = os.getenv("CONTACT_EMAIL", "contact@example.com")
    user_agent_username = quote(str(submitter_username or ""), safe="")
    user_agent = f"WikiArticleContestTool/1.0 (User:{user_agent_username}; ContestCode:{contest.code}; {contact_email}; RequestID:{unique_id})"
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip"
    }
    client = get_http_client()
    sem = get_global_semaphore()
    
    async def fetch_single_http(t: str) -> ValidationResult:
        params = {
            "action": "query",
            "format": "json",
            "titles": t,
            "prop": "revisions|info|pageprops",
            "rvprop": "timestamp|user|size|content",
            "rvlimit": 1,
            "rvdir": "newer",
            "inprop": "url"
        }
        async with sem:
            try:
                response = await wiki_api_request(
                    "POST", MEDIAWIKI_API_URL, client=client, data=params, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                pages = data.get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    raw_title = page.get("title", t)
                    if "missing" in page:
                        return ValidationResult(title=t, is_valid=False, error="Article does not exist")
                        
                    revisions = page.get("revisions", [])
                    if not revisions:
                        return ValidationResult(title=t, is_valid=False, error="No revisions found")
                        
                    first_rev = revisions[0]
                    creator = first_rev.get("user")
                    timestamp_str = first_rev.get("timestamp")
                    page_ns = page.get("ns", 0)
                    is_redirect = "redirect" in page
                    page_size = first_rev.get("size", page.get("length", 0))
                    pageprops = page.get("pageprops", {})
                    is_disambig = "disambiguation" in pageprops
                    content = first_rev.get("*") or first_rev.get("slots", {}).get("main", {}).get("*", "")
                    word_count = len([w for w in content.split() if w.strip()]) if content else 0
                    ref_count = len(re.findall(r'<ref[\s/>]', content, re.IGNORECASE)) if content else 0
                    
                    if not bypass_rules:
                        if getattr(contest, 'rule_mainspace_only', True) and page_ns != 0:
                            return ValidationResult(title=t, is_valid=False, error="Must be in Mainspace (Namespace 0)")
                        if getattr(contest, 'rule_no_redirect', True) and is_redirect:
                            return ValidationResult(title=t, is_valid=False, error="Article is a redirect page")
                        if getattr(contest, 'rule_no_disambig', True) and is_disambig:
                            return ValidationResult(title=t, is_valid=False, error="Article is a disambiguation page")
                        min_b = getattr(contest, 'min_bytes', 0)
                        if min_b > 0 and page_size < min_b:
                            return ValidationResult(title=t, is_valid=False, error=f"Article size too small ({page_size} B < min {min_b} B)")
                        min_w = getattr(contest, 'min_words', 0)
                        if min_w > 0 and word_count < min_w:
                            return ValidationResult(title=t, is_valid=False, error=f"Word count too low ({word_count} < min {min_w} words)")
                        min_r = getattr(contest, 'min_refs', 0)
                        if min_r > 0 and ref_count < min_r:
                            return ValidationResult(title=t, is_valid=False, error=f"Insufficient references ({ref_count} < min {min_r} refs)")
                        if contest.rule_must_be_creator and _normalize_wiki_name(creator) != _normalize_wiki_name(submitter_username):
                            return ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'")
                            
                        creation_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
                        start = contest.start_date.replace(tzinfo=None) if contest.start_date else None
                        end = contest.end_date.replace(tzinfo=None) if contest.end_date else None
                        if start and end and not (start <= creation_time <= end):
                            return ValidationResult(title=t, is_valid=False, error="Created outside contest timeframe")
                            
                    return ValidationResult(title=t, is_valid=True, wiki_creator=creator, wiki_creation_date=timestamp_str)
                return ValidationResult(title=t, is_valid=False, error="Article does not exist")
            except Exception as e:
                return ValidationResult(title=t, is_valid=False, error=f"API Error: {str(e)}")

    http_results = await asyncio.gather(*(fetch_single_http(t) for t in titles_to_check))
    results.extend(http_results)
    return results

@app.get("/api/contests/{code}/my-role")
def get_contest_role(code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
        
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    is_owner = current_user.role == models.RoleEnum.owner
    return {"is_jury": is_jury, "is_owner": is_owner}

@app.post("/api/submit-bulk", response_model=List[ValidationResult])
async def submit_bulk(
    request: BulkSubmitRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contest = db.query(models.Contest).filter_by(code=request.contest_code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    now = utcnow()
    start_date = contest.start_date.replace(tzinfo=None) if contest.start_date else None
    end_date = contest.end_date.replace(tzinfo=None) if contest.end_date else None
    if start_date and now < start_date:
        raise HTTPException(status_code=403, detail="This contest has not started yet. Submissions are not open.")
    if end_date and now > end_date:
        raise HTTPException(status_code=403, detail="This contest has ended. New article submissions are closed.")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    is_privileged = is_owner or is_jury

    submitter_username = current_user.wiki_username
    if request.on_behalf_of:
        if not is_privileged:
            raise HTTPException(status_code=403, detail="Only Jury or Owner can submit on behalf of others.")
        submitter_username = request.on_behalf_of

    clean_titles = list({t.strip() for t in request.titles if t.strip()})
    
    results = await process_articles_batch(
        clean_titles,
        submitter_username,
        contest,
        db,
        bypass_rules=is_privileged
    )
    effective_user = db.query(models.User).filter_by(wiki_username=submitter_username).first()
    if not effective_user:
        try:
            effective_user = models.User(wiki_username=submitter_username, role=models.RoleEnum.participant)
            db.add(effective_user)
            db.commit()
            db.refresh(effective_user)
        except Exception:
            db.rollback()
            effective_user = db.query(models.User).filter_by(wiki_username=submitter_username).first()
            if not effective_user:
                raise HTTPException(status_code=500, detail="Failed to create submitter user record due to database concurrency.")
    existing_articles_map = {
        a.title.lower(): a for a in db.query(models.Article).filter(
            models.Article.contest_id == contest.id,
            models.Article.title.in_(clean_titles)
        ).all()
    }

    for res in results:
        t_lower = res.title.lower()
        existing_art = existing_articles_map.get(t_lower)

        wiki_date = None
        if hasattr(res, 'wiki_creation_date') and res.wiki_creation_date:
            try:
                wiki_date = datetime.strptime(res.wiki_creation_date, "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        if res.is_valid:
            if existing_art and existing_art.status in (models.ArticleStatus.pending, models.ArticleStatus.accepted, models.ArticleStatus.rejected):
                res.is_valid = False
                res.error = "Already submitted"
                continue

            if existing_art:
                existing_art.status = models.ArticleStatus.pending
                existing_art.validation_error = None
                existing_art.submitter_id = effective_user.id
                existing_art.wiki_creator = res.wiki_creator
                existing_art.wiki_creation_date = wiki_date
                existing_art.submitted_at = utcnow()
            else:
                article = models.Article(
                    title=res.title,
                    submitter_id=effective_user.id,
                    contest_id=contest.id,
                    status=models.ArticleStatus.pending,
                    validation_error=None,
                    wiki_creation_date=wiki_date,
                    wiki_creator=res.wiki_creator,
                    submitted_at=utcnow()
                )
                db.add(article)
        else:
            if res.error == "Already submitted":
                continue

            if existing_art:
                existing_art.status = models.ArticleStatus.validation_failed
                existing_art.validation_error = res.error
                existing_art.submitter_id = effective_user.id
                existing_art.wiki_creator = res.wiki_creator
                existing_art.wiki_creation_date = wiki_date
                existing_art.submitted_at = utcnow()
            else:
                article = models.Article(
                    title=res.title,
                    submitter_id=effective_user.id,
                    contest_id=contest.id,
                    status=models.ArticleStatus.validation_failed,
                    validation_error=res.error,
                    wiki_creation_date=wiki_date,
                    wiki_creator=res.wiki_creator,
                    submitted_at=utcnow()
                )
                db.add(article)
            
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database concurrency issue during bulk submit: {str(e)}")

    rebalance_pending_articles(db, contest)

    valid_titles = [r.title for r in results if r.is_valid]
    print(f"[submit-bulk] Talk Template Debug: valid_titles_count={len(valid_titles)}, add_talk_template={contest.add_talk_template}, template_name='{contest.talk_template_name}'")
    if valid_titles and contest.add_talk_template and contest.talk_template_name:
        # Enqueue only. The edits are drained one at a time by
        # talk_queue_worker so a large submission cannot trip MediaWiki's edit
        # rate limit, and a restart resumes instead of losing the remainder.
        queued = enqueue_talk_page_jobs(
            db,
            contest,
            valid_titles,
            current_user.oauth_access_token,
            submitter_username,
        )
        print(f"[submit-bulk] Queued {queued} talk page template job(s) for contest {contest.code}.")

    return results

@app.get("/api/articles/{contest_code}/pending/next")
def get_next_pending(contest_code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=contest_code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to review this contest")
    lock_cutoff = utcnow() - timedelta(minutes=15)
    locked_by_others = db.query(models.ArticleLock.article_id).filter(
        models.ArticleLock.locked_at >= lock_cutoff,
        models.ArticleLock.locked_by != current_user.wiki_username
    ).subquery()
    
    reviewed_by_me = db.query(models.Review.article_id).filter(
        models.Review.reviewer_id == current_user.id
    ).subquery()

    query = db.query(models.Article).options(joinedload(models.Article.submitter)).filter(
        models.Article.contest_id == contest.id, 
        models.Article.status == models.ArticleStatus.pending,
        ~models.Article.id.in_(locked_by_others),
        ~models.Article.id.in_(reviewed_by_me)
    )
    
    if not is_owner and not contest.allow_self_review:
        query = query.filter(models.Article.submitter_id != current_user.id)
    if is_jury and not is_owner:
        query = query.filter(~exists().where(
            models.ContestJuryRestriction.contest_id == contest.id,
            models.ContestJuryRestriction.jury_user_id == current_user.id,
            models.ContestJuryRestriction.submitter_user_id == models.Article.submitter_id,
        ))
        
    article = query.first()    
    if not article:
        raise HTTPException(status_code=404, detail="No pending articles")
        
    return {
        "id": article.id,
        "title": article.title,
        "submitter": article.submitter.wiki_username,
        "submitted_at": article.submitted_at,
        "wiki_creation_date": article.wiki_creation_date
    }

@app.get("/api/contests/{code}/results")
def get_contest_results(code: str, db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    # Aggregated in SQL instead of loading every article/review row into Python —
    # on large contests that full load was the dominant cost of this public page.
    submitter_rows = db.query(
        models.User.wiki_username,
        func.count(models.Article.id),
        func.sum(case((models.Article.status == models.ArticleStatus.accepted, 1), else_=0)),
        func.sum(case((models.Article.status == models.ArticleStatus.rejected, 1), else_=0)),
        func.sum(case((models.Article.status == models.ArticleStatus.pending, 1), else_=0)),
    ).join(models.Article, models.Article.submitter_id == models.User.id) \
     .filter(models.Article.contest_id == contest.id) \
     .group_by(models.User.wiki_username).all()

    jury_rows = db.query(
        models.User.wiki_username,
        func.count(models.Review.id),
        func.sum(case((models.Review.status == models.ReviewStatus.accepted, 1), else_=0)),
        func.sum(case((models.Review.status == models.ReviewStatus.rejected, 1), else_=0)),
    ).join(models.Article, models.Article.id == models.Review.article_id) \
     .join(models.User, models.User.id == models.Review.reviewer_id) \
     .filter(models.Article.contest_id == contest.id) \
     .group_by(models.User.wiki_username).all()

    return {
        "contest": {"name": contest.name, "code": contest.code},
        "submitters": [
            {"username": u, "total": int(t or 0), "accepted": int(a or 0), "rejected": int(r or 0), "pending": int(p or 0)}
            for u, t, a, r, p in submitter_rows
        ],
        "juries": [
            {"username": u, "total": int(t or 0), "accepted": int(a or 0), "rejected": int(r or 0)}
            for u, t, a, r in jury_rows
        ],
    }

@app.get("/api/contests/{code}/stats")
def get_contest_stats(code: str, db: Session = Depends(get_db)):
    """Grouped-count summary for dashboards/polling that only need totals, not every
    article/review row. Also carries a cheap change signature so pollers can skip
    re-fetching the full /log payload when nothing actually changed."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    status_counts = {s.value: 0 for s in models.ArticleStatus}
    total = 0
    for status, count in db.query(
        models.Article.status, func.count(models.Article.id)
    ).filter_by(contest_id=contest.id).group_by(models.Article.status).all():
        status_counts[status.value] = int(count)
        total += int(count)
    status_counts["total"] = total

    # Only the latest non-skipped review per (article, reviewer) counts toward a
    # jury's stats, so a reopened/updated decision doesn't double-count.
    latest_review = db.query(
        models.Review.article_id,
        models.Review.reviewer_id,
        func.max(models.Review.id).label("latest_id"),
    ).filter(models.Review.status != models.ReviewStatus.skipped) \
     .group_by(models.Review.article_id, models.Review.reviewer_id).subquery()

    jury_map = {}
    for username, decision, count in db.query(
        models.User.wiki_username, models.Review.status, func.count(models.Review.id)
    ).join(latest_review, models.Review.id == latest_review.c.latest_id) \
     .join(models.Article, models.Article.id == models.Review.article_id) \
     .join(models.User, models.User.id == models.Review.reviewer_id) \
     .filter(models.Article.contest_id == contest.id) \
     .group_by(models.User.wiki_username, models.Review.status).all():
        entry = jury_map.setdefault(username, {"name": username, "total": 0, "accepted": 0, "rejected": 0})
        entry["total"] += int(count)
        if decision == models.ReviewStatus.accepted:
            entry["accepted"] += int(count)
        elif decision == models.ReviewStatus.rejected:
            entry["rejected"] += int(count)

    latest_article_id = db.query(func.max(models.Article.id)).filter_by(contest_id=contest.id).scalar() or 0
    latest_review_id = db.query(func.max(models.Review.id)) \
        .join(models.Article, models.Article.id == models.Review.article_id) \
        .filter(models.Article.contest_id == contest.id).scalar() or 0

    return {
        "status_counts": status_counts,
        "jury_stats": sorted(jury_map.values(), key=lambda j: j["total"], reverse=True),
        "signature": f"{total}:{latest_article_id}:{latest_review_id}",
    }

@app.get("/api/contests/{code}/log")
def get_contest_log(
    code: str,
    before_id: Optional[int] = Query(default=None),
    offset: Optional[int] = Query(default=None, ge=0),
    page_size: int = Query(default=200, ge=1, le=500),
    include_reviews: bool = Query(default=True),
    status: Optional[str] = Query(default=None),
    submitted_by: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
):
    """Paginated activity log, newest first. Uses keyset pagination (before_id,
    ordered by id) by default rather than offset/limit: this contest keeps
    receiving new submissions while a multi-page crawl is in progress, and
    offset/limit silently skips or re-shuffles rows as the underlying result
    set shifts under concurrent inserts. Cursoring on id is immune to that —
    a page is always "articles with id < before_id", so new rows (always
    higher ids) never perturb pages already fetched or still to come.

    offset is an explicit opt-in to plain offset pagination instead, for
    callers that already have a consistent baseline (e.g. a keyset first
    page plus a known total) and want to fetch the rest as several concurrent
    requests -- offsets don't depend on each other the way keyset cursors do,
    so they can all be requested at once instead of one at a time. This
    reintroduces the same small drift-under-concurrent-inserts risk keyset
    pagination avoids, so it's meant for a background catch-up crawl (whose
    results get de-duplicated by id) after a keyset first page has already
    established the live, always-correct view -- not for a page a user is
    actively relying on being exactly right.

    include_reviews=false skips the reviews join/serialization entirely — the
    submissions/errors moderation views only need title/status/validation
    info per article, not review history, and loading it anyway roughly
    doubles the query and payload cost of every page for no benefit there.

    status filters to one status (e.g. validation_failed) so a consumer that
    only cares about a small subset doesn't have to crawl the whole contest
    looking for it — errored articles are typically a handful out of
    thousands, and could otherwise sit anywhere in the id order.

    submitted_by filters to one submitter, resolved to their user id up front
    so the actual article query filters on the indexed submitter_id column
    directly (ix_articles_contest_submitter) rather than joining through
    users by name -- lets the dashboard's per-user drill-down fetch just that
    user's articles on demand instead of crawling the whole contest log and
    grouping client-side.

    q is a substring title search, applied server-side. Finding one article in
    a 11k-article contest previously meant crawling every page of this endpoint
    and scanning in JavaScript; this filters in SQL and returns only matches,
    so the client fetches one small page instead of the whole contest. It
    combines with status/submitted_by, and `total` reflects the filtered count
    so the caller's pagination stays correct."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    submitter_id = None
    if submitted_by:
        submitter_id = db.query(models.User.id).filter_by(wiki_username=submitted_by).scalar()
        if submitter_id is None:
            return {"items": [], "total": 0, "page_size": page_size, "has_more": False, "next_before_id": None}

    search_term = (q or "").strip()

    def apply_filters(query):
        if status:
            query = query.filter(models.Article.status == status)
        if submitter_id is not None:
            query = query.filter(models.Article.submitter_id == submitter_id)
        if search_term:
            # escape LIKE wildcards so a title containing % or _ searches
            # literally instead of matching everything.
            escaped = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(models.Article.title.like(f"%{escaped}%", escape="\\"))
        return query

    count_query = apply_filters(
        db.query(func.count(models.Article.id)).filter_by(contest_id=contest.id)
    )
    total = count_query.scalar()

    query = db.query(models.Article).options(joinedload(models.Article.submitter))
    if include_reviews:
        query = query.options(selectinload(models.Article.reviews).joinedload(models.Review.reviewer))
    query = apply_filters(query.filter_by(contest_id=contest.id))
    if before_id is not None:
        query = query.filter(models.Article.id < before_id)
    query = query.order_by(models.Article.id.desc())
    if offset is not None:
        query = query.offset(offset)
    articles = query.limit(page_size).all()

    log = []
    active_locks = {}
    if include_reviews:
        now = utcnow()
        lock_cutoff = now - timedelta(minutes=15)
        article_ids = [a.id for a in articles]
        if article_ids:
            lock_rows = db.query(models.ArticleLock).filter(
                models.ArticleLock.article_id.in_(article_ids),
                models.ArticleLock.locked_at >= lock_cutoff
            ).all()
            active_locks = {row.article_id: row.locked_by for row in lock_rows}

    for a in articles:
        entry = {
            "article_id": a.id,
            "title": a.title,
            "submitted_by": a.submitter.wiki_username,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "wiki_creator": a.wiki_creator,
            "wiki_creation_date": a.wiki_creation_date.isoformat() if a.wiki_creation_date else None,
            "status": a.status.value,
            "validation_error": a.validation_error,
            "locked_by": active_locks.get(a.id),
            "reviews": [
                {
                    "reviewer": r.reviewer.wiki_username,
                    "decision": r.status.value,
                    "comment": r.comment,
                    "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
                }
                for r in sorted(a.reviews, key=lambda r: r.timestamp or datetime.min)
                if r.status.value != "skipped"
            ] if include_reviews else [],
        }
        log.append(entry)

    return {
        "items": log,
        "total": total,
        "page_size": page_size,
        "next_before_id": articles[-1].id if articles else None,
        "has_more": len(articles) == page_size,
    }

@app.get("/api/contests/{code}/submitters")
def get_contest_submitters(code: str, db: Session = Depends(get_db)):
    """Cheap per-submitter counts (username + article count), sorted by count
    descending -- backs the dashboard's "Submissions by User" panel's group
    headers without crawling every article in the contest just to group them
    client-side. Each group's actual articles are then fetched on demand,
    filtered by submitter, via GET .../log?submitted_by=<username>."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    rows = db.query(models.User.wiki_username, func.count(models.Article.id)) \
        .join(models.Article, models.Article.submitter_id == models.User.id) \
        .filter(models.Article.contest_id == contest.id) \
        .group_by(models.User.wiki_username) \
        .order_by(func.count(models.Article.id).desc()).all()

    return {"submitters": [{"username": username, "count": int(count)} for username, count in rows]}

def _jury_panel_authorize(contest, current_user, db, view_as=None):
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to view the jury panel")
    if view_as and (not is_owner or view_as not in [j.user.wiki_username for j in contest.juries if j.user]):
        raise HTTPException(status_code=403, detail="Owner view must target an assigned jury member")
    return is_owner

def _jury_panel_base_query(db, contest):
    banned_ids = {b.user_id for b in contest.banned_users}
    query = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer),
    ).filter(models.Article.contest_id == contest.id)
    if banned_ids:
        query = query.filter(~models.Article.submitter_id.in_(banned_ids))
    return query

@app.get("/api/jury-panel/contests/{code}/articles")
def get_jury_panel_articles(code: str, view_as: Optional[str] = Query(default=None), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = _jury_panel_authorize(contest, current_user, db, view_as)
    jury_map = get_eligible_juries(contest)
    rebalance_pending_articles(db, contest, jury_map)

    target = view_as if (is_owner and view_as) else ("*" if is_owner else current_user.wiki_username)
    query = _jury_panel_base_query(db, contest)
    if target != "*":
        target_id = jury_map_username_to_id(jury_map).get(target, -1)
        query = query.filter(models.Article.assigned_to_id == target_id)
    articles = query.order_by(models.Article.id.asc()).all()
    return [serialize_jury_article(a, jury_map) for a in articles]

@app.get("/api/jury-panel/contests/{code}/articles/page")
def get_jury_panel_articles_page(
    code: str,
    after_id: Optional[int] = Query(default=None),
    page_size: int = Query(default=250, ge=25, le=500),
    view_as: Optional[str] = Query(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a bounded page of assigned jury articles and queue metadata.
    Keyset-paginated (after_id, ordered by id) rather than offset/limit -- new
    submissions keep landing while a jury is paging through their queue, and
    offset/limit silently skips or re-shuffles rows under that."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = _jury_panel_authorize(contest, current_user, db, view_as)
    jury_map = get_eligible_juries(contest)
    rebalance_pending_articles(db, contest, jury_map)

    target = view_as if (is_owner and view_as) else ("*" if is_owner else current_user.wiki_username)
    base_query = _jury_panel_base_query(db, contest)
    if target != "*":
        target_id = jury_map_username_to_id(jury_map).get(target, -1)
        base_query = base_query.filter(models.Article.assigned_to_id == target_id)

    total = base_query.count()
    status_counts = {
        status.value: count for status, count in
        base_query.with_entities(models.Article.status, func.count(models.Article.id))
        .group_by(models.Article.status).all()
    }
    status_counts = {s: status_counts.get(s, 0) for s in ("pending", "accepted", "rejected", "validation_failed")}

    page_query = base_query
    if after_id is not None:
        page_query = page_query.filter(models.Article.id > after_id)
    articles = page_query.order_by(models.Article.id.asc()).limit(page_size).all()

    return {
        "items": [serialize_jury_article(a, jury_map) for a in articles],
        "total": total,
        "page_size": page_size,
        "next_after_id": articles[-1].id if articles else None,
        "has_more": len(articles) == page_size,
        "status_counts": status_counts,
    }

@app.get("/api/jury-panel/contests/{code}/progress")
def get_jury_panel_progress(code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return assigned, judged, and remaining counts for this contest's jury members."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = _jury_panel_authorize(contest, current_user, db)
    jury_map = get_eligible_juries(contest)
    rebalance_pending_articles(db, contest, jury_map)

    visible_ids = set(jury_map.keys()) if is_owner else {current_user.id} & set(jury_map.keys())
    if not visible_ids:
        return []

    banned_ids = {b.user_id for b in contest.banned_users}
    filters = [models.Article.contest_id == contest.id, models.Article.assigned_to_id.in_(visible_ids)]
    if banned_ids:
        filters.append(~models.Article.submitter_id.in_(banned_ids))

    stats = {uid: {"assigned": 0, "judged": 0, "accepted": 0, "rejected": 0} for uid in visible_ids}
    for uid, status, count in db.query(
        models.Article.assigned_to_id, models.Article.status, func.count(models.Article.id)
    ).filter(*filters).group_by(models.Article.assigned_to_id, models.Article.status).all():
        stats[uid]["assigned"] += count
        if status == models.ArticleStatus.accepted:
            stats[uid]["judged"] += count
            stats[uid]["accepted"] += count
        elif status == models.ArticleStatus.rejected:
            stats[uid]["judged"] += count
            stats[uid]["rejected"] += count

    progress = []
    for uid, username in jury_map.items():
        if uid not in visible_ids:
            continue
        s = stats[uid]
        progress.append({
            "username": username,
            "assigned": s["assigned"],
            "judged": s["judged"],
            "remaining": max(0, s["assigned"] - s["judged"]),
            "accepted": s["accepted"],
            "rejected": s["rejected"],
            "progress_percent": round((s["judged"] / s["assigned"]) * 100) if s["assigned"] else 0,
        })
    return progress

class ClientErrorLog(BaseModel):
    message: str
    stack_trace: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    level: Optional[str] = "error"

SESSION_SECRET = os.getenv("SESSION_SECRET", "super-secret")

@app.post("/api/admin/force-migration")
def force_migration(_: models.User = Depends(get_owner_user)):
    try:
        from database import run_auto_migrations
        run_auto_migrations(engine)
        return {"status": "success", "message": "Migration forced successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@app.post("/api/logs/client-error")
def log_client_error(
    payload: ClientErrorLog,
    request: Request,
    db: Session = Depends(get_db)
):
    username = None
    token = request.cookies.get("auth_token")
    if token:
        try:
            payload_data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload_data.get("sub")
        except Exception:
            pass

    log_entry = models.SystemLog(
        level=payload.level or "error",
        source="frontend",
        message=payload.message[:2000],
        stack_trace=payload.stack_trace[:4000] if payload.stack_trace else None,
        url=payload.url[:500] if payload.url else None,
        user_agent=(payload.user_agent or request.headers.get("user-agent", ""))[:500],
        username=username,
        timestamp=utcnow()
    )
    db.add(log_entry)
    db.commit()
    return {"status": "ok"}

@app.get("/api/logs")
def get_global_logs(
    contest_code: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 200,
    _: models.User = Depends(get_owner_user),
    db: Session = Depends(get_db)
):
    """
    Returns global activity, error, and system runtime logs.
    Includes: frontend JS errors, backend 500 errors, and backup events (source=backup).
    Filter with ?source=backup to see only backup history.
    """
    logs = []
    sys_query = db.query(models.SystemLog)
    if source:
        sys_query = sys_query.filter(models.SystemLog.source == source)
    sys_logs = sys_query.order_by(models.SystemLog.timestamp.desc()).limit(limit).all()

    for s in sys_logs:
        logs.append({
            "type": "system",
            "id": s.id,
            "source": s.source,
            "level": s.level,
            "message": s.message,
            "stack_trace": s.stack_trace,
            "url": s.url,
            "user_agent": s.user_agent,
            "username": s.username or "Anonymous",
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "status": s.level,  # info | error | warning
        })
    if not (source and source in ("frontend", "backup")):
        art_query = db.query(models.Article).options(
            joinedload(models.Article.submitter),
            joinedload(models.Article.contest)
        )

        if contest_code:
            contest = db.query(models.Contest).filter_by(code=contest_code).first()
            if contest:
                art_query = art_query.filter(models.Article.contest_id == contest.id)
            else:
                art_query = None

        if art_query:
            if status:
                if status.lower() in ("error", "validation_failed"):
                    art_query = art_query.filter(models.Article.status == models.ArticleStatus.validation_failed)
                else:
                    try:
                        enum_status = models.ArticleStatus(status.lower())
                        art_query = art_query.filter(models.Article.status == enum_status)
                    except ValueError:
                        pass

            articles = art_query.order_by(models.Article.submitted_at.desc()).limit(limit).all()
            for a in articles:
                logs.append({
                    "type": "article_submission",
                    "id": a.id,
                    "title": a.title,
                    "contest_code": a.contest.code if a.contest else None,
                    "contest_name": a.contest.name if a.contest else None,
                    "submitted_by": a.submitter.wiki_username if a.submitter else "Unknown",
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                    "status": a.status.value,
                    "validation_error": a.validation_error,
                    "wiki_creator": a.wiki_creator,
                    "wiki_creation_date": a.wiki_creation_date.isoformat() if a.wiki_creation_date else None,
                    "timestamp": a.submitted_at.isoformat() if a.submitted_at else None
                })

    logs.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return logs[:limit]

@app.get("/api/contests/{code}/my-submissions")
def get_my_submissions(code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    articles = db.query(models.Article).filter_by(contest_id=contest.id, submitter_id=current_user.id).all()
    return [{
        "title": a.title,
        "status": a.status.value,
        "validation_error": a.validation_error,
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None
    } for a in articles]

@app.get("/api/contests/{code}/users/{username}")
def get_contest_user_profile(code: str, username: str, db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
        
    user = db.query(models.User).filter_by(wiki_username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    submissions = db.query(models.Article).filter_by(contest_id=contest.id, submitter_id=user.id).order_by(models.Article.submitted_at.desc()).all()

    submission_reviews = db.query(models.Review).join(models.Article)\
        .options(joinedload(models.Review.reviewer))\
        .filter(models.Article.contest_id == contest.id, models.Article.submitter_id == user.id)\
        .order_by(models.Review.timestamp.desc()).all()
    reviews_by_article = {}
    for review in submission_reviews:
        reviews_by_article.setdefault(review.article_id, []).append({
            "jury": review.reviewer.wiki_username if review.reviewer else "Unknown",
            "decision": review.status.value,
            "comment": review.comment,
            "reviewed_at": review.timestamp.isoformat() if review.timestamp else None
        })
    
    reviews = db.query(models.Review).join(models.Article)\
        .options(joinedload(models.Review.article))\
        .filter(
            models.Article.contest_id == contest.id,
            models.Review.reviewer_id == user.id
        ).order_by(models.Review.timestamp.desc()).all()
    
    return {
        "username": user.wiki_username,
        "role": user.role.value,
        "submissions": [
            {
                "id": s.id,
                "title": s.title,
                "status": s.status.value,
                "validation_error": s.validation_error,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "reviews": reviews_by_article.get(s.id, [])
            } for s in submissions
        ],
        "reviews": [
            {
                "article_title": r.article.title,
                "decision": r.status.value,
                "comment": r.comment,
                "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
            } for r in reviews
        ]
    }

@app.get("/api/contests/{code}/user-created-articles")
async def get_user_created_articles(code: str, username: str, db: Session = Depends(get_db)):
    """
    Lists every mainspace article `username` created within the contest's
    date range -- backs SubmitArticles.vue's "Fetch Articles" button. Tries
    the wiki replica DB first (the same source /submit-bulk validates
    against), falling back to the public usercontribs API only if the
    replica is unavailable, instead of the frontend paginating usercontribs
    directly from the browser.
    """
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    if not contest.start_date or not contest.end_date:
        raise HTTPException(status_code=400, detail="Contest has no date range configured")

    titles = query_wiki_replica_user_creations(username, contest.start_date, contest.end_date)
    if titles is not None:
        return {"titles": titles, "source": "db"}

    unique_id = uuid.uuid4().hex[:8]
    contact_email = os.getenv("CONTACT_EMAIL", "contact@example.com")
    user_agent_username = quote(str(username or ""), safe="")
    headers = {
        "User-Agent": f"WikiArticleContestTool/1.0 (User:{user_agent_username}; ContestCode:{contest.code}; {contact_email}; RequestID:{unique_id})",
        "Accept-Encoding": "gzip",
    }
    client = get_http_client()
    start_ts = contest.start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_ts = contest.end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    all_titles = []
    uccontinue = None
    try:
        while True:
            params = {
                "action": "query",
                "list": "usercontribs",
                "ucuser": username,
                "ucstart": start_ts,
                "ucend": end_ts,
                "ucdir": "newer",
                "ucnamespace": 0,
                "ucprop": "title",
                "ucshow": "new",
                "uclimit": "max",
                "format": "json",
            }
            if uccontinue:
                params["uccontinue"] = uccontinue
            response = await wiki_api_request(
                "GET", MEDIAWIKI_API_URL, client=client, params=params, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            all_titles.extend(c["title"] for c in data.get("query", {}).get("usercontribs", []))
            uccontinue = data.get("continue", {}).get("uccontinue")
            if not uccontinue:
                break
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch articles from Wikipedia: {e}")

    return {"titles": list(dict.fromkeys(all_titles)), "source": "api"}

@app.get("/api/users/{username}/profile")
def get_user_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(wiki_username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    participated = {}
    articles = db.query(models.Article).options(joinedload(models.Article.contest))\
        .filter_by(submitter_id=user.id).order_by(models.Article.submitted_at.desc()).all()
    for a in articles:
        c = a.contest
        if c.id not in participated:
            participated[c.id] = {
                "code": c.code,
                "name": c.name,
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "articles": []
            }
        participated[c.id]["articles"].append({
            "id": a.id,
            "title": a.title,
            "status": a.status.value,
            "validation_error": a.validation_error,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "wiki_creator": a.wiki_creator,
            "wiki_creation_date": a.wiki_creation_date.isoformat() if a.wiki_creation_date else None
        })

    def build_judged_entry(contest, role):
        reviews = db.query(models.Review).join(models.Article)\
            .options(joinedload(models.Review.article))\
            .filter(
                models.Article.contest_id == contest.id,
                models.Review.reviewer_id == user.id
            ).order_by(models.Review.timestamp.desc()).all()
        counts = {"accepted": 0, "rejected": 0, "skipped": 0}
        for r in reviews:
            if r.status.value in counts:
                counts[r.status.value] += 1
        return {
            "code": contest.code,
            "name": contest.name,
            "start_date": contest.start_date.isoformat() if contest.start_date else None,
            "end_date": contest.end_date.isoformat() if contest.end_date else None,
            "role_in_contest": role,
            "reviews": [
                {
                    "article_title": r.article.title,
                    "decision": r.status.value,
                    "comment": r.comment,
                    "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
                } for r in reviews
            ],
            "stats": {"total": len(reviews), **counts},
        }

    judged = []
    # Keyed by contest id so the owner pass below can relabel an existing entry
    # with a dict lookup. It used to scan `judged` and run a fresh
    # `Contest.filter_by(id=...).first().code` query for every candidate row --
    # a query per (contest x entry) pair, which also raised AttributeError and
    # returned a 500 whenever that contest row had since been deleted.
    judged_by_contest_id = {}
    jury_assignments = db.query(models.ContestJury)\
        .options(joinedload(models.ContestJury.contest))\
        .filter_by(user_id=user.id).all()
    for ja in jury_assignments:
        entry = build_judged_entry(ja.contest, "jury")
        judged.append(entry)
        judged_by_contest_id[ja.contest.id] = entry

    if user.role == models.RoleEnum.owner:
        # One DISTINCT query for the contest ids, instead of loading every
        # review the owner has ever written just to read contest_id off each.
        owner_contest_ids = {
            cid for (cid,) in db.query(models.Article.contest_id)
            .join(models.Review, models.Review.article_id == models.Article.id)
            .filter(models.Review.reviewer_id == user.id)
            .distinct()
        }
        new_ids = owner_contest_ids - judged_by_contest_id.keys()
        for contest_id in owner_contest_ids & judged_by_contest_id.keys():
            judged_by_contest_id[contest_id]["role_in_contest"] = "owner"
        if new_ids:
            # Batch-fetch the remaining contests rather than one query each.
            for c in db.query(models.Contest).filter(models.Contest.id.in_(new_ids)).all():
                entry = build_judged_entry(c, "owner")
                judged.append(entry)
                judged_by_contest_id[c.id] = entry

    return {
        "username": user.wiki_username,
        "role": user.role.value,
        "participated_contests": list(participated.values()),
        "judged_contests": judged
    }

# Deleting one article at a time cost three round-trips per row (its reviews,
# its locks, then the row itself), so a few hundred selected articles turned
# into a couple of thousand statements inside a single transaction -- slow
# enough on Toolforge's MariaDB to risk tripping the ingress timeout partway
# through and leaving the batch half-applied. Set-based deletes make it three
# statements per chunk no matter how large the batch is.
_DELETE_CHUNK = 500

def _article_child_columns():
    """Every column in the schema with a foreign key onto articles.id.

    Derived from the metadata rather than hand-listed. A hand-listed version
    (reviews + article_locks) silently went stale when talk_page_jobs was
    added, and deleting articles then failed on MariaDB with
    "Cannot delete or update a parent row" -- SQLite doesn't enforce foreign
    keys unless PRAGMA foreign_keys is on, so it passed locally and only
    broke in production. Deriving it means a new child table is covered the
    day it's added.
    """
    columns = []
    for table in models.Base.metadata.sorted_tables:
        if table.name == models.Article.__tablename__:
            continue
        for column in table.columns:
            if any(fk.column is models.Article.__table__.c.id for fk in column.foreign_keys):
                columns.append(column)
    return columns

_ARTICLE_CHILD_COLUMNS = _article_child_columns()

def _delete_articles(articles, current_user, db):
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found")
    # Everything the audit log needs has to be read *before* the rows go away:
    # once they're deleted, lazy-loading article.contest is unreliable.
    article_ids = [article.id for article in articles]
    contest = articles[0].contest
    contest_code = contest.code if contest else "unknown"

    # Resolve submitter names and review counts in two queries rather than two
    # per article -- this runs on batches of up to 500.
    submitter_ids = {article.submitter_id for article in articles if article.submitter_id}
    submitter_names = {}
    if submitter_ids:
        submitter_names = {
            user_id: username
            for user_id, username in db.query(models.User.id, models.User.wiki_username)
                                       .filter(models.User.id.in_(submitter_ids)).all()
        }
    review_counts = {}
    for start in range(0, len(article_ids), _DELETE_CHUNK):
        chunk = article_ids[start:start + _DELETE_CHUNK]
        for article_id, count in db.query(models.Review.article_id, func.count(models.Review.id)) \
                                   .filter(models.Review.article_id.in_(chunk)) \
                                   .group_by(models.Review.article_id).all():
            review_counts[article_id] = count

    deleted_at = datetime.utcnow()
    db.bulk_save_objects([
        models.DeletedArticleLog(
            article_id=article.id,
            contest_id=article.contest_id,
            contest_code=contest_code,
            title=article.title,
            submitted_by=submitter_names.get(article.submitter_id),
            wiki_creator=article.wiki_creator,
            wiki_creation_date=article.wiki_creation_date,
            submitted_at=article.submitted_at,
            status=article.status.value if hasattr(article.status, "value") else article.status,
            validation_error=article.validation_error,
            review_count=review_counts.get(article.id, 0),
            deleted_by=current_user.wiki_username,
            deleted_at=deleted_at,
        )
        for article in articles
    ])

    for start in range(0, len(article_ids), _DELETE_CHUNK):
        chunk = article_ids[start:start + _DELETE_CHUNK]
        # Children first, or MariaDB rejects the parent delete outright.
        for column in _ARTICLE_CHILD_COLUMNS:
            db.execute(column.table.delete().where(column.in_(chunk)))
        db.query(models.Article).filter(models.Article.id.in_(chunk)).delete(synchronize_session=False)
    # synchronize_session=False leaves these instances in the identity map as
    # live rows, so expire-on-commit would try to refresh them from rows that
    # no longer exist (ObjectDeletedError) the moment anything touched them
    # again. Detach them instead; callers use the returned ids, not the objects.
    for article in articles:
        db.expunge(article)
    db.add(models.SystemLog(
        level="info",
        source="backend",
        message=f"User {current_user.wiki_username} removed {len(article_ids)} article(s) from contest '{contest_code}'.",
        username=current_user.wiki_username
    ))
    db.commit()
    return {"status": "deleted", "deleted_count": len(article_ids), "deleted_ids": article_ids}

@app.get("/api/contests/{code}/deleted-articles")
def get_deleted_articles(
    code: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    q: Optional[str] = Query(default=None, max_length=255),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The deletion audit trail for one contest, newest first.

    Jury/owner only: it lists titles that were removed from the contest, which
    is moderation history rather than public standings.
    """
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to view deletions for this contest")

    query = db.query(models.DeletedArticleLog).filter_by(contest_id=contest.id)
    if q and q.strip():
        query = query.filter(models.DeletedArticleLog.title.like(f"%{q.strip()}%"))
    total = query.count()
    rows = query.order_by(models.DeletedArticleLog.deleted_at.desc(), models.DeletedArticleLog.id.desc()) \
                .offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "article_id": row.article_id,
                "title": row.title,
                "submitted_by": row.submitted_by,
                "wiki_creator": row.wiki_creator,
                "wiki_creation_date": row.wiki_creation_date,
                "submitted_at": row.submitted_at,
                "status": row.status,
                "validation_error": row.validation_error,
                "review_count": row.review_count,
                "deleted_by": row.deleted_by,
                "deleted_at": row.deleted_at,
            }
            for row in rows
        ],
    }

@app.delete("/api/articles/{article_id}")

def delete_article(article_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=article.contest_id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to delete articles in this contest")
    try:
        result = _delete_articles([article], current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return result

@app.post("/api/articles/{article_id}/lock")
def lock_article(article_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    own_review = db.query(models.Review).filter_by(
        article_id=article_id, reviewer_id=current_user.id
    ).order_by(models.Review.timestamp.desc()).first()
    if article.status != models.ArticleStatus.pending and not own_review:
        raise HTTPException(status_code=409, detail="Article has already been permanently reviewed.")
        
    contest = article.contest
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to lock articles in this contest")
    existing_lock = db.query(models.ArticleLock).filter_by(article_id=article_id).first()
    if existing_lock and existing_lock.locked_at >= utcnow() - timedelta(minutes=15) \
            and existing_lock.locked_by != current_user.wiki_username:
        raise HTTPException(status_code=409, detail=f"Article is locked by {existing_lock.locked_by}.")
    if existing_lock:
        db.delete(existing_lock)
    db.add(models.ArticleLock(
        article_id=article_id,
        locked_by=current_user.wiki_username,
        locked_at=utcnow()
    ))
    db.query(models.ArticleLock).filter(
        models.ArticleLock.locked_at < utcnow() - timedelta(minutes=15)
    ).delete()
    db.commit()
    return {"success": True, "locked_by": current_user.wiki_username}

@app.delete("/api/articles/{article_id}/lock")
def unlock_article(article_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Release the current user's temporary review lock when they leave an article."""
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    contest = article.contest
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(
        contest_id=contest.id, user_id=current_user.id
    ).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to unlock articles in this contest")

    lock = db.query(models.ArticleLock).filter_by(article_id=article_id).first()
    if lock and lock.locked_by == current_user.wiki_username:
        db.delete(lock)
        db.commit()
    return {"success": True}

@app.get("/api/proxy/article/{title}")
async def proxy_article(title: str):
    unique_id = uuid.uuid4().hex[:8]
    headers = {
        "User-Agent": f"QuoteContestArticleTool/1.0 (contact@example.com; RequestID:{unique_id})"
    }
    client = get_http_client()
    res = await wiki_api_request(
        "GET",
        f"https://bn.wiktionary.org/api/rest_v1/page/mobile-html/{title}",
        client=client,
        headers=headers,
    )
    html = res.text
    html = html.replace("<head>", f'<head><base href="https://bn.wiktionary.org/wiki/">')
    return HTMLResponse(content=html, status_code=res.status_code)

class ReviewRequest(BaseModel):
    decision: str  # "accepted", "rejected", "skipped"
    comment: Optional[str] = None

class BulkReviewRequest(BaseModel):
    article_ids: List[int]
    decision: str
    comment: Optional[str] = None

class BulkDeleteRequest(BaseModel):
    article_ids: List[int]

# Both bulk endpoints used to silently slice the incoming list to the first
# 500 ids. Anything past that was dropped without landing in `succeeded` or
# `failed`, so the caller got a 200 that looked like a clean sweep while most
# of the batch was never touched -- selecting a 814-article submitter and
# hitting delete removed 500 and reported success. Reject an oversized batch
# outright instead; the frontend chunks below this limit.
MAX_BULK_ARTICLE_IDS = 500

def _dedupe_bulk_ids(article_ids):
    unique_ids = list(dict.fromkeys(article_ids))
    if len(unique_ids) > MAX_BULK_ARTICLE_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many articles in one request ({len(unique_ids)}). Send at most {MAX_BULK_ARTICLE_IDS} per batch."
        )
    return unique_ids

@app.post("/api/articles/bulk-review")
def bulk_review_articles(data: BulkReviewRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.decision not in ("accepted", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    succeeded, failed = [], []
    for article_id in _dedupe_bulk_ids(data.article_ids):
        try:
            review_article(article_id, ReviewRequest(decision=data.decision, comment=data.comment), current_user, db)
            succeeded.append(article_id)
        except HTTPException as error:
            failed.append({"article_id": article_id, "detail": error.detail})
    return {"succeeded": succeeded, "failed": failed}

@app.post("/api/articles/bulk-delete")
def bulk_delete_articles(data: BulkDeleteRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    article_ids = _dedupe_bulk_ids(data.article_ids)
    succeeded, failed = [], []
    # One query for the whole batch rather than a SELECT per id -- the old
    # per-id loop cost ~1.9s server-side for 500 ids before a single row was
    # even deleted.
    found = {
        article.id: article
        for article in db.query(models.Article).filter(models.Article.id.in_(article_ids)).all()
    } if article_ids else {}
    is_owner = current_user.role == models.RoleEnum.owner
    jury_contest_ids = set()
    if not is_owner:
        jury_contest_ids = {
            row.contest_id
            for row in db.query(models.ContestJury).filter_by(user_id=current_user.id).all()
        }
    candidates = []
    for article_id in article_ids:
        article = found.get(article_id)
        if not article:
            failed.append({"article_id": article_id, "detail": "Article not found"})
            continue
        if not (is_owner or article.contest_id in jury_contest_ids):
            failed.append({"article_id": article_id, "detail": "Not authorized to delete articles in this contest"})
            continue
        candidates.append(article)
    if candidates:
        # Capture the ids up front: _delete_articles detaches the instances, so
        # reading article.id off them afterwards is not safe.
        candidate_ids = [article.id for article in candidates]
        try:
            _delete_articles(candidates, current_user, db)
            succeeded = candidate_ids
        except HTTPException as error:
            db.rollback()
            failed.extend({"article_id": article_id, "detail": error.detail} for article_id in candidate_ids)
        except Exception as error:
            db.rollback()
            failed.extend({"article_id": article_id, "detail": str(error)} for article_id in candidate_ids)
    return {"succeeded": succeeded, "failed": failed, "deleted_count": len(succeeded)}

@app.post("/api/articles/{article_id}/review")
def review_article(
    article_id: int,
    data: ReviewRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    contest = article.contest
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized")

    if is_jury and not is_owner and not contest.allow_self_review and article.submitter_id == current_user.id:
        raise HTTPException(status_code=403, detail="Jury members cannot review their own articles.")
    if is_jury and not is_owner and db.query(models.ContestJuryRestriction).filter_by(
        contest_id=contest.id, jury_user_id=current_user.id, submitter_user_id=article.submitter_id
    ).first():
        raise HTTPException(status_code=403, detail="This article is restricted for you due to a conflict of interest.")

    own_review = db.query(models.Review).filter_by(
        article_id=article_id, reviewer_id=current_user.id
    ).order_by(models.Review.timestamp.desc()).first()
    if article.status != models.ArticleStatus.pending and not own_review:
        raise HTTPException(status_code=409, detail="Article has already been permanently reviewed.")

    active_lock = db.query(models.ArticleLock).filter_by(article_id=article_id).first()
    if active_lock and active_lock.locked_at < utcnow() - timedelta(minutes=15):
        db.delete(active_lock)
        db.commit()
        active_lock = None
    if active_lock and active_lock.locked_by != current_user.wiki_username:
        raise HTTPException(status_code=409, detail=f"Article is locked by {active_lock.locked_by}.")

    if data.decision not in ("accepted", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    if data.decision in ("accepted", "rejected"):
        article.status = models.ArticleStatus[data.decision]
        # The reviewer owns the article's jury-queue slot after judging it.
        if current_user.id in {j.user_id for j in contest.juries}:
            article.assigned_to_id = current_user.id
    elif own_review:
        article.status = models.ArticleStatus.pending

    if own_review:
        own_review.status = models.ReviewStatus[data.decision]
        own_review.comment = data.comment
        own_review.timestamp = utcnow()
    else:
        db.add(models.Review(
            article_id=article.id,
            reviewer_id=current_user.id,
            status=models.ReviewStatus[data.decision],
            comment=data.comment
        ))
    if data.decision == "skipped" and active_lock and active_lock.locked_by == current_user.wiki_username:
        db.delete(active_lock)
    db.commit()
    return {"status": "success", "decision": data.decision}

@app.post("/api/articles/{article_id}/review/undo")
def undo_review(
    article_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Withdraw the caller's own review of an article, restoring the status it
    would have had without it.

    This grants no authority a reviewer didn't already have -- review_article()
    already lets them overwrite their own decision with any other value at any
    time -- it just expresses "remove it" instead of "change it", which the UI
    previously had no way to say. A misclicked Accept could only be corrected
    by navigating back and re-reviewing.

    `assigned_to_id` is deliberately left alone, matching what a 'skipped'
    decision already does: the article returns to this jury's own queue for
    them to decide again, rather than being thrown back into the pool for
    rebalancing.
    """
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    contest = article.contest
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized")

    own_review = db.query(models.Review).filter_by(
        article_id=article_id, reviewer_id=current_user.id
    ).order_by(models.Review.timestamp.desc()).first()
    if not own_review:
        raise HTTPException(status_code=404, detail="You have no review of this article to undo.")

    # A validation_failed article never legitimately carries a decision, so
    # never resurrect one into the pending queue by undoing something else.
    if article.status == models.ArticleStatus.validation_failed:
        raise HTTPException(status_code=409, detail="This article failed validation and cannot be reopened here.")

    # Read before deleting: after the commit below this instance is gone and
    # its attributes can no longer be loaded.
    undone_decision = own_review.status.value
    db.delete(own_review)
    db.flush()

    # Another jury (or the owner) may also have judged this article. Fall back
    # to whatever the most recent remaining decision was, and only return the
    # article to pending when nothing is left.
    remaining = db.query(models.Review).filter(
        models.Review.article_id == article_id,
        models.Review.status != models.ReviewStatus.skipped,
    ).order_by(models.Review.timestamp.desc(), models.Review.id.desc()).first()
    article.status = models.ArticleStatus[remaining.status.value] if remaining else models.ArticleStatus.pending

    db.commit()
    return {
        "status": "success",
        "undone_decision": undone_decision,
        "restored_status": article.status.value,
    }

INTEGRITY_ISSUE_LIMIT = 2000


@app.post("/api/admin/contests/{code}/integrity-check")
def contest_integrity_check(
    code: str,
    scope: str = Query(default="accepted", pattern="^(accepted|all)$"),
    _: models.User = Depends(get_owner_user),
    db: Session = Depends(get_db),
):
    """Re-check submitted articles against the wiki as it stands today.

    Articles are validated once, at submission, and never revisited. If a page
    is later deleted, moved out of mainspace, turned into a redirect, or
    blanked below the contest's size rule, nothing notices -- an article that
    no longer exists can still be sitting in the accepted column when results
    are published. This re-runs the existence/shape checks over a contest's
    articles and reports what no longer holds.

    Reporting only: no article status is changed. Deciding what to do about a
    flagged article is a judgement call (a page may have been legitimately
    moved, or deleted for reasons unrelated to the contest), so this hands the
    owner a list rather than silently rejecting anyone's work.

    Uses the wiki replica exclusively. The public API fallback that
    /submit-bulk falls back to fetches one title per request, which is fine for
    a submission of a few dozen titles and hopeless for a sweep over thousands
    -- so when the replica is unavailable this reports that plainly instead of
    grinding through an HTTP crawl or, worse, reporting every article as
    missing.
    """
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    query = db.query(models.Article).options(joinedload(models.Article.submitter)) \
        .filter(models.Article.contest_id == contest.id)
    if scope == "accepted":
        query = query.filter(models.Article.status == models.ArticleStatus.accepted)
    else:
        # validation_failed articles never passed the rules in the first place,
        # so re-reporting them here would just be noise.
        query = query.filter(models.Article.status != models.ArticleStatus.validation_failed)
    articles = query.order_by(models.Article.id).all()

    if not articles:
        return {
            "contest": {"code": contest.code, "name": contest.name},
            "scope": scope,
            "checked": 0,
            "checked_at": utcnow().isoformat(),
            "rules": {"min_bytes": getattr(contest, "min_bytes", 0) or 0},
            "summary": {"ok": 0, "missing": 0, "redirect": 0, "below_min_bytes": 0, "creator_changed": 0},
            "issues": [],
            "truncated": False,
        }

    min_bytes = getattr(contest, "min_bytes", 0) or 0
    summary = {"ok": 0, "missing": 0, "redirect": 0, "below_min_bytes": 0, "creator_changed": 0}
    issues = []

    # query_wiki_replica_batch already chunks internally, but feeding it every
    # title in one call would hold the whole contest's page rows in memory at
    # once; this keeps the working set bounded on a 10k+ contest.
    BATCH = 500
    for start in range(0, len(articles), BATCH):
        batch = articles[start:start + BATCH]
        found = query_wiki_replica_batch([a.title for a in batch])
        if found is None:
            raise HTTPException(
                status_code=503,
                detail="Wiki replica is unavailable, so the integrity check cannot run right now. Try again shortly.",
            )

        for article in batch:
            info = found.get(article.title.lower())
            issue = None
            detail = None

            if not info:
                # The replica lookup is scoped to namespace 0, so a page that
                # was moved out of mainspace is indistinguishable here from one
                # that was deleted -- say so rather than asserting "deleted".
                issue, detail = "missing", "No mainspace page with this title (deleted, moved, or renamed)"
            elif info.get("page_is_redirect"):
                issue, detail = "redirect", "Page is now a redirect"
            elif min_bytes and info.get("page_len", 0) < min_bytes:
                issue = "below_min_bytes"
                detail = f"Now {info.get('page_len', 0)} B, contest requires at least {min_bytes} B"
            elif article.wiki_creator and info.get("wiki_creator") and \
                    _normalize_wiki_name(info["wiki_creator"]) != _normalize_wiki_name(article.wiki_creator):
                issue = "creator_changed"
                detail = f"First revision is now by '{info['wiki_creator']}', was '{article.wiki_creator}'"

            if issue is None:
                summary["ok"] += 1
                continue

            summary[issue] += 1
            if len(issues) < INTEGRITY_ISSUE_LIMIT:
                issues.append({
                    "article_id": article.id,
                    "title": article.title,
                    "submitted_by": article.submitter.wiki_username if article.submitter else None,
                    "status": article.status.value,
                    "issue": issue,
                    "detail": detail,
                })

    flagged = len(articles) - summary["ok"]
    message = (
        f"Integrity check on contest {contest.code} ({scope}): {len(articles)} articles checked, "
        f"{flagged} flagged (missing={summary['missing']}, redirect={summary['redirect']}, "
        f"below_min_bytes={summary['below_min_bytes']}, creator_changed={summary['creator_changed']})"
    )
    print(f"[IntegrityCheck] {message}")
    try:
        db.add(models.SystemLog(
            level="warning" if flagged else "info",
            source="integrity_check",
            message=message[:2000],
            timestamp=utcnow(),
        ))
        db.commit()
    except Exception as error:
        db.rollback()
        print(f"[IntegrityCheck] Failed writing SystemLog: {error}")

    return {
        "contest": {"code": contest.code, "name": contest.name},
        "scope": scope,
        "checked": len(articles),
        "checked_at": utcnow().isoformat(),
        "rules": {"min_bytes": min_bytes},
        "summary": summary,
        "issues": issues,
        "truncated": flagged > len(issues),
    }


@app.get("/api/admin/contests/{code}/export/csv")
def export_contest_csv(code: str, mode: str = "summary", _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
        
    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).order_by(models.Article.submitted_at.desc()).all()
    
    def translate_status(s):
        if s == "accepted": return "গৃহীত"
        if s == "rejected": return "প্রত্যাখ্যাত"
        if s == "pending": return "অপেক্ষমাণ"
        if s == "validation_failed": return "যাচাইকরণ ব্যর্থ"
        return s

    output = io.StringIO()
    writer = csv.writer(output)
    
    if mode == "detailed":
        writer.writerow([
            "Article ID", "Title", "Submitter", "Status", "Validation Error",
            "Wiki Creator", "Wiki Creation Date", "Submitted At", "Reviews Count", "Last Review Decision", "Last Reviewer", "Last Review Comment"
        ])
        for a in articles:
            reviews = sorted(a.reviews, key=lambda r: r.timestamp or datetime.min)
            last_rev = reviews[-1] if reviews else None
            writer.writerow([
                a.id, a.title, a.submitter.wiki_username if a.submitter else "",
                translate_status(a.status.value), a.validation_error or "",
                a.wiki_creator or "", a.wiki_creation_date.isoformat() if a.wiki_creation_date else "",
                a.submitted_at.isoformat() if a.submitted_at else "", len(reviews),
                translate_status(last_rev.status.value) if last_rev else "",
                last_rev.reviewer.wiki_username if last_rev and last_rev.reviewer else "",
                last_rev.comment or "" if last_rev else ""
            ])
    else:
        submitters = {}
        juries = {}
        
        for a in articles:
            if a.submitter:
                u = a.submitter.wiki_username
                if u not in submitters:
                    submitters[u] = {"accepted": 0, "rejected": 0, "total": 0}
                submitters[u]["total"] += 1
                if a.status.value == "accepted": submitters[u]["accepted"] += 1
                elif a.status.value == "rejected": submitters[u]["rejected"] += 1
                
            for r in a.reviews:
                if r.reviewer:
                    j = r.reviewer.wiki_username
                    if j not in juries:
                        juries[j] = {"accepted": 0, "rejected": 0, "total": 0}
                    juries[j]["total"] += 1
                    if r.status.value == "accepted": juries[j]["accepted"] += 1
                    elif r.status.value == "rejected": juries[j]["rejected"] += 1
                    
        writer.writerow(["ব্যবহারকারী (Submitter)", "মোট জমা (Total)", "গৃহীত (Accepted)", "প্রত্যাখ্যাত (Rejected)"])
        for u, stats in submitters.items():
            writer.writerow([u, stats["total"], stats["accepted"], stats["rejected"]])
            
        writer.writerow([])
        writer.writerow(["বিচারক (Jury)", "মোট পর্যালোচনা (Total)", "গৃহীত (Accepted)", "প্রত্যাখ্যাত (Rejected)"])
        for j, stats in juries.items():
            writer.writerow([j, stats["total"], stats["accepted"], stats["rejected"]])
        
    output.seek(0)
    filename = f"contest_{code}_export.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/admin/contests/{code}/export/json")
def export_contest_json(code: str, mode: str = "summary", _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
        
    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).order_by(models.Article.submitted_at.desc()).all()
    
    def translate_status(s):
        if s == "accepted": return "গৃহীত"
        if s == "rejected": return "প্রত্যাখ্যাত"
        if s == "pending": return "অপেক্ষমাণ"
        if s == "validation_failed": return "যাচাইকরণ ব্যর্থ"
        return s

    if mode == "detailed":
        return {
            "contest_name": contest.name,
            "contest_code": contest.code,
            "exported_at": utcnow().isoformat(),
            "articles": [
                {
                    "id": a.id, "title": a.title, "submitter": a.submitter.wiki_username if a.submitter else None,
                    "status": translate_status(a.status.value), "validation_error": a.validation_error,
                    "wiki_creator": a.wiki_creator, "wiki_creation_date": a.wiki_creation_date.isoformat() if a.wiki_creation_date else None,
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                    "reviews": [
                        {
                            "reviewer": r.reviewer.wiki_username if r.reviewer else None,
                            "decision": translate_status(r.status.value),
                            "comment": r.comment,
                            "timestamp": r.timestamp.isoformat() if r.timestamp else None
                        } for r in a.reviews
                    ]
                } for a in articles
            ]
        }
    else:
        submitters = {}
        juries = {}
        
        for a in articles:
            if a.submitter:
                u = a.submitter.wiki_username
                if u not in submitters:
                    submitters[u] = {"accepted": 0, "rejected": 0, "total": 0}
                submitters[u]["total"] += 1
                if a.status.value == "accepted": submitters[u]["accepted"] += 1
                elif a.status.value == "rejected": submitters[u]["rejected"] += 1
                
            for r in a.reviews:
                if r.reviewer:
                    j = r.reviewer.wiki_username
                    if j not in juries:
                        juries[j] = {"accepted": 0, "rejected": 0, "total": 0}
                    juries[j]["total"] += 1
                    if r.status.value == "accepted": juries[j]["accepted"] += 1
                    elif r.status.value == "rejected": juries[j]["rejected"] += 1

        return {
            "contest_name": contest.name,
            "contest_code": contest.code,
            "exported_at": utcnow().isoformat(),
            "submitter_stats": [
                {"username": u, **stats} for u, stats in submitters.items()
            ],
            "jury_stats": [
                {"username": j, **stats} for j, stats in juries.items()
            ]
        }

@app.get("/api/admin/contests/{code}/export/wikitable")
def export_contest_wikitable(code: str, mode: str = "summary", _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
        
    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).order_by(models.Article.submitted_at.desc()).all()

    def translate_status(s):
        if s == "accepted": return "গৃহীত"
        if s == "rejected": return "প্রত্যাখ্যাত"
        if s == "pending": return "অপেক্ষমাণ"
        if s == "validation_failed": return "যাচাইকরণ ব্যর্থ"
        return s

    lines = []
    
    if mode == "detailed":
        lines.append('{| class="wikitable sortable"')
        lines.append('|+ প্রতিযোগিতার ফলাফল: ' + contest.name)
        lines.append('|-')
        lines.append('! নিবন্ধের নাম !! জমাদানকারী !! অবস্থা !! পর্যালোচনাকারী !! মন্তব্য')
        
        for a in articles:
            reviews = sorted(a.reviews, key=lambda r: r.timestamp or datetime.min)
            last_rev = reviews[-1] if reviews else None
            status_bn = translate_status(a.status.value)
            reviewer = last_rev.reviewer.wiki_username if last_rev and last_rev.reviewer else ""
            comment = last_rev.comment or "" if last_rev else ""
            
            lines.append('|-')
            lines.append(f'| [[{a.title}]] || {a.submitter.wiki_username if a.submitter else ""} || {status_bn} || {reviewer} || {comment}')
        
        lines.append('|}')
    else:
        submitters = {}
        juries = {}
        
        for a in articles:
            if a.submitter:
                u = a.submitter.wiki_username
                if u not in submitters:
                    submitters[u] = {"accepted": 0, "rejected": 0, "total": 0}
                submitters[u]["total"] += 1
                if a.status.value == "accepted": submitters[u]["accepted"] += 1
                elif a.status.value == "rejected": submitters[u]["rejected"] += 1
                
            for r in a.reviews:
                if r.reviewer:
                    j = r.reviewer.wiki_username
                    if j not in juries:
                        juries[j] = {"accepted": 0, "rejected": 0, "total": 0}
                    juries[j]["total"] += 1
                    if r.status.value == "accepted": juries[j]["accepted"] += 1
                    elif r.status.value == "rejected": juries[j]["rejected"] += 1
        lines.append('{| class="wikitable sortable"')
        lines.append('|+ জমাদানকারীর পরিসংখ্যান: ' + contest.name)
        lines.append('|-')
        lines.append('! ব্যবহারকারী !! মোট জমা !! গৃহীত !! প্রত্যাখ্যাত')
        
        for u, stats in submitters.items():
            lines.append('|-')
            lines.append(f'| [[ব্যবহারকারী:{u}|{u}]] || {stats["total"]} || {stats["accepted"]} || {stats["rejected"]}')
        lines.append('|}')
        lines.append('')
        lines.append('{| class="wikitable sortable"')
        lines.append('|+ বিচারকের পরিসংখ্যান: ' + contest.name)
        lines.append('|-')
        lines.append('! বিচারক !! মোট পর্যালোচনা !! গৃহীত !! প্রত্যাখ্যাত')
        
        for j, stats in juries.items():
            lines.append('|-')
            lines.append(f'| [[ব্যবহারকারী:{j}|{j}]] || {stats["total"]} || {stats["accepted"]} || {stats["rejected"]}')
        lines.append('|}')
        
    output = "\n".join(lines)
    filename = f"contest_{code}_export.txt"
    return StreamingResponse(
        io.BytesIO(output.encode('utf-8')),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend-vue" / "dist"
dist_dir = str(DIST_DIR)
assets_dir = DIST_DIR / "assets"

# Vite content-hashes every filename under assets/ (index-DKPP1s0_.js), so a
# given URL's bytes are immutable by construction and the browser never needs
# to revalidate. Without this the app only sent ETag/Last-Modified, costing a
# conditional request per asset on every single page load.
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
# Files served from dist/ root (favicon, robots.txt, ...) aren't hashed, so
# they get a short TTL instead of an immutable one.
UNHASHED_CACHE_CONTROL = "public, max-age=3600"


class HashedStaticFiles(StaticFiles):
    """StaticFiles that marks its content-hashed responses immutable."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = IMMUTABLE_CACHE_CONTROL
        return response


def _static_cache_headers(path: Path) -> dict:
    if path.parent == assets_dir:
        return {"Cache-Control": IMMUTABLE_CACHE_CONTROL}
    return {"Cache-Control": UNHASHED_CACHE_CONTROL}


if assets_dir.is_dir():
    # Starlette's StaticFiles already refuses to escape its own directory, so
    # /assets/* is safe on its own; the catch-all below is the one that needed
    # a containment check.
    app.mount("/assets", HashedStaticFiles(directory=str(assets_dir)), name="assets")


def _safe_dist_file(path_name: str):
    """Resolve `path_name` inside the built SPA directory, or None if it escapes.

    `{path_name:path}` receives the URL path *after* percent-decoding, so a
    request for "/..%2f..%2fbackend%2f.env" arrived here as the literal
    "../../backend/.env" and os.path.join() happily walked out of dist/ and
    served backend/.env -- OAuth client secret, SESSION_SECRET (which JWT_SECRET
    is derived from) and the replica DB credentials, to any unauthenticated
    caller. Resolving the candidate and requiring it to stay under DIST_DIR
    closes that; symlinks are resolved first so a link inside dist/ can't be
    used to hop out either.
    """
    if not path_name:
        return None
    try:
        candidate = (DIST_DIR / path_name).resolve()
        candidate.relative_to(DIST_DIR)
    except (ValueError, OSError):
        return None
    return candidate if candidate.is_file() else None


@app.get("/{path_name:path}")
async def serve_spa(path_name: str):
    if path_name.startswith("api") or path_name.startswith("auth"):
        raise HTTPException(status_code=404, detail="Not found")

    static_file = _safe_dist_file(path_name)
    if static_file is not None:
        return FileResponse(static_file, headers=_static_cache_headers(static_file))

    index_path = DIST_DIR / "index.html"
    if index_path.is_file():
        # index.html names the content-hashed bundles, so it must never be
        # cached -- otherwise a deploy leaves browsers asking for asset files
        # that no longer exist.
        return FileResponse(index_path, headers={"Cache-Control": "no-cache, must-revalidate"})

    return HTMLResponse("<h1>Frontend not built. Run: cd frontend-vue && npm run build</h1>", status_code=503)
