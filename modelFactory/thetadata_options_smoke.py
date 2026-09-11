"""E8-A3: smoke d'éligibilité ThetaData sur 10 événements Oracle historiques."""
from __future__ import annotations

import argparse
import gzip
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.oracle_options_pilot import build_event_schedule
from modelFactory.thetadata_options import (
    DEFAULT_BASE_URL,
    ThetaDataClient,
    ThetaDataError,
    ThetaDataHttpError,
    ThetaDataUnavailable,
    choose_atm_pair,
    select_synchronized_pair_quote,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_ORACLE_PATH = Path(
    "artifacts/research/multi_horizon_oracle_rolling/"
    "multi-horizon-rolling-20260910141708-d5b30f/aligned_predictions.parquet"
)


@dataclass(frozen=True, slots=True)
class ThetaSmokeConfig:
    dates: int = 5
    symbols_per_date: int = 2
    horizons: tuple[int, ...] = (3, 5, 10, 20)
    min_dte: int = 35
    max_dte: int = 55
    target_dte: int = 45
    entry_start: str = "09:35:00"
    entry_end: str = "10:00:00"
    exit_start: str = "15:30:00"
    exit_end: str = "15:55:00"
    interval: str = "1m"
    max_pair_quote_skew_seconds: int = 60
    minimum_complete_rate: float = 0.80

    def __post_init__(self) -> None:
        if self.dates < 1 or self.symbols_per_date < 1:
            raise ValueError("Le smoke doit contenir des dates et symboles.")
        if not self.horizons or any(value < 1 for value in self.horizons):
            raise ValueError("Horizons invalides.")
        if not 0 < self.min_dte <= self.target_dte <= self.max_dte:
            raise ValueError("Fenêtre DTE invalide.")
        if not 0 < self.minimum_complete_rate <= 1:
            raise ValueError("minimum_complete_rate invalide.")


def _spaced(values: list[pd.Timestamp], count: int) -> list[pd.Timestamp]:
    if len(values) < count:
        raise ValueError(f"Seulement {len(values)} dates Oracle, {count} requises.")
    if count == 1:
        return [values[len(values) // 2]]
    return [values[round(index * (len(values) - 1) / (count - 1))] for index in range(count)]


def select_smoke_events(
    oracle: pd.DataFrame, bars: pd.DataFrame, *, config: ThetaSmokeConfig,
    start_date: str, end_date: str,
) -> pd.DataFrame:
    """Prend, à chaque date, un candidat liquide et un candidat moins liquide."""
    required = {"date", "symbol"}
    missing = sorted(required.difference(oracle.columns))
    if missing:
        raise ValueError(f"Oracle incomplet: {missing}")
    frame = oracle.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if "mh0" in frame:
        top20 = frame["mh0"].fillna(False).astype(bool)
    elif "pct_h20" in frame:
        top20 = pd.to_numeric(frame["pct_h20"], errors="coerce").ge(0.80)
    else:
        raise ValueError("Oracle sans mh0 ni pct_h20.")
    frame = frame[
        top20 & frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    ][["date", "symbol"]].dropna().drop_duplicates()
    dates = _spaced([pd.Timestamp(value) for value in sorted(frame["date"].unique())], config.dates)
    frame = frame[frame["date"].isin(dates)]

    market = bars[["date", "symbol", "close", "volume"]].copy()
    market["date"] = pd.to_datetime(market["date"], errors="coerce").dt.normalize()
    market["dollar_volume"] = (
        pd.to_numeric(market["close"], errors="coerce")
        * pd.to_numeric(market["volume"], errors="coerce")
    )
    frame = frame.merge(market[["date", "symbol", "dollar_volume"]], on=["date", "symbol"], how="left")
    selected: list[pd.DataFrame] = []
    for _, group in frame.groupby("date", sort=True):
        valid = group[np.isfinite(group["dollar_volume"]) & group["dollar_volume"].gt(0)].sort_values(
            ["dollar_volume", "symbol"]
        )
        if len(valid) < config.symbols_per_date:
            raise ValueError("Barres de liquidité insuffisantes pour une date du smoke.")
        valid = valid.copy()
        valid["liquidity_rank_in_top20"] = valid["dollar_volume"].rank(method="first", pct=True)
        indexes = np.linspace(0, len(valid) - 1, config.symbols_per_date).round().astype(int)
        picked = valid.iloc[indexes].drop_duplicates("symbol").copy()
        if len(picked) != config.symbols_per_date:
            raise ValueError("Impossible de sélectionner des symboles distincts.")
        selected.append(picked)
    return pd.concat(selected, ignore_index=True).sort_values(["date", "dollar_volume"])


def _flat_quote(prefix: str, quote: dict[str, Any], output: dict[str, Any]) -> None:
    output[f"{prefix}_timestamp"] = quote["timestamp"]
    output[f"{prefix}_skew_seconds"] = quote["skew_seconds"]
    for right in ("call", "put"):
        for field in ("bid", "ask", "bid_size", "ask_size", "quote_timestamp"):
            output[f"{prefix}_{right}_{field}"] = quote[right].get(field)


def evaluate_smoke_event(
    client: ThetaDataClient, event: dict[str, Any], config: ThetaSmokeConfig,
) -> dict[str, Any]:
    output = dict(event)
    output["status"] = "rejected_schedule"
    if not bool(event.get("schedule_complete")):
        return output
    entry_date = pd.Timestamp(event["entry_date"]).date()
    symbol = str(event["symbol"]).upper()
    contracts = client.list_quoted_contracts(symbol, entry_date, max_dte=config.max_dte)
    output["contracts_returned"] = len(contracts)
    pair = choose_atm_pair(
        contracts, symbol=symbol, spot=float(event["underlying_entry_open"]),
        entry_date=entry_date, min_dte=config.min_dte, max_dte=config.max_dte,
        target_dte=config.target_dte,
    )
    if pair is None:
        output["status"] = "rejected_no_historical_contract_pair"
        return output
    output.update({
        "expiration": pair.expiration.isoformat(), "strike": pair.strike,
        "dte": pair.dte, "historically_expired": pair.expiration < date.today(),
    })
    entry_rows = client.history_quotes(
        pair, entry_date, start_time=config.entry_start, end_time=config.entry_end,
        interval=config.interval,
    )
    entry = select_synchronized_pair_quote(
        entry_rows, prefer="first", max_skew_seconds=config.max_pair_quote_skew_seconds,
    )
    if entry is None:
        output["status"] = "rejected_no_entry_nbbo"
        return output
    _flat_quote("entry", entry, output)
    complete = 0
    timestamps_match_dates = pd.Timestamp(entry["timestamp"]).date() == entry_date
    for horizon in config.horizons:
        exit_date = pd.Timestamp(event[f"h{horizon}_exit_date"]).date()
        rows = client.history_quotes(
            pair, exit_date, start_time=config.exit_start, end_time=config.exit_end,
            interval=config.interval,
        )
        quote = select_synchronized_pair_quote(
            rows, prefer="last", max_skew_seconds=config.max_pair_quote_skew_seconds,
        )
        if quote is None:
            continue
        _flat_quote(f"h{horizon}", quote, output)
        timestamps_match_dates &= pd.Timestamp(quote["timestamp"]).date() == exit_date
        complete += 1
    output["complete_horizons"] = complete
    output["timestamps_match_requested_dates"] = bool(timestamps_match_dates)
    output["status"] = "complete" if complete == len(config.horizons) else "partial_exit_nbbo"
    return output


def assess_smoke(
    results: pd.DataFrame, *, config: ThetaSmokeConfig,
    terminal_error: str | None = None,
) -> dict[str, Any]:
    events = len(results)
    contract_rate = float(
        results.get("expiration", pd.Series(index=results.index, dtype=object)).notna().mean()
    ) if events else 0.0
    complete_rate = float(
        results.get("status", pd.Series(index=results.index, dtype=object)).eq("complete").mean()
    ) if events else 0.0
    expired_rate = float(
        results.get("historically_expired", pd.Series(index=results.index, dtype=bool))
        .fillna(False).mean()
    ) if events else 0.0
    timestamp_values = results.get(
        "timestamps_match_requested_dates", pd.Series(index=results.index, dtype=bool)
    ).dropna()
    timestamps_ok = bool(len(timestamp_values) and timestamp_values.all()) if events else False
    expected_events = config.dates * config.symbols_per_date
    gates = {
        "terminal_reachable": terminal_error is None,
        "expected_event_count": events == expected_events,
        "historical_contract_pair_rate": contract_rate >= config.minimum_complete_rate,
        "historically_expired_contracts": expired_rate >= config.minimum_complete_rate,
        "entry_and_four_exits_complete_rate": complete_rate >= config.minimum_complete_rate,
        "timestamps_match_requested_dates": timestamps_ok,
    }
    if terminal_error == "terminal_unreachable":
        verdict = "BLOCKED_THETA_TERMINAL_NOT_RUNNING"
    elif terminal_error == "entitlement":
        verdict = "BLOCKED_THETADATA_ENTITLEMENT"
    elif all(gates.values()):
        verdict = "GO_E8_A2_PILOT_60_DATES"
    else:
        verdict = "NO_GO_THETADATA_SMOKE_QUALITY"
    return {
        "events": events, "expected_events": expected_events,
        "contract_pair_rate": contract_rate, "complete_rate": complete_rate,
        "historically_expired_pair_rate": expired_rate,
        "gates": gates, "verdict": verdict,
    }


def run(
    *, oracle_path: Path, output_root: Path, base_url: str,
    start_date: str, end_date: str, config: ThetaSmokeConfig,
) -> Path:
    oracle = pd.read_parquet(oracle_path)
    oracle_dates = pd.to_datetime(oracle["date"], errors="coerce")
    candidates = oracle[oracle_dates.between(pd.Timestamp(start_date), pd.Timestamp(end_date))]
    symbols = sorted(candidates["symbol"].dropna().astype(str).unique())
    bars = load_universe_bars(
        get_sqlalchemy_engine(), symbols,
        start_date=pd.Timestamp(start_date).date(),
        end_date=(pd.Timestamp(end_date) + pd.offsets.BDay(max(config.horizons) + 3)).date(),
    )
    events = select_smoke_events(
        oracle, bars, config=config, start_date=start_date, end_date=end_date,
    )
    schedule = build_event_schedule(events, bars, config.horizons)

    run_id = f"thetadata-options-smoke-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    schedule.to_parquet(output / "selected_events.parquet", index=False)
    raw_records: list[dict[str, Any]] = []
    client = ThetaDataClient(base_url=base_url, recorder=raw_records.append)
    rows: list[dict[str, Any]] = []
    terminal_error: str | None = None
    for event in schedule.to_dict(orient="records"):
        try:
            rows.append(evaluate_smoke_event(client, event, config))
        except ThetaDataUnavailable:
            terminal_error = "terminal_unreachable"
            LOGGER.warning("Theta Terminal inaccessible; smoke interrompu.")
            break
        except ThetaDataHttpError as exc:
            terminal_error = "entitlement" if exc.status_code in {401, 403} else "http_error"
            rows.append({**event, "status": terminal_error, "error": str(exc)})
            break
        except ThetaDataError as exc:
            terminal_error = "protocol_error"
            rows.append({**event, "status": terminal_error, "error": str(exc)})
            break
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.to_parquet(output / "event_results.parquet", index=False)
    with gzip.open(output / "raw_responses.jsonl.gz", "wt", encoding="utf-8") as stream:
        for record in raw_records:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    assessment = assess_smoke(frame, config=config, terminal_error=terminal_error)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E8_A3_THETADATA_ELIGIBILITY_SMOKE",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "oracle_path": str(oracle_path), "base_url": base_url,
        "config": asdict(config), "scheduled_events": int(len(schedule)),
        "requests_recorded": len(raw_records), "assessment": assessment,
        "next_action": (
            "collect_60_spread_dates" if assessment["verdict"] == "GO_E8_A2_PILOT_60_DATES"
            else "resolve_terminal_or_entitlement_then_rerun_same_smoke"
        ),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-path", type=Path, default=DEFAULT_ORACLE_PATH)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/thetadata_options"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2024-07-09")
    parser.add_argument("--dates", type=int, default=5)
    parser.add_argument("--symbols-per-date", type=int, default=2)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_path=args.oracle_path, output_root=args.output_root,
        base_url=args.base_url, start_date=args.start_date, end_date=args.end_date,
        config=ThetaSmokeConfig(dates=args.dates, symbols_per_date=args.symbols_per_date),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E8-A3 terminé: {output}")
    print(report["assessment"]["verdict"])


if __name__ == "__main__":
    main()
