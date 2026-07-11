from datetime import UTC, date, datetime, timedelta
from typing import Iterator, Optional

import pandas as pd
from sqlalchemy import MetaData, Table, bindparam, inspect, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Engine

from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY

from screener.models import ScreenerConfig
from database.connection import get_sqlalchemy_engine


REQUIRED_SCORE_COLUMNS = (
	"symbol",
	"liquidity_val",
	"relative_strength_index",
	"historical_range_score",
	"total_score",
	"last_updated_score",
	"sector",
	"anomaly_count",
	"missing_days_count",
	"sanitizer_status",
	"last_updated_scan",
)
ARCHIVABLE_SCORE_COLUMNS = (
	"symbol",
	"sector",
	"liquidity_val",
	"relative_strength_index",
	"historical_range_score",
	"total_score",
	"trend_score",
	"vcp_score",
	"final_score",
	"market_cap",
	"beta_126",
	"spread_bps",
	"earnings_date",
	"days_to_earnings",
	"earnings_blackout",
	"selection_rank",
	"raw_final_score",
	"normalized_total_score",
	"normalized_rsi",
	"total_score_neutralized",
	"relative_strength_index_neutralized",
	"trend_vcp_component",
	"total_score_component",
	"rsi_component",
	"atr_pct_20",
	"weekly_trend_score",
	"high_52w_proximity",
	"volatility_ratio",
	"selector_signal_mode",
	"selection_explanation",
	"sentiment_net_agg",
	"sector_impact_agg",
	"company_idio_score",
	"macro_regime_score",
	"company_idio_signal_norm",
	"macro_regime_signal_norm",
	"company_idio_component",
	"macro_regime_component",
	"quant_component",
	"final_score_sentiment",
	"final_score_walk_forward",
	"walk_forward_sentiment_weight",
	"walk_forward_macro_weight",
	"walk_forward_quant_weight",
	"calibration_run_id",
	"calibration_source",
	"signal_active",
	"anomaly_count",
	"missing_days_count",
	"sanitizer_status",
)
DEFAULT_STOCK_SCORES_COLUMNS = set(ARCHIVABLE_SCORE_COLUMNS)
DEFAULT_STOCK_SCORES_HISTORY_COLUMNS = {
	"snapshot_date",
	"capital_preset_key",
	"config_fingerprint",
	*ARCHIVABLE_SCORE_COLUMNS,
}


def get_engine() -> Engine:
	return get_sqlalchemy_engine()


def _get_scores_table(engine: Engine) -> Table:
	metadata = MetaData()
	return Table("stock_scores", metadata, autoload_with=engine)


def _get_table_columns(engine: Engine, table_name: str, fallback: set[str]) -> set[str]:
	try:
		return {str(column.get("name")) for column in inspect(engine).get_columns(table_name)}
	except Exception:
		return set(fallback)


def _purge_missing_scores(engine: Engine, symbols: list[str]) -> None:
	delete_stmt = text("DELETE FROM stock_scores WHERE symbol NOT IN :symbols").bindparams(
		bindparam("symbols", expanding=True)
	)
	with engine.begin() as conn:
		conn.execute(delete_stmt, {"symbols": symbols})


def iter_symbol_chunks(engine: Engine, chunk_size: int) -> Iterator[list[str]]:
	last_symbol: str | None = None
	stmt = text(
		"""
		SELECT DISTINCT sbd.symbol
		FROM stock_bars_daily sbd
		INNER JOIN stock_metadata sm ON sm.symbol = sbd.symbol
		WHERE sm.status = 'active'
		  AND sm.tradable = 1
		  AND sm.bars_available = 1
		  AND sm.asset_class = 'us_equity'
		  AND (
		        sm.history_status IS NULL
		     OR TRIM(sm.history_status) = ''
		     OR LOWER(TRIM(sm.history_status)) IN ('pending', 'ready')
		  )
		  AND (:last_symbol IS NULL OR sbd.symbol > :last_symbol)
		ORDER BY sbd.symbol
		LIMIT :chunk_size
		"""
	)

	while True:
		with engine.connect() as conn:
			rows = conn.execute(
				stmt,
				{
					"chunk_size": chunk_size,
					"last_symbol": last_symbol,
				},
			).fetchall()

		symbols = [row[0] for row in rows]
		if not symbols:
			break

		yield symbols
		last_symbol = symbols[-1]


