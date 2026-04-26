import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import requests


from common.utils import configure_root_logging
from core.run_summary import attach_schema_version, merge_iex_bias_counters
from database.assets import (
	count_eligible_symbols_with_stale_market_cap,
	get_symbols_missing_fundamentals,
	get_symbols_with_stale_market_cap,
	update_stock_metadata_fundamentals,
)
from service.finnhub.clientFinnhub import MIN_REQUEST_INTERVAL_SECONDS, fetch_company_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_LOG_EVERY = 50
DEFAULT_REFRESH_STALE_DAYS = 30
NOT_AVAILABLE = "N/A"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


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


def update_missing_sectors(
	limit: int | None = None,
	sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
	log_every: int = DEFAULT_LOG_EVERY,
	*,
	refresh_stale_days: int | None = None,
) -> dict[str, Any]:
	if sleep_seconds < 0:
		raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")
	if log_every < 1:
		raise ValueError("log_every doit être supérieur ou égal à 1.")
	if refresh_stale_days is not None and refresh_stale_days < 0:
		raise ValueError("refresh_stale_days doit être >= 0.")

	missing_symbols = get_symbols_missing_sector(limit=limit)
	# Phase 3.1.e : ajouter aussi les symboles dont market_cap_refreshed_at est périmé.
	stale_symbols: list[str] = []
	if refresh_stale_days is not None:
		stale_symbols = get_symbols_with_stale_market_cap(
			max_age_days=refresh_stale_days,
			limit=limit,
		)
	# Fusion en préservant l'ordre, puis recoupe au limit s'il est défini.
	seen: set[str] = set()
	combined: list[str] = []
	for source in (missing_symbols, stale_symbols):
		for sym in source:
			if sym not in seen:
				seen.add(sym)
				combined.append(sym)
	if limit is not None:
		combined = combined[:limit]
	symbols = combined
	total = len(symbols)
	summary: dict[str, Any] = {
		"total": total,
		"updated": 0,
		"skipped": 0,
		"failed": 0,
		"missing_fundamentals_targets": len(missing_symbols),
		"stale_market_cap_targets": len(stale_symbols),
		"refresh_stale_days": refresh_stale_days,
	}

	LOGGER.info(
		"Debut mise a jour fondamentaux stock_metadata | symboles_a_traiter=%s limit=%s",
		total,
		limit,
	)
	LOGGER.info("Debut mise a jour sector stock_metadata")
	if not symbols:
		return summary

	session = requests.Session()
	try:
		for index, symbol in enumerate(symbols, start=1):
			try:
				profile = fetch_company_profile(symbol, session=session)
				sector = str(profile.get("finnhubIndustry") or "").strip()
				market_cap_raw = profile.get("marketCapitalization")
				market_cap = float(market_cap_raw) * 1_000_000.0 if market_cap_raw not in (None, "") else None

				if (not sector or sector == NOT_AVAILABLE) and market_cap is None:
					summary["skipped"] += 1
					LOGGER.warning(
						"Fondamentaux introuvables | symbol=%s progress=%s/%s skipped=%s",
						symbol,
						index,
						total,
						summary["skipped"],
					)
				else:
					normalized_sector = None if not sector or sector == NOT_AVAILABLE else sector
					if market_cap is None and normalized_sector is not None:
						rowcount = update_stock_metadata_sector(symbol, normalized_sector)
					else:
						rowcount = update_stock_metadata_fundamentals(
							symbol,
							sector=normalized_sector,
							market_cap=market_cap,
						)
					if rowcount:
						summary["updated"] += 1
						LOGGER.info(
							"Fondamentaux mis a jour | symbol=%s sector=%s market_cap=%s progress=%s/%s updated=%s",
							symbol,
							normalized_sector,
							market_cap,
							index,
							total,
							summary["updated"],
						)
					else:
						summary["skipped"] += 1
						LOGGER.warning(
							"Aucune ligne mise a jour | symbol=%s progress=%s/%s skipped=%s",
							symbol,
							index,
							total,
							summary["skipped"],
						)
			except Exception:
				summary["failed"] += 1
				LOGGER.exception(
					"Erreur mise a jour fondamentaux | symbol=%s progress=%s/%s failed=%s",
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
	parser = argparse.ArgumentParser(description="Met à jour stock_metadata.sector et market_cap depuis Finnhub")
	parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles à traiter")
	parser.add_argument(
		"--sleep-seconds",
		type=float,
		default=MIN_REQUEST_INTERVAL_SECONDS,
		help="Pause entre deux appels Finnhub",
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
	)
	finished_at = _utc_now_naive()
	cli_summary: dict[str, Any] = {
		"run_id": _build_run_id("update-fundamentals"),
		"started_at": started_at.isoformat(timespec="seconds"),
		"finished_at": finished_at.isoformat(timespec="seconds"),
		"duration_seconds": round((finished_at - started_at).total_seconds(), 2),
		"requested_limit": args.limit,
		"sleep_seconds": args.sleep_seconds,
		"log_every": args.log_every,
		**summary,
	}
	# Phase 3.1.e : compteur biais IEX `stale_market_cap_pct` propagé via
	# le helper transverse pour cohérence inter-modules.
	if refresh_stale_days is not None:
		try:
			stale_count, eligible_total = count_eligible_symbols_with_stale_market_cap(
				max_age_days=refresh_stale_days,
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

