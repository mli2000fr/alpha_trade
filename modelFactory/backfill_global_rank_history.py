"""modelFactory/backfill_global_rank_history.py — Backfill global_rank_history depuis un parquet WF.

P1-4 (2026-08-12) : le backtest Global Ranking (module ``backtesting``) lit
``alpha_trade.global_rank_history`` comme source de vérité. Les rangs OOS
walk-forward sont sauvegardés en parquet par ``train_global_ranking_wf``
(``artifacts/models/{batch_id}/global_rank_cache.parquet``).

Ce script charge le parquet et l'upsert dans la table (par chunks de 5000),
pour permettre au backtest complet (cascade → PortfolioBuilder → exécution)
de tourner sur un batch de recherche.

Usage :
    python -m modelFactory.backfill_global_rank_history --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

_CHUNK_SIZE = 5000


def _resolve_engine():
    """Résout le moteur SQLAlchemy (même logique que predictor.py)."""
    try:
        from ihm.services.db import get_engine
        return get_engine()
    except Exception:
        pass
    try:
        from database.connection import get_sqlalchemy_engine
        return get_sqlalchemy_engine()
    except Exception:
        return None


def backfill_global_rank_history(batch_id: str, *, parquet_path: Path | None = None) -> dict:
    """Charge le parquet WF d'un batch et l'upsert dans global_rank_history."""
    engine = _resolve_engine()
    if engine is None:
        LOGGER.error("No SQLAlchemy engine available")
        return {"status": "error", "reason": "no_engine"}

    if parquet_path is None:
        parquet_path = Path("artifacts") / "models" / batch_id / "global_rank_cache.parquet"
    if not parquet_path.exists():
        LOGGER.error("Parquet not found: %s", parquet_path)
        return {"status": "error", "reason": f"parquet_not_found: {parquet_path}"}

    df = pd.read_parquet(parquet_path)
    if df.empty:
        return {"status": "skipped", "reason": "empty_parquet"}
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    _rank_cols = [
        c for c in ("global_rank_3", "global_rank_5", "global_rank_10", "global_rank_15", "global_rank_20")
        if c in df.columns
    ]
    if not _rank_cols:
        return {"status": "error", "reason": "no_rank_columns"}

    from sqlalchemy import text as _text

    _sql = _text(
        f"INSERT INTO alpha_trade.global_rank_history "
        f"(symbol, `date`, {', '.join(_rank_cols)}, batch_id) "
        f"VALUES ({', '.join(':' + c for c in ['symbol', 'date'] + _rank_cols + ['batch_id'])}) "
        f"ON DUPLICATE KEY UPDATE "
        + ", ".join(f"{c} = VALUES({c})" for c in _rank_cols)
        + ", created_at = CURRENT_TIMESTAMP"
    )

    inserted = 0
    n_chunks = (len(df) + _CHUNK_SIZE - 1) // _CHUNK_SIZE
    for i in range(0, len(df), _CHUNK_SIZE):
        chunk = df.iloc[i:i + _CHUNK_SIZE]
        rows = [
            {
                "symbol": str(r.symbol),
                "date": r.date,
                **{c: (float(getattr(r, c)) if pd.notna(getattr(r, c)) else None) for c in _rank_cols},
                "batch_id": batch_id,
            }
            for r in chunk.itertuples(index=False)
        ]
        try:
            with engine.begin() as conn:
                for row in rows:
                    conn.execute(_sql, row)
            inserted += len(rows)
        except Exception:
            LOGGER.exception("backfill_global_rank_history: DB error at chunk %d", i // _CHUNK_SIZE)
        if (i // _CHUNK_SIZE) % 10 == 0:
            LOGGER.info("backfill_global_rank_history progress %d/%d chunks", i // _CHUNK_SIZE, n_chunks)

    LOGGER.info(
        "backfill_global_rank_history done batch_id=%s rows=%d dates=%s symbols=%d",
        batch_id, inserted, df["date"].nunique(), df["symbol"].nunique(),
    )
    return {
        "status": "completed",
        "batch_id": batch_id,
        "inserted": inserted,
        "dates": int(df["date"].nunique()),
        "symbols": int(df["symbol"].nunique()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill global_rank_history depuis un parquet WF.")
    parser.add_argument("--batch-id", required=True, help="Batch ID (dossier artifacts/models/<batch_id>)")
    parser.add_argument("--parquet", default=None, help="Chemin parquet explicite (défaut: artifacts/models/<batch_id>/global_rank_cache.parquet)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    result = backfill_global_rank_history(args.batch_id, parquet_path=Path(args.parquet) if args.parquet else None)
    print(result)


if __name__ == "__main__":
    main()
