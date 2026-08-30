"""Background drain for the `talk_page_jobs` queue.

Talk-page templates used to be written by a FastAPI BackgroundTask that
looped over an entire bulk submission back to back. Two things broke: a large
submission ran straight into MediaWiki's edit rate limit, and a restart
mid-batch dropped every edit that had not run yet with no record they were
owed. `submit_bulk` now only enqueues rows; this module drains them one at a
time, globally -- MediaWiki's throttling sees this tool's *total* edit rate,
so the delay deliberately applies across all contests and users rather than
per contest.

The tick is an APScheduler interval job rather than a hand-rolled
`while True: await asyncio.sleep(...)`, so start/stop is tied to FastAPI's
lifespan and a slow tick cannot overlap the next one (`max_instances=1`).
"""

import os
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import update

import models
from database import SessionLocal
from timeutils import utcnow

# Seconds between two edits, globally. Slow enough to stay well inside the
# per-user edit rate limit on bn.wiktionary while still draining a few hundred
# submitted titles within the hour.
TALK_QUEUE_INTERVAL_SECONDS = 3.0

# When there is nothing to do, check back less often than the edit interval
# instead of hammering the database every tick.
TALK_QUEUE_IDLE_INTERVAL_SECONDS = 5.0

# A maxlag/read-only/rate-limit refusal is the wiki asking for room. Back off
# globally, growing on repeats, and do not spend one of the job's attempts on
# it -- nothing about the job itself was wrong.
TALK_QUEUE_BACKOFF_SECONDS = 30.0
TALK_QUEUE_MAX_BACKOFF_SECONDS = 300.0

# How many *hard* failures a single job gets before it is parked as `failed`
# for an admin to look at (and retry via the admin endpoint).
TALK_QUEUE_MAX_ATTEMPTS = 3

WORKER_ENABLED = os.getenv("TALK_QUEUE_WORKER_ENABLED", "1") not in ("0", "false", "False")

_scheduler = None
# Monotonic deadline before which ticks return immediately -- how the fixed
# interval job implements "idle a little longer" and "back off after lag".
_paused_until = 0.0
_consecutive_backoffs = 0


def _pause_for(seconds: float):
    global _paused_until
    _paused_until = max(_paused_until, time.monotonic() + seconds)


def _claim_next_job(db):
    """Take the oldest queued job, marking it `processing` in the same step.

    The status guard in the UPDATE is what makes this safe when more than one
    uvicorn worker is running: whoever loses the race updates zero rows and
    moves on instead of editing the same page twice.
    """
    job = (
        db.query(models.TalkPageJob)
        .filter(models.TalkPageJob.status == "queued")
        .order_by(models.TalkPageJob.id)
        .first()
    )
    if not job:
        return None
    claimed = db.execute(
        update(models.TalkPageJob)
        .where(models.TalkPageJob.id == job.id, models.TalkPageJob.status == "queued")
        .values(status="processing")
    )
    db.commit()
    if claimed.rowcount != 1:
        return None
    db.refresh(job)
    return job


def _finish(db, job, status, error=None):
    job.status = status
    job.error = error[:500] if error else None
    if status in ("done", "failed"):
        job.processed_at = utcnow()
    db.commit()


def _record_failure(db, job, detail):
    """Hard failure: spend an attempt, park the job once they run out."""
    from main import log_talk_template_event

    job.attempts = (job.attempts or 0) + 1
    if job.attempts < TALK_QUEUE_MAX_ATTEMPTS:
        _finish(db, job, "queued", detail)
        print(f"[talk-queue] Job {job.id} ('{job.title}') failed, attempt {job.attempts} — requeued: {detail}")
        return
    _finish(db, job, "failed", detail)
    print(f"[talk-queue] Job {job.id} ('{job.title}') failed permanently: {detail}")
    log_talk_template_event(
        "error",
        f"Talk page template failed after {job.attempts} attempts for '{job.title}' "
        f"(submitted by {job.submitted_by}): {detail}",
    )


