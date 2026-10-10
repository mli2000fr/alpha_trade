"""Create US synthetic prediction parents with explicit market lineage."""
from datetime import datetime, timezone

from sqlalchemy import text

from modelFactory.db_registry import _resolve_batch_market_code


def ensure_synthetic_run(engine, *, batch_id: str, run_id: str, symbol: str) -> None:
    # These legacy synthesizers address alpha_trade explicitly, never CN/FR.
    market_code = _resolve_batch_market_code(engine, batch_id, "US_EQ")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO alpha_trade.model_training_run "
            "(run_id, batch_id, market_code, registry_id, symbol, status, started_at, finished_at) "
            "VALUES (:run_id, :batch_id, :market_code, 0, :symbol, 'completed', :now, :now) "
            "ON DUPLICATE KEY UPDATE batch_id=VALUES(batch_id), market_code=VALUES(market_code)"
        ), {"run_id": run_id, "batch_id": batch_id, "market_code": market_code,
            "symbol": symbol, "now": datetime.now(timezone.utc)})
