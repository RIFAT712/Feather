import os
import jwt
import asyncio
import uuid
import csv
import io
import re
import psutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks, Query
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Load local replica credentials before importing database.py, because the
# database module creates the wiki replica engine during import.
load_dotenv()

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import case, exists, func, text
from database import get_db, engine, query_wiki_replica_batch, _pre_migration_backup
import models
from jury_panel_store import sync_and_get as sync_jury_panel, DB_PATH as JURY_PANEL_DB_PATH, engine as jury_panel_engine

models.Base.metadata.create_all(bind=engine)

is_prod = os.getenv("OAUTH_CALLBACK_URL", "").startswith("https://")
app = FastAPI()
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET", "super-secret"),
    https_only=is_prod
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb_str = traceback.format_exc()
    from database import SessionLocal
    db = SessionLocal()
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
            timestamp=datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"[ErrorLog] Failed saving exception log: {e}")
    finally:
        db.close()
        
    return Response(
        content=f'{{"detail": "Internal Server Error: {str(exc)}"}}',
        status_code=500,
        media_type="application/json"
    )

WIKI_DB_USER = os.getenv("WIKI_DB_USER", "")
WIKI_DB_PASSWORD = os.getenv("WIKI_DB_PASSWORD", "")
async def add_talk_pages(titles: list[str], template_name: str, include_header: bool, access_token: str = None, submitter: str = None):
    if not access_token:
        print(f"[add_talk_pages] Skipped — no OAuth access token stored for user. They need to log out and back in.")
        return
            
    template_text = template_name.strip()
    if not template_text.startswith('{{'):
        template_text = f"{{{{{template_text}}}}}"
        
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "QuoteContestArticleTool/1.0 (https://github.com/RIFAT712/Feather)"
        }
        res3 = await client.get(
            "https://bn.wiktionary.org/w/api.php",
            params={"action": "query", "meta": "tokens", "type": "csrf", "format": "json"},
            headers=headers
        )
        token_data = res3.json()
        csrf_token = token_data.get("query", {}).get("tokens", {}).get("csrftoken")
        print(f"[add_talk_pages] CSRF token response: {token_data}")
        if not csrf_token or csrf_token == "+\\":
            msg = f"Failed to get CSRF token (got: {csrf_token!r}). OAuth may have insufficient scope or token is invalid. Full response: {token_data}"
            print(f"[add_talk_pages] {msg}")
            try:
                from database import SessionLocal
                import models
                db = SessionLocal()
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
            if include_header:
                append_text = f"{{{{আলাপ পাতা}}}}\n{template_text}"
            else:
                append_text = template_text
                
            edit_data = {
                "action": "edit",
                "title": talk_title,
                "appendtext": append_text,
                "token": csrf_token,
                "format": "json",
                "summary": "প্রতিযোগিতার টেমপ্লেট যোগ করা হচ্ছে"
            }
                
            edit_res = await client.post(
                "https://bn.wiktionary.org/w/api.php",
                data=edit_data,
                headers=headers
            )
            res_json = {}
            try:
                res_json = edit_res.json()
            except Exception:
                pass
            print(f"[add_talk_pages] Edit result for '{talk_title}': status={edit_res.status_code} body={edit_res.text[:500]}")
            if edit_res.status_code == 200 and "edit" in res_json and res_json["edit"].get("result") == "Success":
                successes.append(title)
            else:
                err_info = res_json.get("error", {}).get("info", edit_res.text[:300])
                failures.append(f"{title}: {err_info}")
        try:
            from database import SessionLocal
            import models
            db = SessionLocal()
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
        except Exception as e:
            print(f"[add_talk_pages] Error writing to SystemLog: {e}")


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

