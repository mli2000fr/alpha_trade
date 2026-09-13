"""POC non planifié de l'historique graphique des enchères NYSE.

La route JSON utilisée par l'interface publique NYSE n'est pas une API
documentée. Ce module reste un outil de recherche : il peut auditer un petit
échantillon ou une photographie quotidienne d'univers, écrit uniquement des artefacts locaux et ne peut alimenter ni une
table de production, ni le serving, ni une décision prise avant l'enchère.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from sqlalchemy import bindparam, text

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from service.forward_pit.batch import _configure_alpaca_session

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.nyse.com"
DEFAULT_SYMBOLS = (
    "IBM,JPM,BAC,XOM,CVX,WMT,DIS,KO,PFE,CAT,"
    "BA,GE,GM,F,UPS,NKE,MCD,HD,V,MA"
)
MAX_SYMBOLS = 20
MAX_DATES = 20
MAX_UNIVERSE_SYMBOLS = 2500
MAX_UNIVERSE_DATES = 1

class NyseRateLimitError(RuntimeError):
    """Raised when the public Web interface asks the POC to stop."""




def _request_json(
    session: requests.Session, path: str, params: dict[str, str], attempts: int = 4,
) -> Any:
    last: Exception | None = None
    last_status: int | None = None
    for attempt in range(attempts):
        try:
            response = session.get(
                f"{BASE_URL}{path}", params=params, timeout=45,
                headers={"User-Agent": "AlphaTradeResearch/1.0"},
            )
            last_status = response.status_code
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 2.0 ** attempt
                )
                if attempt + 1 < attempts:
                    time.sleep(min(30.0, max(1.0, wait)))
                continue
            if response.status_code >= 500:
                if attempt + 1 < attempts:
                    time.sleep(min(10.0, 2.0 ** attempt))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(10.0, 2.0 ** attempt))
    detail = f"HTTP {last_status}" if last_status is not None else str(last)
    if last_status == 429:
        raise NyseRateLimitError(
            f"NYSE public interface rate limited the POC: {detail}"
        )
    raise RuntimeError(f"NYSE public interface unavailable: {detail}")
def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_symbols(value: str) -> list[str]:
    symbols = sorted({item.strip().upper() for item in value.split(",") if item.strip()})
    if not symbols:
        raise ValueError("At least one symbol is required")
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"POC limited to {MAX_SYMBOLS} symbols")
    return symbols


def _candidate_dates(start: date, end: date, limit: int) -> list[date]:
    dates: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates[-limit:]


def _resolve_input_symbols(symbols: str | None, symbol_source: str | None) -> list[str]:
    if symbols and symbol_source:
        raise ValueError("Use either --symbols or --symbol-source, not both")
    if symbol_source:
        resolved = sorted(set(load_universe_file_symbols(symbol_source)))
        if not resolved:
            raise ValueError(f"Empty universe: {symbol_source}")
        if len(resolved) > MAX_UNIVERSE_SYMBOLS:
            raise ValueError(
                f"Research universe limited to {MAX_UNIVERSE_SYMBOLS} symbols"
            )
        return resolved
    return _parse_symbols(symbols or DEFAULT_SYMBOLS)


def _parse_symbol_file(path: Path) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for token in path.read_text(encoding="utf-8-sig").split(","):
        symbol = token.strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return symbols


def _rotate_symbols(symbols: list[str], *, key: str) -> tuple[list[str], int]:
    if not symbols:
        return [], 0
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    offset = int(digest[:16], 16) % len(symbols)
    return [*symbols[offset:], *symbols[:offset]], offset

def summarize_auction_rows(
    rows: list[dict[str, Any]], *, observed_at: datetime,
) -> dict[str, Any] | None:
    """Collapse minute averages into one auditable post-auction observation."""
    if not rows:
        return None
    ordered = sorted(rows, key=lambda row: str(row.get("tradeDate") or ""))
    first, last = ordered[0], ordered[-1]
    imbalances = pd.to_numeric(
        pd.Series([row.get("avgImbalanceQty") for row in ordered]), errors="coerce",
    ).dropna()
    paired = pd.to_numeric(
        pd.Series([row.get("avgPairedQty") for row in ordered]), errors="coerce",
    ).dropna()
    clearing = pd.to_numeric(
        pd.Series([row.get("avgBookClearingPrice") for row in ordered]), errors="coerce",
    ).dropna()
    if imbalances.empty:
        return None
    first_imbalance = float(imbalances.iloc[0])
    last_imbalance = float(imbalances.iloc[-1])
    nonzero_signs = imbalances[imbalances.ne(0)].map(lambda value: 1 if value > 0 else -1)
    last_sign = 1 if last_imbalance > 0 else -1 if last_imbalance < 0 else 0
    persistence = (
        float(nonzero_signs.eq(last_sign).mean())
        if last_sign and not nonzero_signs.empty else None
    )
    latest_paired = float(paired.iloc[-1]) if not paired.empty else None
    reference_price = pd.to_numeric(pd.Series([last.get("price")]), errors="coerce").iloc[0]
    latest_clearing = float(clearing.iloc[-1]) if not clearing.empty else None
    clearing_gap = (
        latest_clearing / float(reference_price) - 1.0
        if latest_clearing and pd.notna(reference_price) and float(reference_price) > 0
        else None
    )
    return {
        "symbol": str(last.get("symbol") or "").upper(),
        "mic": last.get("mic"),
        "auction_date": str(last.get("tradeDate") or "")[:10],
        "first_message_time": first.get("tradeDate"),
        "last_message_time": last.get("tradeDate"),
        "minute_observations": len(ordered),
        "first_signed_imbalance": first_imbalance,
        "last_signed_imbalance": last_imbalance,
        "imbalance_side": "BUY" if last_sign > 0 else "SELL" if last_sign < 0 else "NONE",
        "imbalance_acceleration": last_imbalance - first_imbalance,
        "side_persistence": persistence,
        "last_paired_quantity": latest_paired,
        "imbalance_to_paired": (
            last_imbalance / latest_paired if latest_paired and latest_paired > 0 else None
        ),
        "last_book_clearing_price": latest_clearing,
        "reference_or_auction_price": (
            float(reference_price) if pd.notna(reference_price) else None
        ),
        "clearing_price_gap": clearing_gap,
        "observed_at": observed_at.isoformat(),
        "available_at": observed_at.isoformat(),
        "available_before_auction": False,
        "source_contract": "NYSE_WEB_POST_AUCTION_UNDOCUMENTED_ROUTE",
        "payload_hash": _hash_payload(rows),
    }


def _load_realized_returns(
    symbols: list[str], start: date, end: date,
) -> pd.DataFrame:
    query = text(
        "SELECT symbol, `date`, open, close, volume FROM stock_bars_daily "
        "WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end "
        "ORDER BY symbol, `date`"
    ).bindparams(bindparam("symbols", expanding=True))
    with get_sqlalchemy_engine().connect() as conn:
        bars = pd.read_sql(
            query, conn,
            params={
                "symbols": symbols,
                "start": start - timedelta(days=45),
                "end": end + timedelta(days=45),
            },
        )
    if bars.empty:
        return bars
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    for column in ("open", "close", "volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    output: list[dict[str, Any]] = []
    for symbol, frame in bars.dropna(subset=["date"]).groupby("symbol"):
        frame = frame.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
        frame["adv20"] = frame["volume"].shift(1).rolling(20, min_periods=10).mean()
        for index, row in frame.iterrows():
            item: dict[str, Any] = {
                "symbol": str(symbol).upper(),
                "auction_date": row["date"].date().isoformat(),
                "open": row["open"],
                "adv20": row["adv20"],
            }
            for horizon in (1, 5, 20):
                future_index = index + horizon
                item[f"return_open_to_j_plus_{horizon}"] = (
                    frame.iloc[future_index]["close"] / row["open"] - 1.0
                    if future_index < len(frame) and row["open"] and row["open"] > 0
                    else None
                )
            output.append(item)
    return pd.DataFrame(output)


def _feature_diagnostics(panel: pd.DataFrame) -> list[dict[str, Any]]:
    features = (
        "last_signed_imbalance", "imbalance_acceleration", "side_persistence",
        "imbalance_to_paired", "clearing_price_gap", "last_imbalance_over_adv20",
    )
    targets = tuple(f"return_open_to_j_plus_{horizon}" for horizon in (1, 5, 20))
    diagnostics: list[dict[str, Any]] = []
    for feature in features:
        for target in targets:
            valid = panel[[feature, target]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(valid) < 12:
                diagnostics.append({
                    "feature": feature, "target": target, "observations": len(valid),
                    "spearman_ic": None, "median_split_spread": None,
                    "status": "INSUFFICIENT_SAMPLE",
                })
                continue
            ic = valid[feature].rank(method="average").corr(
                valid[target].rank(method="average"),
            )
            median = valid[feature].median()
            spread = (
                valid.loc[valid[feature] > median, target].mean()
                - valid.loc[valid[feature] <= median, target].mean()
            )
            diagnostics.append({
                "feature": feature, "target": target, "observations": len(valid),
                "spearman_ic": float(ic) if pd.notna(ic) else None,
                "median_split_spread": float(spread) if pd.notna(spread) else None,
                "status": "DIAGNOSTIC_ONLY",
            })
    return diagnostics


def run(args: argparse.Namespace) -> Path:
    symbols = _resolve_input_symbols(args.symbols, args.symbol_source)
    if args.symbol_source and args.max_dates > MAX_UNIVERSE_DATES:
        raise ValueError(
            f"Universe collection is limited to {MAX_UNIVERSE_DATES} date per run"
        )
    if args.max_dates < 1 or args.max_dates > MAX_DATES:
        raise ValueError(f"max_dates must be between 1 and {MAX_DATES}")
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    if start > end:
        raise ValueError("start_date must be <= end_date")
    dates = _candidate_dates(start, end, args.max_dates)
    timestamp = datetime.now(UTC)
    output = (
        Path(args.resume_dir)
        if args.resume_dir
        else Path(args.output_dir) / f"nyse-auction-history-poc-{timestamp.strftime('%Y%m%d%H%M%S')}"
    )
    raw_root = output / "raw" / args.auction_type
    raw_root.mkdir(parents=True, exist_ok=True)

    observations: list[dict[str, Any]] = []
    empty = 0
    resumed = 0
    request_errors: list[dict[str, str]] = []
    stop_reason: str | None = None
    effective_interval = max(args.request_interval_seconds, 1.0 if args.symbol_source else 0.0)

    with requests.Session() as session:
        _configure_alpaca_session(session, use_system_trust_store=True)
        eligible_file = output / "eligible_symbols.txt"
        excluded_file = output / "excluded_symbols.txt"
        rotation_offset: int | None = None
        if args.resume_dir and eligible_file.is_file():
            selected = _parse_symbol_file(eligible_file)
            selected = [symbol for symbol in selected if symbol in set(symbols)]
            excluded = (
                _parse_symbol_file(excluded_file)
                if excluded_file.is_file()
                else sorted(set(symbols) - set(selected))
            )
            nyse_available_count: int | None = None
        else:
            available = _request_json(
                session, "/api/auction-charts/symbols",
                {"auctionType": args.auction_type},
            )
            allowed = {str(symbol).upper() for symbol in available if str(symbol).strip()}
            selected = [symbol for symbol in symbols if symbol in allowed]
            excluded = sorted(set(symbols) - set(selected))
            if args.symbol_source and dates:
                selected, rotation_offset = _rotate_symbols(
                    selected,
                    key=f"{args.auction_type}:{dates[-1].isoformat()}",
                )
            nyse_available_count = len(allowed)
            eligible_file.write_text(",".join(selected), encoding="utf-8")
            excluded_file.write_text(",".join(excluded), encoding="utf-8")
        for trading_date in ([] if args.eligibility_only else dates):
            for symbol in selected:
                raw_path = raw_root / trading_date.isoformat()
                raw_path.mkdir(parents=True, exist_ok=True)
                raw_file = raw_path / f"{symbol}.json"
                observed_at = datetime.now(UTC)
                downloaded = False
                if raw_file.is_file():
                    payload = json.loads(raw_file.read_text(encoding="utf-8"))
                    observed_at = datetime.fromtimestamp(raw_file.stat().st_mtime, UTC)
                    resumed += 1
                else:
                    try:
                        payload = _request_json(
                            session, "/api/auction-charts",
                            {
                                "symbol": symbol,
                                "tradeDate": trading_date.strftime("%m-%d-%Y"),
                                "auctionType": args.auction_type,
                            },
                        )
                        downloaded = True
                    except (NyseRateLimitError, RuntimeError) as exc:
                        stop_reason = "RATE_LIMITED" if isinstance(exc, NyseRateLimitError) else "SOURCE_UNAVAILABLE"
                        request_errors.append({"date": trading_date.isoformat(), "symbol": symbol, "error": str(exc)})
                        LOGGER.warning("Collection stopped cleanly at %s/%s: %s", trading_date, symbol, exc)
                        break
                    raw_file.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                observation = summarize_auction_rows(payload, observed_at=observed_at)
                if observation:
                    observations.append(observation)
                else:
                    empty += 1
                if effective_interval and downloaded:
                    time.sleep(effective_interval)
            if stop_reason:
                break

    panel = pd.DataFrame(observations)
    evaluation_error: str | None = None
    diagnostics: list[dict[str, Any]] = []
    if not panel.empty and not args.no_evaluate:
        try:
            realized = _load_realized_returns(selected, start, end)
            if not realized.empty:
                panel = panel.merge(realized, on=["symbol", "auction_date"], how="left")
                panel["last_imbalance_over_adv20"] = (
                    pd.to_numeric(panel["last_signed_imbalance"], errors="coerce")
                    / pd.to_numeric(panel["adv20"], errors="coerce")
                )
                diagnostics = _feature_diagnostics(panel)
        except Exception as exc:
            evaluation_error = str(exc)
            LOGGER.warning("Realized-return evaluation unavailable: %s", exc)

    if not panel.empty:
        panel.to_csv(output / "observations.csv", index=False)
    requested = len(dates) * len(selected)
    report = {
        "generated_at": timestamp.isoformat(),
        "source": {
            "page": f"{BASE_URL}/nyse-auction-data",
            "route_status": "PUBLIC_UNDOCUMENTED_WEB_INTERFACE",
            "official_live_feed": False,
            "automated_bulk_rights_validated": False,
            "history_window": "approximately trailing three months",
        },
        "contract": {
            "research_only": True,
            "scheduled": False,
            "database_persistence": False,
            "serving_allowed": False,
            "available_before_auction": False,
            "lookahead_warning": (
                "The web interface is updated after the auction. These rows cannot "
                "simulate a live pre-auction decision."
            ),
        },
        "request": {
            "daily_rotation_offset": rotation_offset,
            "auction_type": args.auction_type,
            "symbols": selected,
            "excluded_symbols": excluded,
            "dates": [value.isoformat() for value in dates],
            "symbol_source": args.symbol_source,
            "universe_requested_count": len(symbols),
            "nyse_available_count": nyse_available_count,
            "eligible_count": len(selected),
            "excluded_count": len(excluded),
            "requested_pairs": requested if not args.eligibility_only else 0,
        },
        "collection": {
            "observations": len(panel),
            "empty_pairs": empty,
            "coverage": len(panel) / requested if requested and not args.eligibility_only else 0.0,
            "eligibility_only": bool(args.eligibility_only),
            "completed_pairs": len(panel) + empty,
            "resumed_pairs": resumed,
            "effective_request_interval_seconds": effective_interval,
            "stop_reason": stop_reason,
            "errors": request_errors,
            "complete": not stop_reason and (args.eligibility_only or len(panel) + empty == requested),
        },
        "evaluation": {
            "error": evaluation_error,
            "diagnostics": diagnostics,
            "decision": (
                "ELIGIBILITY_AUDIT_ONLY" if args.eligibility_only else "RESEARCH_SAMPLE_ONLY"
            ),
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    today = datetime.now(UTC).date()
    parser = argparse.ArgumentParser(description="Small NYSE post-auction research POC")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--symbols", default=None)
    scope.add_argument("--symbol-source", default=None)
    parser.add_argument("--start-date", default=(today - timedelta(days=35)).isoformat())
    parser.add_argument("--end-date", default=(today - timedelta(days=1)).isoformat())
    parser.add_argument("--auction-type", choices=("opening", "closing"), default="opening")
    parser.add_argument("--max-dates", type=int, default=20)
    parser.add_argument("--request-interval-seconds", type=float, default=0.10)
    parser.add_argument("--no-evaluate", action="store_true")
    parser.add_argument("--output-dir", default="artifacts/research/nyse_auction_history_poc")
    parser.add_argument("--resume-dir", default=None)
    parser.add_argument("--eligibility-only", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    output = run(args)
    print(json.dumps({
        "output": str(output),
        "report": str(output / "report.json"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

