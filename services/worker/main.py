from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import csv
import time
import httpx
import threading
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session, joinedload, selectinload

from shared_lib.database import get_db, engine
from shared_lib import models
from shared_lib.logger import setup_logger

logger = setup_logger("worker-service")

app = FastAPI(title="Wiktionary Contest Worker Service")

class TalkPagePayload(BaseModel):
    titles: List[str]
    template_name: str
    include_header: bool
    access_token: str
    submitter: Optional[str] = None

# Backup configuration
HOURLY_BACKUP_INTERVAL_SECONDS = 3600  # 1 hour
_is_restarting = False

def _resolve_backup_root() -> str:
    candidates = []
    if os.environ.get("BACKUP_ROOT"):
        candidates.append(("BACKUP_ROOT env var", os.environ["BACKUP_ROOT"]))
    try:
        candidates.append(("Path.home()", str(Path.home())))
    except Exception:
        pass
    candidates.append(("project root fallback", os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    for label, base in candidates:
        probe = os.path.join(base, "backup")
        try:
            os.makedirs(probe, exist_ok=True)
            test_file = os.path.join(probe, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            logger.info(f"Using backup root via {label}: {base}")
            return base
        except Exception as e:
            logger.warning(f"Cannot write to {probe} ({label}): {e} — trying next candidate")

    raise RuntimeError("No writable backup root found!")

def _write_backup_files(dest_dir: str, label: str):
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
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
        logger.info(msg)
        db.add(models.SystemLog(
            level="info",
            source="backup",
            message=msg,
            timestamp=datetime.utcnow(),
        ))
        db.commit()
    except Exception as e:
        err_msg = f"{label} backup FAILED: {e} (dest={dest_dir})"
        logger.error(err_msg, exc_info=True)
        try:
            db.add(models.SystemLog(
                level="error",
                source="backup",
                message=err_msg[:2000],
                timestamp=datetime.utcnow(),
            ))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()

def _hourly_backup_loop():
    logger.info("Starting hourly backup daemon thread")
    try:
        home = _resolve_backup_root()
        os.makedirs(os.path.join(home, 'backup', 'hourly'), exist_ok=True)
        os.makedirs(os.path.join(home, 'backup', 'emergency'), exist_ok=True)
        logger.info(f"Backup directories ready: {home}/backup/{{hourly,emergency}}/")
    except Exception as e:
        logger.error(f"Failed to initialize backup directory on startup: {e}")
        return

    while True:
        try:
            hourly_dir = os.path.join(home, 'backup', 'hourly')
            _write_backup_files(hourly_dir, "HOURLY")
        except Exception as e:
            logger.error(f"Error in backup loop execution: {e}")
        time.sleep(HOURLY_BACKUP_INTERVAL_SECONDS)

# Start backup thread on startup
_hourly_thread = threading.Thread(target=_hourly_backup_loop, daemon=True, name="hourly-backup")
_hourly_thread.start()

async def add_talk_pages(titles: List[str], template_name: str, include_header: bool, access_token: str, submitter: Optional[str] = None):
    logger.info(f"Starting add_talk_pages for {len(titles)} articles")
    template_text = template_name.strip()
    if not template_text.startswith('{{'):
        template_text = f"{{{{{template_text}}}}}"
        
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "QuoteContestArticleTool/1.0 (https://github.com/RIFAT712/Feather)"
        }
        try:
            res = await client.get(
                "https://bn.wiktionary.org/w/api.php",
                params={"action": "query", "meta": "tokens", "type": "csrf", "format": "json"},
                headers=headers
            )
            token_data = res.json()
            csrf_token = token_data.get("query", {}).get("tokens", {}).get("csrftoken")
            logger.debug(f"CSRF token response: {token_data}")
        except Exception as e:
            logger.error(f"Error fetching CSRF token: {e}")
            return

        if not csrf_token or csrf_token == "+\\":
            msg = f"Failed to get CSRF token (got: {csrf_token!r}). OAuth may have insufficient scope or token is invalid."
            logger.error(msg)
            try:
                db = next(get_db())
                db.add(models.SystemLog(
                    level="error", 
                    source="talk_template", 
                    message=msg,
                    timestamp=datetime.utcnow()
                ))
                db.commit()
                db.close()
            except Exception:
                pass
            return

        successes = []
        failures = []
        for title in titles:
            talk_title = f"Talk:{title}" if not title.startswith("Talk:") else title
            append_text = f"{{{{আলাপ পাতা}}}}\n{template_text}" if include_header else template_text
                
            edit_data = {
                "action": "edit",
                "title": talk_title,
                "appendtext": append_text,
                "token": csrf_token,
                "format": "json",
                "summary": "প্রতিযোগিতার টেমপ্লেট যোগ করা হচ্ছে"
            }
            try:
                edit_res = await client.post(
                    "https://bn.wiktionary.org/w/api.php",
                    data=edit_data,
                    headers=headers
                )
                res_json = edit_res.json()
                logger.debug(f"Edit result for '{talk_title}': status={edit_res.status_code}")
                if edit_res.status_code == 200 and "edit" in res_json and res_json["edit"].get("result") == "Success":
                    successes.append(title)
                else:
                    err_info = res_json.get("error", {}).get("info", edit_res.text[:300])
                    failures.append(f"{title}: {err_info}")
            except Exception as e:
                failures.append(f"{title}: {str(e)}")

        try:
            db = next(get_db())
            msg = f"Talk page template added for {len(successes)} articles."
            if failures:
                msg += f" Failures ({len(failures)}): " + ", ".join(failures)[:1500]
            db.add(models.SystemLog(
                level="info" if not failures else "warning", 
                source="talk_template", 
                message=msg,
                timestamp=datetime.utcnow()
            ))
            db.commit()
            db.close()
            logger.info(f"Completed talk page template additions. {msg}")
        except Exception as e:
            logger.error(f"Error writing template results to SystemLog: {e}")

@app.post("/jobs/add-talk-pages")
def queue_add_talk_pages(payload: TalkPagePayload, background_tasks: BackgroundTasks):
    logger.info(f"Queued talk page edits for {len(payload.titles)} pages")
    background_tasks.add_task(
        add_talk_pages,
        payload.titles,
        payload.template_name,
        payload.include_header,
        payload.access_token,
        payload.submitter
    )
    return {"status": "queued", "count": len(payload.titles)}

@app.post("/jobs/backup")
def trigger_backup(background_tasks: BackgroundTasks):
    logger.info("Manual backup triggered")
    home = _resolve_backup_root()
    hourly_dir = os.path.join(home, 'backup', 'hourly')
    background_tasks.add_task(_write_backup_files, hourly_dir, "MANUAL")
    return {"status": "triggered"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "worker", "backup_thread_alive": _hourly_thread.is_alive()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
