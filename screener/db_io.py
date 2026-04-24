from datetime import UTC, date, datetime, timedelta
from typing import Iterator, Optional

import pandas as pd
from sqlalchemy import MetaData, Table, bindparam, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Engine

from screener.models import ScreenerConfig
from database.connection import get_sqlalchemy_engine


REQUIRED_SCORE_COLUMNS = (
	"symbol",
	"liquidity_val",
	"relative_strength_index",
	"historical_range_score",
	"total_score",
	"last_updated_score",
	"is_candidate",
	"sector",
	"anomaly_count",
	"missing_days_count",
	"sanitizer_status",
	"last_updated_scan",
)


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


def iter_symbol_chunks(engine: Engine, chunk_size: int) -> Iterator[list[str]]:
	offset = 0
	stmt = text(
		"""
		SELECT symbol
		FROM (
			SELECT DISTINCT symbol
			FROM stock_bars_daily
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
					"chunk_size": chunk_size,
					"offset": offset,
				},
			).fetchall()

		symbols = [row[0] for row in rows]
		if not symbols:
			break

		yield symbols
		offset += chunk_size


def load_prices_for_chunk(
	engine: Engine,
	symbols: list[str],
	config: ScreenerConfig,
	as_of_date: Optional[date] = None,
) -> pd.DataFrame:
	"""
	Charge l'historique OHLCV pour un chunk de symboles.

	:param as_of_date: Borne supérieure point-in-time (timestamp <= as_of_date).
	    Si None, aucune borne supérieure n'est appliquée (mode live).
	    À TOUJOURS spécifier en backtest pour éviter le look-ahead bias.
	"""
	if not symbols:
		return pd.DataFrame()

	ref_dt = datetime.combine(as_of_date, datetime.min.time()) if as_of_date else datetime.now(UTC).replace(tzinfo=None)
	ref_date = ref_dt.date()
	cutoff_lower = ref_date - timedelta(days=365 * config.lookback_history_years + 30)

	query = """
		SELECT symbol,
		       `date` AS `timestamp`,
		       COALESCE(adj_close, `close`) AS close_price,
		       high AS high_price,
		       low AS low_price,
		       volume
		FROM stock_bars_daily
		WHERE symbol IN :symbols
		  AND `date` >= :cutoff_lower
	"""
	params: dict = {
		"symbols": symbols,
		"cutoff_lower": cutoff_lower,
	}
	if as_of_date is not None:
		query += "  AND `date` <= :cutoff_upper\n"
		params["cutoff_upper"] = as_of_date

	query += "ORDER BY symbol, `date`"
	stmt = text(query).bindparams(bindparam("symbols", expanding=True))

	return pd.read_sql_query(stmt, engine, params=params)


def load_spy_return_6m(
	engine: Engine,
	config: ScreenerConfig,
	as_of_date: Optional[date] = None,
) -> float:
	"""
	Calcule le rendement SPY sur la fenêtre relative (lookback_relative_days).

	:param as_of_date: Borne point-in-time. Si None, on prend le dernier bar disponible.
	"""
	query = """
		SELECT `date` AS `timestamp`, COALESCE(adj_close, `close`) AS close_price
		FROM stock_bars_daily
		WHERE symbol = :symbol
	"""
	params: dict = {"symbol": config.benchmark_symbol}
	if as_of_date is not None:
		query += "  AND `date` <= :cutoff_upper\n"
		params["cutoff_upper"] = as_of_date

	query += "ORDER BY `date`"
	spy_df = pd.read_sql_query(text(query), engine, params=params)
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


def _load_metadata_sectors(engine: Engine, symbols: list[str]) -> pd.DataFrame:
	if not symbols:
		return pd.DataFrame(columns=["symbol", "sector"])

	stmt = text(
		"""
		SELECT symbol, sector
		FROM stock_metadata
		WHERE symbol IN :symbols
		"""
	).bindparams(bindparam("symbols", expanding=True))

	return pd.read_sql_query(stmt, engine, params={"symbols": symbols})


def _enrich_scores_with_metadata_sector(engine: Engine, scores_df: pd.DataFrame) -> pd.DataFrame:
	if scores_df.empty:
		return scores_df.copy()

	enriched = scores_df.copy()
	metadata_sectors = _load_metadata_sectors(engine, enriched["symbol"].astype(str).tolist())
	if metadata_sectors.empty:
		return enriched

	metadata_sectors = metadata_sectors.copy()
	metadata_sectors["sector"] = metadata_sectors["sector"].where(metadata_sectors["sector"].notna(), None)
	sector_map = metadata_sectors.set_index("symbol")["sector"]
	enriched["sector"] = enriched["symbol"].map(sector_map).where(lambda column: column.notna(), enriched.get("sector"))
	return enriched


def _load_latest_audit_metrics(engine: Engine, symbols: list[str]) -> pd.DataFrame:
	if not symbols:
		return pd.DataFrame(columns=["symbol", "anomaly_count", "missing_days_count", "sanitizer_status"])

	stmt = text(
		"""
		SELECT audit.symbol,
		       audit.anomaly_count,
		       audit.missing_days_count,
		       audit.status AS sanitizer_status
		FROM cleaning_audit_log audit
		INNER JOIN (
			SELECT symbol, MAX(id) AS max_id
			FROM cleaning_audit_log
			WHERE symbol IN :symbols
			GROUP BY symbol
		) latest ON latest.max_id = audit.id
		WHERE audit.symbol IN :symbols
		"""
	).bindparams(bindparam("symbols", expanding=True))

	return pd.read_sql_query(stmt, engine, params={"symbols": symbols})


def _enrich_scores_with_audit(engine: Engine, scores_df: pd.DataFrame) -> pd.DataFrame:
	if scores_df.empty:
		return scores_df.copy()

	enriched = scores_df.copy()
	audit_df = _load_latest_audit_metrics(engine, enriched["symbol"].astype(str).tolist())
	if audit_df.empty:
		return enriched

	audit_df = audit_df.copy()
	audit_df["anomaly_count"] = pd.to_numeric(audit_df["anomaly_count"], errors="coerce")
	audit_df["missing_days_count"] = pd.to_numeric(audit_df["missing_days_count"], errors="coerce")
	audit_df["sanitizer_status"] = audit_df["sanitizer_status"].where(audit_df["sanitizer_status"].notna(), None)
	return enriched.merge(audit_df, on="symbol", how="left", suffixes=("", "_audit"))


def _normalize_scores_snapshot(scores_df: pd.DataFrame) -> pd.DataFrame:
	if scores_df.empty:
		return scores_df.copy()

	normalized = scores_df.copy()
	if "last_updated_score" not in normalized.columns and "last_updated" in normalized.columns:
		normalized = normalized.rename(columns={"last_updated": "last_updated_score"})
	if "is_candidate" not in normalized.columns and "top_swing" in normalized.columns:
		normalized = normalized.rename(columns={"top_swing": "is_candidate"})

	if "last_updated_score" not in normalized.columns:
		normalized["last_updated_score"] = datetime.now(UTC).replace(tzinfo=None)
	if "is_candidate" not in normalized.columns:
		normalized["is_candidate"] = 0
	if "sector" not in normalized.columns:
		normalized["sector"] = None
	if "anomaly_count" not in normalized.columns:
		normalized["anomaly_count"] = None
	if "missing_days_count" not in normalized.columns:
		normalized["missing_days_count"] = None
	if "sanitizer_status" not in normalized.columns:
		normalized["sanitizer_status"] = "pending"
	if "last_updated_scan" not in normalized.columns:
		normalized["last_updated_scan"] = normalized["last_updated_score"]

	normalized["last_updated_score"] = pd.to_datetime(normalized["last_updated_score"], utc=False)
	normalized["last_updated_scan"] = pd.to_datetime(normalized["last_updated_scan"], utc=False)
	normalized["is_candidate"] = normalized["is_candidate"].fillna(0).astype(int)
	normalized["sector"] = normalized["sector"].where(normalized["sector"].notna(), None)
	normalized["anomaly_count"] = pd.to_numeric(normalized["anomaly_count"], errors="coerce")
	normalized["missing_days_count"] = pd.to_numeric(normalized["missing_days_count"], errors="coerce")
	normalized["sanitizer_status"] = normalized["sanitizer_status"].where(normalized["sanitizer_status"].notna(), "pending")

	missing_columns = [column for column in REQUIRED_SCORE_COLUMNS if column not in normalized.columns]
	if missing_columns:
		raise ValueError(f"Colonnes manquantes pour stock_scores: {missing_columns}")

	return normalized.loc[:, REQUIRED_SCORE_COLUMNS].copy()


def archive_scores_snapshot(engine: Engine, snapshot_date: Optional[date] = None) -> int:
	"""Archive le contenu actuel de stock_scores dans stock_scores_history.

	Copie toutes les lignes de stock_scores vers stock_scores_history pour la date
	donnée. Utilise ON DUPLICATE KEY UPDATE pour être idempotent (re-exécutable).

	:param engine: SQLAlchemy engine.
	:param snapshot_date: Date d'archivage. Défaut : aujourd'hui.
	:return: Nombre de lignes archivées.
	"""
	ref_date = snapshot_date or date.today()
	stmt = text("""
		INSERT INTO stock_scores_history
			(snapshot_date, symbol, sector,
			 liquidity_val, relative_strength_index, historical_range_score, total_score,
			 trend_score, vcp_score, final_score, is_candidate,
			 sentiment_net_agg, sector_impact_agg, final_score_sentiment, signal_active,
			 anomaly_count, missing_days_count, sanitizer_status)
		SELECT
			:snapshot_date, symbol, sector,
			liquidity_val, relative_strength_index, historical_range_score, total_score,
			trend_score, vcp_score, final_score, is_candidate,
			sentiment_net_agg, sector_impact_agg, final_score_sentiment, signal_active,
			anomaly_count, missing_days_count, sanitizer_status
		FROM stock_scores
		ON DUPLICATE KEY UPDATE
			sector                  = VALUES(sector),
			liquidity_val           = VALUES(liquidity_val),
			relative_strength_index = VALUES(relative_strength_index),
			historical_range_score  = VALUES(historical_range_score),
			total_score             = VALUES(total_score),
			trend_score             = VALUES(trend_score),
			vcp_score               = VALUES(vcp_score),
			final_score             = VALUES(final_score),
			is_candidate            = VALUES(is_candidate),
			sentiment_net_agg       = VALUES(sentiment_net_agg),
			sector_impact_agg       = VALUES(sector_impact_agg),
			final_score_sentiment   = VALUES(final_score_sentiment),
			signal_active           = VALUES(signal_active),
			anomaly_count           = VALUES(anomaly_count),
			missing_days_count      = VALUES(missing_days_count),
			sanitizer_status        = VALUES(sanitizer_status)
	""")
	with engine.begin() as conn:
		result = conn.execute(stmt, {"snapshot_date": ref_date})
	return result.rowcount


def upsert_scores_snapshot(
	engine: Engine,
	scores_df: pd.DataFrame,
	chunksize: int = 1000,
	snapshot_date: Optional[date] = None,
) -> None:
	if scores_df.empty:
		with engine.begin() as conn:
			conn.execute(text("DELETE FROM stock_scores"))
		return

	scores_df = _enrich_scores_with_metadata_sector(engine, scores_df)
	scores_df = _enrich_scores_with_audit(engine, scores_df)
	scores_df = _normalize_scores_snapshot(scores_df)
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
				"last_updated_score": stmt.inserted.last_updated_score,
				"is_candidate": stmt.inserted.is_candidate,
				"sector": stmt.inserted.sector,
				"anomaly_count": stmt.inserted.anomaly_count,
				"missing_days_count": stmt.inserted.missing_days_count,
				"sanitizer_status": stmt.inserted.sanitizer_status,
				"last_updated_scan": stmt.inserted.last_updated_scan,
			}
			conn.execute(stmt.on_duplicate_key_update(**update_dict))

	_purge_missing_scores(engine, symbols)

	# --- Archivage automatique dans stock_scores_history ---
	try:
		archive_scores_snapshot(engine, snapshot_date=snapshot_date)
	except Exception:
		# L'archivage ne doit jamais casser le pipeline principal.
		# Si la table n'existe pas encore, on ignore silencieusement.
		import logging
		logging.getLogger(__name__).warning(
			"Archivage stock_scores_history echoue (table absente ?). Le pipeline principal n'est pas affecte.",
			exc_info=True,
		)

