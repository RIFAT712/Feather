from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import sqlite3
import os
import configparser

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

def get_toolforge_credentials():
    cnf_path = os.path.expanduser("~/replica.my.cnf")
    if os.path.exists(cnf_path):
        try:
            config = configparser.ConfigParser()
            config.read(cnf_path)
            if 'client' in config:
                user = config['client'].get('user', '').strip("'\"")
                password = config['client'].get('password', '').strip("'\"")
                return user, password
        except Exception as e:
            print(f"Error reading replica.my.cnf: {e}")
    return None, None

DB_NAME = os.getenv("DB_NAME", f"{os.getenv('TOOL_TOOLSDB_USER')}__app" if os.getenv("TOOL_TOOLSDB_USER") else None)
DB_HOST = os.getenv("DB_HOST", "tools.db.svc.wikimedia.cloud")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", os.getenv("TOOL_TOOLSDB_USER"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("TOOL_TOOLSDB_PASSWORD"))

# Fallback to replica.my.cnf if toolforge env vars are missing
# NOTE: Do NOT fall back to replica.my.cnf for the app DB —
# those are read-only replica credentials. App DB requires TOOL_TOOLSDB_USER/PASSWORD.

if DB_NAME and DB_USER:
    # Use MySQL/MariaDB for Toolforge
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )
else:
    # Fallback to SQLite
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # Enable TRUNCATE journal mode once at startup on the database file (compatible with NFS on Toolforge)
    try:
        db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=TRUNCATE")
        conn.close()
    except Exception as e:
        print(f"Could not enable TRUNCATE mode: {e}")
        
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False, "timeout": 60},
        poolclass=NullPool
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

