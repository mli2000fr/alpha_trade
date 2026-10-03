"""Jointure diagnostique des barres EODHD avec les versions FIRDS observées.

Une concordance avec l'ISIN fourni aujourd'hui par EODHD ne valide ni le prix,
ni l'identité historique, ni la possibilité d'exécuter un ordre sur cette barre.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json


def classify(day: str, markets: list[dict], missing_days: set[str],
             first_full: str) -> str:
    if day < first_full:
        return "BEFORE_INITIAL_FULL"
    if day in missing_days:
        return "MISSING_DELTA_PUBLICATION_DAY"
    saw_non_equity = False
    for market in markets:
        versions = market.get("versions")
        if versions is not None:
            applicable = [row for row in versions
                          if row["asof_from"] <= day
                          and (row.get("asof_to") is None or day <= row["asof_to"])]
            if len(applicable) > 1:
                return "AMBIGUOUS_REFERENCE_VERSION"
            if applicable and applicable[0].get("event") not in {"TermntdRcrd", "CancRcrd"}:
                cfi = applicable[0].get("cfi")
                if isinstance(cfi, str) and cfi.upper().startswith("E"):
                    return "CURRENT_ISIN_HAS_OBSERVED_TARGET_MIC"
                saw_non_equity = True
            continue
        for interval in market["observed_asof_intervals"]:
            if interval["from"] <= day and (interval["to"] is None or day <= interval["to"]):
                return "CURRENT_ISIN_HAS_OBSERVED_TARGET_MIC"
    if saw_non_equity:
        return "NON_EQUITY_CFI_FOR_CURRENT_ISIN"
    return "NO_OBSERVED_TARGET_MIC_FOR_CURRENT_ISIN"


def valid_bar(row: dict) -> bool:
    try:
        opened, high, low, closed = (float(row[key]) for key in
                                     ("open", "high", "low", "close"))
        volume = float(row["volume"])
        return (all(0 < value < float("inf") for value in
                    (opened, high, low, closed))
                and low <= min(opened, closed) <= max(opened, closed) <= high
                and volume > 0)
    except (KeyError, TypeError, ValueError):
        return False


def audit(history: dict, root: Path, *, start: str, end: str) -> dict:
    if end > history["end"]:
        raise ValueError("fenêtre hors du rejeu FIRDS disponible")
    missing_days = set(history["missing_delta_days"])
    counts = Counter()
    by_year = defaultdict(Counter)
    details = []
    for symbol in history["symbols"]:
        code = symbol["symbol"]
        key = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        metadata_path = root / "symbols" / f"{key}.json"
        if not metadata_path.is_file():
            raise FileNotFoundError(f"archive symbole absente : {code}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["symbol"] != code or metadata["status"] != "COMPLETED":
            raise ValueError(f"archive symbole incomplète : {code}")
        bars_path = root / metadata["payloads"]["eod"]["file"]
        with gzip.open(bars_path, "rt", encoding="utf-8") as stream:
            bars = json.load(stream)
        per_symbol = Counter()
        examples = []
        seen = set()
        for row in bars:
            day = row.get("date")
            if not isinstance(day, str) or not start <= day <= end:
                continue
            if day in seen:
                raise ValueError(f"barre dupliquée : {code}/{day}")
            seen.add(day)
            verdict = (classify(day, symbol["market_reference"], missing_days,
                                history["start"])
                       if valid_bar(row) else "INVALID_OR_ZERO_VOLUME_BAR")
            counts[verdict] += 1
            by_year[day[:4]][verdict] += 1
            per_symbol[verdict] += 1
            if verdict != "CURRENT_ISIN_HAS_OBSERVED_TARGET_MIC" and len(examples) < 5:
                examples.append({"date": day, "category": verdict})
        details.append({"symbol": code, "current_isin": symbol["isin"],
                        "current_provider_status": symbol["provider_status_current"],
                        "counts": dict(per_symbol), "examples": examples})
    attention = sorted(details, key=lambda row: -(
        row["counts"].get("NO_OBSERVED_TARGET_MIC_FOR_CURRENT_ISIN", 0)
        + row["counts"].get("MISSING_DELTA_PUBLICATION_DAY", 0)))
    return {"start": start, "end": end, "history_end": history["end"],
            "symbols": len(details), "counts": dict(counts),
            "by_year": {year: dict(data) for year, data in sorted(by_year.items())},
            "attention_symbols": attention[:50], "canonical_go": False,
            "limitations": [
                "ISIN EODHD courant, pas identité historique prouvée",
                "Concordance FIRDS ne valide pas le prix ni l'exécution",
                "Delta manquants : les états observés voisins ne prouvent pas la continuité",
                "Le contrôle de prix indépendant 2018+ reste à faire",
            ]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--root", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8"))
    report = audit(history, args.root, start=args.start_date, end=args.end_date)
    _atomic_json(args.output, report)
    print(json.dumps({key: report[key] for key in
                      ("start", "end", "symbols", "counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
