from datetime import datetime, timedelta
from typing import Iterator

import pandas as pd
from sqlalchemy import MetaData, Table, bindparam, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Engine

from dataIntegrityEngine.screener.models import ScreenerConfig
from database.connection import get_sqlalchemy_engine


def get_engine() -> Engine:
	return get_sqlalchemy_engine()


def _get_scores_table(engine: Engine) -> Table:
	metadata = MetaData()
	return Table("stock_scores", metadata, autoload_with=engine)


def _purge_missing_scores(engine: Engine, symbols: list[str]) -> None:
	delete_stmt = text("DELETE FROM stock_scores WHERE symbol NOT IN :symbols").bindparams(
		bindparam("symbols", expanding=True)
	)
	with engine.begin() as conn:
		conn.execute(delete_stmt, {"symbols": symbols})


def iter_symbol_chunks(engine: Engine, chunk_size: int, timeframe: str) -> Iterator[list[str]]:
	offset = 0
	stmt = text(
		"""
		SELECT symbol
		FROM (
			SELECT DISTINCT symbol
			FROM stock_bars
			WHERE timeframe = :timeframe
		) s
		ORDER BY symbol
		LIMIT :chunk_size OFFSET :offset
		"""
	)

	while True:
		with engine.connect() as conn:
			rows = conn.execute(
				stmt,
				{
					"timeframe": timeframe,
					"chunk_size": chunk_size,
					"offset": offset,
				},
			).fetchall()

		symbols = [row[0] for row in rows]
		if not symbols:
			break

		yield symbols
		offset += chunk_size


def load_prices_for_chunk(engine: Engine, symbols: list[str], config: ScreenerConfig) -> pd.DataFrame:
	if not symbols:
		return pd.DataFrame()

	cutoff = datetime.utcnow() - timedelta(days=365 * config.lookback_history_years + 30)
	stmt = text(
		"""
		SELECT symbol, `timestamp`, close_price, high_price, low_price, volume
		FROM stock_bars
		WHERE timeframe = :timeframe
		  AND symbol IN :symbols
		  AND `timestamp` >= :cutoff
		ORDER BY symbol, `timestamp`
		"""
	).bindparams(bindparam("symbols", expanding=True))

	return pd.read_sql_query(
		stmt,
		engine,
		params={
			"timeframe": config.timeframe,
			"symbols": symbols,
			"cutoff": cutoff,
		},
	)


def load_spy_return_6m(engine: Engine, config: ScreenerConfig) -> float:
	stmt = text(
		"""
		SELECT `timestamp`, close_price
		FROM stock_bars
		WHERE symbol = :symbol
		  AND timeframe = :timeframe
		ORDER BY `timestamp`
		"""
	)
	spy_df = pd.read_sql_query(
		stmt,
		engine,
		params={"symbol": config.benchmark_symbol, "timeframe": config.timeframe},
	)
	if spy_df.empty:
		raise RuntimeError(f"Aucune donnée benchmark pour {config.benchmark_symbol}.")

	spy_df["timestamp"] = pd.to_datetime(spy_df["timestamp"], utc=False)
	latest = spy_df["timestamp"].max()
	cutoff = latest - pd.Timedelta(days=config.lookback_relative_days)
	window = spy_df[spy_df["timestamp"] >= cutoff]

	if len(window) < 2:
		raise RuntimeError("Historique benchmark insuffisant pour calculer la force relative.")

	start_close = float(window["close_price"].iloc[0])
	end_close = float(window["close_price"].iloc[-1])
	return (end_close / start_close) - 1.0


def upsert_scores_snapshot(engine: Engine, scores_df: pd.DataFrame, chunksize: int = 1000) -> None:
	if scores_df.empty:
		with engine.begin() as conn:
			conn.execute(text("DELETE FROM stock_scores"))
		return

	scores_table = _get_scores_table(engine)
	symbols = scores_df["symbol"].astype(str).tolist()

	with engine.begin() as conn:
		for start in range(0, len(scores_df), chunksize):
			chunk_records = scores_df.iloc[start:start + chunksize].to_dict(orient="records")
			stmt = mysql_insert(scores_table).values(chunk_records)
			update_dict = {
				"liquidity_val": stmt.inserted.liquidity_val,
				"relative_strength_index": stmt.inserted.relative_strength_index,
				"historical_range_score": stmt.inserted.historical_range_score,
				"total_score": stmt.inserted.total_score,
				"last_updated": stmt.inserted.last_updated,
			}
			conn.execute(stmt.on_duplicate_key_update(**update_dict))

	_purge_missing_scores(engine, symbols)

