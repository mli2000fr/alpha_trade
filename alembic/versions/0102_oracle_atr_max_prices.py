"""Retrospective maximum prices of Oracle TOP-N, in predicted score order."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0102_oatr_max_prices'
down_revision = '0101_oatr_intersection_order'
branch_labels = None
depends_on = None
TABLE = 'oracle_atr_market_regime_daily'
COLUMN = 'predicted_oracle_score_order_max_prices'


def existing_columns():
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('Oracle peak migration requires alpha_trade (US)')
    return {c['name'] for c in inspect(bind).get_columns(TABLE)}


def upgrade():
    existing = existing_columns()
    if existing is None or COLUMN not in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {COLUMN} JSON NULL '
                   "COMMENT 'Oracle score order: max high J+1..J+H in signal-day USD price scale; research only'")


def downgrade():
    existing = existing_columns()
    if existing is None or COLUMN in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} DROP COLUMN {COLUMN}')
