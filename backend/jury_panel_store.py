"""Separate review-database projection used by the new jury-panel endpoint."""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func, text
from sqlalchemy.orm import declarative_base, joinedload, sessionmaker, selectinload

Base = declarative_base()
DB_PATH = Path(__file__).resolve().parent / "jury_panel.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class ArticleProjection(Base):
    __tablename__ = "article_projection"
    article_id = Column(Integer, primary_key=True)
    contest_code = Column(String(50), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    submitted_by = Column(String(255), nullable=False)
    status = Column(String(40), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    payload = Column(Text, nullable=False)
    assigned_to = Column(String(255), index=True, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProjectionMeta(Base):
    __tablename__ = "projection_meta"
    contest_code = Column(String(50), primary_key=True)
    article_count = Column(Integer, nullable=False, default=0)
    latest_submitted_at = Column(DateTime, nullable=True)
    latest_review_at = Column(DateTime, nullable=True)
    restriction_count = Column(Integer, nullable=False, default=0)
    jury_signature = Column(String(1000), nullable=False, default="")
    banned_signature = Column(String(1000), nullable=False, default="")
    assignment_signature = Column(String(2000), nullable=False, default="")


Base.metadata.create_all(bind=engine)

# create_all does not add columns to an existing SQLite projection database.
with engine.begin() as connection:
    columns = {row[1] for row in connection.execute(text("PRAGMA table_info(projection_meta)"))}
    for name, definition in {
        "restriction_count": "INTEGER NOT NULL DEFAULT 0",
        "jury_signature": "VARCHAR(1000) NOT NULL DEFAULT ''",
        "banned_signature": "VARCHAR(1000) NOT NULL DEFAULT ''",
        "assignment_signature": "VARCHAR(2000) NOT NULL DEFAULT ''",
    }.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE projection_meta ADD COLUMN {name} {definition}"))


def sync_and_get(db, contest, current_user, view_as=None, offset=0, limit=None, include_meta=False):
    """Read the legacy DB, write only the projection DB, and return this user's queue."""
    mirror = SessionLocal()
    try:
        models = __import__('models')
        juries = [j.user.wiki_username for j in contest.juries if j.user]
        jury_ids = {j.user.wiki_username: j.user_id for j in contest.juries if j.user}
        restrictions = {
            (row.jury_user_id, row.submitter_user_id)
            for row in db.query(models.ContestJuryRestriction).filter_by(contest_id=contest.id).all()
        }
        banned_user_ids = {row.user_id for row in db.query(models.ContestBannedUser).filter_by(contest_id=contest.id).all()}
        source_query = db.query(models.Article).filter(
            models.Article.contest_id == contest.id,
            ~models.Article.submitter_id.in_(banned_user_ids) if banned_user_ids else True,
        )
        source_count = source_query.count()
        latest_submitted_at = source_query.with_entities(func.max(models.Article.submitted_at)).scalar()
        latest_review_at = (db.query(func.max(models.Review.timestamp))
                            .join(models.Article, models.Review.article_id == models.Article.id)
                            .filter(models.Article.contest_id == contest.id)
                            .scalar())
        meta = mirror.get(ProjectionMeta, contest.code)
        mirror_count = mirror.query(ArticleProjection).filter_by(contest_code=contest.code).count()
        restriction_count = len(restrictions)
        jury_signature = "\x1f".join(sorted(juries))
        restriction_signature = "\x1f".join(f"{jury_id}:{submitter_id}" for jury_id, submitter_id in sorted(restrictions))
        assignment_signature = f"self={int(bool(contest.allow_self_review))}\x1e{restriction_signature}"
        banned_signature = "\x1f".join(sorted(
            row.user.wiki_username for row in contest.banned_users if row.user
        ))
        needs_sync = (
            meta is None
            or meta.article_count != source_count
            or mirror_count != source_count
            or meta.latest_submitted_at != latest_submitted_at
            or meta.latest_review_at != latest_review_at
            or meta.restriction_count != restriction_count
            or meta.jury_signature != jury_signature
            or meta.banned_signature != banned_signature
            or meta.assignment_signature != assignment_signature
        )
        articles = []
        if needs_sync:
            # Assignment ownership remains persistent in the separate DB;
            # only changed contests pay the cost of loading the full payload.
            articles = (source_query
                        .options(joinedload(models.Article.submitter),
                                 selectinload(models.Article.reviews).joinedload(models.Review.reviewer))
                        .all())
        existing_rows = ({row.article_id: row for row in mirror.query(ArticleProjection)
                          .filter_by(contest_code=contest.code).all()} if needs_sync else {})
        by_id = {}
        for article in articles:
            payload = {
                "article_id": article.id,
                "title": article.title,
                "submitted_by": article.submitter.wiki_username if article.submitter else "",
                "submitted_at": article.submitted_at.isoformat() if article.submitted_at else None,
                "status": article.status.value,
                "validation_error": article.validation_error,
                "wiki_creator": article.wiki_creator,
                "wiki_creation_date": article.wiki_creation_date.isoformat() if article.wiki_creation_date else None,
                "reviews": [
                    {
                        "reviewer": review.reviewer.wiki_username,
                        "decision": review.status.value,
                        "comment": review.comment,
                        "reviewed_at": review.timestamp.isoformat() if review.timestamp else None,
                    }
                    for review in sorted(article.reviews, key=lambda item: item.timestamp or datetime.min)
                    if review.status.value != "skipped"
                ],
            }
            row = existing_rows.get(article.id)
            if not row:
                row = ArticleProjection(article_id=article.id, contest_code=contest.code, assigned_to=None)
                mirror.add(row)
            row.contest_code = contest.code
            row.title = article.title
            row.submitted_by = payload["submitted_by"]
            row.status = payload["status"]
            row.submitted_at = article.submitted_at
            row.payload = json.dumps(payload, ensure_ascii=False)
            row.updated_at = datetime.utcnow()
            by_id[article.id] = row

        if meta is None:
            meta = ProjectionMeta(contest_code=contest.code)
            mirror.add(meta)
        meta.article_count = source_count
        meta.latest_submitted_at = latest_submitted_at
        meta.latest_review_at = latest_review_at
        meta.restriction_count = restriction_count
        meta.jury_signature = jury_signature
        meta.banned_signature = banned_signature
        meta.assignment_signature = assignment_signature
        mirror.commit()
        if needs_sync:
            # Remove rows deleted from the legacy contest, while retaining the
            # projection database for other contests.
            source_ids = set(by_id)
            for row in existing_rows.values():
                if row.article_id not in source_ids:
                    mirror.delete(row)
            mirror.commit()
        if juries and needs_sync:
            assignment_rows = list(by_id.values())
            submitter_names = {row.submitted_by for row in assignment_rows}
            user_ids = {username: user_id for user_id, username in
                        db.query(models.User.id, models.User.wiki_username)
                        .filter(models.User.wiki_username.in_(submitter_names)).all()}
            for row in assignment_rows:
                submitter_id = user_ids.get(row.submitted_by)
                assigned_id = jury_ids.get(row.assigned_to)
                if (row.status == "pending" and
                    (row.assigned_to not in juries or
                     (not contest.allow_self_review and assigned_id == submitter_id) or
                     (assigned_id, submitter_id) in restrictions)):
                    row.assigned_to = None
            pending = [r for r in assignment_rows if r.status == "pending"]
            # Rebalance all pending work.  Sorting makes assignments stable
            # between polls while the least-loaded eligible jury keeps the
            # distribution even, subject to COI restrictions.
            pending.sort(key=lambda row: row.article_id)
            # Reviewed assignments are fixed; balance new work against the
            # current total so the final jury totals stay as even as possible.
            loads = {
                jury: sum(1 for row in assignment_rows
                          if row.status != "pending" and row.assigned_to == jury)
                for jury in juries
            }
            for row in pending:
                submitter_id = user_ids.get(row.submitted_by)
                choices = [jury for jury in juries
                           if (contest.allow_self_review or jury_ids[jury] != submitter_id)
                           and (jury_ids[jury], submitter_id) not in restrictions]
                if not choices:
                    row.assigned_to = None
                    continue
                chosen = min(choices, key=lambda jury: (loads[jury], jury))
                row.assigned_to = chosen
                loads[chosen] += 1
            mirror.commit()

        query = (mirror.query(ArticleProjection)
                 .filter_by(contest_code=contest.code)
                 .order_by(ArticleProjection.article_id.asc()))
        target = view_as if current_user.role.value == "owner" and view_as else ("*" if current_user.role.value == "owner" else current_user.wiki_username)
        if target != "*":
            query = query.filter_by(assigned_to=target)
        total = query.count()
        status_counts = {
            status: query.filter_by(status=status).count()
            for status in ("pending", "accepted", "rejected", "validation_failed")
        }
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        items = [json.loads(row.payload) | {"assigned_to": row.assigned_to} for row in query.all()]
        if include_meta:
            return {
                "items": items,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + len(items) < total,
                "status_counts": status_counts,
            }
        return items
    finally:
        mirror.close()
