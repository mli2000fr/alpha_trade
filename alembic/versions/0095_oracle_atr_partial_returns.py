"""Explicit partial Oracle/ATR returns and per-list coverage, US only."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0095_oracle_atr_partial_returns'
down_revision = '0094_oracle_atr_score_order'
branch_labels = None
depends_on = None
TABLE = 'oracle_atr_market_regime_daily'
COLUMNS = {'missing_returns_policy': "VARCHAR(16) NOT NULL DEFAULT 'strict'",
           'movement_quality': 'JSON NULL'}


def _existing():
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('La migration 0095 exige alpha_trade (US)')
    return {c['name'] for c in inspect(bind).get_columns(TABLE)}


def upgrade():
    existing = _existing()
    for column, definition in COLUMNS.items():
        if existing is None or column not in existing:
            op.execute(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {column} {definition}')


def downgrade():
    existing = _existing()
    for column in reversed(COLUMNS):
        if existing is None or column in existing:
            op.execute(f'ALTER TABLE alpha_trade.{TABLE} DROP COLUMN {column}')
