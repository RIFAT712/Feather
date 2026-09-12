"""Two checks on the ban path:

1. Banning a participant retires their pending entries without un-counting the
   articles a jury already judged.
2. Lifting the ban puts their restored pending entries back through the
   allocator, so they spread over the jury instead of landing back on whoever
   owned them before the ban.

Run: python test_ban_filter.py
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

import models
from main import _jury_panel_filters, unban_contest_user

engine = create_engine("sqlite://")
models.Base.metadata.create_all(engine)
db = sessionmaker(bind=engine)()

jury = models.User(wiki_username="Jury", role=models.RoleEnum.participant)
x = models.User(wiki_username="X", role=models.RoleEnum.participant)
db.add_all([jury, x])
db.flush()

# X submits 6; the jury has judged 5 of them, 1 is still pending.
for i in range(6):
    db.add(models.Article(
        contest_id=1, title=f"A{i}", submitter_id=x.id, assigned_to_id=jury.id,
        status=models.ArticleStatus.accepted if i < 5 else models.ArticleStatus.pending,
    ))
db.commit()

contest = SimpleNamespace(id=1, banned_users=[])
visible = db.query(models.Article).filter(*_jury_panel_filters(contest)).count()
judged = db.query(models.Article).filter(
    *_jury_panel_filters(contest), models.Article.status == models.ArticleStatus.accepted).count()
assert (visible, judged) == (6, 5), (visible, judged)

contest.banned_users = [SimpleNamespace(user_id=x.id)]
visible = db.query(models.Article).filter(*_jury_panel_filters(contest)).count()
judged = db.query(models.Article).filter(
    *_jury_panel_filters(contest), models.Article.status == models.ArticleStatus.accepted).count()
assert judged == 5, f"ban wiped {5 - judged} of the jury's decisions"
assert visible == 5, f"ban left {visible - 5} pending article(s) in the queue"

print("OK: ban hides the 1 pending entry, keeps all 5 decisions")

# --- unban re-levels the restored pending work -----------------------------
# Real rows this time: the allocator reads juries, restrictions and bans from
# the database, not from the contest object it is handed.
now = datetime.utcnow()
real = models.Contest(id=2, code="unban-test", name="Unban",
                     start_date=now - timedelta(days=1), end_date=now + timedelta(days=1))
db.add(real)
db.flush()
jury2 = models.User(wiki_username="Jury2", role=models.RoleEnum.participant)
db.add(jury2)
db.flush()
db.add_all([models.ContestJury(contest_id=real.id, user_id=jury.id),
            models.ContestJury(contest_id=real.id, user_id=jury2.id)])
# All 8 of X's pending entries start owned by the first jury, as they would be
# if they had been handed out before the ban.
for i in range(8):
    db.add(models.Article(contest_id=real.id, title=f"B{i}", submitter_id=x.id,
                          assigned_to_id=jury.id, status=models.ArticleStatus.pending))
ban = models.ContestBannedUser(contest_id=real.id, user_id=x.id)
db.add(ban)
db.commit()

# Through the endpoint, not the allocator directly -- the point of the check is
# that lifting a ban triggers a redistribution at all.
unban_contest_user("unban-test", ban.id, None, db)

owners = dict(db.query(models.Article.assigned_to_id, func.count(models.Article.id))
              .filter(models.Article.contest_id == real.id)
              .group_by(models.Article.assigned_to_id).all())
assert set(owners) == {jury.id, jury2.id}, f"unban left the queue on one jury: {owners}"
assert min(owners.values()) == 4 and max(owners.values()) == 4, owners

print("OK: unban spreads the 8 restored entries 4/4 across both juries")
