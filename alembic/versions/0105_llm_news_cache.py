"""US stored-news analysis cache and append-only reuse lineage."""
from alembic import context,op
from sqlalchemy import text
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import mysql
from service.llm_directional.news_cache import META

revision='0105_llm_news_cache'
down_revision='0104_news_versions'
branch_labels=None
depends_on=None


def upgrade():
    if context.is_offline_mode():
        op.execute('USE alpha_trade')
        for table in META.sorted_tables:
            op.execute(str(CreateTable(table).compile(dialect=mysql.dialect())))
            for index in table.indexes:op.execute(str(CreateIndex(index).compile(dialect=mysql.dialect())))
    else:
        if op.get_bind().execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
            raise RuntimeError('US alpha_trade required')
        META.create_all(op.get_bind(),checkfirst=True)


def downgrade():
    raise RuntimeError('Paid replies are retained. Destructive purge requires explicit separate approval.')
