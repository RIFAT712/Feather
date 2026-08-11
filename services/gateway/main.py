import os
import jwt
import csv
import io
import uuid
import psutil
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

from shared_lib.database import get_db, engine
from shared_lib import models
from shared_lib.schemas import (
    ContestCreate, ContestUpdate, AssignJury, UnassignJury, 
    BulkSubmitRequest, ValidationResult, ClientErrorLog, ReviewRequest
)
from shared_lib.logger import setup_logger

logger = setup_logger("gateway-service")

app = FastAPI(title="Wiktionary Contest API Gateway")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
VALIDATOR_SERVICE_URL = os.getenv("VALIDATOR_SERVICE_URL", "http://localhost:8002")
WORKER_SERVICE_URL = os.getenv("WORKER_SERVICE_URL", "http://localhost:8003")

JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret") + "_v2"
JWT_ALGORITHM = "HS256"

# Helper function to proxy requests to internal services (like Auth)
async def proxy_request(request: Request, target_url: str) -> Response:
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    params = dict(request.query_params)
    body = await request.body()
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=params,
                content=body,
                follow_redirects=False,
                timeout=30.0
            )
        
        response = Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items() if k.lower() not in ("content-length", "transfer-encoding", "connection")}
        )
        return response
    except httpx.HTTPError as e:
        logger.error(f"Proxy request to {target_url} failed: {e}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

# Proxy Auth routes to Auth Service
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_auth_route(request: Request, path: str):
    target_url = f"{AUTH_SERVICE_URL}/auth/{path}"
    logger.info(f"Proxying auth request to: {target_url}")
    return await proxy_request(request, target_url)

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

@app.get("/api/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "wiki_username": current_user.wiki_username,
        "role": current_user.role.value
    }

@app.get("/api/system/status")
async def system_status(background_tasks: BackgroundTasks):
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent

    overloaded = cpu > 90 or mem > 90
    
    # Trigger emergency backup via worker
    if overloaded:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{WORKER_SERVICE_URL}/jobs/backup", timeout=2.0)
        except Exception as e:
            logger.error(f"Failed to trigger emergency backup: {e}")

    # Check health of downstream microservices
    async def get_service_status(url):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{url}/health", timeout=1.0)
                return "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception:
            return "unreachable"

    return {
        "cpu_percent": cpu,
        "mem_percent": mem,
        "overloaded": overloaded,
        "services": {
            "auth": await get_service_status(AUTH_SERVICE_URL),
            "validator": await get_service_status(VALIDATOR_SERVICE_URL),
            "worker": await get_service_status(WORKER_SERVICE_URL),
        }
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
    db.commit()
    return {"status": "success", "removed": data.wiki_username}

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
    is_owner = current_user.role == models.RoleEnum.owner
    is_jury = db.query(models.ContestJury).filter_by(contest_id=contest.id, user_id=current_user.id).first() is not None
    is_privileged = is_owner or is_jury

    submitter_username = current_user.wiki_username
    if request.on_behalf_of:
        if not is_privileged:
            raise HTTPException(status_code=403, detail="Only Jury or Owner can submit on behalf of others.")
        submitter_username = request.on_behalf_of

    clean_titles = list({t.strip() for t in request.titles if t.strip()})
    
    # Filter existing submissions to avoid duplicate verification
    existing = db.query(models.Article).filter(
        models.Article.contest_id == contest.id,
        models.Article.title.in_(clean_titles)
    ).all()
    existing_titles = {a.title.lower() for a in existing if a.status != models.ArticleStatus.validation_failed}
    
    titles_to_check = []
    results = []
    for t in clean_titles:
        if t.lower() in existing_titles:
            results.append(ValidationResult(title=t, is_valid=False, error="Already submitted"))
        else:
            titles_to_check.append(t)
            
    if titles_to_check:
        # Call Validator Microservice
        validation_payload = {
            "titles": titles_to_check,
            "submitter_username": submitter_username,
            "bypass_rules": is_privileged,
            "rule_must_be_creator": getattr(contest, 'rule_must_be_creator', True),
            "min_bytes": getattr(contest, 'min_bytes', 0),
            "min_words": getattr(contest, 'min_words', 0),
            "min_refs": getattr(contest, 'min_refs', 0),
            "rule_no_redirect": getattr(contest, 'rule_no_redirect', True),
            "rule_no_disambig": getattr(contest, 'rule_no_disambig', True),
            "rule_mainspace_only": getattr(contest, 'rule_mainspace_only', True),
            "start_date": contest.start_date.isoformat(),
            "end_date": contest.end_date.isoformat(),
            "contest_code": contest.code
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{VALIDATOR_SERVICE_URL}/validate", 
                    json=validation_payload, 
                    timeout=45.0
                )
                resp.raise_for_status()
                results_data = resp.json()
            
            # Map Pydantic validator results back
            for r in results_data:
                results.append(ValidationResult(**r))
        except Exception as e:
            logger.error(f"Failed to communicate with validator service: {e}")
            raise HTTPException(status_code=502, detail=f"Validator service error: {str(e)}")

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
    if valid_titles and contest.add_talk_template and contest.talk_template_name:
        # Call Worker microservice to write talk pages in the background
        worker_payload = {
            "titles": valid_titles,
            "template_name": contest.talk_template_name,
            "include_header": contest.include_talk_header,
            "access_token": current_user.oauth_access_token,
            "submitter": request.on_behalf_of
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{WORKER_SERVICE_URL}/jobs/add-talk-pages", json=worker_payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Worker template job failed to queue: {e}")
            # Do not fail submission if worker task enqueue fails, but log it
            
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

    return log

@app.post("/api/admin/force-migration")
def force_migration(_: models.User = Depends(get_owner_user)):
    try:
        from shared_lib.database import run_auto_migrations
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
            "status": s.level,
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
        title_for_log = article.title
        contest_code = article.contest.code if article.contest else "unknown"
        db.query(models.Review).filter_by(article_id=article.id).delete()
        db.query(models.ArticleLock).filter_by(article_id=article.id).delete()
        db.delete(article)
        db.add(models.SystemLog(
            level="info",
            source="backend",
            message=f"User {current_user.wiki_username} removed article '{title_for_log}' from contest '{contest_code}'.",
            username=current_user.wiki_username
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "deleted"}

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
    async with httpx.AsyncClient() as client:
        res = await client.get(f"https://bn.wiktionary.org/api/rest_v1/page/mobile-html/{title}", headers=headers)
        html = res.text
    html = html.replace("<head>", f'<head><base href="https://bn.wiktionary.org/wiki/">')
    return HTMLResponse(content=html, status_code=res.status_code)

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

# Mounting SPA Static files
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend-vue", "dist"))
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

@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
