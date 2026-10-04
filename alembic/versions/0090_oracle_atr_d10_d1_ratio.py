"""Add and backfill the D10/D1 ratio in the US daily study."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0090_oracle_atr_d10_d1_ratio'
down_revision = '0089_oracle_atr_regime'
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise RuntimeError('La migration 0090 exige alpha_trade (US)')
        exists = any(c['name']=='d10_d1_ratio' for c in inspect(bind).get_columns('oracle_atr_market_regime_daily'))
    else:
        exists = False
    if not exists:
        op.execute('ALTER TABLE alpha_trade.oracle_atr_market_regime_daily ADD COLUMN d10_d1_ratio DOUBLE NULL AFTER d10_pct')
    op.execute('UPDATE alpha_trade.oracle_atr_market_regime_daily '
               'SET d10_d1_ratio=CASE WHEN evaluated_count>0 AND d1_count>0 THEN d10_count/d1_count ELSE NULL END')


def downgrade():
    op.execute('ALTER TABLE alpha_trade.oracle_atr_market_regime_daily DROP COLUMN d10_d1_ratio')
