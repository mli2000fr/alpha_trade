"""E7 research-only: features directionnelles d'options dans Oracle TOP20 OOF."""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle_amplitude_audit import GROUP_COL, TOP20
from modelFactory.shared_directional import _semester_label

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")
PRIMARY_FEATURES = (
    "otm_price_risk_reversal",
    "atm_call_put_mid_log_ratio",
    "wing_skew_asymmetry",
    "otm_quote_depth_imbalance",
    "atm_quote_depth_imbalance",
    "call_put_volume_log_ratio",
)
DIAGNOSTIC_IV_FEATURES = ("approx_iv_risk_reversal", "approx_downside_skew_long")


@dataclass(frozen=True, slots=True)
class OptionsDirectionalConfig:
    min_dte: int = 35
    target_dte: int = 45
    max_dte: int = 55
    wing_pct: float = 0.05
    max_wing_target_error_pct: float = 0.03
    strike_band_pct: float = 0.15
    quote_start: str = "15:30"
    quote_end: str = "15:55"
    max_chain_quote_skew_seconds: int = 300
    dates_per_semester: int = 1
    selection_fraction: float = 0.20

    def __post_init__(self) -> None:
        if not 0 < self.min_dte <= self.target_dte <= self.max_dte:
            raise ValueError("Fenêtre DTE incohérente.")
        if not 0 < self.wing_pct < self.strike_band_pct < 1:
            raise ValueError("Moneyness aile/bande incohérente.")
        if not 0 < self.selection_fraction < 0.5:
            raise ValueError("selection_fraction doit être dans ]0,0.5[.")


def select_events(
    source: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    dates_per_semester: int,
    max_symbols_per_date: int | None = None,
) -> pd.DataFrame:
    required = {"date", "symbol", GROUP_COL, "directional_oracle_extreme_pct"}
    missing = sorted(required.difference(source.columns))
    if missing:
        raise ValueError(f"Événements Oracle incomplets: {missing}")
    frame = source.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame = frame[
        frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & frame[GROUP_COL].eq(TOP20)
    ].copy()
    frame["semester"] = frame["date"].map(_semester_label)
    selected_dates: list[pd.Timestamp] = []
    for _, group in frame.groupby("semester", sort=True):
        dates = np.array(sorted(group["date"].unique()))
        count = min(dates_per_semester, len(dates))
        indexes = np.linspace(0, len(dates) - 1, count + 2)[1:-1]
        selected_dates.extend(pd.Timestamp(dates[int(round(value))]) for value in indexes)
    selected = frame[frame["date"].isin(selected_dates)].sort_values(
        ["date", "directional_oracle_extreme_pct", "symbol"],
        ascending=[True, False, True],
    )
    if max_symbols_per_date is not None:
        selected = selected.groupby("date", sort=True, group_keys=False).head(max_symbols_per_date)
    return selected.reset_index(drop=True)


