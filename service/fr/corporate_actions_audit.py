"""Contrôles économiques indicatifs des splits/dividendes EODHD Paris.

Un saut de prix cohérent avec un ratio ne valide ni le MIC ni la date PIT.
Une discordance est une alerte à revoir, jamais un facteur corrigé par force.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json


def split_ratio(raw: str) -> Decimal | None:
    try:
        left, right = str(raw).split("/", 1)
        numerator, denominator = Decimal(left), Decimal(right)
        if (not numerator.is_finite() or not denominator.is_finite()
                or numerator <= 0 or denominator <= 0):
            return None
        return numerator / denominator
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def price_jump_status(ratio: Decimal, before: Decimal, after: Decimal,
                      *, max_deviation: Decimal = Decimal("0.25")) -> tuple[str, float]:
    if ratio <= 0 or before <= 0 or after <= 0:
        return "INVALID_PRICE", float("nan")
    expected = before / ratio
    deviation = after / expected - 1
    return ("PLAUSIBLE" if abs(deviation) <= max_deviation else "PRICE_RATIO_MISMATCH",
            float(deviation))


def _rows(root: Path, meta: dict, kind: str) -> list[dict]:
    item = meta["payloads"][kind]
    with gzip.open(root / item["file"], "rb") as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise ValueError(f"hash invalide {meta['symbol']}/{kind}")
    return json.loads(payload)


def audit(root: Path) -> dict:
    counts = Counter()
    examples = defaultdict(list)
    for path in sorted((root / "symbols").glob("*.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta["payloads"]["splits"]["rows"] == 0 and meta["payloads"]["div"]["rows"] == 0:
            continue
        symbol = meta["symbol"]
        bars = _rows(root, meta, "eod")
        dates = [date.fromisoformat(row["date"]) for row in bars]
        for event in _rows(root, meta, "splits"):
            counts["split_events"] += 1
            ratio = split_ratio(event.get("split"))
            if ratio is None:
                status = "INVALID_RATIO"
                deviation = None
            else:
                day = date.fromisoformat(event["date"])
                at = bisect_left(dates, day)
                if at == 0 or at == len(bars):
                    status = "MISSING_NEIGHBOR_PRICE"
                    deviation = None
                elif (day - dates[at - 1]).days > 10 or (dates[at] - day).days > 10:
                    status = "DISTANT_NEIGHBOR_PRICE"
                    deviation = None
                else:
                    try:
                        before = Decimal(str(bars[at - 1]["close"]))
                        after = Decimal(str(bars[at]["close"]))
                        status, deviation = price_jump_status(ratio, before, after)
                    except (InvalidOperation, TypeError, KeyError):
                        status, deviation = "INVALID_PRICE", None
            counts[f"split_{status}"] += 1
            if status != "PLAUSIBLE" and len(examples[status]) < 20:
                examples[status].append({"symbol": symbol, "date": event.get("date"),
                                         "ratio": event.get("split"), "deviation": deviation})
        for event in _rows(root, meta, "div"):
            counts["dividend_events"] += 1
            try:
                amount = Decimal(str(event.get("unadjustedValue")))
            except (InvalidOperation, TypeError):
                amount = None
            if amount is None or not amount.is_finite() or amount < 0:
                counts["dividend_invalid_unadjusted_amount"] += 1
            if event.get("currency") not in ("EUR", None):
                counts["dividend_non_eur_currency"] += 1
            if not event.get("declarationDate"):
                counts["dividend_unknown_declaration_date"] += 1
    return {"counts": dict(sorted(counts.items())), "examples": dict(examples),
            "rule": "split price jump +/-25% with <=10 calendar-day neighbor; diagnostic only",
            "warning": "Aucun ajustement n'est appliqué automatiquement; vérifier annonces et événements complexes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    args = parser.parse_args()
    report = audit(args.root)
    _atomic_json(args.root / "corporate_actions_audit.json", report)
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
