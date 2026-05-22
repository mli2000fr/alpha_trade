from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, text

from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.engine import CorporateActionEngine
from tests.test_corporate_actions import SQLITE_SCHEMA, FakeProvider, _make_dividend_event


def _build_sqlite_repo() -> CorporateActionRepository:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        for stmt in SQLITE_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return CorporateActionRepository(engine=engine)


def test_cash_ledger_is_idempotent_when_same_dividend_is_reapplied() -> None:
    repo = _build_sqlite_repo()
    event = _make_dividend_event(symbol="AAPL", amount=0.25, ex_date=date(2026, 4, 10))
    engine = CorporateActionEngine(provider=FakeProvider([event]), repo=repo)

    sync_stats = engine.sync()
    assert sync_stats["inserted"] == 1

    with repo.engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO broker_positions_snapshots
                (exec_run_id, broker_mode, symbol, qty, avg_entry_price, market_value, unrealized_pnl)
            VALUES ('run-001', 'paper', 'AAPL', 100, 150.0, 15000.0, 500.0)
            """
        ))

    first_apply = engine.apply(as_of=date(2026, 12, 31))
    second_apply = engine.apply(as_of=date(2026, 12, 31))

    assert first_apply["applied"] == 1
    assert second_apply["applied"] == 0
    assert repo.get_total_dividends(symbol="AAPL") == 25.0

    with repo.engine.connect() as conn:
        ledger_count = conn.execute(text("SELECT COUNT(*) FROM portfolio_cash_ledger WHERE symbol = 'AAPL'")).scalar_one()
    assert int(ledger_count) == 1

