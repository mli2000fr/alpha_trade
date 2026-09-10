"""E6-B1 research-only: pilote REST de straddles sur événements Oracle OOF.

Le pilote sélectionne les contrats avec ``as_of`` à J+1, achète une paire
call/put au même strike aux asks, puis la valorise aux bids. Il est conçu pour
tester la couverture et le coût exécutable avant toute campagne complète.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_amplitude_audit import GROUP_COL, TOP20
from modelFactory.shared_directional import _semester_label

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class OptionsPilotConfig:
    horizons: tuple[int, ...] = (3, 5, 10, 20)
    min_dte: int = 35
    max_dte: int = 55
    target_dte: int = 45
    minimum_exit_buffer_days: int = 5
    strike_band_pct: float = 0.25
    entry_start: str = "09:35"
    entry_end: str = "10:00"
    exit_start: str = "15:30"
    exit_end: str = "15:55"
    max_pair_quote_skew_seconds: int = 60
    commission_per_contract_side: float = 0.65

    def __post_init__(self) -> None:
        if not self.horizons or any(h < 1 for h in self.horizons):
            raise ValueError("Horizons options invalides.")
        if not 0 < self.min_dte <= self.target_dte <= self.max_dte:
            raise ValueError("Contrat DTE incohérent.")
        if self.minimum_exit_buffer_days < 0:
            raise ValueError("Le buffer avant expiration doit être positif.")
        if not 0 < self.strike_band_pct < 1:
            raise ValueError("strike_band_pct doit être dans ]0,1[.")
        if self.max_pair_quote_skew_seconds < 0:
            raise ValueError("La tolérance de synchronisation doit être positive.")


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def select_pilot_events(
    events: pd.DataFrame,
    *,
    dates_per_semester: int = 1,
    max_symbols_per_date: int | None = None,
    start_date: str = "2022-03-07",
    end_date: str = "2025-07-11",
) -> pd.DataFrame:
    """Échantillonne des dates avant toute observation des prix d'options."""
    required = {"date", "symbol", GROUP_COL, "directional_oracle_extreme_pct"}
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"Événements Oracle incomplets: {missing}")
    frame = events.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[
        frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & frame[GROUP_COL].eq(TOP20)
    ].copy()
    if "amplitude_entry_eligible" in frame:
        frame = frame[frame["amplitude_entry_eligible"].fillna(False).astype(bool)]
    if "h20_max_abs_excursion_capped_100pct" in frame:
        frame = frame[frame["h20_max_abs_excursion_capped_100pct"].notna()]
    frame["semester"] = frame["date"].map(_semester_label)
    selected_dates: list[pd.Timestamp] = []
    for _, group in frame.groupby("semester", sort=True):
        dates = np.array(sorted(group["date"].unique()))
        if not len(dates):
            continue
        indexes = np.linspace(0, len(dates) - 1, min(dates_per_semester, len(dates)) + 2)[1:-1]
        selected_dates.extend(pd.Timestamp(dates[int(round(index))]) for index in indexes)
    selected = frame[frame["date"].isin(selected_dates)].copy()
    selected = selected.sort_values(
        ["date", "directional_oracle_extreme_pct", "symbol"],
        ascending=[True, False, True],
    )
    if max_symbols_per_date is not None:
        selected = selected.groupby("date", sort=True, group_keys=False).head(max_symbols_per_date)
    return selected.reset_index(drop=True)


def build_event_schedule(
    events: pd.DataFrame, bars: pd.DataFrame, horizons: tuple[int, ...]
) -> pd.DataFrame:
    """Résout J+1 et les sorties en séances propres à chaque symbole."""
    output: list[dict[str, Any]] = []
    max_horizon = max(horizons)
    for symbol, requested in events.groupby("symbol", sort=False):
        available = bars[bars["symbol"].astype(str).str.upper().eq(str(symbol).upper())].copy()
        available["date"] = pd.to_datetime(available["date"], errors="coerce").dt.normalize()
        available = available.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        by_date = {value: index for index, value in enumerate(available["date"])}
        for event in requested.to_dict(orient="records"):
            signal = pd.Timestamp(event["date"]).normalize()
            index = by_date.get(signal)
            row = dict(event)
            row["schedule_complete"] = False
            if index is None or index + max_horizon >= len(available):
                output.append(row)
                continue
            entry_index = index + 1
            entry_open = pd.to_numeric(pd.Series([available.loc[entry_index, "open"]]), errors="coerce").iloc[0]
            if not np.isfinite(entry_open) or entry_open <= 0:
                output.append(row)
                continue
            row["entry_date"] = available.loc[entry_index, "date"]
            row["underlying_entry_open"] = float(entry_open)
            for horizon in horizons:
                exit_index = entry_index + horizon - 1
                row[f"h{horizon}_exit_date"] = available.loc[exit_index, "date"]
            row["schedule_complete"] = True
            output.append(row)
    return pd.DataFrame(output)


