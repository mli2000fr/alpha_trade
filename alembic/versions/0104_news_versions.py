"""Prospective immutable news/mapping versions and post-commit availability."""
from alembic import context, op
from sqlalchemy import text
from pathlib import Path

revision = '0104_news_versions'
down_revision = '0103_oatr_max_returns'
branch_labels = None
depends_on = None


def guard():
    if not context.is_offline_mode() and op.get_bind().execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
        raise RuntimeError('News archive migration requires US alpha_trade')


def upgrade():
    guard()
    source=Path(__file__).resolve().parents[2]/'database/sql/news/news_archive_versions.sql'
    for statement in source.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    guard()
    raise RuntimeError('News history is retained. Destructive downgrade requires an explicit, separately reviewed purge.')
