"""Immutable, prospectively available producer-direct macro versions (US)."""
from pathlib import Path

from alembic import context, op
from sqlalchemy import text

revision = '0096_public_macro_versions'
down_revision = '0095_oracle_atr_partial_returns'
branch_labels = None
depends_on = None


def _guard():
    if not context.is_offline_mode():
        if op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise RuntimeError('Migration 0096 requires alpha_trade (US)')


def upgrade():
    _guard()
    path = Path(__file__).resolve().parents[2] / 'database/sql/forward_pit/public_macro_observation_versions.sql'
    op.execute(path.read_text(encoding='utf-8'))


def downgrade():
    _guard()
    op.execute('DROP TABLE alpha_trade.macro_public_observation_versions')
