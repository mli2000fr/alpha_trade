"""Préfiltre un univers ML sans lancer ni modifier aucun batch.

Le script est strictement en lecture seule côté base. Il :
1. résout l'univers demandé avec le registre ModelFactory ;
2. applique le filtre de liquidité canonique, par blocs ;
3. compte les barres dans la fenêtre d'entraînement ;
4. exporte la liste éligible, un rapport CSV et un résumé JSON.

Exemple :
    python scripts/filter_ml_training_universe.py \
      --symbol-source stock-bars-daily \
      --training-start-date 2021-01-01 \
      --training-end-date 2024-06-30 \
      --min-history-bars 800
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from modelFactory.db_registry import load_symbols_for_source
from modelFactory.liquidity_filter import filter_symbols_by_liquidity


LOGGER = logging.getLogger("filter_ml_training_universe")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Date ISO invalide : {value}") from exc


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


_HISTORY_SQL = text(
    """
    SELECT
        UPPER(TRIM(b.symbol)) AS symbol,
        COUNT(*) AS bar_count,
        COUNT(DISTINCT b.date) AS distinct_bar_dates,
        MIN(b.date) AS first_bar_date,
        MAX(b.date) AS last_bar_date,
        MAX(sm.market_cap) AS market_cap
    FROM stock_bars_daily b
    LEFT JOIN stock_metadata sm ON sm.symbol = b.symbol
    WHERE b.symbol IN :symbols
      AND b.date BETWEEN :start_date AND :end_date
    GROUP BY UPPER(TRIM(b.symbol))
    """
).bindparams(bindparam("symbols", expanding=True))


def load_history_stats(
    engine: Engine,
    symbols: list[str],
    *,
    start_date: date,
    end_date: date,
    chunk_size: int,
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    blocks = list(_chunks(symbols, chunk_size))
    for index, block in enumerate(blocks, start=1):
        with engine.connect() as conn:
            rows = conn.execute(
                _HISTORY_SQL,
                {
                    "symbols": block,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ).mappings().all()
        for row in rows:
            symbol = str(row["symbol"]).strip().upper()
            stats[symbol] = {
                "bar_count": int(row["bar_count"] or 0),
                "distinct_bar_dates": int(row["distinct_bar_dates"] or 0),
                "first_bar_date": row["first_bar_date"],
                "last_bar_date": row["last_bar_date"],
                "market_cap": float(row["market_cap"]) if row["market_cap"] is not None else None,
            }
        LOGGER.info("historique bloc %d/%d traité (%d symboles)", index, len(blocks), len(block))
    return stats


def load_liquidity_exclusions(
    engine: Engine,
    symbols: list[str],
    *,
    end_date: date,
    chunk_size: int,
    min_avg_volume_20d: int,
    min_market_cap: float,
    max_market_cap: float,
    min_daily_dollar_volume: float,
    min_price: float,
    max_avg_high_low_range_pct: float,
    max_spread_bps: float,
    spread_fallback_mode: str,
    spread_max_quote_age_days: int,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    excluded: dict[str, str] = {}
    block_diagnostics: list[dict[str, Any]] = []
    blocks = list(_chunks(symbols, chunk_size))
    for index, block in enumerate(blocks, start=1):
        block_excluded, diagnostics = filter_symbols_by_liquidity(
            engine,
            block,
            end_date=end_date,
            min_avg_volume_20d=min_avg_volume_20d,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            min_daily_dollar_volume=min_daily_dollar_volume,
            min_price=min_price,
            max_avg_high_low_range_pct=max_avg_high_low_range_pct,
            max_spread_bps=max_spread_bps,
            spread_fallback_mode=spread_fallback_mode,  # type: ignore[arg-type]
            spread_max_quote_age_days=spread_max_quote_age_days,
        )
        details = diagnostics.get("details") or {}
        for symbol in block_excluded:
            normalized = str(symbol).strip().upper()
            excluded[normalized] = str(details.get(symbol) or details.get(normalized) or "liquidite")
        block_diagnostics.append(
            {
                "block": index,
                "requested": len(block),
                "excluded": len(block_excluded),
                "market_cap": diagnostics.get("market_cap_diagnostics"),
                "spread": diagnostics.get("spread_diagnostics"),
                "error": diagnostics.get("error"),
            }
        )
        LOGGER.info(
            "liquidité bloc %d/%d traité : exclus=%d/%d",
            index,
            len(blocks),
            len(block_excluded),
            len(block),
        )
    return excluded, block_diagnostics


def _serialize_date(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Préfiltrage read-only de l'univers ML Per-Symbol.")
    parser.add_argument(
        "--symbol-source",
        default="stock-bars-daily",
        choices=("stock-bars-daily", "ticket-recherche"),
    )
    parser.add_argument("--training-start-date", type=_iso_date, required=True)
    parser.add_argument("--training-end-date", type=_iso_date, required=True)
    parser.add_argument("--min-history-bars", type=int, default=800)
    parser.add_argument("--min-avg-volume-20d", type=int, default=50_000)
    parser.add_argument("--min-market-cap", type=float, default=500_000_000.0)
    parser.add_argument(
        "--require-market-cap",
        action="store_true",
        help="Exclut aussi les symboles sans market cap connue (strict, peut réduire fortement l'univers).",
    )
    parser.add_argument("--max-market-cap", type=float, default=20_000_000_000.0)
    parser.add_argument("--min-daily-dollar-volume", type=float, default=1_000_000.0)
    parser.add_argument("--min-price", type=float, default=10.0)
    parser.add_argument("--max-avg-high-low-range-pct", type=float, default=5.0)
    parser.add_argument("--max-spread-bps", type=float, default=40.0)
    parser.add_argument(
        "--spread-fallback-mode",
        choices=("pass", "reject", "warn_only"),
        default="warn_only",
    )
    parser.add_argument("--spread-max-quote-age-days", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/universe_filter"))
    parser.add_argument("--name", default="screening_h20")
    parser.add_argument(
        "--symbols-output",
        type=Path,
        default=None,
        help="Copie optionnelle de la liste au format SYM1,SYM2 sans espaces.",
    )
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING"), default="INFO")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    if args.training_start_date > args.training_end_date:
        raise SystemExit("training-start-date doit être <= training-end-date")
    if args.min_history_bars < 1 or args.chunk_size < 1:
        raise SystemExit("min-history-bars et chunk-size doivent être >= 1")

    engine = get_sqlalchemy_engine()
    symbols = sorted(
        {
            str(symbol).strip().upper()
            for symbol in load_symbols_for_source(engine, args.symbol_source)
            if str(symbol).strip()
        }
    )
    LOGGER.info("univers source=%s : %d symboles", args.symbol_source, len(symbols))

    history = load_history_stats(
        engine,
        symbols,
        start_date=args.training_start_date,
        end_date=args.training_end_date,
        chunk_size=args.chunk_size,
    )
    liquidity_excluded, liquidity_blocks = load_liquidity_exclusions(
        engine,
        symbols,
        end_date=args.training_end_date,
        chunk_size=args.chunk_size,
        min_avg_volume_20d=args.min_avg_volume_20d,
        min_market_cap=args.min_market_cap,
        max_market_cap=args.max_market_cap,
        min_daily_dollar_volume=args.min_daily_dollar_volume,
        min_price=args.min_price,
        max_avg_high_low_range_pct=args.max_avg_high_low_range_pct,
        max_spread_bps=args.max_spread_bps,
        spread_fallback_mode=args.spread_fallback_mode,
        spread_max_quote_age_days=args.spread_max_quote_age_days,
    )

    rows: list[dict[str, Any]] = []
    eligible: list[str] = []
    reasons = Counter()
    for symbol in symbols:
        stat = history.get(symbol) or {}
        bar_count = int(stat.get("bar_count") or 0)
        history_reason = "" if bar_count >= args.min_history_bars else "historique_brut_insuffisant"
        liquidity_reason = liquidity_excluded.get(symbol, "")
        market_cap = stat.get("market_cap")
        market_cap_reason = "market_cap_absente" if args.require_market_cap and market_cap is None else ""
        reason = history_reason or liquidity_reason or market_cap_reason
        is_eligible = not reason
        if is_eligible:
            eligible.append(symbol)
        else:
            reasons[reason] += 1
        rows.append(
            {
                "symbol": symbol,
                "eligible": int(is_eligible),
                "exclusion_reason": reason,
                "history_reason": history_reason,
                "liquidity_reason": liquidity_reason,
                "market_cap_reason": market_cap_reason,
                "market_cap": market_cap,
                "bar_count": bar_count,
                "distinct_bar_dates": int(stat.get("distinct_bar_dates") or 0),
                "first_bar_date": _serialize_date(stat.get("first_bar_date")),
                "last_bar_date": _serialize_date(stat.get("last_bar_date")),
            }
        )

    output_dir = args.output_dir / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "universe_filter_report.csv"
    symbols_path = output_dir / "eligible_symbols.txt"
    summary_path = output_dir / "summary.json"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["symbol"])
        writer.writeheader()
        writer.writerows(rows)
    symbols_path.write_text("\n".join(eligible) + ("\n" if eligible else ""), encoding="utf-8")
    if args.symbols_output is not None:
        args.symbols_output.parent.mkdir(parents=True, exist_ok=True)
        args.symbols_output.write_text(",".join(eligible), encoding="utf-8")

    summary = {
        "read_only": True,
        "symbol_source": args.symbol_source,
        "training_start_date": args.training_start_date.isoformat(),
        "training_end_date": args.training_end_date.isoformat(),
        "source_count": len(symbols),
        "eligible_count": len(eligible),
        "excluded_count": len(symbols) - len(eligible),
        "eligible_pct": round(100.0 * len(eligible) / len(symbols), 2) if symbols else 0.0,
        "exclusion_reasons": dict(sorted(reasons.items())),
        "thresholds": {
            "min_history_bars": args.min_history_bars,
            "min_avg_volume_20d": args.min_avg_volume_20d,
            "min_market_cap": args.min_market_cap,
            "require_market_cap": args.require_market_cap,
            "max_market_cap": args.max_market_cap,
            "min_daily_dollar_volume": args.min_daily_dollar_volume,
            "min_price": args.min_price,
            "max_avg_high_low_range_pct": args.max_avg_high_low_range_pct,
            "max_spread_bps": args.max_spread_bps,
            "spread_fallback_mode": args.spread_fallback_mode,
            "spread_max_quote_age_days": args.spread_max_quote_age_days,
        },
        "liquidity_block_diagnostics": liquidity_blocks,
        "outputs": {
            "report_csv": str(csv_path.resolve()),
            "eligible_symbols": str(symbols_path.resolve()),
            "comma_separated_symbols": (
                str(args.symbols_output.resolve()) if args.symbols_output is not None else None
            ),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
