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

article_locks = {}  # { article_id: { "user": "wiki_username", "time": datetime } }

from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel
import httpx

from sqlalchemy.orm import Session, joinedload, selectinload
from database import get_db, engine, query_wiki_replica_batch
import models

from dotenv import load_dotenv
load_dotenv()

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
        token = request.cookies.get("session_token")
        if token:
            try:
                payload_data = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
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
WIKI_BOT_USERNAME = os.getenv("WIKI_BOT_USERNAME", "")
WIKI_BOT_PASSWORD = os.getenv("WIKI_BOT_PASSWORD", "")

async def bot_edit_talk_pages(titles: list[str], template_name: str, include_header: bool):
    if not WIKI_BOT_USERNAME or not WIKI_BOT_PASSWORD:
        return
        
    template_text = template_name.strip()
    if not template_text.startswith('{{'):
        template_text = f"{{{{{template_text}}}}}"
        
    async with httpx.AsyncClient() as client:
        # 1. Get login token
        res1 = await client.get(
            "https://bn.wiktionary.org/w/api.php",
            params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}
        )
        login_token = res1.json().get("query", {}).get("tokens", {}).get("logintoken")
        if not login_token: return
        
        # 2. Login
        res2 = await client.post(
            "https://bn.wiktionary.org/w/api.php",
            data={
                "action": "login",
                "lgname": WIKI_BOT_USERNAME,
                "lgpassword": WIKI_BOT_PASSWORD,
                "lgtoken": login_token,
                "format": "json"
            }
        )
        # 3. Get CSRF token
        res3 = await client.get(
            "https://bn.wiktionary.org/w/api.php",
            params={"action": "query", "meta": "tokens", "type": "csrf", "format": "json"}
        )
        csrf_token = res3.json().get("query", {}).get("tokens", {}).get("csrftoken")
        if not csrf_token: return
        
        # 4. Edit each talk page
        for title in titles:
            talk_title = f"Talk:{title}" if not title.startswith("Talk:") else title
            append_text = f"\n{template_text}\n"
            if include_header:
                append_text = f"\n== Contest Submission ==\n{append_text}"
                
            await client.post(
                "https://bn.wiktionary.org/w/api.php",
                data={
                    "action": "edit",
                    "title": talk_title,
                    "appendtext": append_text,
                    "bot": 1,
                    "token": csrf_token,
                    "format": "json",
                    "summary": "Adding contest template"
                }
            )

oauth = OAuth()
oauth.register(
    name='wikimedia',
    client_id=os.getenv("WIKIMEDIA_CLIENT_ID", ""),
    client_secret=os.getenv("WIKIMEDIA_CLIENT_SECRET", ""),
    access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
    authorize_url='https://meta.wikimedia.org/w/rest.php/oauth2/authorize',
    api_base_url='https://meta.wikimedia.org/w/rest.php/oauth2/resource/',
    client_kwargs={'scope': 'basic'}
)

MEDIAWIKI_API_URL = os.getenv("MEDIAWIKI_API_URL", "https://bn.wiktionary.org/w/api.php")
JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret")
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

# Pydantic Schemas
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

class AssignJury(BaseModel):
    contest_code: str
    wiki_usernames: List[str]

class UnassignJury(BaseModel):
    contest_code: str
    wiki_username: str

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

# Auth Dependencies
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
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_owner_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.owner:
        raise HTTPException(status_code=403, detail="Owner privileges required")
    return current_user

# Routes
@app.get("/auth/login")
async def login(request: Request, next: Optional[str] = None):
    host = request.headers.get("x-forwarded-host", request.url.hostname)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    
    if next:
        request.session['next_url'] = next
        
    # Dynamically set the callback URL if running on Toolforge
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
            user = models.User(wiki_username=username, role=role)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if username == "R1F4T" and user.role != models.RoleEnum.owner:
                user.role = models.RoleEnum.owner
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
            samesite="lax"
        )
        return redirect_res
        
    except Exception as e:
        print(f"Login failed: {e}")
        return RedirectResponse(url="/?error=login_failed")

@app.post("/auth/logout")
async def logout():
    response = Response(status_code=200)
    response.delete_cookie("auth_token")
    return response

@app.get("/api/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"wiki_username": current_user.wiki_username, "role": current_user.role.value}

_is_restarting = False

# ── Shared backup helper ──────────────────────────────────────────────────────
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

        # Users
        users = db.query(models.User).all()
        users_file = f'users_{timestamp}.csv' if label == "EMERGENCY" else 'users.csv'
        with open(os.path.join(dest_dir, users_file), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'wiki_username', 'role'])
            for u in users:
                writer.writerow([u.id, u.wiki_username, u.role.value])

        # Contests
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

