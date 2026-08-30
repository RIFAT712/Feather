"""Isolated jury-panel service.

This service deliberately does not import or modify the legacy backend.  It
mirrors the legacy article-list API into its own SQLite database and exposes a
separate assigned queue.
"""
import os
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import Cookie, FastAPI, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

LEGACY_API = os.getenv("LEGACY_API_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("JURY_PANEL_DATABASE_URL", "sqlite:///./jury_panel.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class MirrorArticle(Base):
    __tablename__ = "mirror_articles"
    article_id = Column(Integer, primary_key=True)
    contest_code = Column(String(50), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    submitted_by = Column(String(255), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String(40), nullable=False)
    validation_error = Column(String(500), nullable=True)
    payload = Column(Text, nullable=False)
    assigned_to = Column(String(255), index=True, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MirrorJury(Base):
    __tablename__ = "mirror_juries"
    id = Column(Integer, primary_key=True)
    contest_code = Column(String(50), index=True, nullable=False)
    username = Column(String(255), nullable=False)
    active = Column(Boolean, default=True, nullable=False)


Base.metadata.create_all(engine)
app = FastAPI(title="Feather Isolated Jury Panel")


class SyncRequest(BaseModel):
    contest_code: str


async def legacy_user(cookie: Optional[str]) -> dict:
    if not cookie:
        raise HTTPException(status_code=401, detail="Login required")
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(f"{LEGACY_API}/api/me", cookies={"session": cookie})
    if res.status_code != 200:
        raise HTTPException(status_code=401, detail="Legacy session is invalid")
    return res.json()


async def sync_contest(contest_code: str) -> int:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"{LEGACY_API}/api/contests/{contest_code}/log")
        jury_res = await client.get(f"{LEGACY_API}/api/contests/{contest_code}")
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail="Unable to read legacy article list")
    articles = res.json()
    contest = jury_res.json() if jury_res.status_code == 200 else {}
    juries = contest.get("juries", [])
    db = SessionLocal()
    try:
        for username in juries:
            if not db.query(MirrorJury).filter_by(contest_code=contest_code, username=username).first():
                db.add(MirrorJury(contest_code=contest_code, username=username))
        for item in articles:
            existing = db.get(MirrorArticle, item["article_id"])
            if existing:
                existing.title = item["title"]
                existing.submitted_by = item["submitted_by"]
                existing.status = item["status"]
                existing.validation_error = item.get("validation_error")
                existing.payload = __import__("json").dumps(item, ensure_ascii=False)
                existing.updated_at = datetime.utcnow()
            else:
                db.add(MirrorArticle(
                    article_id=item["article_id"], contest_code=contest_code,
                    title=item["title"], submitted_by=item["submitted_by"],
                    submitted_at=datetime.fromisoformat(item["submitted_at"]) if item.get("submitted_at") else None,
                    status=item["status"], validation_error=item.get("validation_error"),
                    payload=__import__("json").dumps(item, ensure_ascii=False),
                ))
        db.commit()
        await assign_unassigned(db, contest_code)
        return len(articles)
    finally:
        db.close()


async def assign_unassigned(db, contest_code: str) -> None:
    juries = [j.username for j in db.query(MirrorJury).filter_by(contest_code=contest_code, active=True).all()]
    if not juries:
        return
    rows = db.query(MirrorArticle).filter_by(contest_code=contest_code, status="pending", assigned_to=None).all()
    random.SystemRandom().shuffle(rows)
    counts = {j: db.query(MirrorArticle).filter_by(contest_code=contest_code, assigned_to=j, status="pending").count() for j in juries}
    by_submitter = {}
    for row in rows:
        by_submitter.setdefault(row.submitted_by, []).append(row)
    for group in by_submitter.values():
        random.SystemRandom().shuffle(group)
        used = set()
        for row in group:
            choices = [j for j in juries if j not in used] or juries
            chosen = min(choices, key=lambda j: (counts[j], random.random()))
            row.assigned_to = chosen
            counts[chosen] += 1
            used.add(chosen)
    db.commit()


@app.get("/health")
def health():
    return {"status": "ok", "service": "jury-panel"}


@app.post("/jury-panel/sync")
async def sync(payload: SyncRequest):
    return {"synced": await sync_contest(payload.contest_code)}


@app.get("/jury-panel/contests/{contest_code}/articles")
async def assigned_articles(contest_code: str, session: Optional[str] = Cookie(default=None)):
    user = await legacy_user(session)
    db = SessionLocal()
    try:
        if user.get("role") == "owner":
            rows = db.query(MirrorArticle).filter_by(contest_code=contest_code).all()
        else:
            await sync_contest(contest_code)
            rows = db.query(MirrorArticle).filter_by(contest_code=contest_code, assigned_to=user["wiki_username"]).all()
        return [__import__("json").loads(row.payload) | {"assigned_to": row.assigned_to} for row in rows]
    finally:
        db.close()