def _resolve_reference_date(as_of_date: Optional[date]) -> date:
	ref_dt = datetime.combine(as_of_date, datetime.min.time()) if as_of_date else datetime.now(UTC).replace(tzinfo=None)
	return ref_dt.date()


def _load_price_frame(
	engine: Engine,
	symbols: list[str],
	*,
	cutoff_lower: date,
	as_of_date: Optional[date] = None,
) -> pd.DataFrame:
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


def load_recent_prices_for_chunk(
	engine: Engine,
	symbols: list[str],
	config: ScreenerConfig,
	as_of_date: Optional[date] = None,
) -> pd.DataFrame:
	"""Charge uniquement la fenêtre récente nécessaire à la passe 1 du screener."""
	if not symbols:
		return pd.DataFrame()

	ref_date = _resolve_reference_date(as_of_date)
	effective_window_days = int(getattr(config, "effective_first_pass_window_days", config.first_pass_window_days))
	cutoff_lower = ref_date - timedelta(days=effective_window_days)
	return _load_price_frame(
		engine,
		symbols,
		cutoff_lower=cutoff_lower,
		as_of_date=as_of_date,
	)


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

	ref_date = _resolve_reference_date(as_of_date)
	cutoff_lower = ref_date - timedelta(days=365 * config.lookback_history_years + 30)
	return _load_price_frame(
		engine,
		symbols,
		cutoff_lower=cutoff_lower,
		as_of_date=as_of_date,
	)


def load_historical_range_stats_for_symbols(
	engine: Engine,
	symbols: list[str],
	config: ScreenerConfig,
	as_of_date: Optional[date] = None,
) -> pd.DataFrame:
	"""Charge uniquement les agrégats min/max historiques nécessaires au range score."""
	if not symbols:
		return pd.DataFrame(columns=["symbol", "hist_low", "hist_high"])

	ref_date = _resolve_reference_date(as_of_date)
	cutoff_lower = ref_date - timedelta(days=config.historical_range_lookback_days)
	# Phase 3.2.a : exclure les barres forward-filled du sanitizer pour ne pas
	# polluer min/max historiques (pic figé par un fill long > seuil bas etc.).
	query = """
		SELECT symbol,
		       MIN(low) AS hist_low,
		       MAX(high) AS hist_high
		FROM stock_bars_daily
		WHERE symbol IN :symbols
		  AND `date` >= :cutoff_lower
		  AND (is_filled IS NULL OR is_filled = 0)
	"""
	params: dict = {
		"symbols": symbols,
		"cutoff_lower": cutoff_lower,
	}
	if as_of_date is not None:
		query += "  AND `date` <= :cutoff_upper\n"
		params["cutoff_upper"] = as_of_date

	query += "GROUP BY symbol ORDER BY symbol"
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
		SELECT symbol,
		       anomaly_count,
		       missing_days_count,
		       status AS sanitizer_status
		FROM cleaning_audit_latest
		WHERE symbol IN :symbols
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
	if "last_updated_score" not in normalized.columns:
		normalized["last_updated_score"] = datetime.now(UTC).replace(tzinfo=None)
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
	normalized["sector"] = normalized["sector"].where(normalized["sector"].notna(), None)
	normalized["anomaly_count"] = pd.to_numeric(normalized["anomaly_count"], errors="coerce")
	normalized["missing_days_count"] = pd.to_numeric(normalized["missing_days_count"], errors="coerce")
	normalized["sanitizer_status"] = normalized["sanitizer_status"].where(normalized["sanitizer_status"].notna(), "pending")

	missing_columns = [column for column in REQUIRED_SCORE_COLUMNS if column not in normalized.columns]
	if missing_columns:
		raise ValueError(f"Colonnes manquantes pour stock_scores: {missing_columns}")

	return normalized.loc[:, REQUIRED_SCORE_COLUMNS].copy()


def _coerce_mysql_scalar(value: object) -> object:
	if value is None:
		return None
	try:
		if pd.isna(value):
			return None
	except (TypeError, ValueError):
		# Certains objets scalaires ne sont pas compatibles avec pd.isna.
		return value
	return value


def _records_with_mysql_nulls(records: list[dict[str, object]]) -> list[dict[str, object]]:
	return [
		{key: _coerce_mysql_scalar(value) for key, value in record.items()}
		for record in records
	]


