import argparse
import logging
import os
import sys
import time
from typing import Any

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.utils import configure_root_logging
from database.assets import get_symbols_missing_sector, update_stock_metadata_sector
from service.finnhub.clientFinnhub import MIN_REQUEST_INTERVAL_SECONDS, fetch_company_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_LOG_EVERY = 50
NOT_AVAILABLE = "N/A"


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
		"Debut mise a jour sector stock_metadata | symboles_a_traiter=%s limit=%s",
		total,
		limit,
	)
	if not symbols:
		return summary

	session = requests.Session()
	try:
		for index, symbol in enumerate(symbols, start=1):
			try:
				profile = fetch_company_profile(symbol, session=session)
				sector = str(profile.get("finnhubIndustry") or "").strip()
				if not sector or sector == NOT_AVAILABLE:
					summary["skipped"] += 1
					LOGGER.warning(
						"Sector introuvable | symbol=%s progress=%s/%s skipped=%s",
						symbol,
						index,
						total,
						summary["skipped"],
					)
				else:
					rowcount = update_stock_metadata_sector(symbol, sector)
					if rowcount:
						summary["updated"] += 1
						LOGGER.info(
							"Sector mis a jour | symbol=%s sector=%s progress=%s/%s updated=%s",
							symbol,
							sector,
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
					"Erreur mise a jour sector | symbol=%s progress=%s/%s failed=%s",
					symbol,
					index,
					total,
					summary["failed"],
				)

			if index % log_every == 0 or index == total:
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
		"Fin mise a jour sector stock_metadata | total=%s updated=%s skipped=%s failed=%s",
		summary["total"],
		summary["updated"],
		summary["skipped"],
		summary["failed"],
	)
	return summary


def _build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Met à jour stock_metadata.sector depuis Finnhub")
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

