from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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

class ClientErrorLog(BaseModel):
    message: str
    stack_trace: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    level: Optional[str] = "error"

class ReviewRequest(BaseModel):
    decision: str  # "accepted", "rejected", "skipped"
    comment: Optional[str] = None

class ValidationRequestPayload(BaseModel):
    titles: List[str]
    submitter_username: str
    bypass_rules: bool = False
    rule_must_be_creator: bool = True
    min_bytes: int = 0
    min_words: int = 0
    min_refs: int = 0
    rule_no_redirect: bool = True
    rule_no_disambig: bool = True
    rule_mainspace_only: bool = True
    start_date: datetime
    end_date: datetime
    contest_code: str
