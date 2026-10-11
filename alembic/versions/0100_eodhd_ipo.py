"""Independent EODHD IPO observations and resumable windows."""
from pathlib import Path
from alembic import context, op
from sqlalchemy import text

revision = '0100_eodhd_ipo'
down_revision = '0099_eodhd_consensus'
branch_labels = None
depends_on = None


def guard():
    if not context.is_offline_mode() and op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('IPO migration requires alpha_trade')


def upgrade():
    guard()
    source = Path(__file__).resolve().parents[2] / 'database/sql/forward_pit/stock_ipo_eodhd_history.sql'
    for statement in source.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    guard()
    op.execute('DROP TABLE alpha_trade.eodhd_ipo_collection_windows')
    op.execute('DROP TABLE alpha_trade.stock_ipo_eodhd_history')
