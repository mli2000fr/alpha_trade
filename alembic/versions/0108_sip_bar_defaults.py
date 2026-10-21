"""SIP defaults for future US bar inserts, never relabel stored values."""
from alembic import op
from sqlalchemy import text

revision = "0108_sip_bar_defaults"
down_revision = "0106_quote_provenance"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade":
        raise RuntimeError("US alpha_trade required")
    previous = bind.execute(text("SELECT @@SESSION.lock_wait_timeout")).scalar_one()
    op.execute("SET SESSION lock_wait_timeout = 5")
    try:
        for table in ("stock_bars", "stock_bars_daily"):
            op.execute(f"ALTER TABLE `{table}` ALTER COLUMN data_source SET DEFAULT 'alpaca_sip', ALGORITHM=INSTANT")
    finally:
        op.execute(f"SET SESSION lock_wait_timeout = {int(previous)}")


def downgrade():
    raise RuntimeError("Do not silently restore an IEX default")
