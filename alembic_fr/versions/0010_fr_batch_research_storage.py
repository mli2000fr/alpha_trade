"""FR batch research documents and normalized market observations."""
from pathlib import Path
from alembic import op

revision = '0010_fr_batch_research_storage'
down_revision = '0009_fr_mifir_options_research'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().exec_driver_sql('SELECT DATABASE()').scalar() != 'alpha_trade_fr':
        raise RuntimeError('Migration batchs FR limitée à alpha_trade_fr')
    path = Path(__file__).resolve().parents[2] / 'database/sql/fr/migration_fr_0010_batch_research_storage.sql'
    for statement in path.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError('Suppression des archives de recherche FR interdite sans sauvegarde vérifiée')
