"""CN SQL-primary collection resources and queryable research evidence."""
from alembic import op
from service.market.cn_collection_storage import metadata

revision='0008_collection_sql_primary'
down_revision='0007_universe_audit_indexes'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if bind.exec_driver_sql('SELECT DATABASE()').scalar()!='alpha_trade_cn':
        raise RuntimeError('CN migration refused outside alpha_trade_cn')
    metadata.create_all(bind)

def downgrade():
    raise RuntimeError('CN SQL-primary data: destructive downgrade requires an explicit migration')
