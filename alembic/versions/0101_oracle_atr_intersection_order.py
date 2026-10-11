"""Intersection realized returns in predicted Oracle score order, US only."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0101_oatr_intersection_order'
down_revision = '0100_eodhd_ipo'
branch_labels = None
depends_on = None
TABLE = 'oracle_atr_market_regime_daily'
COLUMN = 'intersection_oracle_score_order_returns_pct'


def existing_columns():
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('Intersection order migration requires alpha_trade (US)')
    return {c['name'] for c in inspect(bind).get_columns(TABLE)}


def upgrade():
    existing = existing_columns()
    if existing is None or COLUMN not in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {COLUMN} JSON NULL')


def downgrade():
    existing = existing_columns()
    if existing is None or COLUMN in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} DROP COLUMN {COLUMN}')
