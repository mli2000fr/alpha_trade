"""Contrôle indépendant, non canonique, des prix France 2016 par ISIN.

L'archive Bnains est une source tierce. Les ISIN EODHD sont des métadonnées
actuelles : une absence de jointure historique ne prouve pas une erreur de prix.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json


def read_archive(path: Path, target_isins: set[str]):
    """Parcourt les 12 ZIP mensuels puis les TXT quotidiens sans extraction disque."""
    with zipfile.ZipFile(path) as year:
        bad = year.testzip()
        if bad:
            raise ValueError(f"Archive annuelle corrompue : {bad}")
        for month_name in sorted(year.namelist()):
            if not month_name.lower().endswith(".zip"):
                continue
            with zipfile.ZipFile(io.BytesIO(year.read(month_name))) as month:
                bad = month.testzip()
                if bad:
                    raise ValueError(f"Archive mensuelle corrompue : {month_name}/{bad}")
                for day_name in sorted(month.namelist()):
                    if not day_name.lower().endswith(".txt"):
                        continue
                    day = date.fromisoformat(f"{day_name[-12:-8]}-{day_name[-8:-6]}-{day_name[-6:-4]}")
                    for line in month.read(day_name).decode("latin-1").splitlines():
                        cells = line.strip().split("\t")
                        if len(cells) < 7 or cells[0] not in target_isins:
                            continue
                        try:
                            prices = tuple(float(value.replace(",", ".")) for value in cells[2:6])
                            volume = float(cells[6].replace(",", "."))
                        except ValueError:
                            continue
                        yield day.isoformat(), cells[0], cells[1], prices, volume


def compare(*, root: Path, archive_path: Path) -> dict:
    audit = json.loads((root / "sprint5_subset_audit.json").read_text(encoding="utf-8"))
    candidates = [row for row in audit["symbols"] if row["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"]
    by_symbol = {row["symbol"]: row for row in candidates}
    by_isin = {row["isin_reported"]: row for row in candidates}
    metadata = {}
    for path in (root / "symbols").glob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("symbol") in by_symbol:
            metadata[row["symbol"]] = row
    bars_by_isin = {}
    for isin, candidate in by_isin.items():
        payload = metadata[candidate["symbol"]]["payloads"]["eod"]["file"]
        with gzip.open(root / payload, "rt", encoding="utf-8") as stream:
            bars_by_isin[isin] = {bar["date"]: bar for bar in json.load(stream) if bar["date"].startswith("2016-")}

    counts = Counter()
    by_status = defaultdict(Counter)
    observed_isins = set()
    examples = []
    duplicate_keys = set()
    seen = set()
    close_ratios = defaultdict(list)
    for day, isin, name, prices, volume in read_archive(archive_path, set(by_isin)):
        candidate = by_isin[isin]
        status = candidate["provider_status_current"]
        observed_isins.add(isin)
        key = day, isin
        if key in seen:
            duplicate_keys.add(key)
            continue
        seen.add(key)
        counts["reference_rows"] += 1
        by_status[status]["reference_rows"] += 1
        bar = bars_by_isin[isin].get(day)
        if not bar:
            counts["missing_eodhd_date"] += 1
            by_status[status]["missing_eodhd_date"] += 1
            continue
        counts["matched_rows"] += 1
        by_status[status]["matched_rows"] += 1
        fields = ("open", "high", "low", "close")
        relative = {field: abs(float(bar[field]) - value) / max(abs(value), 0.01)
                    for field, value in zip(fields, prices)}
        worst = max(relative.values())
        if prices[3] > 0 and float(bar["close"]) > 0:
            close_ratios[candidate["symbol"]].append(float(bar["close"]) / prices[3])
        if worst <= 0.001:
            counts["ohlc_within_0_1pct"] += 1
            by_status[status]["ohlc_within_0_1pct"] += 1
        elif worst <= 0.01:
            counts["ohlc_within_1pct_only"] += 1
            by_status[status]["ohlc_within_1pct_only"] += 1
        else:
            counts["ohlc_over_1pct"] += 1
            by_status[status]["ohlc_over_1pct"] += 1
            if len(examples) < 30:
                examples.append({"date": day, "symbol": candidate["symbol"], "isin": isin,
                                 "reference_name": name, "status": status,
                                 "reference_ohlc": dict(zip(fields, prices)),
                                 "eodhd_ohlc": {field: bar[field] for field in fields},
                                 "worst_relative_gap": round(worst, 6)})
        if abs(float(bar["volume"]) - volume) < 0.5:
            counts["volume_equal"] += 1
        else:
            counts["volume_different"] += 1

    symbol_ratios = []
    for symbol, values in close_ratios.items():
        if len(values) < 10:
            continue
        median = statistics.median(values)
        relative_mad = statistics.median(abs(value / median - 1) for value in values)
        symbol_ratios.append({"symbol": symbol, "status": by_symbol[symbol]["provider_status_current"],
                              "days": len(values), "median_eodhd_over_reference_close": round(median, 6),
                              "relative_mad": round(relative_mad, 6),
                              "suspected_stable_restatement": abs(median - 1) > 0.01 and relative_mad < 0.001})
    restated = [row for row in symbol_ratios if row["suspected_stable_restatement"]]
    return {
        "source": "bnains.org/archives/cours/france/2016.ZIP (tiers, pas Euronext officiel)",
        "scope": "490 candidats Sprint 5, correspondance par ISIN actuel EODHD, prix OHLC bruts 2016",
        "canonical_go": False,
        "candidate_symbols": len(candidates),
        "candidates_with_reference_isin": len(observed_isins),
        "reference_isins_by_current_provider_status": dict(Counter(by_isin[isin]["provider_status_current"] for isin in observed_isins)),
        "candidates_without_reference_isin": len(by_isin) - len(observed_isins),
        "duplicate_reference_keys": len(duplicate_keys),
        "counts": dict(counts),
        "symbols_with_stable_price_restatement_over_1pct": len(restated),
        "stable_restatement_examples": sorted(restated, key=lambda row: abs(row["median_eodhd_over_reference_close"] - 1), reverse=True)[:30],
        "symbols_with_over_1pct_median_ratio": sum(abs(row["median_eodhd_over_reference_close"] - 1) > 0.01 for row in symbol_ratios),
        "by_current_provider_status": {key: dict(value) for key, value in by_status.items()},
        "price_outlier_examples": examples,
        "limitations": ["Archive tierce non PIT et non officielle", "ISIN EODHD actuel potentiellement différent de celui de 2016",
                        "Une ligne absente ou discordante exige une vérification de l'identité et des actions sur titres",
                        "Les volumes EODHD peuvent être ajustés lors d'un split"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--archive", type=Path, default=Path("artifacts/fr/price_reference_bnains/2016.ZIP"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/fr/price_reference_bnains/report_2016.json"))
    args = parser.parse_args()
    report = compare(root=args.root, archive_path=args.archive)
    _atomic_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("candidate_symbols", "candidates_with_reference_isin", "counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
