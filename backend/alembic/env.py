"""Alembic environment for Feather.

The database URL is deliberately *not* read from alembic.ini: database.py
already resolves it (SQLite locally, Toolforge MariaDB from TOOL_TOOLSDB_*
env vars or ~/replica.my.cnf), and a second copy of that logic would migrate
the wrong database the first time the two disagreed. This imports the engine
the application itself uses.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from database import engine  # noqa: E402
import models  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Keep autogenerate away from objects models.py does not own.

    `article_deletion_snapshots`, `contest_timezone_migrations` and the
    hand-tuned composite indexes on `articles` are created by
    database.py's run_auto_migrations, not by the ORM metadata. Left to
    itself, the first `--autogenerate` proposes dropping all of them.
    """
    if reflected and type_ in ("table", "index") and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            # SQLite cannot ALTER most things in place; batch mode rewrites
            # the table instead, so the same revision runs on SQLite locally
            # and MariaDB on Toolforge.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
