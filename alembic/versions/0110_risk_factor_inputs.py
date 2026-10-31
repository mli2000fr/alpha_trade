"""Immutable prospective risk-factor inputs, independent of selected stocks."""
from alembic import op

revision = '0110_risk_factor_inputs'
down_revision = '0109_market_cap_daily'
branch_labels = None
depends_on = None


def upgrade():
    from database.risk_factor_inputs import install_schema
    install_schema(op.get_bind())


def downgrade():
    raise RuntimeError('Conserver les preuves factorielles ; suppression soumise à accord distinct')
