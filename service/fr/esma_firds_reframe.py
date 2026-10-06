"""Recalcule les intervalles d'observation d'un replay FIRDS déjà vérifié.

Ne relit pas les gros ZIP : le rapport conserve chaque événement brut dans
l'ordre de rejeu. Le fichier source reste intact et son SHA-256 est conservé.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json
from service.fr.esma_firds_history import _observed_interval, _trading_episodes, apply_event

DERIVED_KEYS = {"asof_from", "asof_to", "archive_date", "source_file"}


def reframe(report: dict, source_sha256: str) -> dict:
    revised = {key: value for key, value in report.items() if key not in {"symbols", "anomalies", "counts"}}
    revised["derived_from_sha256"] = source_sha256
    revised["asof_contract"] = "observed_archive_day_v2; FIRDS FrDt retained separately"
    anomalies = []
    symbols = []
    version_count = 0
    for symbol in report["symbols"]:
        markets = []
        for market in symbol["market_reference"]:
            rebuilt = {}
            for version in market["versions"]:
                raw_record = {key: value for key, value in version.items() if key not in DERIVED_KEYS}
                apply_event(rebuilt, raw_record, date.fromisoformat(version["archive_date"]),
                            version["source_file"], anomalies)
            versions = rebuilt[(symbol["isin"], market["mic"])]
            if len(versions) != len(market["versions"]):
                raise ValueError("perte d'événement au recalcul")
            version_count += len(versions)
            markets.append({"mic": market["mic"], "versions": versions,
                            "observed_asof_intervals": [window for version in versions
                                                       if (window := _observed_interval(version))],
                            "trading_episodes": _trading_episodes(versions)})
        symbols.append({**symbol, "market_reference": markets})
    if version_count != report["counts"]["version_records"]:
        raise ValueError("nombre de versions modifié au recalcul")
    revised["symbols"] = symbols
    revised["anomalies"] = anomalies
    revised["counts"] = {**report["counts"], "version_records": version_count}
    revised["canonical_go"] = False
    return revised


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("le rapport original doit rester intact")
    raw = args.input.read_bytes()
    result = reframe(json.loads(raw), hashlib.sha256(raw).hexdigest())
    _atomic_json(args.output, result)
    print(json.dumps({"versions": result["counts"]["version_records"],
                      "anomalies": len(result["anomalies"]),
                      "source_sha256": result["derived_from_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
