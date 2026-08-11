from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import sqlite3
import os
import configparser
from datetime import datetime

DB_NAME = os.getenv("DB_NAME", f"{os.getenv('TOOL_TOOLSDB_USER')}__app" if os.getenv("TOOL_TOOLSDB_USER") else None)
DB_HOST = os.getenv("DB_HOST", "tools.db.svc.wikimedia.cloud")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", os.getenv("TOOL_TOOLSDB_USER"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("TOOL_TOOLSDB_PASSWORD"))

if DB_NAME and DB_USER:
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )
else:
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
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
        from sqlalchemy import inspect
        from . import models
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

        # Create tables if not exist
        models.Base.metadata.create_all(bind=db_engine)
        
        # Apply incremental column migrations
        if 'users' in existing_tables:
            add_col_if_missing('users', 'oauth_access_token', 'TEXT')
            if is_mysql:
                with db_engine.connect() as conn:
                    try:
                        conn.execute(text("ALTER TABLE `users` MODIFY COLUMN `oauth_access_token` TEXT"))
                        conn.commit()
                        print("[Migration] OK: MODIFY COLUMN users.oauth_access_token → TEXT")
                    except Exception as ex:
                        print(f"[Migration] WARN modifying oauth_access_token type: {ex}")
        
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

        # Timezone migrations
        migration_table_sql = """
            CREATE TABLE IF NOT EXISTS contest_timezone_migrations (
                migration_key VARCHAR(100) PRIMARY KEY,
                applied_at DATETIME NOT NULL
            )
        """
        with db_engine.connect() as conn:
            conn.execute(text(migration_table_sql))
            conn.commit()

        migration_key = "contest_dates_bst_to_utc_20260801"
        with db_engine.connect() as conn:
            already_applied = conn.execute(
                text("SELECT 1 FROM contest_timezone_migrations WHERE migration_key = :key"),
                {"key": migration_key}
            ).first()

            if not already_applied and 'contests' in existing_tables:
                if is_mysql:
                    conn.execute(text(
                        "UPDATE contests SET start_date = DATE_SUB(start_date, INTERVAL 6 HOUR), "
                        "end_date = DATE_SUB(end_date, INTERVAL 6 HOUR)"
                    ))
                else:
                    conn.execute(text(
                        "UPDATE contests SET start_date = datetime(start_date, '-6 hours'), "
                        "end_date = datetime(end_date, '-6 hours')"
                    ))
                conn.execute(text(
                    "INSERT INTO contest_timezone_migrations (migration_key, applied_at) "
                    "VALUES (:key, :applied_at)"
                ), {"key": migration_key, "applied_at": datetime.utcnow()})
                conn.commit()
                print("[Migration] Shifted existing contest windows from legacy UTC storage to BST-correct UTC.")
            elif not already_applied:
                conn.execute(text(
                    "INSERT INTO contest_timezone_migrations (migration_key, applied_at) "
                    "VALUES (:key, :applied_at)"
                ), {"key": migration_key, "applied_at": datetime.utcnow()})
                conn.commit()
                print("[Migration] Recorded contest timezone migration; no existing contests to shift.")

        if 'article_locks' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    conn.execute(text("""
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