def attach_signal_close(events: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    price = bars[["date", "symbol", "close"]].copy()
    price["date"] = pd.to_datetime(price["date"], errors="coerce").dt.normalize()
    price["symbol"] = price["symbol"].astype(str).str.upper().str.strip()
    price["signal_close"] = pd.to_numeric(price["close"], errors="coerce")
    price = price.drop(columns="close").drop_duplicates(["date", "symbol"], keep="last")
    merged = events.merge(price, on=["date", "symbol"], how="left", validate="one_to_one")
    return merged[merged["signal_close"].gt(0)].reset_index(drop=True)


def choose_surface_contracts(
    contracts: list[dict[str, Any]],
    *,
    spot: float,
    signal_date: date,
    config: OptionsDirectionalConfig,
) -> dict[str, Any] | None:
    by_expiry: dict[date, dict[str, list[tuple[float, str]]]] = {}
    for item in contracts:
        try:
            expiry = date.fromisoformat(str(item["expiration_date"]))
            strike = float(item["strike_price"])
            side = str(item["contract_type"]).lower()
            ticker = str(item["ticker"])
        except (KeyError, TypeError, ValueError):
            continue
        dte = (expiry - signal_date).days
        if side not in {"call", "put"} or not config.min_dte <= dte <= config.max_dte:
            continue
        by_expiry.setdefault(expiry, {"call": [], "put": []})[side].append((strike, ticker))
    for expiry in sorted(by_expiry, key=lambda value: (abs((value-signal_date).days-config.target_dte), value)):
        sides = by_expiry[expiry]
        calls = dict(sides["call"])
        puts = dict(sides["put"])
        paired = sorted(set(calls).intersection(puts))
        upper = [(strike, ticker) for strike, ticker in sides["call"] if strike > spot]
        lower = [(strike, ticker) for strike, ticker in sides["put"] if strike < spot]
        if not paired or not upper or not lower:
            continue
        atm = min(paired, key=lambda strike: abs(strike / spot - 1.0))
        call_wing = min(upper, key=lambda value: abs(value[0] / spot - (1 + config.wing_pct)))
        put_wing = min(lower, key=lambda value: abs(value[0] / spot - (1 - config.wing_pct)))
        call_error = abs(call_wing[0] / spot - (1 + config.wing_pct))
        put_error = abs(put_wing[0] / spot - (1 - config.wing_pct))
        if max(call_error, put_error) > config.max_wing_target_error_pct:
            continue
        return {
            "expiration_date": expiry.isoformat(),
            "dte": (expiry-signal_date).days,
            "atm_strike": atm,
            "atm_call_ticker": calls[atm],
            "atm_put_ticker": puts[atm],
            "otm_call_strike": call_wing[0],
            "otm_call_ticker": call_wing[1],
            "otm_put_strike": put_wing[0],
            "otm_put_ticker": put_wing[1],
        }
    return None


def _results(response: Any) -> list[dict[str, Any]]:
    if not response.ok:
        return []
    payload = response.json()
    result = payload.get("results") if isinstance(payload, dict) else None
    return result if isinstance(result, list) else []


def fetch_surface_contracts(
    client: EroyaClient,
    symbol: str,
    signal_date: date,
    spot: float,
    config: OptionsDirectionalConfig,
) -> dict[str, Any] | None:
    response = client.get("reference/options/contracts", params={
        "underlying_ticker": symbol,
        "as_of": signal_date.isoformat(),
        "expiration_date.gte": (
            pd.Timestamp(signal_date) + pd.Timedelta(days=config.min_dte)
        ).date().isoformat(),
        "expiration_date.lte": (
            pd.Timestamp(signal_date) + pd.Timedelta(days=config.max_dte)
        ).date().isoformat(),
        "strike_price.gte": round(spot * (1-config.strike_band_pct), 4),
        "strike_price.lte": round(spot * (1+config.strike_band_pct), 4),
        "limit": 1000, "sort": "ticker", "order": "asc",
    })
    return choose_surface_contracts(
        _results(response), spot=spot, signal_date=signal_date, config=config
    )


def _nanoseconds(session_date: date, clock: str) -> int:
    return int(datetime.combine(session_date, time.fromisoformat(clock), tzinfo=NY).timestamp() * 1e9)


def fetch_close_quote(
    client: EroyaClient, ticker: str, session_date: date, config: OptionsDirectionalConfig
) -> dict[str, Any] | None:
    response = client.get(f"quotes/{ticker}", params={
        "timestamp.gte": str(_nanoseconds(session_date, config.quote_start)),
        "timestamp.lte": str(_nanoseconds(session_date, config.quote_end)),
        "sort": "timestamp", "order": "desc", "limit": 1,
    })
    values = _results(response)
    if not values:
        return None
    item = values[0]
    try:
        bid, ask = float(item["bid_price"]), float(item["ask_price"])
        bid_size, ask_size = float(item.get("bid_size") or 0), float(item.get("ask_size") or 0)
        timestamp = int(item["sip_timestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    if bid <= 0 or ask <= 0 or ask < bid or timestamp <= 0:
        return None
    return {
        "bid": bid, "ask": ask, "mid": (bid+ask)/2,
        "bid_size": bid_size, "ask_size": ask_size, "timestamp": timestamp,
        "relative_spread": (ask-bid) / ((ask+bid)/2),
    }


def fetch_daily_volume(client: EroyaClient, ticker: str, session_date: date) -> float | None:
    day = session_date.isoformat()
    response = client.get(f"aggs/ticker/{ticker}/range/1/day/{day}/{day}", params={
        "adjusted": "true", "sort": "asc", "limit": 10,
    })
    values = _results(response)
    if not values:
        return None
    value = pd.to_numeric(pd.Series([values[-1].get("volume")]), errors="coerce").iloc[0]
    return float(value) if np.isfinite(value) and value >= 0 else None


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _black_price(forward: float, strike: float, years: float, sigma: float, side: str) -> float:
    scale = sigma * math.sqrt(years)
    if scale <= 0:
        return max(forward-strike, 0.0) if side == "call" else max(strike-forward, 0.0)
    d1 = (math.log(forward/strike) + 0.5*sigma*sigma*years) / scale
    d2 = d1 - scale
    if side == "call":
        return forward*_normal_cdf(d1) - strike*_normal_cdf(d2)
    return strike*_normal_cdf(-d2) - forward*_normal_cdf(-d1)


def implied_volatility(
    price: float, *, forward: float, strike: float, years: float, side: str
) -> float | None:
    intrinsic = max(forward-strike, 0.0) if side == "call" else max(strike-forward, 0.0)
    if not all(np.isfinite([price, forward, strike, years])) or price <= intrinsic or min(forward, strike, years) <= 0:
        return None
    low, high = 0.001, 5.0
    if _black_price(forward, strike, years, high, side) < price:
        return None
    for _ in range(80):
        middle = (low+high)/2
        if _black_price(forward, strike, years, middle, side) < price:
            low = middle
        else:
            high = middle
    return (low+high)/2


def compute_features(
    *,
    spot: float,
    surface: dict[str, Any],
    quotes: dict[str, dict[str, Any]],
    volumes: dict[str, float | None],
) -> dict[str, Any]:
    ac, ap, oc, op = (quotes[name] for name in ("atm_call", "atm_put", "otm_call", "otm_put"))
    volume_complete = all(
        volumes.get(name) is not None
        for name in ("atm_call", "otm_call", "atm_put", "otm_put")
    )
    call_volume = (
        sum(float(volumes[name]) for name in ("atm_call", "otm_call"))
        if volume_complete else None
    )
    put_volume = (
        sum(float(volumes[name]) for name in ("atm_put", "otm_put"))
        if volume_complete else None
    )
    call_depth = oc["bid_size"] + oc["ask_size"]
    put_depth = op["bid_size"] + op["ask_size"]
    atm_call_depth = ac["bid_size"] + ac["ask_size"]
    atm_put_depth = ap["bid_size"] + ap["ask_size"]
    forward = float(surface["atm_strike"]) + ac["mid"] - ap["mid"]
    years = float(surface["dte"]) / 365.0
    atm_call_iv = implied_volatility(ac["mid"], forward=forward, strike=float(surface["atm_strike"]), years=years, side="call")
    atm_put_iv = implied_volatility(ap["mid"], forward=forward, strike=float(surface["atm_strike"]), years=years, side="put")
    call_iv = implied_volatility(oc["mid"], forward=forward, strike=float(surface["otm_call_strike"]), years=years, side="call")
    put_iv = implied_volatility(op["mid"], forward=forward, strike=float(surface["otm_put_strike"]), years=years, side="put")
    atm_ivs = [value for value in (atm_call_iv, atm_put_iv) if value is not None]
    atm_iv = float(np.mean(atm_ivs)) if atm_ivs else None
    return {
        "otm_price_risk_reversal": math.log(oc["mid"] / op["mid"]),
        "atm_call_put_mid_log_ratio": math.log(ac["mid"] / ap["mid"]),
        "wing_skew_asymmetry": math.log(oc["mid"] / ac["mid"]) - math.log(op["mid"] / ap["mid"]),
        "otm_quote_depth_imbalance": math.log((call_depth+1)/(put_depth+1)),
        "atm_quote_depth_imbalance": math.log((atm_call_depth+1)/(atm_put_depth+1)),
        "call_put_volume_log_ratio": (
            math.log((call_volume+1)/(put_volume+1))
            if call_volume is not None and put_volume is not None else None
        ),
        "approx_iv_risk_reversal": call_iv-put_iv if call_iv is not None and put_iv is not None else None,
        "approx_downside_skew_long": atm_iv-put_iv if atm_iv is not None and put_iv is not None else None,
        "approx_atm_iv": atm_iv,
        "inferred_forward": forward,
        "inferred_forward_distance_pct": forward/spot-1,
        "call_volume": call_volume,
        "put_volume": put_volume,
        **{f"{name}_relative_spread": value["relative_spread"] for name, value in quotes.items()},
    }


def evaluate_event(
    client: EroyaClient, event: dict[str, Any], config: OptionsDirectionalConfig
) -> dict[str, Any]:
    result = dict(event)
    result["status"] = "rejected_no_surface"
    signal_date = pd.Timestamp(event["date"]).date()
    spot = float(event["signal_close"])
    surface = fetch_surface_contracts(client, str(event["symbol"]), signal_date, spot, config)
    if surface is None:
        return result
    result.update(surface)
    tickers = {
        "atm_call": surface["atm_call_ticker"], "atm_put": surface["atm_put_ticker"],
        "otm_call": surface["otm_call_ticker"], "otm_put": surface["otm_put_ticker"],
    }
    quotes = {name: fetch_close_quote(client, ticker, signal_date, config) for name, ticker in tickers.items()}
    if any(value is None for value in quotes.values()):
        result["status"] = "rejected_incomplete_nbbo"
        return result
    complete_quotes = {name: value for name, value in quotes.items() if value is not None}
    timestamps = [value["timestamp"] for value in complete_quotes.values()]
    skew_seconds = (max(timestamps)-min(timestamps))/1e9
    result["chain_quote_skew_seconds"] = skew_seconds
    if skew_seconds > config.max_chain_quote_skew_seconds:
        result["status"] = "rejected_stale_chain"
        return result
    volumes = {name: fetch_daily_volume(client, ticker, signal_date) for name, ticker in tickers.items()}
    result.update(compute_features(spot=spot, surface=surface, quotes=complete_quotes, volumes=volumes))
    result["volume_legs_available"] = sum(value is not None for value in volumes.values())
    result["status"] = "complete"
    return result


def _safe_daily_ic(frame: pd.DataFrame, feature: str, target: str) -> pd.Series:
    def correlation(group: pd.DataFrame) -> float:
        valid = group[[feature, target]].dropna()
        if len(valid) < 10 or valid[feature].nunique() < 2 or valid[target].nunique() < 2:
            return np.nan
        return float(valid[feature].corr(valid[target], method="spearman"))
    return frame.groupby("date").apply(correlation, include_groups=False).dropna()


def evaluate_feature(frame: pd.DataFrame, feature: str, target: str, fraction: float) -> dict[str, Any]:
    valid = frame.dropna(subset=[feature, target]).copy()
    valid["feature_rank"] = valid.groupby("date")[feature].rank(method="average", pct=True)
    valid["target_decile"] = valid.groupby("date")[target].rank(method="first", pct=True).mul(10).apply(np.ceil).clip(1, 10)
    tails = valid[valid["target_decile"].isin([1, 10])]
    auc = roc_auc(tails["target_decile"].eq(10).astype(float).to_numpy(), tails[feature].to_numpy())
    daily_ic = _safe_daily_ic(valid, feature, target)
    high = valid[valid["feature_rank"].gt(1-fraction)]
    low = valid[valid["feature_rank"].le(fraction)]
    pool_mean = float(valid[target].mean())
    year_ics = {
        str(year): float(values.mean())
        for year, group in valid.groupby(valid["date"].dt.year)
        if len(values := _safe_daily_ic(group, feature, target))
    }
    long_lift = float(high[target].mean()-pool_mean)
    short_lift = float(-low[target].mean()+pool_mean)
    coverage = float(len(valid)/len(frame)) if len(frame) else 0.0
    gates = {
        "coverage_gte_0_40": coverage >= 0.40,
        "daily_ic_gte_0_03": float(daily_ic.mean()) >= 0.03 if len(daily_ic) else False,
        "auc_d10_d1_gte_0_53": auc is not None and auc >= 0.53,
        "positive_ic_years_gte_3": sum(value > 0 for value in year_ics.values()) >= 3,
        "top_bottom_spread_positive": float(high[target].mean()-low[target].mean()) > 0,
        "both_side_lifts_positive": long_lift > 0 and short_lift > 0,
    }
    return {
        "coverage": coverage, "observations": int(len(valid)),
        "mean_daily_ic": float(daily_ic.mean()) if len(daily_ic) else None,
        "auc_d10_vs_d1": auc,
        "long_mean_return": float(high[target].mean()),
        "short_signed_return": float(-low[target].mean()),
        "long_lift_vs_pool": long_lift, "short_lift_vs_pool": short_lift,
        "top_bottom_spread": float(high[target].mean()-low[target].mean()),
        "year_ics": year_ics, "gates": gates, "all_gates_passed": all(gates.values()),
    }


def evaluate_features(frame: pd.DataFrame, config: OptionsDirectionalConfig) -> dict[str, Any]:
    frame = frame.copy()
    # Older/interrupted checkpoints can contain the former neutral-zero fallback.
    # A four-leg put/call ratio is not observable unless all four volumes exist.
    if "volume_legs_available" in frame and "call_put_volume_log_ratio" in frame:
        frame.loc[
            frame["volume_legs_available"].fillna(0).lt(4),
            "call_put_volume_log_ratio",
        ] = np.nan
    results: dict[str, Any] = {}
    for horizon in (3, 10, 20):
        target = f"h{horizon}_terminal_return"
        results[f"h{horizon}"] = {
            feature: evaluate_feature(frame, feature, target, config.selection_fraction)
            for feature in (*PRIMARY_FEATURES, *DIAGNOSTIC_IV_FEATURES)
            if feature in frame and target in frame
        }
    primary_passes = [
        (horizon, feature) for horizon, values in results.items()
        for feature, metrics in values.items()
        if feature in PRIMARY_FEATURES and metrics["all_gates_passed"]
    ]
    return {"horizons": results, "primary_passes": primary_passes,
            "verdict": "GO_RESEARCH" if primary_passes else "NO_GO"}


def run(
    client_factory: Any,
    events_path: Path,
    output: Path,
    *,
    start_date: str,
    end_date: str,
    max_symbols_per_date: int | None,
    max_workers: int,
    config: OptionsDirectionalConfig,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    selected_path = output / "selected_events.parquet"
    if selected_path.exists():
        selected = pd.read_parquet(selected_path)
    else:
        source = pd.read_parquet(events_path)
        selected = select_events(
            source, start_date=start_date, end_date=end_date,
            dates_per_semester=config.dates_per_semester,
            max_symbols_per_date=max_symbols_per_date,
        )
        bars = load_universe_bars(
            get_sqlalchemy_engine(), sorted(selected["symbol"].unique()),
            start_date=pd.Timestamp(start_date).date(), end_date=pd.Timestamp(end_date).date(),
        )
        selected = attach_signal_close(selected, bars)
        selected.to_parquet(selected_path, index=False)
    checkpoint = output / "event_results.jsonl"
    completed: dict[tuple[str, str], dict[str, Any]] = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[(str(item["date"])[:10], str(item["symbol"]))] = item
    pending = [item for item in selected.to_dict(orient="records")
               if (str(item["date"])[:10], str(item["symbol"])) not in completed]
    local = threading.local()
    def task(item: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(local, "client"):
            local.client = client_factory()
        return evaluate_event(local.client, item, config)
    mode = "a" if checkpoint.exists() else "w"
    with checkpoint.open(mode, encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(task, item): item for item in pending}
        for index, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {**item, "status": "error", "error": f"{type(error).__name__}: {error}"}
            completed[(str(result["date"])[:10], str(result["symbol"]))] = result
            stream.write(json.dumps(result, ensure_ascii=False, default=str)+"\n")
            stream.flush()
            if index % 10 == 0 or index == len(pending):
                LOGGER.info("E7 options %d/%d nouveaux; total=%d/%d", index, len(pending), len(completed), len(selected))
    frame = pd.DataFrame(completed.values())
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame.to_parquet(output / "option_features.parquet", index=False)
    statuses = frame["status"].value_counts(dropna=False).to_dict()
    report = {
        "schema_version": 1, "experiment": "E7_OPTIONS_DIRECTIONAL_POC_V1",
        "generated_at": datetime.now(UTC).isoformat(), "research_only": True,
        "source_events": str(events_path), "config": asdict(config),
        "selection": {"events": int(len(selected)), "dates": int(selected["date"].nunique()),
                      "symbols": int(selected["symbol"].nunique()), "start_date": start_date, "end_date": end_date},
        "statuses": statuses,
        "complete_rate": float(frame["status"].eq("complete").mean()),
    }
    (output / "collection_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    evaluation = evaluate_features(frame[frame["status"].eq("complete")].copy(), config)
    evaluation_report = {**report, "evaluation": evaluation}
    (output / "evaluation_report.json").write_text(
        json.dumps(evaluation_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return evaluation_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2025-07-11")
    parser.add_argument("--dates-per-semester", type=int, default=1)
    parser.add_argument("--max-symbols-per-date", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--min-dte", type=int, default=35)
    parser.add_argument("--target-dte", type=int, default=45)
    parser.add_argument("--max-dte", type=int, default=55)
    parser.add_argument("--wing-pct", type=float, default=0.05)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    key = os.environ.get("EROYA_API_KEY", "")
    if not key:
        raise SystemExit("EROYA_API_KEY absente.")
    config = OptionsDirectionalConfig(
        min_dte=args.min_dte, target_dte=args.target_dte, max_dte=args.max_dte,
        wing_pct=args.wing_pct, dates_per_semester=args.dates_per_semester,
    )
    report = run(
        lambda: EroyaClient(key), args.events_path, args.output,
        start_date=args.start_date, end_date=args.end_date,
        max_symbols_per_date=args.max_symbols_per_date,
        max_workers=args.max_workers, config=config,
    )
    print(json.dumps({"output": str(args.output), "complete_rate": report["complete_rate"],
                      "verdict": report["evaluation"]["verdict"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
