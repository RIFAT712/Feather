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
if DB_NAME and not DB_USER:
    user, password = get_toolforge_credentials()
    if user and password:
        DB_USER = user
        DB_PASSWORD = password

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
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db_engine)
        if 'contests' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('contests')]
            new_cols = [
                ("min_bytes", "INTEGER DEFAULT 0"),
                ("min_words", "INTEGER DEFAULT 0"),
                ("min_refs", "INTEGER DEFAULT 0"),
                ("rule_no_redirect", "BOOLEAN DEFAULT 1"),
                ("rule_no_disambig", "BOOLEAN DEFAULT 1"),
                ("rule_mainspace_only", "BOOLEAN DEFAULT 1"),
                ("allow_self_review", "BOOLEAN DEFAULT 0"),
                ("add_talk_template", "BOOLEAN DEFAULT 0"),
                ("talk_template_name", "VARCHAR(255)"),
                ("include_talk_header", "BOOLEAN DEFAULT 1")
            ]
            with db_engine.connect() as conn:
                for col_name, col_type in new_cols:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE contests ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            print(f"[Migration] Added column '{col_name}' to contests table.")
                        except Exception as ex:
                            print(f"[Migration] Failed adding {col_name}: {ex}")
    except Exception as e:
        print(f"[Migration] Error inspecting database: {e}")

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

    title_map = {}
    for t in titles:
        clean = t.strip()
        if clean:
            db_fmt = clean.replace(" ", "_")
            title_map[db_fmt] = clean

    db_titles = list(title_map.keys())
    if not db_titles:
        return {}

    results = {}
    chunk_size = 500

    try:
        with wiki_engine.connect() as conn:
            from sqlalchemy import text
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
                    JOIN revision r ON p.page_id = r.rev_page
                    JOIN actor a ON r.rev_actor = a.actor_id
                    WHERE r.rev_parent_id = 0
                      AND p.page_title IN :titles
                """)
                res = conn.execute(query, {"titles": tuple(chunk)})
                for row in res:
                    db_title = row.page_title
                    orig_title = title_map.get(db_title, db_title.replace("_", " "))
                    ts_str = row.rev_timestamp
                    wiki_date = None
                    iso_str = None
                    if ts_str:
                        try:
                            wiki_date = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
                            iso_str = wiki_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                        except Exception:
                            pass
                    results[orig_title] = {
                        "exists": True,
                        "wiki_creator": row.actor_name,
                        "wiki_creation_date": wiki_date,
                        "timestamp_str": iso_str,
                        "page_namespace": int(row.page_namespace) if row.page_namespace is not None else 0,
                        "page_is_redirect": bool(row.page_is_redirect),
                        "page_len": int(row.page_len) if row.page_len is not None else 0
                    }
        print(f"[Replica] Query succeeded: {len(results)}/{len(db_titles)} articles found")
        return results
    except Exception as e:
        print(f"[Replica] Wiki replica query error, falling back to HTTP API: {e}")
        return None


