import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Literal
from typing import Any
from uuid import uuid4

import requests


from common.utils import configure_root_logging
from core.run_summary import attach_schema_version, merge_iex_bias_counters
from database.assets import (
	count_eligible_symbols_with_stale_market_cap,
	get_symbols_missing_fundamentals,
	get_stock_metadata_fundamentals_map,
	get_symbols_with_stale_market_cap,
	list_eligible_stock_symbols,
	update_stock_metadata_fundamentals,
)
from service.eodhd.clientEodhd import (
	EodhdPermissionError,
	fetch_symbol_fundamentals_record as fetch_eodhd_fundamentals_record,
)
from service.finnhub.clientFinnhub import (
	MIN_REQUEST_INTERVAL_SECONDS,
	fetch_symbol_fundamentals_record as fetch_finnhub_fundamentals_record,
)
from service.yahoo.clientYahooFinance import (
	fetch_symbol_fundamentals_record as fetch_yahoo_fundamentals_record,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_LOG_EVERY = 50
DEFAULT_REFRESH_STALE_DAYS = 30
NOT_AVAILABLE = "N/A"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
FundamentalsProvider = Literal["yahoo_finance", "eodhd", "finnhub"]
DEFAULT_PROVIDER_FALLBACK: FundamentalsProvider = "finnhub"


def _utc_now_naive() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
	return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, Any]) -> None:
	print(
		f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
		flush=True,
	)

# Compatibilité rétroactive pour les tests / appelants legacy.
get_symbols_missing_sector = get_symbols_missing_fundamentals


def update_stock_metadata_sector(symbol: str, sector: str) -> int:
	return update_stock_metadata_fundamentals(symbol, sector=sector)


def _normalize_provider(provider: str) -> FundamentalsProvider:
	normalized = str(provider or "yahoo_finance").strip().lower()
	provider_aliases = {
		"yahoo": "yahoo_finance",
		"yahoo_finance": "yahoo_finance",
		"yfinance": "yahoo_finance",
		"eodhd": "eodhd",
		"finnhub": "finnhub",
	}
	if normalized not in provider_aliases:
		raise ValueError("provider doit être 'yahoo_finance', 'eodhd' ou 'finnhub'.")
	normalized = provider_aliases[normalized]
	return normalized  # type: ignore[return-value]


def _select_target_symbols(
	*,
	limit: int | None,
	refresh_stale_days: int | None,
	overwrite_existing: bool,
) -> tuple[list[str], list[str], list[str]]:
	missing_symbols = get_symbols_missing_sector(limit=limit)
	stale_symbols: list[str] = []
	if refresh_stale_days is not None:
		stale_symbols = get_symbols_with_stale_market_cap(
			max_age_days=refresh_stale_days,
			limit=limit,
		)

	if overwrite_existing:
		eligible_symbols = list_eligible_stock_symbols(limit=limit)
		return eligible_symbols, missing_symbols, stale_symbols

	seen: set[str] = set()
	combined: list[str] = []
	for source in (missing_symbols, stale_symbols):
		for sym in source:
			if sym not in seen:
				seen.add(sym)
				combined.append(sym)
	if limit is not None:
		combined = combined[:limit]
	return combined, missing_symbols, stale_symbols


def _fetch_fundamentals(
	symbol: str,
	*,
	provider: FundamentalsProvider,
	session: requests.Session,
) -> dict[str, Any]:
	if provider == "yahoo_finance":
		return fetch_yahoo_fundamentals_record(symbol, session=session)
	if provider == "finnhub":
		return fetch_finnhub_fundamentals_record(symbol, session=session)
	return fetch_eodhd_fundamentals_record(symbol, session=session)


def _normalize_sector(value: Any) -> str | None:
	sector = str(value or "").strip()
	if not sector or sector == NOT_AVAILABLE:
		return None
	return sector


def _build_update_payload(
	*,
	symbol: str,
	fetched_sector: str | None,
	fetched_market_cap: float | None,
	existing_row: dict[str, Any],
	stale_symbols: set[str],
	overwrite_existing: bool,
) -> dict[str, Any]:
	current_sector = _normalize_sector(existing_row.get("sector"))
	current_market_cap = existing_row.get("market_cap")
	payload: dict[str, Any] = {"symbol": symbol}

	if overwrite_existing:
		if fetched_sector is not None:
			payload["sector"] = fetched_sector
		if fetched_market_cap is not None:
			payload["market_cap"] = fetched_market_cap
		return payload

	if current_sector is None and fetched_sector is not None:
		payload["sector"] = fetched_sector
	if (current_market_cap is None or symbol in stale_symbols) and fetched_market_cap is not None:
		payload["market_cap"] = fetched_market_cap
	return payload


