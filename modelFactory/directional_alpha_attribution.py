"""E18-A: locked beta, sector and regime attribution of E17 residual momentum."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.directional_alpha_book_robustness import select_offset_dates

LOGGER = logging.getLogger(__name__)
DEFAULT_PROTOCOL = Path("config/research/e18a_residual_momentum_attribution.json")
LOCKED_PROTOCOL_SHA256 = "36d2d2c7e3d07ed8885c9622c7415d2a4abd81de5ad07cff317f5bfa76651b1a"


def load_locked_protocol(path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(
        protocol, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != LOCKED_PROTOCOL_SHA256:
        raise ValueError(
            "Le protocole E18-A a changé après verrouillage : "
            f"sha256={digest}, attendu={LOCKED_PROTOCOL_SHA256}."
        )
    if protocol.get("oracle_used") is not False:
        raise ValueError("E18-A doit rester indépendant de l’Oracle.")
    return protocol


def build_ex_ante_context(
    bars: pd.DataFrame, benchmark: pd.DataFrame, protocol: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute beta and market regimes using observations available at close J."""
    frame = bars.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    raw_close = pd.to_numeric(frame["close"], errors="coerce")
    frame["adjusted_close"] = pd.to_numeric(
        frame.get("adj_close", raw_close), errors="coerce"
    ).fillna(raw_close)
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(
        ["symbol", "date"], keep="last"
    )
    frame["asset_return"] = frame.groupby("symbol")["adjusted_close"].pct_change(
        fill_method=None
    )

    market = benchmark.copy()
    market["date"] = pd.to_datetime(market["date"], errors="coerce").dt.normalize()
    market_raw = pd.to_numeric(market["close"], errors="coerce")
    market["spy_close"] = pd.to_numeric(
        market.get("adj_close", market_raw), errors="coerce"
    ).fillna(market_raw)
    market = market.sort_values("date").drop_duplicates("date", keep="last")
    market["market_return"] = market["spy_close"].pct_change(fill_method=None)
    market["spy_sma200"] = market["spy_close"].rolling(200, min_periods=200).mean()
    market["spy_rv20"] = market["market_return"].rolling(20, min_periods=20).std()
    market["spy_rv252"] = market["market_return"].rolling(252, min_periods=252).std()
    market["trend_state"] = np.where(
        market["spy_close"].ge(market["spy_sma200"]), "bull", "bear"
    )
    market["volatility_state"] = np.where(
        market["spy_rv20"].gt(market["spy_rv252"]), "stressed", "calm"
    )
    context_valid = market[["spy_sma200", "spy_rv20", "spy_rv252"]].notna().all(axis=1)
    market["market_regime"] = (
        market["trend_state"] + "_" + market["volatility_state"]
    ).where(context_valid)

    frame = frame.merge(
        market[["date", "market_return"]], on="date", how="left", validate="many_to_one"
    )
    lookback = int(protocol["beta"]["lookback_sessions"])
    minimum = int(protocol["beta"]["minimum_sessions"])

    def rolling_beta(group: pd.DataFrame) -> pd.Series:
        covariance = group["asset_return"].rolling(lookback, min_periods=minimum).cov(
            group["market_return"]
        )
        variance = group["market_return"].rolling(lookback, min_periods=minimum).var()
        low, high = map(float, protocol["beta"]["individual_beta_clip"])
        return (covariance / variance.replace(0.0, np.nan)).clip(low, high)

    frame["beta_ex_ante"] = frame.groupby("symbol", group_keys=False).apply(
        rolling_beta, include_groups=False
    ).reset_index(level=0, drop=True).sort_index()
    return (
        frame[["date", "symbol", "beta_ex_ante"]],
        market[[
            "date", "spy_close", "spy_sma200", "spy_rv20", "spy_rv252",
            "market_regime",
        ]],
    )


def _sector_neutral_leg(
    group: pd.DataFrame, protocol: dict[str, Any],
) -> tuple[float, float, float, int] | None:
    sector_config = protocol["sector_neutral"]
    score = protocol["score_column"]
    minimum = int(sector_config["minimum_sector_members"])
    usable = group[group["sector"].notna() & group["sector"].ne("UNKNOWN")].copy()
    counts = usable.groupby("sector")["symbol"].transform("nunique")
    usable = usable[counts.ge(minimum)]
    if usable.empty:
        return None
    total = len(usable)
    selected_return = 0.0
    selected_beta = 0.0
    universe_return = 0.0
    selected_count = 0
    for _, sector in usable.groupby("sector", sort=True):
        weight = len(sector) / total
        count = max(1, math.floor(len(sector) * float(protocol["portfolio"]["tail_pct"])))
        selected = sector.sort_values([score, "symbol"]).tail(count)
        selected_return += weight * float(selected["future_return_h120"].mean())
        selected_beta += weight * float(selected["beta_ex_ante"].mean())
        universe_return += weight * float(sector["future_return_h120"].mean())
        selected_count += len(selected)
    return selected_return, selected_beta, universe_return, selected_count