@app.on_event("shutdown")
async def shutdown_event():
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
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
                
        expire = datetime.utcnow() + timedelta(days=7)
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
        print(f"[Backup] {msg}")
        db.add(models.SystemLog(
            level="info",
            source="backup",
            message=msg,
            timestamp=datetime.utcnow(),
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
                timestamp=datetime.utcnow(),
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
    now = datetime.utcnow()
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

@app.get("/api/admin/jury-panel/backup/download")
def download_jury_panel_backup(_: models.User = Depends(get_owner_user)):
    """Download the jury-panel projection database directly. It's always local
    SQLite (even when the main app database is MariaDB on Toolforge), so unlike
    the main backup this never falls back to a JSON dump — open it in any SQLite
    browser to inspect article/jury assignment state directly."""
    if not JURY_PANEL_DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Jury panel database file not found")
    # WAL mode can leave recent commits sitting in jury_panel.db-wal rather than
    # the main file; checkpoint first so the downloaded file is complete on its own.
    try:
        with jury_panel_engine.begin() as connection:
            connection.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    except Exception as error:
        print(f"[Jury Panel Backup] Checkpoint failed, downloading as-is: {error}")
    return FileResponse(
        str(JURY_PANEL_DB_PATH), media_type="application/x-sqlite3",
        filename="feather_jury_panel.db"
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
                import unicodedata
                creator_norm = unicodedata.normalize('NFC', creator or "").replace('_', ' ').strip()
                sub_norm = unicodedata.normalize('NFC', submitter_username or "").replace('_', ' ').strip()
                if contest.rule_must_be_creator and creator_norm != sub_norm:
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
                response = await client.post(MEDIAWIKI_API_URL, data=params, headers=headers)
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
                        import unicodedata
                        creator_norm = unicodedata.normalize('NFC', creator or "").replace('_', ' ').strip()
                        sub_norm = unicodedata.normalize('NFC', submitter_username or "").replace('_', ' ').strip()
                        if contest.rule_must_be_creator and creator_norm != sub_norm:
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
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contest = db.query(models.Contest).filter_by(code=request.contest_code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    now = datetime.utcnow()
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
                existing_art.submitted_at = datetime.utcnow()
            else:
                article = models.Article(
                    title=res.title,
                    submitter_id=effective_user.id,
                    contest_id=contest.id,
                    status=models.ArticleStatus.pending,
                    validation_error=None,
                    wiki_creation_date=wiki_date,
                    wiki_creator=res.wiki_creator,
                    submitted_at=datetime.utcnow()
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
                existing_art.submitted_at = datetime.utcnow()
            else:
                article = models.Article(
                    title=res.title,
                    submitter_id=effective_user.id,
                    contest_id=contest.id,
                    status=models.ArticleStatus.validation_failed,
                    validation_error=res.error,
                    wiki_creation_date=wiki_date,
                    wiki_creator=res.wiki_creator,
                    submitted_at=datetime.utcnow()
                )
                db.add(article)
            
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database concurrency issue during bulk submit: {str(e)}")
        
    valid_titles = [r.title for r in results if r.is_valid]
    print(f"[submit-bulk] Talk Template Debug: valid_titles_count={len(valid_titles)}, add_talk_template={contest.add_talk_template}, template_name='{contest.talk_template_name}'")
    if valid_titles and contest.add_talk_template and contest.talk_template_name:
        background_tasks.add_task(
            add_talk_pages, 
            valid_titles, 
            contest.talk_template_name, 
            contest.include_talk_header,
            current_user.oauth_access_token,
            request.on_behalf_of
        )
        
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
    lock_cutoff = datetime.utcnow() - timedelta(minutes=15)
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    total = db.query(func.count(models.Article.id)).filter_by(contest_id=contest.id).scalar()

    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).order_by(models.Article.submitted_at.desc()) \
     .offset((page - 1) * page_size).limit(page_size).all()

    log = []
    now = datetime.utcnow()
    lock_cutoff = now - timedelta(minutes=15)
    article_ids = [a.id for a in articles]
    active_locks = {}
    if article_ids:
        lock_rows = db.query(models.ArticleLock).filter(
            models.ArticleLock.article_id.in_(article_ids),
            models.ArticleLock.locked_at >= lock_cutoff
        ).all()
        active_locks = {row.article_id: row.locked_by for row in lock_rows}

    for a in articles:
        locked_by = active_locks.get(a.id)

        entry = {
            "article_id": a.id,
            "title": a.title,
            "submitted_by": a.submitter.wiki_username,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "wiki_creator": a.wiki_creator,
            "wiki_creation_date": a.wiki_creation_date.isoformat() if a.wiki_creation_date else None,
            "status": a.status.value,
            "validation_error": a.validation_error,
            "locked_by": locked_by,
            "reviews": [
                {
                    "reviewer": r.reviewer.wiki_username,
                    "decision": r.status.value,
                    "comment": r.comment,
                    "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
                }
                for r in sorted(a.reviews, key=lambda r: r.timestamp or datetime.min)
                if r.status.value != "skipped"
            ]
        }
        log.append(entry)

    return {
        "items": log,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }

@app.get("/api/jury-panel/contests/{code}/articles")
def get_jury_panel_articles(code: str, view_as: Optional[str] = Query(default=None), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """New assigned queue backed by jury_panel.db; the legacy queue is unchanged."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to view the jury panel")
    if view_as and (not is_owner or view_as not in [j.user.wiki_username for j in contest.juries if j.user]):
        raise HTTPException(status_code=403, detail="Owner view must target an assigned jury member")
    return sync_jury_panel(db, contest, current_user, view_as=view_as)

@app.get("/api/jury-panel/contests/{code}/articles/page")
def get_jury_panel_articles_page(
    code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=250, ge=25, le=500),
    view_as: Optional[str] = Query(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a bounded page of assigned jury articles and queue metadata."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to view the jury panel")
    if view_as and (not is_owner or view_as not in [j.user.wiki_username for j in contest.juries if j.user]):
        raise HTTPException(status_code=403, detail="Owner view must target an assigned jury member")
    return sync_jury_panel(
        db, contest, current_user, view_as=view_as,
        offset=(page - 1) * page_size, limit=page_size, include_meta=True,
    ) | {"page": page, "page_size": page_size}

@app.get("/api/jury-panel/contests/{code}/progress")
def get_jury_panel_progress(code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return assigned, judged, and remaining counts for this contest's jury members."""
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to view jury progress")

    projected = sync_jury_panel(db, contest, current_user)
    jury_names = [j.user.wiki_username for j in contest.juries if j.user]
    visible_names = set(jury_names if is_owner else [current_user.wiki_username])
    progress = []
    for username in jury_names:
        if username not in visible_names:
            continue
        assigned = [article for article in projected if article.get("assigned_to") == username]
        judged = 0
        accepted = 0
        rejected = 0
        for article in assigned:
            own_reviews = [review for review in article.get("reviews", []) if review.get("reviewer") == username]
            if own_reviews:
                judged += 1
                decision = own_reviews[-1].get("decision")
                if decision == "accepted":
                    accepted += 1
                elif decision == "rejected":
                    rejected += 1
        progress.append({
            "username": username,
            "assigned": len(assigned),
            "judged": judged,
            "remaining": max(0, len(assigned) - judged),
            "accepted": accepted,
            "rejected": rejected,
            "progress_percent": round((judged / len(assigned)) * 100) if assigned else 0,
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
        timestamp=datetime.utcnow()
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
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None
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

    judged = []
    judged_contest_ids = set()
    jury_assignments = db.query(models.ContestJury)\
        .options(joinedload(models.ContestJury.contest))\
        .filter_by(user_id=user.id).all()
    for ja in jury_assignments:
        c = ja.contest
        judged_contest_ids.add(c.id)
        reviews = db.query(models.Review).join(models.Article)\
            .options(joinedload(models.Review.article))\
            .filter(
                models.Article.contest_id == c.id,
                models.Review.reviewer_id == user.id
            ).order_by(models.Review.timestamp.desc()).all()
        total = len(reviews)
        accepted = sum(1 for r in reviews if r.status.value == "accepted")
        rejected = sum(1 for r in reviews if r.status.value == "rejected")
        skipped = sum(1 for r in reviews if r.status.value == "skipped")
        judged.append({
            "code": c.code,
            "name": c.name,
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "role_in_contest": "jury",
            "reviews": [
                {
                    "article_title": r.article.title,
                    "decision": r.status.value,
                    "comment": r.comment,
                    "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
                } for r in reviews
            ],
            "stats": {
                "total": total,
                "accepted": accepted,
                "rejected": rejected,
                "skipped": skipped
            }
        })
    if user.role == models.RoleEnum.owner:
        owner_reviews = db.query(models.Review)\
            .options(joinedload(models.Review.article))\
            .filter_by(reviewer_id=user.id).all()
        owner_contest_ids = {r.article.contest_id for r in owner_reviews}
        for contest_id in owner_contest_ids:
            if contest_id in judged_contest_ids:
                for entry in judged:
                    if entry["code"] == db.query(models.Contest).filter_by(id=contest_id).first().code:
                        entry["role_in_contest"] = "owner"
                continue
            c = db.query(models.Contest).filter_by(id=contest_id).first()
            if not c:
                continue
            judged_contest_ids.add(c.id)
            reviews = db.query(models.Review).join(models.Article)\
                .options(joinedload(models.Review.article))\
                .filter(
                    models.Article.contest_id == c.id,
                    models.Review.reviewer_id == user.id
                ).order_by(models.Review.timestamp.desc()).all()
            total = len(reviews)
            accepted = sum(1 for r in reviews if r.status.value == "accepted")
            rejected = sum(1 for r in reviews if r.status.value == "rejected")
            skipped = sum(1 for r in reviews if r.status.value == "skipped")
            judged.append({
                "code": c.code,
                "name": c.name,
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "role_in_contest": "owner",
                "reviews": [
                    {
                        "article_title": r.article.title,
                        "decision": r.status.value,
                        "comment": r.comment,
                        "reviewed_at": r.timestamp.isoformat() if r.timestamp else None
                    } for r in reviews
                ],
                "stats": {
                    "total": total,
                    "accepted": accepted,
                    "rejected": rejected,
                    "skipped": skipped
                }
            })

    return {
        "username": user.wiki_username,
        "role": user.role.value,
        "participated_contests": list(participated.values()),
        "judged_contests": judged
    }

def _delete_articles(articles, current_user, db):
    if not articles:
        raise HTTPException(status_code=404, detail="No articles found")
    for article in articles:
        db.query(models.Review).filter_by(article_id=article.id).delete()
        db.query(models.ArticleLock).filter_by(article_id=article.id).delete()
        db.delete(article)
    contest_code = articles[0].contest.code if articles[0].contest else "unknown"
    db.add(models.SystemLog(
        level="info",
        source="backend",
        message=f"User {current_user.wiki_username} removed {len(articles)} article(s) from contest '{contest_code}'.",
        username=current_user.wiki_username
    ))
    db.commit()
    return {"status": "deleted", "deleted_count": len(articles)}

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
    if existing_lock and existing_lock.locked_at >= datetime.utcnow() - timedelta(minutes=15) \
            and existing_lock.locked_by != current_user.wiki_username:
        raise HTTPException(status_code=409, detail=f"Article is locked by {existing_lock.locked_by}.")
    if existing_lock:
        db.delete(existing_lock)
    db.add(models.ArticleLock(
        article_id=article_id,
        locked_by=current_user.wiki_username,
        locked_at=datetime.utcnow()
    ))
    db.query(models.ArticleLock).filter(
        models.ArticleLock.locked_at < datetime.utcnow() - timedelta(minutes=15)
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
    res = await client.get(f"https://bn.wiktionary.org/api/rest_v1/page/mobile-html/{title}", headers=headers)
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

@app.post("/api/articles/bulk-review")
def bulk_review_articles(data: BulkReviewRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.decision not in ("accepted", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    succeeded, failed = [], []
    for article_id in list(dict.fromkeys(data.article_ids))[:500]:
        try:
            review_article(article_id, ReviewRequest(decision=data.decision, comment=data.comment), current_user, db)
            succeeded.append(article_id)
        except HTTPException as error:
            failed.append({"article_id": article_id, "detail": error.detail})
    return {"succeeded": succeeded, "failed": failed}

@app.post("/api/articles/bulk-delete")
def bulk_delete_articles(data: BulkDeleteRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    succeeded, failed = [], []
    candidates = []
    for article_id in list(dict.fromkeys(data.article_ids))[:500]:
        article = db.query(models.Article).filter_by(id=article_id).first()
        if not article:
            failed.append({"article_id": article_id, "detail": "Article not found"})
            continue
        is_owner = current_user.role == models.RoleEnum.owner
        is_jury = db.query(models.ContestJury).filter_by(contest_id=article.contest_id, user_id=current_user.id).first() is not None
        if not (is_owner or is_jury):
            failed.append({"article_id": article_id, "detail": "Not authorized to delete articles in this contest"})
            continue
        candidates.append(article)
    if candidates:
        try:
            _delete_articles(candidates, current_user, db)
            succeeded = [article.id for article in candidates]
        except HTTPException as error:
            failed.extend({"article_id": article.id, "detail": error.detail} for article in candidates)
        except Exception as error:
            db.rollback()
            failed.extend({"article_id": article.id, "detail": str(error)} for article in candidates)
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
    if active_lock and active_lock.locked_at < datetime.utcnow() - timedelta(minutes=15):
        db.delete(active_lock)
        db.commit()
        active_lock = None
    if active_lock and active_lock.locked_by != current_user.wiki_username:
        raise HTTPException(status_code=409, detail=f"Article is locked by {active_lock.locked_by}.")

    if data.decision not in ("accepted", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    if data.decision in ("accepted", "rejected"):
        article.status = models.ArticleStatus[data.decision]
    elif own_review:
        article.status = models.ArticleStatus.pending

    if own_review:
        own_review.status = models.ReviewStatus[data.decision]
        own_review.comment = data.comment
        own_review.timestamp = datetime.utcnow()
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
            "exported_at": datetime.utcnow().isoformat(),
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
            "exported_at": datetime.utcnow().isoformat(),
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

dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend-vue", "dist")
assets_dir = os.path.join(dist_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
@app.get("/{path_name:path}")
async def serve_spa(path_name: str):
    if path_name.startswith("api") or path_name.startswith("auth"):
        raise HTTPException(status_code=404, detail="Not found")
    if path_name:
        file_path = os.path.join(dist_dir, path_name)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return HTMLResponse("<h1>Frontend not built. Run: cd frontend-vue && npm run build</h1>", status_code=503)