def update_missing_sectors(
	limit: int | None = None,
	sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
	log_every: int = DEFAULT_LOG_EVERY,
	*,
	refresh_stale_days: int | None = None,
	provider: FundamentalsProvider = "yahoo_finance",
	overwrite_existing: bool = False,
) -> dict[str, Any]:
	provider = _normalize_provider(provider)
	if sleep_seconds < 0:
		raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")
	if log_every < 1:
		raise ValueError("log_every doit être supérieur ou égal à 1.")
	if refresh_stale_days is not None and refresh_stale_days < 0:
		raise ValueError("refresh_stale_days doit être >= 0.")

	symbols, missing_symbols, stale_symbols = _select_target_symbols(
		limit=limit,
		refresh_stale_days=refresh_stale_days,
		overwrite_existing=overwrite_existing,
	)
	total = len(symbols)
	stale_symbol_set = {str(symbol).strip().upper() for symbol in stale_symbols}
	existing_rows = get_stock_metadata_fundamentals_map(symbols)
	summary: dict[str, Any] = {
		"total": total,
		"updated": 0,
		"skipped": 0,
		"failed": 0,
		"missing_fundamentals_targets": len(missing_symbols),
		"stale_market_cap_targets": len(stale_symbols),
		"refresh_stale_days": refresh_stale_days,
		"provider": provider,
		"provider_effective": provider,
		"overwrite_existing": bool(overwrite_existing),
		"provider_fallback_triggered": False,
		"provider_fallback_count": 0,
	}

	LOGGER.info(
		"Debut mise a jour fondamentaux stock_metadata | provider=%s overwrite_existing=%s symboles_a_traiter=%s limit=%s",
		provider,
		overwrite_existing,
		total,
		limit,
	)
	LOGGER.info("Debut mise a jour sector stock_metadata")
	if not symbols:
		return summary

	session = requests.Session()
	effective_provider: FundamentalsProvider = provider
	try:
		for index, symbol in enumerate(symbols, start=1):
			try:
				try:
					record = _fetch_fundamentals(symbol, provider=effective_provider, session=session)
				except EodhdPermissionError as exc:
					if effective_provider != "eodhd":
						raise
					fallback_provider = DEFAULT_PROVIDER_FALLBACK
					effective_provider = fallback_provider
					summary["provider_effective"] = fallback_provider
					summary["provider_fallback_triggered"] = True
					summary["provider_fallback_count"] = int(summary.get("provider_fallback_count", 0) or 0) + 1
					summary["provider_fallback_from"] = provider
					summary["provider_fallback_to"] = fallback_provider
					summary["provider_fallback_reason"] = str(exc)
					LOGGER.warning(
						"Provider fundamentals indisponible, bascule globale vers %s | requested_provider=%s symbol=%s progress=%s/%s reason=%s",
						fallback_provider,
						provider,
						symbol,
						index,
						total,
						exc,
					)
					record = _fetch_fundamentals(symbol, provider=effective_provider, session=session)
				normalized_sector = _normalize_sector(record.get("sector"))
				market_cap_raw = record.get("market_cap")
				market_cap = float(str(market_cap_raw)) if market_cap_raw not in (None, "") else None
				existing_row = existing_rows.get(symbol, {})
				payload = _build_update_payload(
					symbol=symbol,
					fetched_sector=normalized_sector,
					fetched_market_cap=market_cap,
					existing_row=existing_row,
					stale_symbols=stale_symbol_set,
					overwrite_existing=overwrite_existing,
				)

				if normalized_sector is None and market_cap is None:
					summary["skipped"] += 1
					LOGGER.warning(
						"Fondamentaux introuvables | provider=%s symbol=%s progress=%s/%s skipped=%s",
						effective_provider,
						symbol,
						index,
						total,
						summary["skipped"],
					)
				elif set(payload) == {"symbol"}:
					summary["skipped"] += 1
					LOGGER.info(
						"Fondamentaux deja presents, pas d'ecrasement | provider=%s symbol=%s progress=%s/%s skipped=%s",
						effective_provider,
						symbol,
						index,
						total,
						summary["skipped"],
					)
				else:
					rowcount = update_stock_metadata_fundamentals(
						symbol,
						sector=payload.get("sector"),
						market_cap=payload.get("market_cap"),
					)
					if rowcount:
						summary["updated"] += 1
						LOGGER.info(
							"Fondamentaux mis a jour | provider=%s symbol=%s sector=%s market_cap=%s progress=%s/%s updated=%s",
							effective_provider,
							symbol,
							payload.get("sector"),
							payload.get("market_cap"),
							index,
							total,
							summary["updated"],
						)
					else:
						summary["skipped"] += 1
						LOGGER.warning(
							"Aucune ligne mise a jour | provider=%s symbol=%s progress=%s/%s skipped=%s",
							effective_provider,
							symbol,
							index,
							total,
							summary["skipped"],
						)
			except Exception:
				summary["failed"] += 1
				LOGGER.exception(
					"Erreur mise a jour fondamentaux | provider=%s symbol=%s progress=%s/%s failed=%s",
					effective_provider,
					symbol,
					index,
					total,
					summary["failed"],
				)

			if index % log_every == 0 or index == total:
				LOGGER.info(
					"Progression fondamentaux | current=%s/%s updated=%s skipped=%s failed=%s",
					index,
					total,
					summary["updated"],
					summary["skipped"],
					summary["failed"],
				)
				LOGGER.info(
					"Progression sector | current=%s/%s updated=%s skipped=%s failed=%s",
					index,
					total,
					summary["updated"],
					summary["skipped"],
					summary["failed"],
				)

			if index < total:
				time.sleep(sleep_seconds)
	finally:
		session.close()

	LOGGER.info(
		"Fin mise a jour fondamentaux stock_metadata | total=%s updated=%s skipped=%s failed=%s",
		summary["total"],
		summary["updated"],
		summary["skipped"],
		summary["failed"],
	)
	LOGGER.info("Fin mise a jour sector stock_metadata")
	return summary


