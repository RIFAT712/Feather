"""Smoke test for the API surface. Run: python test_api.py

Two layers, both aimed at the same failure:

1. ROUTES -- the exact set of paths FastAPI has registered, compared against the
   list below. A deletion that takes one line too many can strip an `@app.get`
   decorator off the *next* function; the module still imports, the function is
   still defined, and nothing looks wrong until a page comes up empty. That is
   how /jury/review-v2 lost its only source of articles. Adding or removing a
   route means editing EXPECTED_ROUTES on purpose.

2. GETS -- every read endpoint actually called against the local database, so a
   route that is registered but raises is caught too.

Read-only: no POST/PUT/DELETE is exercised. The one write that does happen is
rebalance_pending_articles(), which the jury-panel reads call themselves.

Runs against whatever backend/.env points at (SQLite locally).
"""
import sys

import main
from fastapi.testclient import TestClient
from database import get_db

EXPECTED_ROUTES = {
    ("DELETE", "/api/admin/contests/{code}"),
    ("DELETE", "/api/admin/contests/{code}/banned-users/{ban_id}"),
    ("DELETE", "/api/admin/contests/{code}/jury-restrictions/{restriction_id}"),
    ("DELETE", "/api/articles/{article_id}"),
    ("DELETE", "/api/articles/{article_id}/lock"),
    ("GET", "/api/admin/backup/download"),
    ("GET", "/api/admin/contests/{code}/banned-users"),
    ("GET", "/api/admin/contests/{code}/export/csv"),
    ("GET", "/api/admin/contests/{code}/export/json"),
    ("GET", "/api/admin/contests/{code}/export/wikitable"),
    ("GET", "/api/admin/contests/{code}/jury-restrictions"),
    ("GET", "/api/admin/contests/{code}/talk-queue"),
    ("GET", "/api/admin/db-diagnostics"),
    ("GET", "/api/admin/stats"),
    ("GET", "/api/contests"),
    ("GET", "/api/contests/{code}"),
    ("GET", "/api/contests/{code}/deleted-articles"),
    ("GET", "/api/contests/{code}/log"),
    ("GET", "/api/contests/{code}/my-role"),
    ("GET", "/api/contests/{code}/results"),
    ("GET", "/api/contests/{code}/stats"),
    ("GET", "/api/contests/{code}/submitters"),
    ("GET", "/api/contests/{code}/user-created-articles"),
    ("GET", "/api/contests/{code}/users/{username}"),
    ("GET", "/api/jury-panel/contests/{code}/articles/page"),
    ("GET", "/api/jury-panel/contests/{code}/progress"),
    ("GET", "/api/jury-panel/contests/{code}/queue-stats"),
    ("GET", "/api/logs"),
    ("GET", "/api/me"),
    ("GET", "/api/system/status"),
    ("GET", "/api/users/{username}/profile"),
    ("GET", "/auth/callback"),
    ("GET", "/auth/login"),
    ("POST", "/api/admin/assign-jury"),
    ("POST", "/api/admin/contests"),
    ("POST", "/api/admin/contests/{code}/banned-users"),
    ("POST", "/api/admin/contests/{code}/integrity-check"),
    ("POST", "/api/admin/contests/{code}/jury-restrictions"),
    ("POST", "/api/admin/contests/{code}/redistribute"),
    ("POST", "/api/admin/contests/{code}/talk-queue/backfill"),
    ("POST", "/api/admin/contests/{code}/talk-queue/retry-failed"),
    ("POST", "/api/admin/force-migration"),
    ("POST", "/api/admin/unassign-jury"),
    ("POST", "/api/articles/bulk-delete"),
    ("POST", "/api/articles/bulk-review"),
    ("POST", "/api/articles/{article_id}/lock"),
    ("POST", "/api/articles/{article_id}/review"),
    ("POST", "/api/articles/{article_id}/review/undo"),
    ("POST", "/api/submit-bulk"),
    ("POST", "/auth/logout"),
    ("PUT", "/api/admin/contests/{code}"),
}

# Hits the Wikimedia replica / MediaWiki API, which a clean checkout has no
# credentials for. Registration is still asserted above.
NEEDS_WIKI = {"/api/contests/{code}/user-created-articles"}
# Writes a database snapshot to disk as a side effect.
HAS_SIDE_EFFECTS = {"/api/admin/backup/download"}
# Not callable without a real OAuth round trip.
AUTH_FLOW = {"/auth/callback", "/auth/login", "/auth/logout"}


def registered_routes():
    out = set()
    for r in main.app.routes:
        methods = getattr(r, "methods", None)
        if methods and r.path.startswith(("/api", "/auth")):
            for m in methods - {"HEAD", "OPTIONS"}:
                out.add((m, r.path))
    return out