# ── Backup root resolution ────────────────────────────────────────────────────
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
            # Verify write access
            test_file = os.path.join(probe, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            print(f"[Backup] Using backup root via {label}: {base}")
            return base
        except Exception as e:
            print(f"[Backup] Cannot write to {probe} ({label}): {e} — trying next candidate")

    raise RuntimeError("[Backup] No writable backup root found!")

# ── Emergency backup (triggered on server overload) ───────────────────────────
# Always creates NEW files — never overwrites (timestamp in filename).
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

# ── Hourly scheduled backup ───────────────────────────────────────────────────
HOURLY_BACKUP_INTERVAL_SECONDS = 3600  # 1 hour

def _hourly_backup_loop():
    """Runs in a daemon thread; takes a backup every hour."""
    # Resolve writable backup root and pre-create both subdirectories at startup
    home = _resolve_backup_root()
    os.makedirs(os.path.join(home, 'backup', 'hourly'), exist_ok=True)
    os.makedirs(os.path.join(home, 'backup', 'emergency'), exist_ok=True)
    print(f"[Backup] Directories ready: {home}/backup/{{hourly,emergency}}/")
    while True:
        hourly_dir = os.path.join(home, 'backup', 'hourly')
        _write_backup_files(hourly_dir, "HOURLY")
        time.sleep(HOURLY_BACKUP_INTERVAL_SECONDS)

# Start the hourly backup daemon thread when the module loads
_hourly_thread = threading.Thread(target=_hourly_backup_loop, daemon=True, name="hourly-backup")
_hourly_thread.start()

# ── System status & overload detection ───────────────────────────────────────
@app.get("/api/system/status")
def system_status(background_tasks: BackgroundTasks):
    global _is_restarting
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent

    overloaded = cpu > 90 or mem > 90 or _is_restarting

    if overloaded and not _is_restarting:
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
        selectinload(models.Contest.articles),
        selectinload(models.Contest.juries).joinedload(models.ContestJury.user)
    ).all()
    res = []
    for c in contests:
        jury_list = [j.user.wiki_username for j in c.juries if j.user]
        arts = c.articles
        accepted = sum(1 for a in arts if a.status == models.ArticleStatus.accepted)
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
            "articles_count": len(arts),
            "accepted_count": accepted,
            "juries_count": len(jury_list),
            "juries": jury_list
        })
    return res

