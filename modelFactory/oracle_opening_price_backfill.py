"""Backfill historique compact E20 price-only sur les événements Oracle OOF.

Les minutes Alpaca SIP sont agrégées immédiatement en features OHLC. Le RAW
minute n'est pas persisté : ce chemin de recherche évite plusieurs dizaines de
millions de lignes en base. Un Parquet par séance et un état atomique rendent
le téléchargement reprenable et idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from modelFactory.oracle_opening_price_confirmation import (
    E20BConfig,
    build_price_only_features,
)
from modelFactory.oracle_opening_window_availability_audit import (
    attach_next_oracle_session,
    load_oracle_events,
)
from service.alpaca.clientAlpaca import get_alpaca_credentials
from service.forward_pit.batch import (
    ALPACA_DATA_URL,
    configure_alpaca_session,
    market_datetime,
    paginated_json,
)

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class BackfillConfig:
    feed: str = "sip"
    adjustment: str = "raw"
    timeframe: str = "1Min"
    window_start: str = "09:30"
    window_end: str = "10:30"
    symbol_batch_size: int = 100
    max_pages_per_batch: int = 5
    request_interval_seconds: float = 0.35
    maximum_consecutive_session_failures: int = 5
    use_system_trust_store: bool = True

    def __post_init__(self) -> None:
        if self.feed != "sip" or self.timeframe != "1Min":
            raise ValueError("E20 historique impose SIP/1Min.")
        if self.window_start != "09:30" or self.window_end != "10:30":
            raise ValueError("E20 price-only impose la fenêtre 09:30–10:30 NY.")
        if self.symbol_batch_size <= 0 or self.max_pages_per_batch <= 0:
            raise ValueError("Paramètres de pagination invalides.")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def build_event_schedule(
    oracle_path: Path, *, start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    events = attach_next_oracle_session(load_oracle_events(oracle_path))
    if start_date:
        events = events[events["date"].ge(pd.Timestamp(start_date))]
    if end_date:
        events = events[events["date"].le(pd.Timestamp(end_date))]
    return events[["date", "target_session", "symbol"]].drop_duplicates().sort_values(
        ["target_session", "symbol"]
    ).reset_index(drop=True)


def normalize_alpaca_pages(
    pages: list[tuple[dict[str, Any], int]], *, session_date: pd.Timestamp,
) -> pd.DataFrame:
    """Ne conserve que OHLC et l'horloge nécessaires aux features price-only."""
    rows: list[dict[str, Any]] = []
    normalized_date = pd.Timestamp(session_date).normalize()
    for payload, _status in pages:
        bars = payload.get("bars") or {}
        if not isinstance(bars, dict):
            raise RuntimeError("Réponse Alpaca sans objet bars.")
        for raw_symbol, items in bars.items():
            symbol = str(raw_symbol or "").strip().upper()
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                try:
                    local_ts, utc_ts = market_datetime(item.get("t"))
                    minute = local_ts.hour * 60 + local_ts.minute
                    prices = {name: float(item[key]) for name, key in (
                        ("open", "o"), ("high", "h"),
                        ("low", "l"), ("close", "c"),
                    )}
                except (KeyError, TypeError, ValueError):
                    continue
                if not 570 <= minute < 630 or min(prices.values()) <= 0:
                    continue
                if prices["high"] < max(prices["open"], prices["close"]):
                    continue
                if prices["low"] > min(prices["open"], prices["close"]):
                    continue
                rows.append({
                    "session_date": normalized_date, "symbol": symbol,
                    "minute_of_day": minute, "bar_timestamp": utc_ts,
                    **prices,
                })
    if not rows:
        return pd.DataFrame(columns=[
            "session_date", "symbol", "minute_of_day", "bar_timestamp",
            "open", "high", "low", "close",
        ])
    return pd.DataFrame(rows).drop_duplicates(
        ["session_date", "symbol", "bar_timestamp"], keep="last"
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    temporary.replace(path)


def _new_state(
    *, batch_id: str, horizon: int, oracle_path: Path,
    schedule: pd.DataFrame, config: BackfillConfig,
) -> dict[str, Any]:
    return {
        "schema_version": 1, "experiment": "E20_PRICE_ONLY_HISTORICAL_BACKFILL",
        "batch_id": batch_id, "horizon": horizon,
        "oracle_path": str(oracle_path), "oracle_sha256": file_sha256(oracle_path),
        "config": asdict(config), "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "planned_sessions": int(schedule["target_session"].nunique()),
        "planned_events": len(schedule), "sessions": {},
    }


def load_or_create_state(
    state_path: Path, *, batch_id: str, horizon: int, oracle_path: Path,
    schedule: pd.DataFrame, config: BackfillConfig,
) -> dict[str, Any]:
    expected_hash = file_sha256(oracle_path)
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (
            state.get("batch_id") != batch_id
            or int(state.get("horizon", -1)) != horizon
            or state.get("oracle_sha256") != expected_hash
            or state.get("config") != asdict(config)
        ):
            raise ValueError(
                "État de reprise incompatible avec le batch, l'Oracle ou la configuration."
            )
        return state
    return _new_state(
        batch_id=batch_id, horizon=horizon, oracle_path=oracle_path,
        schedule=schedule, config=config,
    )


def _fetch_session(
    session: requests.Session, headers: dict[str, str], *,
    session_date: pd.Timestamp, symbols: list[str], config: BackfillConfig,
) -> tuple[pd.DataFrame, int]:
    day = pd.Timestamp(session_date).date()
    start = datetime.combine(day, datetime.strptime(config.window_start, "%H:%M").time(), NY)
    end = datetime.combine(day, datetime.strptime(config.window_end, "%H:%M").time(), NY)
    all_pages: list[tuple[dict[str, Any], int]] = []
    page_count = 0
    for chunk in _chunks(symbols, config.symbol_batch_size):
        pages = paginated_json(
            session, f"{ALPACA_DATA_URL}/v2/stocks/bars",
            params={
                "symbols": ",".join(chunk), "timeframe": config.timeframe,
                "start": start.astimezone(UTC).isoformat(),
                "end": end.astimezone(UTC).isoformat(),
                "feed": config.feed, "adjustment": config.adjustment,
                "limit": 10000, "sort": "asc",
            }, headers=headers, page_key="next_page_token",
            max_pages=config.max_pages_per_batch,
            pause_seconds=config.request_interval_seconds,
        )
        page_count += len(pages)
        all_pages.extend(pages)
    return normalize_alpaca_pages(all_pages, session_date=session_date), page_count


def _consolidate(partition_dir: Path, output_path: Path) -> int:
    files = sorted(partition_dir.glob("*.parquet"))
    if not files:
        return 0
    frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    frame = frame.sort_values(["session_date", "symbol"]).drop_duplicates(
        ["session_date", "symbol"], keep="last"
    )
    frame.to_parquet(output_path, index=False)
    return len(frame)


def run(
    *, batch_id: str, horizon: int, oracle_path: Path, output_dir: Path,
    config: BackfillConfig, feature_config: E20BConfig,
    start_date: str | None = None, end_date: str | None = None,
    max_sessions: int | None = None,
) -> Path:
    schedule = build_event_schedule(
        oracle_path, start_date=start_date, end_date=end_date,
    )
    if schedule.empty:
        raise ValueError("Aucun événement Oracle OOF dans la période demandée.")
    output_dir.mkdir(parents=True, exist_ok=True)
    partition_dir = output_dir / "session_features"
    partition_dir.mkdir(exist_ok=True)
    state_path = output_dir / "state.json"
    state = load_or_create_state(
        state_path, batch_id=batch_id, horizon=horizon,
        oracle_path=oracle_path, schedule=schedule, config=config,
    )
    state["feature_config"] = asdict(feature_config)
    state["updated_at"] = datetime.now(UTC).isoformat()
    _atomic_json(state_path, state)

    pending: list[tuple[pd.Timestamp, pd.DataFrame]] = []
    for session_date, group in schedule.groupby("target_session", sort=True):
        key = pd.Timestamp(session_date).date().isoformat()
        if (state["sessions"].get(key) or {}).get("status") == "COMPLETED":
            continue
        pending.append((pd.Timestamp(session_date), group))
    if max_sessions is not None:
        if max_sessions <= 0:
            raise ValueError("max_sessions doit être strictement positif.")
        pending = pending[:max_sessions]

    key, secret = get_alpaca_credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    consecutive_failures = 0
    with requests.Session() as session:
        configure_alpaca_session(
            session, use_system_trust_store=config.use_system_trust_store,
        )
        total = len(pending)
        for index, (session_date, group) in enumerate(pending, start=1):
            session_key = session_date.date().isoformat()
            symbols = sorted(group["symbol"].astype(str).str.upper().unique())
            started = datetime.now(UTC)
            try:
                minute_rows, pages = _fetch_session(
                    session, headers, session_date=session_date,
                    symbols=symbols, config=config,
                )
                features = build_price_only_features(minute_rows, feature_config)
                features = features[features["symbol"].isin(symbols)].copy()
                features["provider"] = "alpaca"
                features["feed"] = config.feed
                features["adjustment"] = config.adjustment
                features["acquired_at"] = datetime.now(UTC).replace(tzinfo=None)
                part_path = partition_dir / f"{session_key}.parquet"
                temporary = part_path.with_suffix(".parquet.tmp")
                features.to_parquet(temporary, index=False)
                temporary.replace(part_path)
                covered = int(features["symbol"].nunique()) if len(features) else 0
                state["sessions"][session_key] = {
                    "status": "COMPLETED", "signal_dates": sorted(
                        pd.to_datetime(group["date"]).dt.date.astype(str).unique().tolist()
                    ),
                    "requested_symbols": len(symbols), "covered_symbols": covered,
                    "coverage": covered / len(symbols) if symbols else 0,
                    "minute_rows_received": len(minute_rows), "pages": pages,
                    "partition": str(part_path), "started_at": started.isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                }
                consecutive_failures = 0
                LOGGER.info(
                    "E20 backfill %s/%s session=%s symbols=%s covered=%s bars=%s pages=%s",
                    index, total, session_key, len(symbols), covered, len(minute_rows), pages,
                )
            except Exception as exc:
                consecutive_failures += 1
                state["sessions"][session_key] = {
                    "status": "FAILED", "requested_symbols": len(symbols),
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "error": str(exc)[:2000],
                }
                LOGGER.exception("E20 backfill session=%s en échec", session_key)
            finally:
                state["updated_at"] = datetime.now(UTC).isoformat()
                _atomic_json(state_path, state)
            if consecutive_failures >= config.maximum_consecutive_session_failures:
                raise RuntimeError(
                    f"Arrêt de sécurité après {consecutive_failures} séances en échec."
                )

    consolidated_path = output_dir / "price_only_features.parquet"
    consolidated_rows = _consolidate(partition_dir, consolidated_path)
    statuses = [item.get("status") for item in state["sessions"].values()]
    completed = statuses.count("COMPLETED")
    failed = statuses.count("FAILED")
    report = {
        "schema_version": 1, "experiment": "E20_PRICE_ONLY_HISTORICAL_BACKFILL",
        "status": "COMPLETE" if completed == state["planned_sessions"] and not failed else "PARTIAL",
        "research_only": True, "production_change": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "batch_id": batch_id, "horizon": horizon,
        "oracle_path": str(oracle_path), "oracle_sha256": state["oracle_sha256"],
        "config": asdict(config), "feature_config": asdict(feature_config),
        "population": {
            "planned_sessions": state["planned_sessions"],
            "planned_events": state["planned_events"],
            "completed_sessions": completed, "failed_sessions": failed,
            "pending_sessions": state["planned_sessions"] - completed,
            "consolidated_feature_rows": consolidated_rows,
        },
        "artifacts": {
            "state": str(state_path), "partitions": str(partition_dir),
            "features": str(consolidated_path),
        },
        "data_contract": {
            "price_only": True,
            "used_fields": ["t", "o", "h", "l", "c"],
            "ignored_fields": ["v", "n", "vw"],
            "historical_acquisition_is_not_original_pit_availability": True,
        },
    }
    _atomic_json(output_dir / "report.json", report)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--oracle-path", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--symbol-batch-size", type=int, default=100)
    parser.add_argument("--request-interval-seconds", type=float, default=0.35)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    oracle_path = args.oracle_path or (
        Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet"
    )
    output_dir = args.output_dir or (
        Path("artifacts/research/oracle_opening_price_backfill")
        / f"{args.batch_id}-h{args.horizon}"
    )
    output = run(
        batch_id=args.batch_id, horizon=args.horizon,
        oracle_path=oracle_path, output_dir=output_dir,
        config=BackfillConfig(
            symbol_batch_size=args.symbol_batch_size,
            request_interval_seconds=args.request_interval_seconds,
        ),
        feature_config=E20BConfig(), start_date=args.start_date,
        end_date=args.end_date, max_sessions=args.max_sessions,
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E20 backfill: {output}")
    print(json.dumps(report["population"], ensure_ascii=False))


if __name__ == "__main__":
    main()