def build_attribution_cohorts(
    frame: pd.DataFrame, protocol: dict[str, Any],
) -> pd.DataFrame:
    score = protocol["score_column"]
    required = {
        "date", "symbol", "sector", "market_eligible", score,
        "future_return_h120", "future_excess_h120", "beta_ex_ante", "market_regime",
    }
    if missing := required - set(frame.columns):
        raise ValueError(f"Panel E18-A incomplet : {sorted(missing)}")
    scope = frame[
        frame["market_eligible"]
        & frame[score].notna()
        & frame["future_return_h120"].notna()
        & frame["future_excess_h120"].notna()
        & frame["beta_ex_ante"].notna()
        & frame["market_regime"].notna()
    ].copy()
    portfolio = protocol["portfolio"]
    dates = select_offset_dates(
        scope["date"], rebalance_sessions=int(portfolio["rebalance_sessions"]),
        offset=int(portfolio["calendar_offset"]),
    )
    long_cost = float(portfolio["long_round_trip_cost_bps"]) / 10_000.0
    hedge_cost = float(portfolio["spy_hedge_round_trip_cost_bps"]) / 10_000.0
    rows: list[dict[str, Any]] = []
    for cohort_date, group in scope[scope["date"].isin(dates)].groupby("date", sort=True):
        ordered = group.sort_values([score, "symbol"])
        count = max(
            int(portfolio["minimum_selected_symbols"]),
            math.floor(len(ordered) * float(portfolio["tail_pct"])),
        )
        if len(ordered) < count:
            continue
        selected = ordered.tail(count)
        spy_return = float(
            (ordered["future_return_h120"] - ordered["future_excess_h120"]).median()
        )
        raw_gross = float(selected["future_return_h120"].mean())
        universe_gross = float(ordered["future_return_h120"].mean())
        beta = float(selected["beta_ex_ante"].mean())
        sector_leg = _sector_neutral_leg(ordered, protocol)
        if sector_leg is None:
            continue
        sector_gross, sector_beta, sector_universe_gross, sector_count = sector_leg
        rows.append({
            "date": pd.Timestamp(cohort_date),
            "market_regime": str(ordered["market_regime"].iloc[0]),
            "universe": int(len(ordered)),
            "selected_symbols": int(len(selected)),
            "raw_portfolio_beta": beta,
            "sector_neutral_beta": sector_beta,
            "raw_long_net": raw_gross - long_cost,
            "raw_excess_vs_universe": raw_gross - universe_gross,
            "raw_excess_vs_spy": raw_gross - spy_return,
            "beta_hedged_net": (
                raw_gross - beta * spy_return - long_cost - abs(beta) * hedge_cost
            ),
            "sector_neutral_long_net": sector_gross - long_cost,
            "sector_neutral_excess_vs_universe": (
                sector_gross - sector_universe_gross
            ),
            "combined_beta_sector_net": (
                sector_gross - sector_beta * spy_return
                - long_cost - abs(sector_beta) * hedge_cost
            ),
            "market_component": beta * spy_return,
            "raw_specific_component": raw_gross - beta * spy_return,
            "sector_selected_symbols": int(sector_count),
        })
    return pd.DataFrame(rows)


def _bootstrap_ci(
    values: pd.Series, protocol: dict[str, Any], *, seed_offset: int = 0,
) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    boot = protocol["bootstrap"]
    block = int(boot["block_cohorts"])
    if len(clean) < max(10, 2 * block):
        return float("nan"), float("nan")
    block = min(block, len(clean))
    blocks = math.ceil(len(clean) / block)
    rng = np.random.default_rng(int(boot["seed"]) + seed_offset)
    means = np.empty(int(boot["samples"]), dtype=float)
    for index in range(len(means)):
        starts = rng.integers(0, len(clean) - block + 1, size=blocks)
        sample = np.concatenate([clean[start : start + block] for start in starts])[: len(clean)]
        means[index] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarize(cohorts: pd.DataFrame, protocol: dict[str, Any], *, seed: int = 0) -> dict[str, Any]:
    if cohorts.empty:
        return {"cohorts": 0}
    columns = (
        "raw_long_net", "raw_excess_vs_universe", "raw_excess_vs_spy",
        "beta_hedged_net", "sector_neutral_long_net",
        "sector_neutral_excess_vs_universe", "combined_beta_sector_net",
        "raw_portfolio_beta", "sector_neutral_beta", "market_component",
        "raw_specific_component",
    )
    result: dict[str, Any] = {"cohorts": int(len(cohorts))}
    for index, column in enumerate(columns):
        result[f"mean_{column}"] = float(cohorts[column].mean())
        if column in {
            "raw_excess_vs_universe", "raw_excess_vs_spy", "beta_hedged_net",
            "sector_neutral_excess_vs_universe", "combined_beta_sector_net",
        }:
            result[f"ci95_{column}"] = list(
                _bootstrap_ci(cohorts[column], protocol, seed_offset=seed + index)
            )
    return result