@app.get("/api/contests/{code}")
def get_contest(code: str, db: Session = Depends(get_db)):
    c = db.query(models.Contest).options(
        selectinload(models.Contest.articles),
        selectinload(models.Contest.juries).joinedload(models.ContestJury.user)
    ).filter_by(code=code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contest not found")
    jury_list = [j.user.wiki_username for j in c.juries if j.user]
    arts = c.articles
    accepted = sum(1 for a in arts if a.status == models.ArticleStatus.accepted)
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
        "articles_count": len(arts),
        "accepted_count": accepted,
        "juries_count": len(jury_list),
        "juries": jury_list
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
    
    return {
        "total_contests": total_contests,
        "active_contests": active_contests,
        "total_articles": total_articles,
        "accepted_articles": accepted_articles,
        "total_users": total_users,
        "total_juries": total_juries
    }

# Admin endpoints
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
def update_contest(code: str, data: ContestCreate, _: models.User = Depends(get_owner_user), db: Session = Depends(get_db)):
    c = db.query(models.Contest).filter_by(code=code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    c.name = data.name
    c.start_date = data.start_date
    c.end_date = data.end_date
    c.rule_must_be_creator = data.rule_must_be_creator
    c.min_bytes = data.min_bytes
    c.min_words = data.min_words
    c.min_refs = data.min_refs
    c.rule_no_redirect = data.rule_no_redirect
    c.rule_no_disambig = data.rule_no_disambig
    c.rule_mainspace_only = data.rule_mainspace_only
    c.allow_self_review = data.allow_self_review
    c.add_talk_template = data.add_talk_template
    c.talk_template_name = data.talk_template_name
    c.include_talk_header = data.include_talk_header
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
    db.commit()
    return {"status": "success", "removed": data.wiki_username}

# Submissions
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
    # Filter out articles with validation_failed status so they can be re-submitted and re-validated
    existing_titles = {a.title.lower() for a in existing if a.status != models.ArticleStatus.validation_failed}
    
    titles_to_check = []
    for t in titles:
        if t.lower() in existing_titles:
            results.append(ValidationResult(title=t, is_valid=False, error="Already submitted"))
        else:
            titles_to_check.append(t)
            
    if not titles_to_check:
        return results

    # 1. Attempt batch validation via Wiktionary Replica MariaDB (Fast, zero rate limits)
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
                if contest.rule_must_be_creator and creator != submitter_username:
                    results.append(ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'"))
                    continue
                if wiki_date and not (contest.start_date <= wiki_date <= contest.end_date):
                    results.append(ValidationResult(title=t, is_valid=False, error="Created outside contest timeframe"))
                    continue
                    
            results.append(ValidationResult(title=t, is_valid=True, wiki_creator=creator, wiki_creation_date=timestamp_str))
        return results

    # 2. Fallback to HTTP MediaWiki API if DB Replica is unavailable (e.g. running locally)
    unique_id = uuid.uuid4().hex[:8]
    contact_email = os.getenv("CONTACT_EMAIL", "contact@example.com")
    user_agent = f"WikiArticleContestTool/1.0 (User:{submitter_username}; ContestCode:{contest.code}; {contact_email}; RequestID:{unique_id})"
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
                    
                    # Content text analysis for min_words & min_refs
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
                        if contest.rule_must_be_creator and creator != submitter_username:
                            return ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'")
                            
                        creation_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
                        if not (contest.start_date <= creation_time <= contest.end_date):
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

    # Determine privileges once
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
    
    # Find or create submitter user record for the effective submitter
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

    # Query existing articles for clean_titles to decide insert vs update
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
                # Upgrade previous validation_failed entry to pending
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
                # Update existing validation_failed entry with latest error & timestamp
                existing_art.status = models.ArticleStatus.validation_failed
                existing_art.validation_error = res.error
                existing_art.submitter_id = effective_user.id
                existing_art.wiki_creator = res.wiki_creator
                existing_art.wiki_creation_date = wiki_date
                existing_art.submitted_at = datetime.utcnow()
            else:
                # Log failed validation event into DB so it appears in the contest log
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
    if valid_titles and contest.add_talk_template and contest.talk_template_name:
        background_tasks.add_task(bot_edit_talk_pages, valid_titles, contest.talk_template_name, contest.include_talk_header)
        
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
    
    article = db.query(models.Article).options(joinedload(models.Article.submitter)).filter_by(
        contest_id=contest.id, 
        status=models.ArticleStatus.pending
    ).first()
    
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

    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).all()

    submitters = {}
    juries = {}

    for a in articles:
        if a.submitter:
            u = a.submitter.wiki_username
            if u not in submitters:
                submitters[u] = {"accepted": 0, "rejected": 0, "pending": 0, "total": 0}
            submitters[u]["total"] += 1
            if a.status.value == "accepted": submitters[u]["accepted"] += 1
            elif a.status.value == "rejected": submitters[u]["rejected"] += 1
            elif a.status.value == "pending": submitters[u]["pending"] += 1
            
        for r in a.reviews:
            if r.reviewer:
                j = r.reviewer.wiki_username
                if j not in juries:
                    juries[j] = {"accepted": 0, "rejected": 0, "total": 0}
                juries[j]["total"] += 1
                if r.status.value == "accepted": juries[j]["accepted"] += 1
                elif r.status.value == "rejected": juries[j]["rejected"] += 1

    return {
        "contest": {"name": contest.name, "code": contest.code},
        "submitters": [{"username": u, **stats} for u, stats in submitters.items()],
        "juries": [{"username": j, **stats} for j, stats in juries.items()]
    }

@app.get("/api/contests/{code}/log")
def get_contest_log(code: str, db: Session = Depends(get_db)):
    contest = db.query(models.Contest).filter_by(code=code).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    articles = db.query(models.Article).options(
        joinedload(models.Article.submitter),
        selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
    ).filter_by(contest_id=contest.id).order_by(models.Article.submitted_at.desc()).all()

    log = []
    now = datetime.utcnow()
    for a in articles:
        # Check lock
        locked_by = None
        if a.id in article_locks:
            lock = article_locks[a.id]
            if now - lock["time"] < timedelta(minutes=15):
                locked_by = lock["user"]

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

    return log

class ClientErrorLog(BaseModel):
    message: str
    stack_trace: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    level: Optional[str] = "error"

SESSION_SECRET = os.getenv("SESSION_SECRET", "super-secret")

@app.post("/api/logs/client-error")
def log_client_error(
    payload: ClientErrorLog,
    request: Request,
    db: Session = Depends(get_db)
):
    username = None
    token = request.cookies.get("session_token")
    if token:
        try:
            payload_data = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
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
    db: Session = Depends(get_db)
):
    """
    Returns global activity, error, and system runtime logs.
    Includes: frontend JS errors, backend 500 errors, and backup events (source=backup).
    Filter with ?source=backup to see only backup history.
    """
    logs = []

    # 1. System runtime error logs (Frontend JS errors, Button click errors, Backend 500 errors)
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

    # 2. Article validation & submission logs (skip when filtering by backup source)
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

    # Contests where user is explicitly assigned as jury
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

    # Owners can review any contest — include any contest they reviewed
    # that isn't already covered by a jury assignment
    if user.role == models.RoleEnum.owner:
        owner_reviews = db.query(models.Review)\
            .options(joinedload(models.Review.article))\
            .filter_by(reviewer_id=user.id).all()
        owner_contest_ids = {r.article.contest_id for r in owner_reviews}
        for contest_id in owner_contest_ids:
            if contest_id in judged_contest_ids:
                # Already present; upgrade role label to owner+jury if needed
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

@app.post("/api/articles/{article_id}/lock")
def lock_article(article_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    article = db.query(models.Article).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    contest = article.contest
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_jury):
        raise HTTPException(status_code=403, detail="Not authorized to lock articles in this contest")

    article_locks[article_id] = {
        "user": current_user.wiki_username,
        "time": datetime.utcnow()
    }
    return {"success": True, "locked_by": current_user.wiki_username}

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

    if not getattr(contest, 'allow_self_review', False) and article.submitter_id == current_user.id and not is_owner:
        raise HTTPException(status_code=403, detail="Self-review is disabled for this contest.")

    if data.decision not in ("accepted", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="Invalid decision")

    # Update article status (skipped stays pending for other jurors)
    if data.decision in ("accepted", "rejected"):
        article.status = models.ArticleStatus[data.decision]

    review = models.Review(
        article_id=article.id,
        reviewer_id=current_user.id,
        status=models.ReviewStatus[data.decision],
        comment=data.comment
    )
    db.add(review)
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

        # Submitters Table
        lines.append('{| class="wikitable sortable"')
        lines.append('|+ জমাদানকারীর পরিসংখ্যান: ' + contest.name)
        lines.append('|-')
        lines.append('! ব্যবহারকারী !! মোট জমা !! গৃহীত !! প্রত্যাখ্যাত')
        
        for u, stats in submitters.items():
            lines.append('|-')
            lines.append(f'| [[ব্যবহারকারী:{u}|{u}]] || {stats["total"]} || {stats["accepted"]} || {stats["rejected"]}')
        lines.append('|}')
        lines.append('')
        
        # Juries Table
        lines.append('{| class="wikitable sortable"')
        lines.append('|+ বিচারকের পরিসংখ্যান: ' + contest.name)
        lines.append('|-')
        lines.append('! বিচারক !! মোট পর্যালোচনা !! গৃহীত !! প্রত্যাখ্যাত')
        
        for j, stats in juries.items():
            lines.append('|-')
            lines.append(f'| [[ব্যবহারকারী:{j}|{j}]] || {stats["total"]} || {stats["accepted"]} || {stats["rejected"]}')
        lines.append('|}')
        
    output = "\\n".join(lines)
    filename = f"contest_{code}_export.txt"
    return StreamingResponse(
        io.BytesIO(output.encode('utf-8')),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# Serve SPA frontend static files in production / Toolforge
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend-vue", "dist")

# Mount assets — only if directory exists (built SPA)
assets_dir = os.path.join(dist_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Catch-all: ALWAYS registered so the root / never hits FastAPI's 404
@app.get("/{path_name:path}")
async def serve_spa(path_name: str):
    # Let /api and /auth fall through to FastAPI's own routers
    if path_name.startswith("api") or path_name.startswith("auth"):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve exact static file if it exists
    if path_name:
        file_path = os.path.join(dist_dir, path_name)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

    # Always fall back to index.html for SPA routing (including root "/")
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return HTMLResponse("<h1>Frontend not built. Run: cd frontend-vue && npm run build</h1>", status_code=503)
