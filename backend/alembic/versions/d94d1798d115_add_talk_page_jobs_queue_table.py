"""add talk_page_jobs queue table

Revision ID: d94d1798d115
Revises:
Create Date: 2026-08-30 10:06:44.907395

This is the first Alembic revision in the project. Schema changes before it
were applied by `create_all` plus the hand-written idempotent statements in
database.py's `run_auto_migrations`, and those are deliberately *not*
replayed here -- this revision only adds the new table, and future changes
are what belongs under version control.

`main.py` still calls `Base.metadata.create_all`, which creates this table on
a fresh boot as well, so every step below checks first and does nothing when
the object is already there. Running the migration and starting the app in
either order gives the same schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd94d1798d115'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "talk_page_jobs"
INDEXES = [
    ("ix_talk_page_jobs_id", ["id"]),
    ("ix_talk_page_jobs_contest_id", ["contest_id"]),
    ("ix_talk_page_jobs_status", ["status"]),
]


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('article_id', sa.Integer(), nullable=False),
            sa.Column('contest_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False),
            sa.Column('error', sa.String(length=500), nullable=True),
            sa.Column('access_token', sa.Text(), nullable=False),
            sa.Column('submitted_by', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('processed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ),
            sa.ForeignKeyConstraint(['contest_id'], ['contests.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        inspector = sa.inspect(bind)

    existing = {index["name"] for index in inspector.get_indexes(TABLE)}
    for name, columns in INDEXES:
        if name not in existing:
            op.create_index(name, TABLE, columns, unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing = {index["name"] for index in inspector.get_indexes(TABLE)}
    for name, _columns in INDEXES:
        if name in existing:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