def check_routes():
    actual = registered_routes()
    missing = EXPECTED_ROUTES - actual
    extra = actual - EXPECTED_ROUTES
    assert not missing, "routes DISAPPEARED (decorator lost?): %s" % sorted(missing)
    assert not extra, "routes ADDED without updating EXPECTED_ROUTES: %s" % sorted(extra)
    print("  routes: %d registered, all accounted for" % len(actual))


def fixtures():
    db = next(get_db())
    try:
        contest = db.query(main.models.Contest).first()
        owner = db.query(main.models.User).filter_by(
            role=main.models.RoleEnum.owner).first()
        article = db.query(main.models.Article).first()
        return (contest.code if contest else None,
                owner.wiki_username if owner else None,
                article.id if article else None)
    finally:
        db.close()


def check_gets(client, code, username):
    """Call every registered GET with real parameters."""
    substitutions = {"{code}": code, "{username}": username}
    # Keep pages small: the local database has a five-figure contest in it.
    query = {
        "/api/contests/{code}/log": "?page_size=25",
        "/api/jury-panel/contests/{code}/articles/page": "?page_size=25",
        "/api/contests/{code}/deleted-articles": "?page_size=25",
    }
    checked = 0
    for method, path in sorted(EXPECTED_ROUTES):
        if method != "GET" or path in NEEDS_WIKI | HAS_SIDE_EFFECTS | AUTH_FLOW:
            continue
        url = path
        for token, value in substitutions.items():
            url = url.replace(token, value)
        assert "{" not in url, "unsubstituted parameter in %s" % url
        res = client.get(url + query.get(path, ""))
        assert res.status_code == 200, "GET %s -> %s %s" % (
            url, res.status_code, res.text[:160])
        checked += 1
    print("  gets: %d endpoints returned 200" % checked)


def check_review_queue(client, code):
    """The exact request /jury/review-v2 makes for its article list."""
    res = client.get("/api/jury-panel/contests/%s/articles/page?page_size=25" % code)
    assert res.status_code == 200, res.status_code
    body = res.json()
    for key in ("items", "total", "status_counts", "has_more", "next_after_id"):
        assert key in body, "missing %r in %s" % (key, sorted(body))
    assert isinstance(body["items"], list)
    assert body["total"] > 0, "no articles in the queue -- review-v2 would render empty"
    assert body["items"], "total=%d but the page is empty" % body["total"]
    first = body["items"][0]
    for key in ("article_id", "title", "status"):
        assert key in first, "missing %r in %s" % (key, sorted(first))
    print("  review queue: %d articles, %d on the first page"
          % (body["total"], len(body["items"])))


def check_exports(client, code):
    assert main.translate_status("accepted") == "গৃহীত"
    assert main.translate_status("rejected") == "প্রত্যাখ্যাত"
    assert main.translate_status("pending") == "অপেক্ষমাণ"
    assert main.translate_status("validation_failed") == "যাচাইকরণ ব্যর্থ"
    # Anything the enum grows later must pass through, not vanish.
    assert main.translate_status("skipped") == "skipped"

    # All three formats are reachable from the UI: ContestResult.vue offers csv,
    # json and wikitable side by side, and AdminDashboard.vue offers csv.
    for fmt in ("csv", "json", "wikitable"):
        assert client.get("/api/admin/contests/__nope__/export/%s" % fmt).status_code == 404
    for fmt, marker in (("csv", "Submitter"), ("wikitable", "{|"), ("json", "contest_code")):
        for mode in ("summary", "detailed"):
            res = client.get("/api/admin/contests/%s/export/%s?mode=%s" % (code, fmt, mode))
            assert res.status_code == 200, (fmt, mode, res.status_code)
            assert marker in res.text, (fmt, mode, res.text[:200])
    detailed = client.get("/api/admin/contests/%s/export/json?mode=detailed" % code).json()
    assert detailed["articles"], "detailed json export has no articles"
    summary = client.get("/api/admin/contests/%s/export/json?mode=summary" % code).json()
    assert summary["submitter_stats"], "summary json export has no submitter stats"
    print("  exports: csv + json + wikitable, summary + detailed")


def demo():
    check_routes()

    code, username, _article_id = fixtures()
    if not code or not username:
        print("  no contest/owner in this database - skipped the live checks")
        return

    db = next(get_db())
    owner = db.query(main.models.User).filter_by(wiki_username=username).first()
    # Authentication is not what's under test; the handlers are.
    main.app.dependency_overrides[main.get_current_user] = lambda: owner
    main.app.dependency_overrides[main.get_owner_user] = lambda: owner
    try:
        client = TestClient(main.app)
        check_gets(client, code, username)
        check_review_queue(client, code)
        check_exports(client, code)
    finally:
        main.app.dependency_overrides.clear()
        db.close()

    print("all ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    demo()
