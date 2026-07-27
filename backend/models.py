from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime
import secrets

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    participant = "participant"
    owner = "owner"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    wiki_username = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.participant, nullable=False)
    
    articles = relationship("Article", back_populates="submitter")
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

class ContestJury(Base):
    __tablename__ = 'contest_jury'
    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey('contests.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    contest = relationship("Contest", back_populates="juries")
    user = relationship("User", back_populates="jury_assignments")

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
    submitted_at = Column(DateTime, default=datetime.utcnow) # date it was submitted to this contest
    
    submitter = relationship("User", back_populates="articles")
    contest = relationship("Contest", back_populates="articles")
    reviews = relationship("Review", back_populates="article")

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
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    article = relationship("Article", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")
