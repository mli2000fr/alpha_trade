"""Explicit historical quote feed and archived evidence, US only."""
from alembic import op
import sqlalchemy as sa

revision = "0106_quote_provenance"
down_revision = "0088_us_fact_instrument_constraints"
branch_labels = ("quote_provenance",)
depends_on = None


def upgrade():
    if op.get_bind().execute(sa.text("SELECT DATABASE()")).scalar_one() != "alpha_trade":
        raise RuntimeError("US alpha_trade required")
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("stock_quote_snapshots")}
    definitions = {"provider": "VARCHAR(20)", "feed": "VARCHAR(20)",
                   "quality_status": "VARCHAR(32)", "collected_at": "DATETIME(6)",
                   "source_timestamp": "DATETIME(6)", "raw_payload_sha256": "VARCHAR(64)",
                   "raw_payload_path": "VARCHAR(512)"}
    missing = [f"ADD COLUMN `{name}` {kind} NULL" for name, kind in definitions.items() if name not in columns]
    if missing:
        # Explicit INSTANT prevents a silent COPY/INPLACE table rebuild.
        # Metadata lock wait is bounded; failure leaves collection blocked.
        previous = op.get_bind().execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one()
        op.execute("SET SESSION lock_wait_timeout = 5")
        try:
            op.execute("ALTER TABLE stock_quote_snapshots " + ", ".join(missing) + ", ALGORITHM=INSTANT")
        finally:
            op.execute(f"SET SESSION lock_wait_timeout = {int(previous)}")
    # Additive only: preserve the legacy DATETIME on large existing tables.
    # Precise timestamps use the new nullable source_timestamp column.


def downgrade():
    raise RuntimeError("Quote provenance retained; destructive downgrade requires separate approval")