def archive_scores_snapshot(
	engine: Engine,
	snapshot_date: Optional[date] = None,
	*,
	capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
	config_fingerprint: str | None = None,
) -> int:
	"""Archive le contenu actuel de stock_scores dans stock_scores_history.

	Copie toutes les lignes de stock_scores vers stock_scores_history pour la date
	donnée. Utilise ON DUPLICATE KEY UPDATE pour être idempotent (re-exécutable).

	:param engine: SQLAlchemy engine.
	:param snapshot_date: Date d'archivage. Défaut : aujourd'hui.
	:return: Nombre de lignes archivées.
	"""
	ref_date = snapshot_date or date.today()
	resolved_preset_key = str(capital_preset_key or DEFAULT_CAPITAL_PRESET_KEY).strip() or DEFAULT_CAPITAL_PRESET_KEY
	source_columns = _get_table_columns(engine, "stock_scores", DEFAULT_STOCK_SCORES_COLUMNS)
	target_columns = _get_table_columns(engine, "stock_scores_history", DEFAULT_STOCK_SCORES_HISTORY_COLUMNS)
	archivable_columns = [
		column for column in ARCHIVABLE_SCORE_COLUMNS
		if column in source_columns and column in target_columns
	]
	if not archivable_columns:
		return 0
	insert_columns = ["snapshot_date", "capital_preset_key", "config_fingerprint", *archivable_columns]
	select_columns = [":snapshot_date", ":capital_preset_key", ":config_fingerprint", *archivable_columns]
	update_columns = [column for column in archivable_columns if column != "symbol"]
	if not update_columns:
		update_columns = [archivable_columns[0]]
	update_clause = ",\n\t\t\t".join(f"{column} = VALUES({column})" for column in update_columns)
	stmt = text(
		"INSERT INTO stock_scores_history\n"
		f"\t({', '.join(insert_columns)})\n"
		"\tSELECT\n"
		f"\t\t{', '.join(select_columns)}\n"
		"\tFROM stock_scores\n"
		"\tON DUPLICATE KEY UPDATE\n"
		f"\t\t\t{update_clause}"
	)
	with engine.begin() as conn:
		result = conn.execute(
			stmt,
			{
				"snapshot_date": ref_date,
				"capital_preset_key": resolved_preset_key,
				"config_fingerprint": config_fingerprint,
			},
		)
	return result.rowcount


def upsert_scores_snapshot(
	engine: Engine,
	scores_df: pd.DataFrame,
	chunksize: int = 1000,
	snapshot_date: Optional[date] = None,
	*,
	capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
	config_fingerprint: str | None = None,
	delete_existing_on_empty: bool = False,
	purge_missing: bool = True,
	archive_snapshot: bool = True,
) -> None:
	if scores_df.empty:
		if delete_existing_on_empty:
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
			chunk_records = _records_with_mysql_nulls(chunk_records)
			stmt = mysql_insert(scores_table).values(chunk_records)
			update_dict = {
				"liquidity_val": stmt.inserted.liquidity_val,
				"relative_strength_index": stmt.inserted.relative_strength_index,
				"historical_range_score": stmt.inserted.historical_range_score,
				"total_score": stmt.inserted.total_score,
				"last_updated_score": stmt.inserted.last_updated_score,
				"sector": stmt.inserted.sector,
				"anomaly_count": stmt.inserted.anomaly_count,
				"missing_days_count": stmt.inserted.missing_days_count,
				"sanitizer_status": stmt.inserted.sanitizer_status,
				"last_updated_scan": stmt.inserted.last_updated_scan,
			}
			conn.execute(stmt.on_duplicate_key_update(**update_dict))

	if purge_missing:
		_purge_missing_scores(engine, symbols)

	# --- Archivage automatique dans stock_scores_history ---
	if archive_snapshot:
		try:
			archive_scores_snapshot(
				engine,
				snapshot_date=snapshot_date,
				capital_preset_key=capital_preset_key,
				config_fingerprint=config_fingerprint,
			)
		except Exception:
			# L'archivage ne doit jamais casser le pipeline principal.
			# Si la table n'existe pas encore, on ignore silencieusement.
			import logging
			logging.getLogger(__name__).warning(
				"Archivage stock_scores_history echoue (table absente ?). Le pipeline principal n'est pas affecte.",
				exc_info=True,
			)

