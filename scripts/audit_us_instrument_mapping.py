"""Audit à blanc du futur mapping stock_metadata vers instruments US.

Le script ne réalise aucune écriture en base. Il refuse d'inventer un MIC
lorsque la valeur exchange historique est absente ou ambiguë.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine

DEFAULT_OUTPUT = Path("artifacts/audits/market_integration/sprint_02/us_mapping_dry_run.json")

_EXCHANGE_TO_MIC = {
    "NASDAQ": "XNAS",
    "NASDAQGS": "XNAS",
    "NASDAQGM": "XNAS",
    "NASDAQCM": "XNAS",
    "NYSE": "XNYS",
    "AMEX": "XASE",
    "NYSEAMERICAN": "XASE",
    "NYSE AMERICAN": "XASE",
    "ARCA": "ARCX",
    "NYSEARCA": "ARCX",
    "NYSE ARCA": "ARCX",
    "BATS": "BATS",
}
_OTC_MARKERS = ("OTC", "PINK", "GREY")


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    symbol: str
    exchange_raw: str | None
    exchange_mic: str | None
    mapping_status: str
    flags: tuple[str, ...]


def _normalize_exchange(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().replace("_", " ").split())


def classify_stock_metadata(row: dict[str, Any]) -> MappingCandidate:
    symbol = str(row.get("symbol") or "").strip().upper()
    exchange_raw = str(row.get("exchange") or "").strip() or None
    exchange = _normalize_exchange(exchange_raw)
    company_name = str(row.get("company_name") or "").upper()
    asset_class = str(row.get("asset_class") or "").upper()
    flags: list[str] = []

    if any(separator in symbol for separator in (".", "/", "-")):
        flags.append("class_or_punctuated_symbol")
    if any(marker in company_name for marker in (" ADR", "ADS", "DEPOSITARY")):
        flags.append("possible_adr")
    if "OTC" in asset_class or any(marker in exchange for marker in _OTC_MARKERS):
        flags.append("otc")
    if not exchange:
        flags.append("missing_exchange")

    mic = None if "otc" in flags else _EXCHANGE_TO_MIC.get(exchange.replace(" ", ""))
    if mic is None and "missing_exchange" not in flags and "otc" not in flags:
        flags.append("unknown_exchange")

    return MappingCandidate(
        symbol=symbol,
        exchange_raw=exchange_raw,
        exchange_mic=mic,
        mapping_status="mapped" if mic else "mapping_pending",
        flags=tuple(flags),
    )


def load_stock_metadata(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT symbol, company_name, exchange, asset_class
                    FROM stock_metadata
                    ORDER BY symbol
                    """
                )
            ).mappings()
        ]


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [classify_stock_metadata(row) for row in rows]
    mapped = [candidate for candidate in candidates if candidate.exchange_mic]
    pending = [candidate for candidate in candidates if not candidate.exchange_mic]
    flag_counts = Counter(flag for candidate in candidates for flag in candidate.flags)
    exchange_counts = Counter(candidate.exchange_raw or "<missing>" for candidate in candidates)
    mic_counts = Counter(candidate.exchange_mic or "mapping_pending" for candidate in candidates)
    total = len(candidates)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "dry_run_no_database_write",
        "source_table": "stock_metadata",
        "market_code": "US_EQ",
        "total_symbols": total,
        "mapped_symbols": len(mapped),
        "mapping_pending_symbols": len(pending),
        "mapping_rate": round(len(mapped) / total, 6) if total else 0.0,
        "flag_counts": dict(sorted(flag_counts.items())),
        "exchange_counts": dict(sorted(exchange_counts.items())),
        "mic_counts": dict(sorted(mic_counts.items())),
        "pending_samples": [asdict(candidate) for candidate in pending[:200]],
        "flagged_samples": [asdict(candidate) for candidate in candidates if candidate.flags][:200],
        "policy": {
            "unknown_exchange": "mapping_pending",
            "missing_exchange": "mapping_pending",
            "otc": "mapping_pending",
            "punctuated_symbol": "reported_without_inventing_a_new_identity",
            "write_performed": False,
        },
    }


def run(
    *,
    engine: Engine | None = None,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    report = build_report(load_stock_metadata(engine or get_sqlalchemy_engine()))
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = run(output_path=args.output)
    print(
        "Audit mapping US terminé : "
        f"{report['mapped_symbols']}/{report['total_symbols']} mappables "
        f"({report['mapping_rate']:.2%}), "
        f"{report['mapping_pending_symbols']} en mapping_pending. "
        f"Rapport : {args.output}"
    )


if __name__ == "__main__":
    main()
