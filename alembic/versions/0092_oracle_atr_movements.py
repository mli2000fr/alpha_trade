"""Four realized-return comparison lists, exclusively in the US database."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0092_oracle_atr_movements'
down_revision = '0091_oracle_atr_total_pct'
branch_labels = None
depends_on = None
TABLE = 'oracle_atr_market_regime_daily'
COLUMNS = ('real_oracle_top_returns_pct', 'intersection_returns_pct',
           'predicted_oracle_top_returns_pct', 'atr_top_returns_pct')


def _existing():
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('La migration 0092 exige alpha_trade (US)')
    return {c['name'] for c in inspect(bind).get_columns(TABLE)}


def upgrade():
    existing = _existing()
    for column in COLUMNS:
        if existing is None or column not in existing:
            op.execute(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {column} JSON NULL')


def downgrade():
    existing = _existing()
    for column in reversed(COLUMNS):
        if existing is None or column in existing:
            op.execute(f'ALTER TABLE alpha_trade.{TABLE} DROP COLUMN {column}')