def run_auto_migrations(db_engine):
    """Idempotent schema migrations. Uses IF NOT EXISTS so it's safe to run every startup."""
    try:
        from sqlalchemy import inspect, text
        is_mysql = "mysql" in str(db_engine.url)
        inspector = inspect(db_engine)
        existing_tables = inspector.get_table_names()
        print(f"[Migration] Starting. is_mysql={is_mysql}, tables={existing_tables}")

        def add_col_if_missing(table, col_name, col_type):
            """Adds a column using IF NOT EXISTS (MariaDB) or manual check (SQLite)."""
            if is_mysql:
                sql = f"ALTER TABLE `{table}` ADD COLUMN IF NOT EXISTS `{col_name}` {col_type}"
                with db_engine.connect() as conn:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"[Migration] OK: {sql}")
                    except Exception as ex:
                        print(f"[Migration] WARN ({table}.{col_name}): {ex}")
            else:
                # SQLite: inspect first since it doesn't support IF NOT EXISTS on ALTER
                cols = [c['name'] for c in inspect(db_engine).get_columns(table)]
                if col_name not in cols:
                    sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    with db_engine.connect() as conn:
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                            print(f"[Migration] OK: {sql}")
                        except Exception as ex:
                            print(f"[Migration] WARN ({table}.{col_name}): {ex}")
                else:
                    print(f"[Migration] Skip: {table}.{col_name} already exists")

        # ── users table ──────────────────────────────────────────────────
        if 'users' in existing_tables:
            # Add column if missing (new installs)
            add_col_if_missing('users', 'oauth_access_token', 'TEXT')
            # Widen existing VARCHAR(1000) → TEXT (Wikimedia OAuth2 JWTs exceed 1000 chars)
            if is_mysql:
                with db_engine.connect() as conn:
                    try:
                        conn.execute(text("ALTER TABLE `users` MODIFY COLUMN `oauth_access_token` TEXT"))
                        conn.commit()
                        print("[Migration] OK: MODIFY COLUMN users.oauth_access_token → TEXT")
                    except Exception as ex:
                        print(f"[Migration] WARN modifying oauth_access_token type: {ex}")
        else:
            print("[Migration] 'users' table not found — create_all will handle it.")

        # ── contests table ───────────────────────────────────────────────
        if 'contests' in existing_tables:
            for col_name, col_type in [
                ("min_bytes",           "INTEGER DEFAULT 0"),
                ("min_words",           "INTEGER DEFAULT 0"),
                ("min_refs",            "INTEGER DEFAULT 0"),
                ("rule_no_redirect",    "BOOLEAN DEFAULT 1"),
                ("rule_no_disambig",    "BOOLEAN DEFAULT 1"),
                ("rule_mainspace_only", "BOOLEAN DEFAULT 1"),
                ("allow_self_review",   "BOOLEAN DEFAULT 0"),
                ("add_talk_template",   "BOOLEAN DEFAULT 0"),
                ("talk_template_name",  "VARCHAR(255)"),
                ("include_talk_header", "BOOLEAN DEFAULT 1"),
            ]:
                add_col_if_missing('contests', col_name, col_type)
        else:
            print("[Migration] 'contests' table not found — create_all will handle it.")

        # ── article_locks table ──────────────────────────────────────────
        if 'article_locks' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    pk_syntax = "AUTO_INCREMENT PRIMARY KEY" if is_mysql else "PRIMARY KEY"
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS article_locks (
                            article_id INTEGER NOT NULL PRIMARY KEY,
                            locked_by  VARCHAR(255) NOT NULL,
                            locked_at  DATETIME NOT NULL,
                            FOREIGN KEY(article_id) REFERENCES articles(id)
                        )
                    """))
                    conn.commit()
                    print("[Migration] Created 'article_locks' table.")
                except Exception as ex:
                    print(f"[Migration] WARN creating article_locks: {ex}")
        else:
            print("[Migration] 'article_locks' table already exists.")

        # ── system_logs table ────────────────────────────────────────────
        if 'system_logs' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    auto_inc = "AUTO_INCREMENT" if is_mysql else ""
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS system_logs (
                            id          INTEGER NOT NULL {auto_inc} PRIMARY KEY,
                            level       VARCHAR(50)   NOT NULL DEFAULT 'error',
                            source      VARCHAR(50)   NOT NULL DEFAULT 'frontend',
                            message     VARCHAR(2000) NOT NULL,
                            stack_trace VARCHAR(4000),
                            url         VARCHAR(500),
                            user_agent  VARCHAR(500),
                            username    VARCHAR(255),
                            timestamp   DATETIME
                        )
                    """))
                    conn.commit()
                    print("[Migration] Created 'system_logs' table.")
                except Exception as ex:
                    print(f"[Migration] WARN creating system_logs: {ex}")
        else:
            print("[Migration] 'system_logs' table already exists.")

        print("[Migration] All done.")
    except Exception as e:
        print(f"[Migration] FATAL error: {e}")

