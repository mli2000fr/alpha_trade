"""FR SQL primary storage, including state and binary responses."""
from pathlib import Path
from alembic import op

revision = '0012_fr_sql_primary'
down_revision = '0011_fr_public_option_oi'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().exec_driver_sql('SELECT DATABASE()').scalar() != 'alpha_trade_fr':
        raise RuntimeError('Migration réservée à alpha_trade_fr')
    path = Path(__file__).resolve().parents[2]/'database/sql/fr/migration_fr_0012_sql_primary.sql'
    for statement in path.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError('Stockage principal : restauration explicite requise, pas de suppression automatique')