def _build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Met à jour stock_metadata.sector et market_cap depuis Yahoo Finance, EODHD ou Finnhub")
	parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles à traiter")
	parser.add_argument(
		"--provider",
		type=str,
		choices=("yahoo_finance", "eodhd", "finnhub"),
		default="yahoo_finance",
		help="Source fundamentals utilisée pour sector et market_cap.",
	)
	parser.add_argument(
		"--sleep-seconds",
		type=float,
		default=MIN_REQUEST_INTERVAL_SECONDS,
		help="Pause entre deux appels provider",
	)
	parser.add_argument(
		"--log-every",
		type=int,
		default=DEFAULT_LOG_EVERY,
		help="Fréquence d'affichage du compteur de progression",
	)
	parser.add_argument(
		"--refresh-stale-days",
		type=int,
		default=DEFAULT_REFRESH_STALE_DAYS,
		help=(
			"Rafraîchir aussi les symboles dont market_cap_refreshed_at "
			"est antérieur à N jours (Phase 3.1.e). 0 pour désactiver."
		),
	)
	parser.add_argument(
		"--overwrite-existing",
		action="store_true",
		default=False,
		help="Écrase aussi les sector / market_cap déjà présents pour les symboles ciblés.",
	)
	return parser


def main() -> None:
	configure_root_logging(
		level=logging.INFO,
		log_path="./log/update_sector.log",
		fmt="%(asctime)s %(levelname)s %(message)s",
	)
	args = _build_arg_parser().parse_args()
	started_at = _utc_now_naive()
	refresh_stale_days = args.refresh_stale_days if args.refresh_stale_days and args.refresh_stale_days > 0 else None
	summary = update_missing_sectors(
		limit=args.limit,
		sleep_seconds=args.sleep_seconds,
		log_every=args.log_every,
		refresh_stale_days=refresh_stale_days,
		provider=args.provider,
		overwrite_existing=bool(args.overwrite_existing),
	)
	finished_at = _utc_now_naive()
	cli_summary: dict[str, Any] = {
		"run_id": _build_run_id("update-fundamentals"),
		"started_at": started_at.isoformat(timespec="seconds"),
		"finished_at": finished_at.isoformat(timespec="seconds"),
		"duration_seconds": round((finished_at - started_at).total_seconds(), 2),
		"requested_limit": args.limit,
		"provider": args.provider,
		"overwrite_existing": bool(args.overwrite_existing),
		"sleep_seconds": args.sleep_seconds,
		"log_every": args.log_every,
		**summary,
	}
	# Phase 3.1.e : compteur biais IEX `stale_market_cap_pct` propagé via
	# le helper transverse pour cohérence inter-modules.
	if refresh_stale_days is not None:
		try:
			stale_count, eligible_total = count_eligible_symbols_with_stale_market_cap(
				max_age_days=int(refresh_stale_days),
			)
			pct = round(stale_count / eligible_total, 4) if eligible_total > 0 else 0.0
			merge_iex_bias_counters(cli_summary, {"stale_market_cap_pct": pct})
			cli_summary["stale_market_cap_eligible_total"] = eligible_total
			cli_summary["stale_market_cap_stale_count"] = stale_count
		except Exception:
			LOGGER.exception("Echec calcul stale_market_cap_pct (non bloquant).")
	_emit_run_summary(attach_schema_version(cli_summary))


if __name__ == "__main__":
	main()

