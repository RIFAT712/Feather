from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import sqlite3
import os
import configparser

from datetime import datetime
from timeutils import utcnow
from dotenv import load_dotenv
load_dotenv()
import json
import shutil
import subprocess
from pathlib import Path

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

def _mysql_driver():
    """SQLAlchemy dialect for the MariaDB connections, preferring a C driver.

    pymysql decodes every column of every row in pure Python, which is the same
    class of overhead as building ORM objects for rows nobody reads -- it just
    happens one layer lower, where it is invisible from the app. mysqlclient
    (MySQLdb) does that decoding in C and is typically several times faster on
    the multi-thousand-row pages the jury panel and /log serve.

    Chosen by import probe rather than pinned, so this is a no-op unless the
    image actually has the C driver: an environment with only pymysql keeps
    working exactly as before instead of failing to start. Set FEATHER_DB_DRIVER
    to force a specific dialect (e.g. "pymysql") if a build needs to opt out.
    """
    forced = os.getenv("FEATHER_DB_DRIVER")
    if forced:
        return forced
    try:
        import MySQLdb  # noqa: F401  (provided by mysqlclient)
        return "mysqldb"
    except ImportError:
        return "pymysql"

MYSQL_DRIVER = _mysql_driver()

DB_NAME = os.getenv("DB_NAME", f"{os.getenv('TOOL_TOOLSDB_USER')}__app" if os.getenv("TOOL_TOOLSDB_USER") else None)
DB_HOST = os.getenv("DB_HOST", "tools.db.svc.wikimedia.cloud")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", os.getenv("TOOL_TOOLSDB_USER"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("TOOL_TOOLSDB_PASSWORD"))

if DB_NAME and DB_USER:
    SQLALCHEMY_DATABASE_URL = f"mysql+{MYSQL_DRIVER}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    print(f"[DB] Application engine driver: mysql+{MYSQL_DRIVER}")
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
        # WAL lets API reads continue while a submission, migration, or
        # projection refresh is writing. TRUNCATE made the entire app queue
        # behind one SQLite writer.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")
        conn.close()
    except Exception as e:
        print(f"Could not enable SQLite WAL mode: {e}")
        
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False, "timeout": 60},
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

# MySQL/MariaDB string escaping, as a translation table so str.translate does it
# in C. Matches what pymysql's own escaper emits (verified against
# pymysql.converters.escape_string); NUL and Ctrl-Z have to be escaped or the
# dump file cannot be fed back through the mysql client.
_MYSQL_ESCAPES = str.maketrans({
    "\\": "\\\\",
    "'": "\\'",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\x00": "\\0",
    "\x1a": "\\Z",
})

