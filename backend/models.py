from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime
import secrets

from timeutils import utcnow

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    participant = "participant"
    owner = "owner"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    wiki_username = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.participant, nullable=False)
    oauth_access_token = Column(Text, nullable=True)
    
    articles = relationship("Article", back_populates="submitter", foreign_keys="Article.submitter_id")
    reviews = relationship("Review", back_populates="reviewer")
    jury_assignments = relationship("ContestJury", back_populates="user")

def generate_contest_code():
    return secrets.token_hex(3) # 6 chars

class Contest(Base):
    __tablename__ = 'contests'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, default=generate_contest_code, nullable=False)
    name = Column(String(255), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    rule_must_be_creator = Column(Boolean, default=True, nullable=False)
    min_bytes = Column(Integer, default=0, nullable=False)
    min_words = Column(Integer, default=0, nullable=False)
    min_refs = Column(Integer, default=0, nullable=False)
    rule_no_redirect = Column(Boolean, default=True, nullable=False)
    rule_no_disambig = Column(Boolean, default=True, nullable=False)
    rule_mainspace_only = Column(Boolean, default=True, nullable=False)
    allow_self_review = Column(Boolean, default=False, nullable=False)
    add_talk_template = Column(Boolean, default=False, nullable=False)
    talk_template_name = Column(String(255), nullable=True)
    include_talk_header = Column(Boolean, default=True, nullable=False)
    
    articles = relationship("Article", back_populates="contest")
    juries = relationship("ContestJury", back_populates="contest")
    jury_restrictions = relationship("ContestJuryRestriction", back_populates="contest", cascade="all, delete-orphan")
    banned_users = relationship("ContestBannedUser", back_populates="contest", cascade="all, delete-orphan")

class ContestJury(Base):
    __tablename__ = 'contest_jury'
    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    contest = relationship("Contest", back_populates="juries")
    # Eager: a ContestJury row is never useful without the user behind it, and
    # get_eligible_juries() -- called on every jury-panel request -- walks
    # contest.juries reading j.user.wiki_username off each one. Lazily that is
    # one SELECT per jury member, which costs nothing against local SQLite and
    # is a separate network round trip each against Toolforge's ToolsDB.
    user = relationship("User", back_populates="jury_assignments", lazy="joined")

class ContestJuryRestriction(Base):
    __tablename__ = 'contest_jury_restrictions'
    __table_args__ = (UniqueConstraint('contest_id', 'jury_user_id', 'submitter_user_id', name='uq_contest_jury_submitter'),)
    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False, index=True)
    jury_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    submitter_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    contest = relationship("Contest", back_populates="jury_restrictions")
    jury_user = relationship("User", foreign_keys=[jury_user_id])
    submitter_user = relationship("User", foreign_keys=[submitter_user_id])

class ContestBannedUser(Base):
    """A submitter whose articles are hidden from this contest's review-v2 panel."""
    __tablename__ = 'contest_banned_users'
    __table_args__ = (UniqueConstraint('contest_id', 'user_id', name='uq_contest_banned_user'),)
    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    contest = relationship("Contest", back_populates="banned_users")
    user = relationship("User")

class ArticleStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    validation_failed = "validation_failed"

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True, nullable=False)
    submitter_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False)
    status = Column(Enum(ArticleStatus), default=ArticleStatus.pending, nullable=False)
    validation_error = Column(String(500), nullable=True)     # error reason if validation_failed
    wiki_creation_date = Column(DateTime, nullable=True)   # date article was created on Wikipedia
    wiki_creator = Column(String(255), nullable=True)        # who created it on Wikipedia
    submitted_at = Column(DateTime, default=utcnow) # date it was submitted to this contest
    assigned_to_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # jury queue ownership

    submitter = relationship("User", back_populates="articles", foreign_keys=[submitter_id])
    contest = relationship("Contest", back_populates="articles")
    reviews = relationship("Review", back_populates="article")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])

class ReviewStatus(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"
    skipped = "skipped"

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(Enum(ReviewStatus), nullable=False)
    comment = Column(String(1000), nullable=True)
    timestamp = Column(DateTime, default=utcnow)
    
    article = relationship("Article", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")

class ArticleLock(Base):
    """DB-backed per-article review lock. Replaces the in-memory article_locks dict.
    Visible across all workers/processes. Auto-expires after 15 minutes (enforced in queries).
    Uses article_id as primary key so only one lock row per article can exist.
    """
    __tablename__ = 'article_locks'
    article_id = Column(Integer, ForeignKey('articles.id'), primary_key=True, nullable=False)
    locked_by  = Column(String(255), nullable=False)   # wiki_username of the reviewer holding the lock
    locked_at  = Column(DateTime, nullable=False, default=utcnow)

    article = relationship("Article")

class SystemLog(Base):
    __tablename__ = 'system_logs'
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(50), default="error", nullable=False)      # error, warning, info
    source = Column(String(50), default="frontend", nullable=False)   # frontend, backend
    message = Column(String(2000), nullable=False)
    stack_trace = Column(String(4000), nullable=True)
    url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    username = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=utcnow)

class DeletedArticleLog(Base):
    """Permanent record of every article removed from a contest.

    Deletion used to leave nothing behind but a SystemLog line with a count
    ("removed 500 article(s)"), so there was no way to tell *which* pages went
    or to put them back. One row is written here per deleted article, before
    the row is destroyed, capturing enough to identify and re-submit it.

    Deliberately not a foreign key to articles.id -- the article is gone. The
    original id is kept as a plain integer for cross-referencing older logs.
    This table is never auto-pruned; it is the audit trail.
    """
    __tablename__ = 'deleted_article_log'
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, nullable=False, index=True)   # id the article had before deletion
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False, index=True)
    contest_code = Column(String(50), nullable=True)
    title = Column(String(255), nullable=False)
    submitted_by = Column(String(255), nullable=True)          # wiki_username of the submitter
    wiki_creator = Column(String(255), nullable=True)
    wiki_creation_date = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)                 # status at the moment of deletion
    validation_error = Column(String(500), nullable=True)
    review_count = Column(Integer, default=0, nullable=False)  # reviews destroyed along with it
    deleted_by = Column(String(255), nullable=False)           # wiki_username who performed the delete
    deleted_at = Column(DateTime, default=utcnow, nullable=False, index=True)

class TalkPageJob(Base):

    """One queued talk-page template edit.

    Talk-page templates used to be written by a FastAPI BackgroundTask that
    looped over an entire bulk submission and edited every page back to back:
    a large submission tripped MediaWiki's edit rate limit, and a restart
    mid-batch dropped the remaining edits with no record they were ever owed.
    Each edit is now a row here, drained one at a time by
    talk_queue_worker.py, so the work survives restarts and is inspectable.
    """
    __tablename__ = 'talk_page_jobs'
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(String(20), default="queued", nullable=False, index=True)  # queued, processing, done, failed
    attempts = Column(Integer, default=0, nullable=False)
    error = Column(String(500), nullable=True)
    # Snapshot of the submitter's OAuth token at enqueue time: the edit is
    # attributed to them, and the worker runs long after their request ended.
    access_token = Column(Text, nullable=False)
    submitted_by = Column(String(255), nullable=False)  # wiki_username, for edit summary/logging
    created_at = Column(DateTime, default=utcnow)
    processed_at = Column(DateTime, nullable=True)

    article = relationship("Article")
    contest = relationship("Contest")
