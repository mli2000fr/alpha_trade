"""Preserve Oracle double precision and index CN evidence lookups."""
from alembic import op

revision='0009_collection_lookup_indexes'
down_revision='0008_collection_sql_primary'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if bind.exec_driver_sql('SELECT DATABASE()').scalar()!='alpha_trade_cn':
        raise RuntimeError('CN migration refused outside alpha_trade_cn')
    op.execute('ALTER TABLE cn_oracle_prospective_candidates MODIFY COLUMN oracle_score DOUBLE NULL')
    op.create_index('ix_cn_snapshot_session_observed','cn_dragon_tiger_snapshots',['trade_date','observed_at_utc'])
    op.create_index('ix_cn_events_session_code','cn_dragon_tiger_events',['trade_date','exchange','code'])
    op.create_index('ix_cn_candidates_decision_code','cn_oracle_prospective_candidates',['decision_date','exchange','code'])
    op.create_index('ix_cn_matches_decision','cn_dragon_tiger_matches',['decision_date'])
    op.create_index('ix_cn_reports_batch_status','cn_collection_reports',['batch_name','status'])

def downgrade():
    raise RuntimeError('CN SQL evidence precision downgrade requires an explicit migration')
