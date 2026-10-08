"""Realized returns in original predicted Oracle score order (US only)."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0094_oracle_atr_score_order'
down_revision = '0093_llm_directional'
branch_labels = None
depends_on = None
TABLE = 'oracle_atr_market_regime_daily'
COLUMN = 'predicted_oracle_score_order_returns_pct'


def _existing():
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('La migration 0094 exige alpha_trade (US)')
    return {c['name'] for c in inspect(bind).get_columns(TABLE)}


def upgrade():
    existing = _existing()
    if existing is None or COLUMN not in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {COLUMN} JSON NULL')


def downgrade():
    existing = _existing()
    if existing is None or COLUMN in existing:
        op.execute(f'ALTER TABLE alpha_trade.{TABLE} DROP COLUMN {COLUMN}')
