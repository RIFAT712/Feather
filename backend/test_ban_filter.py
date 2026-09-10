"""One check: banning a participant must retire their pending entries without
un-counting the articles a jury already judged.

Run: python test_ban_filter.py
"""
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from main import _jury_panel_filters

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
