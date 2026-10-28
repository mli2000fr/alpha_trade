"""Dedicated FR MiFIR research snapshots, contracts, trades and receipts."""
from pathlib import Path

from alembic import op

revision = '0009_fr_mifir_options_research'
down_revision = '0008_fr_reference_research'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().exec_driver_sql('SELECT DATABASE()').scalar() != 'alpha_trade_fr':
        raise RuntimeError('Migration options FR limitée à alpha_trade_fr')
    path = Path(__file__).resolve().parents[2] / 'database/sql/fr/migration_fr_0009_mifir_options_research.sql'
    for statement in path.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError('Suppression des archives options FR interdite sans sauvegarde vérifiée')
