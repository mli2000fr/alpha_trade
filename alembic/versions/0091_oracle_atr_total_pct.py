"""Add and backfill the combined D1/D10 percentage in the US study."""
from alembic import context, op
from sqlalchemy import inspect, text

revision = '0091_oracle_atr_total_pct'
down_revision = '0090_oracle_atr_d10_d1_ratio'
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise RuntimeError('La migration 0091 exige alpha_trade (US)')
        exists = any(c['name']=='d1_d10_total_pct' for c in inspect(bind).get_columns('oracle_atr_market_regime_daily'))
    else:
        exists = False
    if not exists:
        op.execute('ALTER TABLE alpha_trade.oracle_atr_market_regime_daily ADD COLUMN d1_d10_total_pct DOUBLE NULL AFTER d10_d1_ratio')
    op.execute('UPDATE alpha_trade.oracle_atr_market_regime_daily '
               'SET d1_d10_total_pct=CASE WHEN evaluated_count>0 THEN 100.0*(d1_count+d10_count)/evaluated_count ELSE NULL END')


def downgrade():
    op.execute('ALTER TABLE alpha_trade.oracle_atr_market_regime_daily DROP COLUMN d1_d10_total_pct')
