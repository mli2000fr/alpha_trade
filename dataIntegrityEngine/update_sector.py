import argparse
import logging
import os
import sys
import time
from typing import Any

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.utils import configure_root_logging
from database.assets import get_symbols_missing_fundamentals, update_stock_metadata_fundamentals
from service.finnhub.clientFinnhub import MIN_REQUEST_INTERVAL_SECONDS, fetch_company_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_LOG_EVERY = 50
NOT_AVAILABLE = "N/A"

# Compatibilité rétroactive pour les tests / appelants legacy.
get_symbols_missing_sector = get_symbols_missing_fundamentals


def update_stock_metadata_sector(symbol: str, sector: str) -> int:
	return update_stock_metadata_fundamentals(symbol, sector=sector)


def update_missing_sectors(
	limit: int | None = None,
	sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
	log_every: int = DEFAULT_LOG_EVERY,
) -> dict[str, Any]:
	if sleep_seconds < 0:
		raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")
	if log_every < 1:
		raise ValueError("log_every doit être supérieur ou égal à 1.")

	symbols = get_symbols_missing_sector(limit=limit)
	total = len(symbols)
	summary = {
		"total": total,
		"updated": 0,
		"skipped": 0,
		"failed": 0,
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
	return parser


def main() -> None:
	configure_root_logging(
		level=logging.INFO,
		log_path="./log/update_sector.log",
		fmt="%(asctime)s %(levelname)s %(message)s",
	)
	args = _build_arg_parser().parse_args()
	update_missing_sectors(limit=args.limit, sleep_seconds=args.sleep_seconds, log_every=args.log_every)


if __name__ == "__main__":
	main()