def choose_contract_pair(
    contracts: list[dict[str, Any]], *, spot: float, entry_date: date,
    config: OptionsPilotConfig,
) -> dict[str, Any] | None:
    """Choisit sans données futures le même strike call/put le plus ATM."""
    pairs: dict[tuple[date, float], dict[str, dict[str, Any]]] = {}
    for contract in contracts:
        try:
            expiry = date.fromisoformat(str(contract["expiration_date"]))
            strike = float(contract["strike_price"])
            side = str(contract["contract_type"]).lower()
            ticker = str(contract["ticker"])
        except (KeyError, TypeError, ValueError):
            continue
        dte = (expiry - entry_date).days
        if side not in {"call", "put"} or not config.min_dte <= dte <= config.max_dte:
            continue
        if not spot * (1-config.strike_band_pct) <= strike <= spot * (1+config.strike_band_pct):
            continue
        pairs.setdefault((expiry, strike), {})[side] = {**contract, "ticker": ticker}
    complete = [(key, sides) for key, sides in pairs.items() if {"call", "put"}.issubset(sides)]
    if not complete:
        return None
    (expiry, strike), sides = min(
        complete,
        key=lambda item: (
            abs(item[0][1] / spot - 1.0),
            abs((item[0][0] - entry_date).days - config.target_dte),
            item[0][0],
        ),
    )
    return {
        "expiration_date": expiry.isoformat(), "strike": strike,
        "dte": (expiry-entry_date).days,
        "call_ticker": sides["call"]["ticker"], "put_ticker": sides["put"]["ticker"],
    }


def _results(response: Any) -> list[dict[str, Any]]:
    if not response.ok:
        return []
    payload = response.json()
    result = payload.get("results") if isinstance(payload, dict) else None
    return result if isinstance(result, list) else []


def fetch_contract_pair(
    client: EroyaClient, symbol: str, entry_date: date, spot: float,
    config: OptionsPilotConfig,
) -> dict[str, Any] | None:
    start_expiry = entry_date + timedelta(days=config.min_dte)
    end_expiry = entry_date + timedelta(days=config.max_dte)
    response = client.get("reference/options/contracts", params={
        "underlying_ticker": symbol, "as_of": entry_date.isoformat(),
        "expiration_date.gte": start_expiry.isoformat(),
        "expiration_date.lte": end_expiry.isoformat(),
        "strike_price.gte": round(spot * (1-config.strike_band_pct), 4),
        "strike_price.lte": round(spot * (1+config.strike_band_pct), 4),
        "limit": 1000, "sort": "ticker", "order": "asc",
    })
    return choose_contract_pair(_results(response), spot=spot, entry_date=entry_date, config=config)


def fetch_quote(
    client: EroyaClient, ticker: str, session_date: date,
    *, start_clock: str, end_clock: str, order: str,
) -> dict[str, Any] | None:
    start = datetime.combine(session_date, _clock(start_clock), tzinfo=NY)
    end = datetime.combine(session_date, _clock(end_clock), tzinfo=NY)
    response = client.get(f"quotes/{ticker}", params={
        "timestamp.gte": str(_ns(start)), "timestamp.lte": str(_ns(end)),
        "sort": "timestamp", "order": order, "limit": 1,
    })
    values = _results(response)
    if not values:
        return None
    quote = values[0]
    bid = float(quote.get("bid_price") or 0)
    ask = float(quote.get("ask_price") or 0)
    timestamp = int(quote.get("sip_timestamp") or 0)
    if bid <= 0 or ask <= 0 or ask < bid or timestamp <= 0:
        return None
    return {"bid": bid, "ask": ask, "timestamp": timestamp}