run_auto_migrations(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


WIKI_DB_HOST = os.getenv("WIKI_DB_HOST", "bnwiktionary.web.db.svc.wikimedia.cloud")
WIKI_DB_NAME = os.getenv("WIKI_DB_NAME", "bnwiktionary_p")
WIKI_DB_PORT = int(os.getenv("WIKI_DB_PORT", "3306"))
WIKI_DB_USER = os.getenv("WIKI_DB_USER", os.getenv("TOOL_REPLICA_USER"))
WIKI_DB_PASSWORD = os.getenv("WIKI_DB_PASSWORD", os.getenv("TOOL_REPLICA_PASSWORD"))

if not WIKI_DB_USER or not WIKI_DB_PASSWORD:
    tf_user, tf_pass = get_toolforge_credentials()
    if tf_user and tf_pass:
        WIKI_DB_USER = WIKI_DB_USER or tf_user
        WIKI_DB_PASSWORD = WIKI_DB_PASSWORD or tf_pass

wiki_engine = None
if WIKI_DB_USER and WIKI_DB_PASSWORD:
    try:
        wiki_db_url = f"mysql+pymysql://{WIKI_DB_USER}:{WIKI_DB_PASSWORD}@{WIKI_DB_HOST}:{WIKI_DB_PORT}/{WIKI_DB_NAME}?charset=utf8mb4"
        wiki_engine = create_engine(
            wiki_db_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        print(f"[DB] Wiki replica engine initialized: {WIKI_DB_HOST}/{WIKI_DB_NAME} as {WIKI_DB_USER}")
    except Exception as e:
        print(f"[DB] Could not initialize Wiki Replica DB engine: {e}")
else:
    print(f"[DB] Wiki replica engine NOT initialized — WIKI_DB_USER={WIKI_DB_USER!r}, TOOL_REPLICA_USER={os.getenv('TOOL_REPLICA_USER')!r}, replica.my.cnf exists={os.path.exists(os.path.expanduser('~/replica.my.cnf'))}")


def query_wiki_replica_batch(titles: list) -> dict:
    """
    Queries the Wikimedia MariaDB replica for bnwiktionary_p to validate article creation date & creator.
    Returns a dict: { original_title: { "exists": True, "wiki_creator": str, "wiki_creation_date": datetime, "timestamp_str": str } }
    Returns None if the replica engine is unavailable or query fails (triggering HTTP API fallback).
    """
    if not wiki_engine or not titles:
        print(f"[Replica] Skipping: wiki_engine={wiki_engine is not None}, titles_count={len(titles) if titles else 0}")
        return None

    title_map = {}  # db_fmt -> original_title
    db_titles_set = set()
    for t in titles:
        clean = t.strip()
        if clean:
            db_fmt = clean.replace(" ", "_")
            if db_fmt not in title_map:
                title_map[db_fmt] = clean
            db_titles_set.add(db_fmt)
            # Add capitalized title variant (MediaWiki standard title capitalization)
            db_fmt_cap = db_fmt[0].upper() + db_fmt[1:] if db_fmt else db_fmt
            if db_fmt_cap not in title_map:
                title_map[db_fmt_cap] = clean
            db_titles_set.add(db_fmt_cap)

    db_titles = list(db_titles_set)
    if not db_titles:
        return {}

    results = {}
    chunk_size = 500

    try:
        with wiki_engine.connect() as conn:
            from sqlalchemy import text, bindparam
            for i in range(0, len(db_titles), chunk_size):
                chunk = db_titles[i:i + chunk_size]
                query = text("""
                    SELECT 
                        CONVERT(p.page_title USING utf8mb4) as page_title,
                        p.page_namespace,
                        p.page_is_redirect,
                        p.page_len,
                        CONVERT(r.rev_timestamp USING utf8mb4) as rev_timestamp,
                        CONVERT(a.actor_name USING utf8mb4) as actor_name
                    FROM page p
                    JOIN revision r ON (r.rev_page = p.page_id AND r.rev_parent_id = 0)
                    JOIN actor a ON r.rev_actor = a.actor_id
                    WHERE p.page_namespace = 0
                      AND (CONVERT(p.page_title USING utf8mb4) IN :titles OR p.page_title IN :titles)
                """).bindparams(bindparam("titles", expanding=True))
                res = conn.execute(query, {"titles": list(chunk)})
                for row in res:
                    db_title = row.page_title
                    orig_title = title_map.get(db_title, title_map.get(db_title.replace("_", " "), db_title.replace("_", " ")))
                    ts_str = row.rev_timestamp
                    wiki_date = None
                    iso_str = None
                    if ts_str:
                        try:
                            wiki_date = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
                            iso_str = wiki_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                        except Exception:
                            pass
                    
                    entry = {
                        "exists": True,
                        "wiki_creator": row.actor_name,
                        "wiki_creation_date": wiki_date,
                        "timestamp_str": iso_str,
                        "page_namespace": int(row.page_namespace) if row.page_namespace is not None else 0,
                        "page_is_redirect": bool(row.page_is_redirect),
                        "page_len": int(row.page_len) if row.page_len is not None else 0
                    }
                    results[orig_title.lower()] = entry
                    results[db_title.lower()] = entry
                    results[db_title.replace("_", " ").lower()] = entry
        print(f"[Replica] Query succeeded: {len(results)}/{len(db_titles)} article keys mapped")
        return results
    except Exception as e:
        print(f"[Replica] Wiki replica query error, falling back to HTTP API: {e}")
        return None
