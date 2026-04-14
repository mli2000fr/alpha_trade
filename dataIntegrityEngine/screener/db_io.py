from datetime import datetime, timedelta
from typing import Iterator, List

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from dataIntegrityEngine.screener.models import ScreenerConfig
from database.connection import get_sqlalchemy_engine


def get_engine() -> Engine:
	return get_sqlalchemy_engine()


def iter_symbol_chunks(engine: Engine, chunk_size: int, timeframe: str) -> Iterator[List[str]]:
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


def load_prices_for_chunk(engine: Engine, symbols: List[str], config: ScreenerConfig) -> pd.DataFrame:
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
		raise RuntimeError(f"Aucune donnee benchmark pour {config.benchmark_symbol}.")

	spy_df["timestamp"] = pd.to_datetime(spy_df["timestamp"], utc=False)
	latest = spy_df["timestamp"].max()
	cutoff = latest - pd.Timedelta(days=config.lookback_relative_days)
	window = spy_df[spy_df["timestamp"] >= cutoff]

	if len(window) < 2:
		raise RuntimeError("Historique benchmark insuffisant pour calculer la force relative.")

	start_close = float(window["close_price"].iloc[0])
	end_close = float(window["close_price"].iloc[-1])
	return (end_close / start_close) - 1.0


def recreate_scores_table(engine: Engine) -> None:
	ddl = """
	DROP TABLE IF EXISTS stock_scores;
	CREATE TABLE stock_scores (
		symbol VARCHAR(20) NOT NULL,
		liquidity_val DOUBLE NOT NULL,
		relative_strength_index DOUBLE NOT NULL,
		historical_range_score DOUBLE NOT NULL,
		total_score DOUBLE NOT NULL,
		last_updated DATETIME NOT NULL,
		PRIMARY KEY (symbol),
		INDEX idx_total_score (total_score)
	) ENGINE=InnoDB;
	"""
	with engine.begin() as conn:
		for statement in [s.strip() for s in ddl.split(";") if s.strip()]:
			conn.execute(text(statement))


def write_scores_bulk(engine: Engine, scores_df: pd.DataFrame, chunksize: int = 1000) -> None:
	if scores_df.empty:
		return

	scores_df.to_sql(
		"stock_scores",
		con=engine,
		if_exists="append",
		index=False,
		method="multi",
		chunksize=chunksize,
	)

