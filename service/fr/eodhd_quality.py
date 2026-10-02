"""Audit hors base de l'archive EODHD Paris, sans GO automatique ML/PIT."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from common.market_calendar import get_market_calendar
from service.fr.eodhd_backfill import _atomic_json


def audit(root: Path) -> dict:
    manifest = json.loads((root / "universe.json").read_text(encoding="utf-8"))
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    start, end = (date.fromisoformat(item) for item in summary["window"])
    sessions = set(get_market_calendar("FR_EQ").session_dates(start, end))
    counts = Counter()
    by_year = defaultdict(lambda: Counter())
    examples: dict[str, list] = defaultdict(list)
    candidates = [{**row, "provider_status": status}
                  for status in ("active", "delisted") for row in manifest[status]
                  if row.get("Type") == "Common Stock" and row.get("Currency") == "EUR" and row.get("Code")]
    candidates.sort(key=lambda row: (row["provider_status"], row["Code"]))
    records = {f"{row['Code']}.PA": row for row in candidates[:summary["selected"]]}

    def issue(name: str, symbol: str, day: str) -> None:
        counts[name] += 1
        if len(examples[name]) < 20:
            examples[name].append({"symbol": symbol, "date": day})

    for symbol, record in sorted(records.items()):
        key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
        meta_path = root / "symbols" / f"{key}.json"
        if not meta_path.exists():
            issue("uncollected_symbols", symbol, "")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") != "COMPLETED":
            issue("uncollected_symbols", symbol, "")
            continue
        if not record.get("Isin"):
            counts["missing_isin_symbols"] += 1
        counts[f"{record['provider_status']}_symbols"] += 1
        year_seen = set()
        dates_seen = set()
        for kind in ("eod", "splits", "div"):
            item = meta["payloads"][kind]
            path = root / item["file"]
            with gzip.open(path, "rb") as stream:
                payload = stream.read()
            if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                issue("sha256_mismatch", symbol, kind)
                continue
            rows = json.loads(payload)
            counts[f"{kind}_rows"] += len(rows)
            if kind != "eod":
                continue
            if not rows:
                issue("empty_eod_symbols", symbol, "")
            for row in rows:
                day_text = str(row.get("date", ""))
                try:
                    day = date.fromisoformat(day_text)
                except ValueError:
                    issue("invalid_date", symbol, day_text)
                    continue
                if day in dates_seen:
                    issue("duplicate_date", symbol, day_text)
                dates_seen.add(day)
                if day not in sessions:
                    issue("non_xpar_session", symbol, day_text)
                if not start <= day <= end:
                    issue("outside_window", symbol, day_text)
                year_seen.add(day.year)
                by_year[str(day.year)]["bar_rows"] += 1
                try:
                    opened, high, low, closed = (Decimal(str(row[field])) for field in
                                                  ("open", "high", "low", "close"))
                    if (not all(value.is_finite() and value > 0 for value in
                                (opened, high, low, closed)) or
                            low > min(opened, closed) or high < max(opened, closed)):
                        issue("bad_ohlc", symbol, day_text)
                    if (opened == high == low == closed == Decimal("999999.9999")
                            and row.get("volume") == 0):
                        issue("placeholder_price", symbol, day_text)
                except (KeyError, InvalidOperation, TypeError):
                    issue("bad_ohlc", symbol, day_text)
                if row.get("adjusted_close") is not None:
                    counts["adjusted_close_rows"] += 1
                if row.get("volume") is not None:
                    counts["split_adjusted_volume_rows"] += 1
        for year in year_seen:
            by_year[str(year)]["symbols_with_bars"] += 1
    return {"window": summary["window"], "selected": summary["selected"],
            "archived": counts["active_symbols"] + counts["delisted_symbols"],
            "counts": dict(sorted(counts.items())),
            "by_year": {year: dict(data) for year, data in sorted(by_year.items())},
            "examples": dict(examples),
            "limitations": ["Statut actif/radié et ISIN observés aujourd'hui, non PIT historique",
                            "Volume EODHD ajusté des splits, pas volume brut",
                            "Adjusted close EODHD ajusté splits et dividendes",
                            "Heure de publication historique non démontrée",
                            "Aucune licence de référence indépendante ni GO ML implicite"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    args = parser.parse_args()
    report = audit(args.root)
    _atomic_json(args.root / "quality_report.json", report)
    print(f"Audit FR : {report['archived']}/{report['selected']} symboles ; "
          f"{report['counts'].get('eod_rows', 0)} barres ; "
          f"rapport={args.root / 'quality_report.json'}")


if __name__ == "__main__":
    main()
