"""Prépare les preuves de prix à rechercher, sans modifier les admissions FR."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from service.fr.universe_liquidity_6b import _load_symbol_bars
from service.fr.yahoo_price_reference_pilot import normalize_chart


def requested_pairs(frame: pd.DataFrame) -> list[tuple[str, str]]:
    pairs = set()
    for row in frame.itertuples():
        for window in (row.feature_window_blockers, row.label_path_blockers):
            for blocker in window:
                if "INDEPENDENT_PRICE_CORROBORATION_MISSING" in blocker["reasons"]:
                    pairs.add((row.provider_symbol, blocker["date"]))
    return sorted(pairs)


def run(diagnostics: Path, output: Path) -> dict:
    frame = pd.read_parquet(diagnostics)
    pairs = requested_pairs(frame)
    with gzip.open("artifacts/fr/sprint6c_reference/identities.jsonl.gz", "rt", encoding="utf-8") as f:
        identities = {r["provider_symbol"]: r for r in map(json.loads, f)}
    rows = []
    for symbol in sorted({s for s, _ in pairs}):
        identity = identities[symbol]
        eodhd = _load_symbol_bars(Path("artifacts/fr/eodhd/backfill_2016"), symbol)
        key = hashlib.sha256(symbol.encode()).hexdigest()[:16]
        cache = Path("artifacts/fr/yahoo_daily_reference/cache") / f"{key}_2018-01-01_2026-10-01.json"
        yahoo, _ = normalize_chart(json.loads(cache.read_text(encoding="utf-8"))["payload"])
        for s, day in pairs:
            if s != symbol:
                continue
            e, y = eodhd.get(day), yahoo.get(day)
            rows.append({"symbol": symbol, "isin": identity["isin"], "date": day,
                         "mics": [ref["mic"] for ref in identity["market_reference"] if any(
                             i["from"] <= day and (i["to"] is None or i["to"] >= day)
                             for i in ref["observed_asof_intervals"])],
                         "eodhd": e, "yahoo": y,
                         "disputed_fields": [field for field in ("open", "high", "low", "close")
                                              if e and y and abs(e[field] - y[field]) > .0001],
                         "yahoo_cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
                         "request": "Independent OHLC convention-compatible evidence; volume separately diagnostic"})
    report = {"diagnostics_sha256": hashlib.sha256(diagnostics.read_bytes()).hexdigest(),
              "requested_pairs": len(rows), "by_date": dict(Counter(r["date"] for r in rows)),
              "requests": rows, "repaired_rows": 0, "models_trained": 0,
              "canonical_writes": False, "target_performance_inspected": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "requests"}))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diagnostics", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.diagnostics, a.output)