def fetch_pair_quote(
    client: EroyaClient, pair: dict[str, Any], session_date: date,
    *, start_clock: str, end_clock: str, order: str, max_skew_seconds: int,
) -> dict[str, Any] | None:
    call = fetch_quote(
        client, pair["call_ticker"], session_date,
        start_clock=start_clock, end_clock=end_clock, order=order,
    )
    put = fetch_quote(
        client, pair["put_ticker"], session_date,
        start_clock=start_clock, end_clock=end_clock, order=order,
    )
    if call is None or put is None:
        return None
    skew = abs(call["timestamp"] - put["timestamp"]) / 1_000_000_000
    if skew > max_skew_seconds:
        return None
    return {"call": call, "put": put, "skew_seconds": skew}


def evaluate_event(
    client: EroyaClient, event: dict[str, Any], config: OptionsPilotConfig
) -> dict[str, Any]:
    result = dict(event)
    result["status"] = "rejected_schedule"
    if not bool(event.get("schedule_complete")):
        return result
    entry_date = pd.Timestamp(event["entry_date"]).date()
    pair = fetch_contract_pair(
        client, str(event["symbol"]), entry_date,
        float(event["underlying_entry_open"]), config,
    )
    if pair is None:
        result["status"] = "rejected_no_contract_pair"
        return result
    result.update(pair)
    entry = fetch_pair_quote(
        client, pair, entry_date, start_clock=config.entry_start,
        end_clock=config.entry_end, order="asc",
        max_skew_seconds=config.max_pair_quote_skew_seconds,
    )
    if entry is None:
        result["status"] = "rejected_no_synchronous_entry_nbbo"
        return result
    premium = entry["call"]["ask"] + entry["put"]["ask"]
    if premium <= 0:
        result["status"] = "rejected_invalid_entry_premium"
        return result
    result.update({
        "entry_call_bid": entry["call"]["bid"], "entry_put_bid": entry["put"]["bid"],
        "entry_call_ask": entry["call"]["ask"], "entry_put_ask": entry["put"]["ask"],
        "entry_premium": premium, "entry_quote_skew_seconds": entry["skew_seconds"],
    })
    entry_bid = entry["call"]["bid"] + entry["put"]["bid"]
    entry_mid = (entry_bid + premium) / 2.0
    result["entry_bid_value"] = entry_bid
    result["entry_midpoint_value"] = entry_mid
    result["entry_combined_relative_spread"] = (
        (premium-entry_bid) / entry_mid if entry_mid > 0 else np.nan
    )
    result["entry_premium_pct_underlying"] = premium / float(event["underlying_entry_open"])
    result["strike_distance_pct"] = abs(
        float(pair["strike"]) / float(event["underlying_entry_open"])-1.0
    )
    complete = 0
    for horizon in config.horizons:
        exit_date = pd.Timestamp(event[f"h{horizon}_exit_date"]).date()
        expiry = date.fromisoformat(pair["expiration_date"])
        if expiry < exit_date + timedelta(days=config.minimum_exit_buffer_days):
            continue
        exit_quote = fetch_pair_quote(
            client, pair, exit_date, start_clock=config.exit_start,
            end_clock=config.exit_end, order="desc",
            max_skew_seconds=config.max_pair_quote_skew_seconds,
        )
        if exit_quote is None:
            continue
        liquidation = exit_quote["call"]["bid"] + exit_quote["put"]["bid"]
        commission = 4.0 * config.commission_per_contract_side / 100.0
        result.update({
            f"h{horizon}_exit_call_bid": exit_quote["call"]["bid"],
            f"h{horizon}_exit_put_bid": exit_quote["put"]["bid"],
            f"h{horizon}_exit_call_ask": exit_quote["call"]["ask"],
            f"h{horizon}_exit_put_ask": exit_quote["put"]["ask"],
            f"h{horizon}_liquidation": liquidation,
            f"h{horizon}_gross_return": liquidation / premium - 1.0,
            f"h{horizon}_net_return": (liquidation - premium - commission) / premium,
            f"h{horizon}_mid_entry_to_bid_return": (
                (liquidation-entry_mid-commission) / entry_mid
            ),
            f"h{horizon}_quote_skew_seconds": exit_quote["skew_seconds"],
        })
        complete += 1
    result["complete_horizons"] = complete
    result["status"] = "complete" if complete == len(config.horizons) else "partial_exit_nbbo"
    return result


