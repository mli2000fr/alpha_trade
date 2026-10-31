"""Public Euronext option OI research observations."""
from pathlib import Path
from alembic import op

revision = '0011_fr_public_option_oi'
down_revision = '0010_fr_batch_research_storage'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().exec_driver_sql('SELECT DATABASE()').scalar() != 'alpha_trade_fr':
        raise RuntimeError('Migration OI publique réservée à alpha_trade_fr')
    path = Path(__file__).resolve().parents[2] / 'database/sql/fr/migration_fr_0011_public_option_oi.sql'
    for statement in path.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError('Suppression des observations OI interdite sans sauvegarde vérifiée')
