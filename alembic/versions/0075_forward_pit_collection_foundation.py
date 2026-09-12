"""Forward PIT collection foundation.

Revision ID: 0075_forward_pit_collection
Revises: 0074_fundamental_pit_contract
"""
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0075_forward_pit_collection"
down_revision: str | None = "0074_fundamental_pit_contract"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLES = (
    "pit_data_quality_issues", "pit_data_quality_metrics", "macro_vintage_observations",
    "sec_ownership_snapshots", "sec_corporate_events", "stock_opening_window_bars",
    "stock_option_snapshots", "stock_analyst_consensus_snapshots",
    "stock_borrow_status_snapshots", "sec_filing_raw", "corporate_action_source_events",
    "security_master_changes", "security_master_snapshots", "stock_bars_daily_versions",
    "pit_raw_payloads", "pit_collection_runs",
)


def _statements() -> list[str]:
    path = Path(__file__).resolve().parents[2] / "database" / "sql" / "forward_pit" / "forward_pit_tables.sql"
    content = path.read_text(encoding="utf-8")
    content = "\n".join(
        line for line in content.splitlines() if not line.lstrip().startswith("--")
    )
    return [part.strip() for part in content.split(";") if part.strip()]


def upgrade() -> None:
    for statement in _statements():
        op.execute(statement)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS alpha_trade.{table}")
