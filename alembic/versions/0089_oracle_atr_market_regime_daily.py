"""US daily Oracle ATR regime study.

Revision ID: 0089_oracle_atr_regime
Revises: 0088_us_fact_instrument_constraints
"""
from pathlib import Path
from alembic import op, context
from sqlalchemy import text

revision = '0089_oracle_atr_regime'
down_revision = '0088_us_fact_instrument_constraints'
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode() and op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('La migration 0089 doit être exécutée sur alpha_trade (US)')
    sql = (Path(__file__).resolve().parents[2] / 'database/sql/ml/oracle_atr_market_regime_daily.sql').read_text(encoding='utf-8')
    op.execute(sql)


def downgrade():
    op.execute('DROP TABLE alpha_trade.oracle_atr_market_regime_daily')