async def _process_job(db, job):
    """Run one queued edit. Returns True when the wiki asked us to back off."""
    from main import (
        build_talk_append_text,
        build_talk_template_text,
        edit_talk_page,
        fetch_csrf_token,
        wiki_auth_headers,
    )

    contest = db.query(models.Contest).filter_by(id=job.contest_id).first()
    if not contest or not contest.talk_template_name:
        _finish(db, job, "failed", "Contest no longer has a talk template configured")
        return False

    template_text = build_talk_template_text(contest.talk_template_name)
    append_text = build_talk_append_text(contest.talk_template_name, contest.include_talk_header)
    headers = wiki_auth_headers(job.access_token)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            csrf_token, token_data = await fetch_csrf_token(client, headers)
        except Exception as e:
            _record_failure(db, job, f"CSRF token request failed: {e}")
            return False
        if not csrf_token:
            _record_failure(
                db, job,
                f"Failed to get CSRF token for {job.submitted_by}. OAuth may have insufficient "
                f"scope or the stored token is invalid. Response: {token_data}",
            )
            return False

        try:
            outcome, detail = await edit_talk_page(
                client, headers, csrf_token, job.title, append_text, template_text
            )
        except Exception as e:
            _record_failure(db, job, str(e))
            return False

    if outcome in ("done", "skipped"):
        _finish(db, job, "done", None if outcome == "done" else detail)
        print(f"[talk-queue] Job {job.id} ('{job.title}') {outcome}.")
        return False
    if outcome == "transient":
        # Put it back untouched; the attempt counter is for the job's own
        # problems, not for the wiki being busy.
        _finish(db, job, "queued", detail)
        print(f"[talk-queue] Job {job.id} ('{job.title}') deferred (wiki asked us to wait): {detail}")
        return True
    _record_failure(db, job, detail or "Unknown edit failure")
    return False


async def drain_one_job():
    """One tick: claim at most one job and edit at most one page."""
    global _consecutive_backoffs

    if time.monotonic() < _paused_until:
        return

    db = SessionLocal()
    try:
        job = _claim_next_job(db)
        if not job:
            _pause_for(TALK_QUEUE_IDLE_INTERVAL_SECONDS - TALK_QUEUE_INTERVAL_SECONDS)
            return
        try:
            backed_off = await _process_job(db, job)
        except Exception as e:
            # A job must never be left stuck in `processing` by an unexpected
            # error -- that would silently remove it from the queue forever.
            db.rollback()
            try:
                _record_failure(db, job, f"Worker error: {e}")
            except Exception:
                db.rollback()
            print(f"[talk-queue] Unexpected worker error on job {job.id}: {e}")
            backed_off = False

        if backed_off:
            _consecutive_backoffs += 1
            delay = min(
                TALK_QUEUE_BACKOFF_SECONDS * (2 ** (_consecutive_backoffs - 1)),
                TALK_QUEUE_MAX_BACKOFF_SECONDS,
            )
            _pause_for(delay)
            print(f"[talk-queue] Backing off {delay:.0f}s after a transient wiki refusal.")
        else:
            _consecutive_backoffs = 0
    finally:
        db.close()


def start_talk_queue_worker():
    """Register the drain tick. Called once from the FastAPI lifespan."""
    global _scheduler
    if not WORKER_ENABLED:
        print("[talk-queue] Worker disabled via TALK_QUEUE_WORKER_ENABLED.")
        return None
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        drain_one_job,
        "interval",
        seconds=TALK_QUEUE_INTERVAL_SECONDS,
        id="talk_queue_drain",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    print(f"[talk-queue] Worker started (one edit per {TALK_QUEUE_INTERVAL_SECONDS}s).")
    return _scheduler


def shutdown_talk_queue_worker():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[talk-queue] Worker stopped.")


def requeue_stale_processing_jobs(minutes: int = 15) -> int:
    """Return jobs abandoned mid-flight by a restart to the queue.

    A job is marked `processing` before the edit; if the process dies between
    those two points nothing else would ever pick it up -- which is the exact
    failure this queue exists to prevent.
    """
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(minutes=minutes)
        result = db.execute(
            update(models.TalkPageJob)
            .where(
                models.TalkPageJob.status == "processing",
                models.TalkPageJob.created_at < cutoff,
            )
            .values(status="queued")
        )
        db.commit()
        if result.rowcount:
            print(f"[talk-queue] Requeued {result.rowcount} job(s) left in 'processing' by a restart.")
        return result.rowcount
    finally:
        db.close()
