"""Prospective SEC x close / Finnhub cap snapshots, separate from SEC facts."""
from alembic import op
import sqlalchemy as sa

revision = '0109_market_cap_daily'
down_revision = '0107_merge_quote_provenance'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
        raise RuntimeError('US alpha_trade required')
    from database.market_cap_snapshots import snapshots
    snapshots.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError('Conserver les observations ; suppression nécessite un accord distinct')