def classify_attribution(
    cohorts: pd.DataFrame, protocol: dict[str, Any],
) -> dict[str, Any]:
    overall = summarize(cohorts, protocol)
    blocks: dict[str, Any] = {}
    for name, (start, end) in protocol["time_blocks"].items():
        part = cohorts[cohorts["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
        blocks[name] = summarize(part, protocol, seed=20)

    regime_config = protocol["regimes"]
    regimes: dict[str, Any] = {}
    repeated_regimes: list[str] = []
    for regime in regime_config["states"]:
        part = cohorts[cohorts["market_regime"].eq(regime)]
        item = summarize(part, protocol, seed=40)
        positive_blocks = 0
        block_details: dict[str, Any] = {}
        for name, (start, end) in protocol["time_blocks"].items():
            block = part[part["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
            block_summary = summarize(block, protocol, seed=60)
            block_details[name] = block_summary
            if (
                block_summary.get("cohorts", 0)
                >= int(regime_config["minimum_cohorts_per_time_block"])
                and block_summary.get("mean_combined_beta_sector_net", -np.inf) > 0
            ):
                positive_blocks += 1
        item["time_blocks"] = block_details
        item["positive_time_blocks"] = positive_blocks
        repeated = (
            item.get("cohorts", 0) >= int(regime_config["minimum_total_cohorts"])
            and item.get("mean_combined_beta_sector_net", -np.inf) > 0
            and item.get("ci95_combined_beta_sector_net", [-np.inf])[0] > 0
            and positive_blocks >= int(regime_config["minimum_positive_time_blocks"])
        )
        item["repeated_regime_candidate"] = repeated
        if repeated:
            repeated_regimes.append(regime)
        regimes[regime] = item

    sector_ci = overall.get("ci95_sector_neutral_excess_vs_universe", [-np.inf])
    combined_ci = overall.get("ci95_combined_beta_sector_net", [-np.inf])
    raw_ci = overall.get("ci95_raw_excess_vs_universe", [-np.inf])
    all_blocks_positive = all(
        item.get("mean_combined_beta_sector_net", -np.inf) > 0
        for item in blocks.values()
    )
    structural = sector_ci[0] > 0 and combined_ci[0] > 0 and all_blocks_positive
    if structural:
        verdict = "STRUCTURAL_SELECTION_CANDIDATE"
    elif repeated_regimes:
        verdict = "REGIME_DEPENDENT_CANDIDATE"
    elif raw_ci[0] > 0 and combined_ci[0] <= 0:
        verdict = "MARKET_OR_SECTOR_EXPOSURE"
    else:
        verdict = "NO_STABLE_ALPHA"
    return {
        "verdict": verdict,
        "overall": overall,
        "time_blocks": blocks,
        "all_time_blocks_combined_positive": all_blocks_positive,
        "regimes": regimes,
        "repeated_regime_candidates": repeated_regimes,
        "classification_evidence": {
            "sector_neutral_excess_ci95_low": sector_ci[0],
            "combined_beta_sector_ci95_low": combined_ci[0],
            "raw_excess_universe_ci95_low": raw_ci[0],
        },
    }


def run(*, protocol_path: Path, output_root: Path) -> Path:
    protocol = load_locked_protocol(protocol_path)
    panel_columns = [
        "date", "symbol", "sector", "market_eligible", protocol["score_column"],
        "future_return_h120", "future_excess_h120",
    ]
    panel = pd.read_parquet(Path(protocol["source_artifact"]), columns=panel_columns)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    start, end = map(pd.Timestamp, protocol["period"])
    panel = panel[panel["date"].between(start, end)].copy()

    symbols = sorted(set(load_universe_file_symbols(protocol["symbol_source"])))
    history_start = start - pd.offsets.BDay(300)
    engine = get_sqlalchemy_engine()
    bars = load_universe_bars(
        engine, symbols, start_date=history_start.date(), end_date=end.date()
    )
    benchmark = load_universe_bars(
        engine, ["SPY"], start_date=history_start.date(), end_date=end.date()
    )
    beta, market = build_ex_ante_context(bars, benchmark, protocol)
    panel = panel.merge(beta, on=["date", "symbol"], how="left", validate="one_to_one")
    panel = panel.merge(market, on="date", how="left", validate="many_to_one")
    cohorts = build_attribution_cohorts(panel, protocol)
    result = classify_attribution(cohorts, protocol)

    run_id = f"e18a-attribution-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    cohorts.to_csv(output / "attribution_cohorts.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E18A_RESIDUAL_MOMENTUM_H120_ATTRIBUTION",
        "status": "complete",
        "research_only": True,
        "validation_class": protocol["validation_class"],
        "oracle_used": False,
        "registration_id": protocol["registration_id"],
        "registered_at": protocol["registered_at"],
        "protocol_sha256": LOCKED_PROTOCOL_SHA256,
        "population": {
            "panel_rows": int(len(panel)),
            "symbols": int(panel["symbol"].nunique()),
            "dates": int(panel["date"].nunique()),
            "cohorts": int(len(cohorts)),
        },
        "result": result,
        "oos_claim_authorized": False,
        "promotion_authorized": False,
        "regime_filter_activation_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E18-A terminé: %s verdict=%s", output, result["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/directional_alpha_attribution"),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(protocol_path=args.protocol, output_root=args.output_root)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E18-A terminé: {output}")
    print(report["result"]["verdict"])


if __name__ == "__main__":
    main()