def summarize(results: pd.DataFrame, config: OptionsPilotConfig) -> dict[str, Any]:
    statuses = results["status"].value_counts(dropna=False).to_dict() if not results.empty else {}
    report: dict[str, Any] = {
        "events": int(len(results)), "statuses": statuses,
        "contract_pair_rate": float(results["call_ticker"].notna().mean()) if "call_ticker" in results else 0.0,
        "entry_nbbo_rate": float(results["entry_premium"].notna().mean()) if "entry_premium" in results else 0.0,
    }
    for horizon in config.horizons:
        column = f"h{horizon}_net_return"
        values = pd.to_numeric(results.get(column), errors="coerce").dropna()
        report[f"h{horizon}"] = {
            "observations": int(len(values)),
            "coverage": float(len(values) / len(results)) if len(results) else 0.0,
            "mean_net_return": float(values.mean()) if len(values) else None,
            "median_net_return": float(values.median()) if len(values) else None,
            "positive_rate": float(values.gt(0).mean()) if len(values) else None,
        }
    return report


def run_pilot(
    client: EroyaClient, events_path: Path, output: Path,
    *, dates_per_semester: int, max_symbols_per_date: int | None,
    start_date: str, end_date: str, config: OptionsPilotConfig,
) -> dict[str, Any]:
    source = pd.read_parquet(events_path)
    events = select_pilot_events(
        source, dates_per_semester=dates_per_semester,
        max_symbols_per_date=max_symbols_per_date, start_date=start_date, end_date=end_date,
    )
    symbols = sorted(events["symbol"].unique())
    bars = load_universe_bars(
        get_sqlalchemy_engine(), symbols,
        start_date=pd.Timestamp(start_date).date(),
        end_date=(pd.Timestamp(end_date)+pd.offsets.BDay(max(config.horizons)+3)).date(),
    )
    schedule = build_event_schedule(events, bars, config.horizons)
    output.mkdir(parents=True, exist_ok=False)
    schedule.to_parquet(output / "selected_events.parquet", index=False)
    checkpoint = output / "event_results.jsonl"
    rows: list[dict[str, Any]] = []
    with checkpoint.open("w", encoding="utf-8") as stream:
        for index, event in enumerate(schedule.to_dict(orient="records"), start=1):
            LOGGER.info("E6-B1 event %d/%d %s %s", index, len(schedule), event["date"], event["symbol"])
            result = evaluate_event(client, event, config)
            rows.append(result)
            stream.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
            stream.flush()
    frame = pd.DataFrame(rows)
    frame.to_parquet(output / "event_results.parquet", index=False)
    metrics = summarize(frame, config)
    report = {
        "schema_version": 1, "experiment": "E6_B1_oracle_options_rest_pilot_v1",
        "generated_at": datetime.now(UTC).isoformat(), "research_only": True,
        "source_events": str(events_path), "config": asdict(config),
        "selection": {
            "start_date": start_date, "end_date": end_date,
            "dates_per_semester": dates_per_semester,
            "max_symbols_per_date": max_symbols_per_date,
            "dates": int(schedule["date"].nunique()), "events": int(len(schedule)),
            "symbols": int(schedule["symbol"].nunique()),
        },
        "metrics": metrics,
        "interpretation_allowed": (
            "coverage_only" if max_symbols_per_date
            else "provisional_pilot_economics_no_deployment"
        ),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2025-07-11")
    parser.add_argument("--dates-per-semester", type=int, default=1)
    parser.add_argument("--max-symbols-per-date", type=int, default=None)
    parser.add_argument("--horizons", default="3,5,10,20")
    parser.add_argument("--min-dte", type=int, default=35)
    parser.add_argument("--max-dte", type=int, default=55)
    parser.add_argument("--target-dte", type=int, default=45)
    parser.add_argument("--minimum-exit-buffer-days", type=int, default=5)
    parser.add_argument("--max-pair-quote-skew-seconds", type=int, default=60)
    parser.add_argument("--commission-per-contract-side", type=float, default=0.65)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    key = __import__("os").environ.get("EROYA_API_KEY", "")
    if not key:
        raise SystemExit("EROYA_API_KEY absente.")
    config = OptionsPilotConfig(
        horizons=tuple(int(value) for value in args.horizons.split(",")),
        min_dte=args.min_dte, max_dte=args.max_dte, target_dte=args.target_dte,
        minimum_exit_buffer_days=args.minimum_exit_buffer_days,
        max_pair_quote_skew_seconds=args.max_pair_quote_skew_seconds,
        commission_per_contract_side=args.commission_per_contract_side,
    )
    report = run_pilot(
        EroyaClient(key), args.events_path, args.output,
        dates_per_semester=args.dates_per_semester,
        max_symbols_per_date=args.max_symbols_per_date,
        start_date=args.start_date, end_date=args.end_date, config=config,
    )
    print(f"E6-B1 terminé: {args.output}")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