def _sql_literal(value, mysql: bool) -> str:
    """Render one Python value as a SQL literal for a dump file.

    SQLite has no backslash escape: a quote is doubled and everything else is
    taken literally, so it needs its own branch rather than MySQL's rules.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (bytes, bytearray)):
        return f"X'{value.hex()}'" if value else "''"
    if isinstance(value, datetime):
        return "'" + value.isoformat(sep=" ") + "'"
    if hasattr(value, "isoformat"):          # date, time
        return "'" + value.isoformat() + "'"
    text_value = str(value)
    if mysql:
        return "'" + text_value.translate(_MYSQL_ESCAPES) + "'"
    return "'" + text_value.replace("'", "''") + "'"

# Each INSERT is capped well under MariaDB's default 16MB max_allowed_packet:
# one statement per table would be unrestorable on any table of real size.
_MAX_INSERT_BYTES = 800_000

def write_sql_dump(db_engine, target: Path) -> Path:
    """Write a restorable .sql dump of every table, without needing mysqldump.

    The DDL is the database's own: SHOW CREATE TABLE on MariaDB, and the stored
    CREATE statement out of sqlite_master on SQLite -- so indexes, constraints,
    AUTO_INCREMENT and charset come back exactly as they are rather than being
    reconstructed from SQLAlchemy's view of them. Rows are streamed, not read
    into memory, and batched into multi-row INSERTs.

    The result restores with `mysql < dump.sql` (or `sqlite3 db < dump.sql`)
    like a mysqldump would -- which a JSON snapshot of the same data does not:
    JSON records the contents but no engine can read it back, so restoring one
    means writing a bespoke loader at the exact moment you least want to.
    """
    from sqlalchemy import inspect, text
    mysql = "mysql" in str(db_engine.url)
    inspector = inspect(db_engine)

    with db_engine.connect() as connection, target.open("w", encoding="utf-8", newline="\n") as out:
        out.write("-- Feather database dump\n")
        out.write(f"-- Engine: {db_engine.url.get_backend_name()}\n")
        out.write(f"-- Generated: {utcnow().isoformat()}\n")
        out.write("-- Written by Feather (mysqldump unavailable); restorable with the standard client.\n\n")
        if mysql:
            out.write("SET NAMES utf8mb4;\n")
            out.write("SET FOREIGN_KEY_CHECKS=0;\n")
            out.write("SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n\n")
        else:
            out.write("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n\n")

        for table in inspector.get_table_names():
            if mysql:
                ddl = connection.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()[1]
                quoted = f"`{table}`"
            else:
                ddl = connection.execute(
                    text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
                    {"n": table},
                ).scalar()
                quoted = f'"{table}"'
            out.write(f"--\n-- Table structure for {table}\n--\n\n")
            out.write(f"DROP TABLE IF EXISTS {quoted};\n{ddl};\n\n")

            columns = [column["name"] for column in inspector.get_columns(table)]
            column_list = ", ".join((f"`{c}`" if mysql else f'"{c}"') for c in columns)
            prefix = f"INSERT INTO {quoted} ({column_list}) VALUES\n"
            rows = connection.execution_options(stream_results=True, yield_per=1000).execute(
                text(f"SELECT {column_list} FROM {quoted}")
            )
            batch, batch_bytes, row_count = [], 0, 0
            for row in rows:
                values = "(" + ",".join(_sql_literal(v, mysql) for v in row) + ")"
                if batch and batch_bytes + len(values) > _MAX_INSERT_BYTES:
                    out.write(prefix + ",\n".join(batch) + ";\n")
                    batch, batch_bytes = [], 0
                batch.append(values)
                batch_bytes += len(values) + 2
                row_count += 1
            if batch:
                out.write(prefix + ",\n".join(batch) + ";\n")
            out.write(f"-- {row_count} row(s) in {table}\n\n")

            # Indexes live inside SHOW CREATE TABLE on MariaDB, but are separate
            # rows in sqlite_master, so SQLite needs them written out too.
            if not mysql:
                for (index_ddl,) in connection.execute(
                    text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:n AND sql IS NOT NULL"),
                    {"n": table},
                ).all():
                    out.write(f"{index_ddl};\n")
                out.write("\n")

        out.write("SET FOREIGN_KEY_CHECKS=1;\n" if mysql else "COMMIT;\nPRAGMA foreign_keys=ON;\n")
    return target

def _pre_migration_backup(db_engine):
    """Create a rollback snapshot before touching the application schema."""
    backup_root = Path(os.getenv("BACKUP_ROOT", Path(__file__).resolve().parent.parent)) / "backup" / "pre_migration"
    backup_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(backup_root, 0o700)
    except OSError:
        pass

    def protect(path):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    stamp = utcnow().strftime("%Y%m%d_%H%M%S_%f")
    is_mysql = "mysql" in str(db_engine.url)

    # The jury panel projection is a second local SQLite database. Preserve
    # it too when the primary application database is MariaDB.
    if is_mysql:
        for local_db in Path(__file__).resolve().parent.glob("*.db"):
            local_target = backup_root / f"{local_db.stem}_{stamp}.db"
            shutil.copy2(local_db, local_target)
            protect(local_target)
            print(f"[Migration Backup] Local SQLite snapshot created: {local_target}")

    if not is_mysql:
        source = Path(db_engine.url.database or "app.db")
        if not source.is_absolute():
            source = Path.cwd() / source
        target = backup_root / f"app_{stamp}.db"
        if source.exists():
            shutil.copy2(source, target)
            protect(target)
            print(f"[Migration Backup] SQLite snapshot created: {target}")
        else:
            empty_target = backup_root / f"app_{stamp}.empty"
            empty_target.write_text(
                "Database did not exist before migration.\n", encoding="utf-8"
            )
            protect(empty_target)
            print("[Migration Backup] SQLite database does not exist yet; recorded empty snapshot.")
        source_resolved = source.resolve()
        for local_db in Path(__file__).resolve().parent.glob("*.db"):
            if local_db.resolve() == source_resolved:
                continue
            local_target = backup_root / f"{local_db.stem}_{stamp}.db"
            shutil.copy2(local_db, local_target)
            protect(local_target)
            print(f"[Migration Backup] Local SQLite snapshot created: {local_target}")
        return target if source.exists() else empty_target

    # Prefer a native SQL dump because it preserves schema, indexes, and data.
    sql_target = backup_root / f"app_{stamp}.sql"
    dump_env = os.environ.copy()
    if DB_PASSWORD:
        dump_env["MYSQL_PWD"] = DB_PASSWORD
    dump_cmd = [
        "mysqldump", "--single-transaction", "--routines", "--triggers",
        "--host", str(DB_HOST), "--port", str(DB_PORT), "--user", str(DB_USER),
        str(DB_NAME),
    ]
    try:
        with sql_target.open("wb") as output:
            subprocess.run(dump_cmd, env=dump_env, stdout=output, stderr=subprocess.PIPE, check=True)
        protect(sql_target)
        print(f"[Migration Backup] MariaDB dump created: {sql_target}")
        return sql_target
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        if sql_target.exists():
            sql_target.unlink()
        print(f"[Migration Backup] mysqldump unavailable or failed ({error}); dumping SQL in Python.")

    # Toolforge images do not always ship mysqldump. This used to fall back to a
    # JSON snapshot, which captured the data but was not a backup anyone could
    # restore: no client reads it, so recovering from one meant writing a loader
    # by hand at the worst possible moment. write_sql_dump produces the same
    # .sql a mysqldump would, using the database's own DDL.
    try:
        write_sql_dump(db_engine, sql_target)
        protect(sql_target)
        print(f"[Migration Backup] SQL dump created without mysqldump: {sql_target}")
        return sql_target
    except Exception as error:
        if sql_target.exists():
            sql_target.unlink()
        print(f"[Migration Backup] SQL dump failed ({error}); falling back to JSON snapshot.")

    # Last resort only. A pre-migration snapshot must never be skipped outright,
    # so if even the SQL writer fails we still capture the rows in a form that
    # can be re-loaded by hand rather than proceeding with no backup at all.
    json_target = backup_root / f"app_{stamp}.json"
    from sqlalchemy import inspect, text
    inspector = inspect(db_engine)
    snapshot = {"database": str(DB_NAME), "created_at": utcnow().isoformat(), "tables": {}}
    with db_engine.connect() as connection:
        for table in inspector.get_table_names():
            columns = inspector.get_columns(table)
            rows = connection.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
            snapshot["tables"][table] = {
                "columns": [{"name": column["name"], "type": str(column["type"])} for column in columns],
                "rows": [dict(row) for row in rows],
            }
    json_target.write_text(json.dumps(snapshot, ensure_ascii=False, default=str), encoding="utf-8")
    protect(json_target)
    print(f"[Migration Backup] MariaDB JSON snapshot created: {json_target}")
    return json_target


def _schema_requires_migration(db_engine):
    """Return whether a destructive/schema-changing migration is pending.

    This check is intentionally metadata-only.  A full MariaDB snapshot on
    every process start defeats the purpose of a fast web application.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    if not tables:
        return False

    required_columns = {
        "users": {"oauth_access_token"},
        "contests": {
            "min_bytes", "min_words", "min_refs", "rule_no_redirect",
            "rule_no_disambig", "rule_mainspace_only", "allow_self_review",
            "add_talk_template", "talk_template_name", "include_talk_header",
        },
        "articles": {"assigned_to_id"},
    }
    for table, columns in required_columns.items():
        if table in tables:
            actual = {column["name"] for column in inspector.get_columns(table)}
            if columns - actual:
                return True

    required_tables = {
        "article_locks", "system_logs", "contest_jury_restrictions",
        "contest_banned_users", "contest_timezone_migrations",
    }
    if required_tables - tables:
        return True

    if "contests" in tables:
        with db_engine.connect() as connection:
            migrated = connection.execute(text(
                "SELECT 1 FROM contest_timezone_migrations "
                "WHERE migration_key = 'contest_dates_bst_to_utc_20260801'"
            )).first()
        if not migrated:
            return True

    # These indexes keep the common contest and queue queries bounded without
    # changing their response shape.
    indexes = {
        index["name"] for index in inspector.get_indexes("articles")
    } if "articles" in tables else set()
    if {"ix_articles_contest_id", "ix_articles_contest_status", "ix_articles_contest_assigned", "ix_articles_contest_id_pk"} - indexes:
        return True
    return False


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
        else:
            print("[Migration] 'users' table not found — create_all will handle it.")
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
        if 'articles' in existing_tables:
            # Jury assignment now lives directly on the article instead of a
            # separate projection database — see jury panel merge.
            add_col_if_missing('articles', 'assigned_to_id', 'INTEGER')
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
                ), {"key": migration_key, "applied_at": utcnow()})
                conn.commit()
                print("[Migration] Shifted existing contest windows from legacy UTC storage to BST-correct UTC.")
            elif not already_applied:
                conn.execute(text(
                    "INSERT INTO contest_timezone_migrations (migration_key, applied_at) "
                    "VALUES (:key, :applied_at)"
                ), {"key": migration_key, "applied_at": utcnow()})
                conn.commit()
                print("[Migration] Recorded contest timezone migration; no existing contests to shift.")
            else:
                print("[Migration] Contest timezone migration already applied.")

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

        if 'contest_jury_restrictions' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS contest_jury_restrictions (
                            id INTEGER NOT NULL {"AUTO_INCREMENT" if is_mysql else ""} PRIMARY KEY,
                            contest_id INTEGER NOT NULL,
                            jury_user_id INTEGER NOT NULL,
                            submitter_user_id INTEGER NOT NULL,
                            CONSTRAINT uq_contest_jury_submitter UNIQUE (contest_id, jury_user_id, submitter_user_id),
                            FOREIGN KEY (contest_id) REFERENCES contests(id),
                            FOREIGN KEY (jury_user_id) REFERENCES users(id),
                            FOREIGN KEY (submitter_user_id) REFERENCES users(id)
                        )
                    """))
                    conn.commit()
                    print("[Migration] Created 'contest_jury_restrictions' table.")
                except Exception as ex:
                    print(f"[Migration] WARN creating contest_jury_restrictions: {ex}")
        else:
            print("[Migration] 'contest_jury_restrictions' table already exists.")

        if 'contest_banned_users' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS contest_banned_users (
                            id INTEGER NOT NULL {"AUTO_INCREMENT" if is_mysql else ""} PRIMARY KEY,
                            contest_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            CONSTRAINT uq_contest_banned_user UNIQUE (contest_id, user_id),
                            FOREIGN KEY (contest_id) REFERENCES contests(id),
                            FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    """))
                    conn.commit()
                    print("[Migration] Created 'contest_banned_users' table.")
                except Exception as ex:
                    print(f"[Migration] WARN creating contest_banned_users: {ex}")
        else:
            print("[Migration] 'contest_banned_users' table already exists.")

        if 'deleted_article_log' not in existing_tables:
            with db_engine.connect() as conn:
                try:
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS deleted_article_log (
                            id INTEGER NOT NULL {"AUTO_INCREMENT" if is_mysql else ""} PRIMARY KEY,
                            article_id INTEGER NOT NULL,
                            contest_id INTEGER NOT NULL,
                            contest_code VARCHAR(50),
                            title VARCHAR(255) NOT NULL,
                            submitted_by VARCHAR(255),
                            wiki_creator VARCHAR(255),
                            wiki_creation_date DATETIME,
                            submitted_at DATETIME,
                            status VARCHAR(50),
                            validation_error VARCHAR(500),
                            review_count INTEGER NOT NULL DEFAULT 0,
                            deleted_by VARCHAR(255) NOT NULL,
                            deleted_at DATETIME NOT NULL,
                            FOREIGN KEY (contest_id) REFERENCES contests(id)
                        )
                    """))
                    conn.commit()
                    print("[Migration] Created 'deleted_article_log' table.")
                except Exception as ex:
                    print(f"[Migration] WARN creating deleted_article_log: {ex}")
        else:
            print("[Migration] 'deleted_article_log' table already exists.")

        # Composite indexes used by contest dashboards and jury queues.
        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_articles_contest_id ON articles (contest_id)",
            "CREATE INDEX IF NOT EXISTS ix_articles_contest_status ON articles (contest_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_articles_contest_assigned ON articles (contest_id, assigned_to_id)",
            # The deletion audit trail is read per contest, newest first.
            "CREATE INDEX IF NOT EXISTS ix_deleted_log_contest_time ON deleted_article_log (contest_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_deleted_log_article ON deleted_article_log (article_id)",
            # /log and /articles/page filter by contest_id and paginate by
            # ORDER BY id (keyset cursor). Without contest_id+id together in
            # one index, MariaDB can't satisfy both the filter and the sort
            # from an index and falls back to a much slower plan -- this is
            # what made a 500-row page take ~2.2s on a live 12k-article
            # contest instead of milliseconds.
            "CREATE INDEX IF NOT EXISTS ix_articles_contest_id_pk ON articles (contest_id, id)",
            # GET /log?submitted_by=... and /submitters filter/group by
            # (contest_id, submitter_id) -- the dashboard's per-user
            # drill-down fetches one submitter's articles on demand instead
            # of crawling the whole contest and grouping client-side, so this
            # needs to be an index lookup, not a filtered scan.
            "CREATE INDEX IF NOT EXISTS ix_articles_contest_submitter ON articles (contest_id, submitter_id)",
            # /log and the jury panel both fetch a page's review history with a
            # single WHERE article_id IN (...) over up to 5,000 ids, instead of
            # a lazy load per article. InnoDB gets this index free from the
            # foreign key; SQLite does not, so state it explicitly.
            "CREATE INDEX IF NOT EXISTS ix_reviews_article_id ON reviews (article_id)",
        ]
        with db_engine.connect() as conn:
            for statement in index_statements:
                try:
                    conn.execute(text(statement))
                    conn.commit()
                except Exception as ex:
                    print(f"[Migration] WARN creating performance index: {ex}")

        print("[Migration] All done.")
    except Exception as e:
        print(f"[Migration] FATAL error: {e}")

if _schema_requires_migration(engine):
    print("[Migration Backup] Schema change detected; creating rollback snapshot.")
    _pre_migration_backup(engine)
else:
    print("[Migration Backup] Schema is current; skipping full database snapshot.")
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
        wiki_db_url = f"mysql+{MYSQL_DRIVER}://{WIKI_DB_USER}:{WIKI_DB_PASSWORD}@{WIKI_DB_HOST}:{WIKI_DB_PORT}/{WIKI_DB_NAME}?charset=utf8mb4"
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
    Keys preserve the full page-title case: on Wiktionary, `GOD` and `god`
    can be distinct entries. Spaces and underscores are still normalized only
    for the replica lookup.
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
                    results[orig_title] = entry
                    results[db_title] = entry
                    results[db_title.replace("_", " ")] = entry
        print(f"[Replica] Query succeeded: {len(results)}/{len(db_titles)} article keys mapped")
        return results
    except Exception as e:
        print(f"[Replica] Wiki replica query error, falling back to HTTP API: {e}")
        return None


def _parse_mw_timestamp(value):
    """MediaWiki's fixed-width "YYYYMMDDHHMMSS" timestamp -> naive UTC datetime.

    The replica returns it as bytes or str depending on the driver, and very
    old rows can carry zero-padded junk, so anything unparseable becomes None
    rather than failing the whole listing.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    try:
        return datetime.strptime(str(value).strip(), "%Y%m%d%H%M%S")
    except (ValueError, TypeError):
        return None

