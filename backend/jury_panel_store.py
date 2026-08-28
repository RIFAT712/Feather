"""Separate review-database projection used by the new jury-panel endpoint."""
import json
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func, or_, text
from sqlalchemy.orm import declarative_base, joinedload, sessionmaker, selectinload

Base = declarative_base()
DB_PATH = Path(__file__).resolve().parent / "jury_panel.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 60},
    pool_size=3,
    max_overflow=5,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_sync_lock = threading.Lock()


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

# Keep jury refreshes from blocking normal reads from the projection DB.
with engine.begin() as connection:
    connection.execute(text("PRAGMA journal_mode=WAL"))
    connection.execute(text("PRAGMA busy_timeout=60000"))

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
    # Several page/progress requests can arrive together on a fresh deploy.
    # Serializing the rebuild prevents duplicate projection_meta inserts and
    # avoids hammering the remote MariaDB connection with parallel full reads.
    _sync_lock.acquire()
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
        # Catches both truly-unassigned rows (assigned_to IS NULL) and rows still
        # pointing at a name that is no longer a valid jury for this contest — a
        # removed jury member, or a stale value left behind by an older allocator.
        # Checking NULL alone missed that second case: those rows never counted as
        # "unassigned," so needs_assignment stayed false and they were stuck with
        # whatever a much older, capped allocator run had given them, forever.
        stuck_pending_query = mirror.query(ArticleProjection).filter(
            ArticleProjection.contest_code == contest.code,
            ArticleProjection.status == "pending",
        )
        if juries:
            stuck_pending_query = stuck_pending_query.filter(
                or_(ArticleProjection.assigned_to.is_(None), ~ArticleProjection.assigned_to.in_(juries))
            )
        else:
            stuck_pending_query = stuck_pending_query.filter(ArticleProjection.assigned_to.is_(None))
        unassigned_pending = stuck_pending_query.count()
        restriction_count = len(restrictions)
        jury_signature = "\x1f".join(sorted(juries))
        restriction_signature = "\x1f".join(f"{jury_id}:{submitter_id}" for jury_id, submitter_id in sorted(restrictions))
        # Version this fingerprint when assignment semantics change so older
        # projections are rebuilt and reviewed-page ownership is repaired once.
        # Bump this whenever assignment rules change. v3 forces existing
        # under-assigned projections (from the old 50-item rollout) to be
        # rebuilt across the complete contest, not just the first page.
        assignment_signature = f"v=3\x1eself={int(bool(contest.allow_self_review))}\x1e{restriction_signature}"
        banned_signature = "\x1f".join(sorted(
            row.user.wiki_username for row in contest.banned_users if row.user
        ))
        assignment_rules_changed = (
            meta is None
            or meta.jury_signature != jury_signature
            or meta.restriction_count != restriction_count
            or meta.banned_signature != banned_signature
            or meta.assignment_signature != assignment_signature
        )
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
        # Self-heal projections created by the old capped allocator. The
        # source mirror can be current while thousands of pending rows still
        # have no jury assignment.
        needs_assignment = needs_sync or bool(juries and unassigned_pending)
        by_id = {}
        deleted_articles = False
        if needs_sync:
            # Do not materialize the whole contest as ORM objects and do not
            # commit once per article.  A fresh Toolforge projection can have
            # tens of thousands of rows, so mirror it in bounded batches.
            existing_rows = {row.article_id: row.assigned_to for row in mirror.query(ArticleProjection)
                             .filter_by(contest_code=contest.code).all()}
            existing_ids = set(existing_rows.keys())
            batch = []

            def flush_batch(items):
                if not items:
                    return
                inserts = []
                updates = []
                now = datetime.utcnow()
                for article in items:
                    submitted_by = article.submitter.wiki_username if article.submitter else ""
                    non_skipped_reviews = sorted(
                        (review for review in article.reviews if review.status.value != "skipped"),
                        key=lambda item: item.timestamp or datetime.min,
                    )
                    last_review = non_skipped_reviews[-1] if non_skipped_reviews else None
                    reviewed_by = (
                        last_review.reviewer.wiki_username
                        if last_review and last_review.reviewer else None
                    )
                    payload = {
                        "article_id": article.id,
                        "title": article.title,
                        "submitted_by": submitted_by,
                        "submitted_at": article.submitted_at.isoformat() if article.submitted_at else None,
                        "status": article.status.value,
                        "validation_error": article.validation_error,
                        "wiki_creator": article.wiki_creator,
                        "wiki_creation_date": article.wiki_creation_date.isoformat() if article.wiki_creation_date else None,
                        # The reviewer owns the page after judging. This lets a
                        # rebuild recover the assignment from the source DB,
                        # even if the projection was recreated.
                        "reviewed_by": reviewed_by,
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
                    values = {
                        "article_id": article.id,
                        "contest_code": contest.code,
                        "title": article.title,
                        "submitted_by": submitted_by,
                        "status": payload["status"],
                        "submitted_at": article.submitted_at,
                        "payload": json.dumps(payload, ensure_ascii=False),
                        "assigned_to": reviewed_by if reviewed_by in juries else existing_rows.get(article.id),
                        "updated_at": now,
                    }
                    source_ids.add(article.id)
                    by_id[article.id] = values
                    (updates if article.id in existing_rows else inserts).append(values)
                if inserts:
                    mirror.bulk_insert_mappings(ArticleProjection, inserts)
                if updates:
                    mirror.bulk_update_mappings(ArticleProjection, updates)
                mirror.commit()

            # Mirror articles that aren't in the projection yet first, scoped to
            # just those ids, before touching anything already mirrored. A
            # request that dies partway through (Toolforge proxy/worker
            # timeout) used to always restart this loop from the top of the
            # full contest query on the next attempt, re-doing the same
            # already-mirrored rows before it could reach anything new — on a
            # large contest that backlog never shrank. Batches still commit as
            # they go, and mirror_count vs. source_count keeps needs_sync true
            # across requests, so bounding + prioritizing missing rows here
            # makes every request a guaranteed step of forward progress.
            all_source_ids = [row[0] for row in source_query.with_entities(models.Article.id).all()]
            source_ids = set(all_source_ids)
            missing_ids = [aid for aid in all_source_ids if aid not in existing_ids]
            SYNC_BATCH_LIMIT = 4000
            ids_to_fetch = missing_ids[:SYNC_BATCH_LIMIT]

            if ids_to_fetch:
                missing_query = source_query.options(
                    joinedload(models.Article.submitter),
                    selectinload(models.Article.reviews).joinedload(models.Review.reviewer)
                ).filter(models.Article.id.in_(ids_to_fetch))
                for article in missing_query.yield_per(500):
                    batch.append(article)
                    if len(batch) >= 500:
                        flush_batch(batch)
                        batch = []
                flush_batch(batch)
                batch = []
                # flush_batch decides insert-vs-update per row from
                # existing_rows, captured before this pass ran. Fold the rows
                # it just inserted back into existing_rows so the refresh pass
                # below (which may run immediately after, in this same
                # request) correctly treats them as updates instead of
                # attempting to insert the same article_id twice.
                for aid in ids_to_fetch:
                    if aid in by_id:
                        existing_rows[aid] = by_id[aid]["assigned_to"]

            # Only refresh already-mirrored rows (for status/review changes)
            # once this request has cleared the entire backlog of missing rows
            # — i.e. ids_to_fetch covered all of missing_ids, not just a bounded
            # slice of it. Waiting for "not missing_ids" (computed before this
            # request ran) meant the very request that closed the last of the
            # backlog still deferred refreshing review/status data by one more
            # request-cycle, even though it's now safe to do immediately.
            if len(missing_ids) <= SYNC_BATCH_LIMIT:
                for article in (source_query
                                .options(joinedload(models.Article.submitter),
                                         selectinload(models.Article.reviews).joinedload(models.Review.reviewer))
                                .yield_per(500)):
                    batch.append(article)
                    if len(batch) >= 500:
                        flush_batch(batch)
                        batch = []
                flush_batch(batch)

            # Remove rows deleted from the source contest without a giant
            # SQLite IN clause (and retain projections for other contests).
            stale_ids = set(existing_rows) - source_ids
            deleted_articles = bool(stale_ids)
            for start in range(0, len(stale_ids), 500):
                mirror.query(ArticleProjection).filter(
                    ArticleProjection.contest_code == contest.code,
                    ArticleProjection.article_id.in_(list(stale_ids)[start:start + 500]),
                ).delete(synchronize_session=False)
            mirror.commit()

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
        if juries and needs_assignment:
            assignment_rows = mirror.query(ArticleProjection).filter_by(contest_code=contest.code).all()
            submitter_names = {row.submitted_by for row in assignment_rows}
            user_ids = {username: user_id for user_id, username in
                        db.query(models.User.id, models.User.wiki_username)
                        .filter(models.User.wiki_username.in_(submitter_names)).all()}
            for row in assignment_rows:
                reviewed_by = json.loads(row.payload).get("reviewed_by")
                if row.status != "pending":
                    # Reviewed pages stay with the jury member who made the
                    # decision. They count toward that member's load when new
                    # pending pages are distributed below.
                    row.assigned_to = reviewed_by if reviewed_by in juries else None
                submitter_id = user_ids.get(row.submitted_by)
                assigned_id = jury_ids.get(row.assigned_to)
                if (row.status == "pending" and
                    (assignment_rules_changed or deleted_articles or
                     row.assigned_to not in juries or
                     (not contest.allow_self_review and assigned_id == submitter_id) or
                     (assigned_id, submitter_id) in restrictions)):
                    row.assigned_to = None
            # A jury/rule change rebalances the whole unreviewed pool. A new
            # article only contributes an unassigned row, so existing pending
            # work stays put and the new row goes to the least-loaded jury.
            pending = [r for r in assignment_rows
                       if r.status == "pending" and r.assigned_to is None]
            pending.sort(key=lambda row: row.article_id)
            # Count both reviewed ownership and retained pending assignments.
            # This makes a newly added jury immediately eligible for work while
            # preventing a new submission from moving the whole queue.
            loads = {
                jury: sum(1 for row in assignment_rows
                          if row.assigned_to == jury)
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
            mirror.bulk_update_mappings(
                ArticleProjection,
                [{"article_id": row.article_id, "assigned_to": row.assigned_to} for row in assignment_rows],
            )
            mirror.commit()
            assignment_counts = {
                jury: sum(1 for row in assignment_rows if row.assigned_to == jury)
                for jury in juries
            }
            print(
                f"[Jury Panel] Distributed {len(assignment_rows)} articles for "
                f"{contest.code}: {assignment_counts}; "
                f"unassigned_pending={sum(1 for row in assignment_rows if row.status == 'pending' and row.assigned_to is None)}"
            )

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
        _sync_lock.release()