def query_wiki_replica_user_creations(username: str, start: datetime, end: datetime, page_size: int = 5000) -> list:
    """
    Queries the Wikimedia MariaDB replica for every mainspace page `username`
    created (first revision, rev_parent_id = 0) between `start` and `end` --
    the same underlying page/revision/actor tables query_wiki_replica_batch()
    validates individual titles against, just filtered by author + date range
    instead of by a title list. Used to auto-populate SubmitArticles.vue's
    "Articles You Can Submit" list instead of paginating the public
    usercontribs API from the browser.
    Returns a list of {"title", "created_at"} dicts (titles use spaces, not
    underscores; created_at is a naive-UTC datetime), or None if the replica
    engine is unavailable or the query fails (triggering the usercontribs
    HTTP fallback in main.py). The creation timestamp comes free with the
    row the query already reads, and SubmitArticles.vue shows and sorts by it.

    Results are read from the replica in keyset-paginated pages. A contest
    period can contain far more than 5,000 creations, so `page_size` bounds
    one SQL result set only; it is not a cap on the returned list. The
    `(rev_timestamp, rev_id)` cursor keeps rows with identical second-level
    MediaWiki timestamps deterministic without the performance penalty or
    drift risk of OFFSET pagination.
    """
    if not wiki_engine or not username:
        return None

    # MediaWiki usernames are always capitalized on first letter; actor_name
    # is stored in that display form (unlike page_title, which uses
    # underscores for spaces), so this is the one normalization worth doing.
    clean_username = username.strip().replace("_", " ")
    if not clean_username:
        return None
    clean_username = clean_username[0].upper() + clean_username[1:]

    # rev_timestamp is MediaWiki's fixed-width "YYYYMMDDHHMMSS" format, which
    # sorts and compares correctly as a plain string.
    start_ts = start.strftime("%Y%m%d%H%M%S")
    end_ts = end.strftime("%Y%m%d%H%M%S")

    try:
        with wiki_engine.connect() as conn:
            from sqlalchemy import text
            query = text("""
                SELECT CONVERT(p.page_title USING utf8mb4) as page_title,
                       r.rev_timestamp as rev_timestamp,
                       r.rev_id as rev_id
                FROM revision r
                JOIN actor a ON r.rev_actor = a.actor_id
                JOIN page p ON p.page_id = r.rev_page
                WHERE a.actor_name = :username
                  AND r.rev_parent_id = 0
                  AND p.page_namespace = 0
                  AND r.rev_timestamp >= :start_ts
                  AND r.rev_timestamp <= :end_ts
                  AND (
                    :last_timestamp IS NULL
                    OR r.rev_timestamp > :last_timestamp
                    OR (r.rev_timestamp = :last_timestamp AND r.rev_id > :last_rev_id)
                  )
                ORDER BY r.rev_timestamp ASC, r.rev_id ASC
                LIMIT :page_size
            """)
            titles = []
            last_timestamp = None
            last_rev_id = 0
            page_count = 0
            while True:
                rows = conn.execute(query, {
                    "username": clean_username,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "last_timestamp": last_timestamp,
                    "last_rev_id": last_rev_id,
                    "page_size": page_size,
                }).fetchall()
                if not rows:
                    break

                page_count += 1
                titles.extend({
                    "title": row.page_title.replace("_", " "),
                    "created_at": _parse_mw_timestamp(row.rev_timestamp),
                } for row in rows)
                last_timestamp = rows[-1].rev_timestamp
                last_rev_id = rows[-1].rev_id

                if len(rows) < page_size:
                    break
        print(
            f"[Replica] User-creations query for {clean_username!r} "
            f"({start_ts}-{end_ts}): {len(titles)} pages across {page_count} query page(s)"
        )
        return titles
    except Exception as e:
        print(f"[Replica] Wiki replica user-creations query error, falling back to HTTP API: {e}")
        return None
