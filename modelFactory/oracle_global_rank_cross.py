"""E11: croisement OOF Oracle Extreme H20 x Global Ranking H20.

Cette experience est volontairement research-only. Elle refuse la table
``global_rank_history`` car celle-ci melange des rangs Walk-Forward et des
predictions de pre-remplissage sans colonne de provenance.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.oracle_post_signal_confirmation import prepare_price_panel

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E11Config:
    horizon: int = 20
    oracle_top_pct: float = 0.20
    rank_side_pct: float = 0.20
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    minimum_daily_symbols: int = 10
    minimum_join_coverage: float = 0.70
    minimum_events_per_side: int = 500
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260911

    def __post_init__(self) -> None:
        if self.horizon != 20:
            raise ValueError("E11 primaire est gele a H20.")
        if not 0 < self.oracle_top_pct < 0.5:
            raise ValueError("oracle_top_pct invalide.")
        if not 0 < self.rank_side_pct < 0.5:
            raise ValueError("rank_side_pct invalide.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0

    def bootstrap_config(self) -> RollingConfig:
        return RollingConfig(
            top_pct=self.oracle_top_pct,
            commission_bps=self.commission_bps,
            slippage_bps=self.slippage_bps,
            bootstrap_samples=self.bootstrap_samples,
            bootstrap_block_sessions=self.bootstrap_block_sessions,
            bootstrap_seed=self.bootstrap_seed,
        )


def load_oof_inputs(
    oracle_gate_path: Path, global_rank_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Charge uniquement les deux artefacts OOF, jamais les tables de serving."""
    if oracle_gate_path.name != "_oracle_oof_gate.parquet":
        raise ValueError("E11 exige l'artefact _oracle_oof_gate.parquet.")
    if global_rank_path.name != "global_rank_cache.parquet":
        raise ValueError("E11 exige l'artefact OOF global_rank_cache.parquet.")
    if not oracle_gate_path.is_file() or not global_rank_path.is_file():
        raise ValueError("Un artefact OOF E11 est absent.")
    oracle = pd.read_parquet(oracle_gate_path)
    ranking = pd.read_parquet(global_rank_path)
    return oracle, ranking


def build_cross_events(
    oracle: pd.DataFrame,
    ranking: pd.DataFrame,
    bars: pd.DataFrame,
    config: E11Config,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    oracle_required = {
        "date", "symbol", "directional_oracle_fold_start",
        "directional_oracle_proba_extreme", "directional_oracle_eligible",
        "directional_oracle_oof_available",
    }
    rank_col = f"global_rank_{config.horizon}"
    rank_required = {"date", "symbol", rank_col}
    if missing := oracle_required - set(oracle.columns):
        raise ValueError(f"Artefact Oracle incomplet: {sorted(missing)}")
    if missing := rank_required - set(ranking.columns):
        raise ValueError(f"Artefact Global Ranking incomplet: {sorted(missing)}")

    left = oracle.copy()
    right = ranking.copy()
    for frame in (left, right):
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    if left.duplicated(["date", "symbol"]).any():
        raise ValueError("Doublons (date,symbol) dans l'artefact Oracle.")
    if right.duplicated(["date", "symbol"]).any():
        raise ValueError("Doublons (date,symbol) dans l'artefact Global Ranking.")
    left = left[
        left["directional_oracle_oof_available"].fillna(False)
        & left["directional_oracle_eligible"].fillna(False)
        & left["directional_oracle_fold_start"].notna()
    ].copy()
    left["oracle_fold"] = pd.to_datetime(
        left["directional_oracle_fold_start"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    right[rank_col] = pd.to_numeric(right[rank_col], errors="coerce")
    right = right.dropna(subset=["date", "symbol", rank_col])
    right = right[right[rank_col].between(0.0, 1.0)]

    joined = left.merge(
        right[["date", "symbol", rank_col]],
        on=["date", "symbol"], how="inner", validate="one_to_one",
    )
    coverage = {
        "oracle_top20_events": int(len(left)),
        "joined_events_before_prices": int(len(joined)),
        "join_coverage": float(len(joined) / len(left)) if len(left) else 0.0,
        "oracle_dates": int(left["date"].nunique()),
        "joined_dates_before_prices": int(joined["date"].nunique()),
        "oracle_symbols": int(left["symbol"].nunique()),
        "joined_symbols_before_prices": int(joined["symbol"].nunique()),
    }

    panel = prepare_price_panel(bars, ())
    price_cols = [
        "date", "symbol", "immediate_entry_open", "terminal_exit_open", "terminal_date"
    ]
    joined = joined.merge(
        panel[price_cols], on=["date", "symbol"], how="left", validate="one_to_one"
    ).dropna(subset=["immediate_entry_open", "terminal_exit_open"])
    joined = joined[
        joined["immediate_entry_open"].gt(0) & joined["terminal_exit_open"].gt(0)
    ].copy()
    joined["future_return_h20"] = (
        joined["terminal_exit_open"] / joined["immediate_entry_open"] - 1.0
    )
    joined["oracle_long_net_h20"] = joined["future_return_h20"] - config.round_trip_cost
    joined["rank_in_oracle_pool"] = joined.groupby("date")[rank_col].rank(
        method="average", pct=True
    )
    joined["side"] = "ABSTAIN"
    joined.loc[
        joined["rank_in_oracle_pool"].gt(1.0 - config.rank_side_pct), "side"
    ] = "LONG"
    joined.loc[
        joined["rank_in_oracle_pool"].le(config.rank_side_pct), "side"
    ] = "SHORT"
    joined["directional_net_h20"] = np.where(
        joined["side"].eq("LONG"),
        joined["future_return_h20"] - config.round_trip_cost,
        np.where(
            joined["side"].eq("SHORT"),
            -joined["future_return_h20"] - config.round_trip_cost,
            np.nan,
        ),
    )
    joined["semester"] = (
        joined["date"].dt.year.astype(str)
        + "H"
        + np.where(joined["date"].dt.month.le(6), "1", "2")
    )
    coverage.update({
        "joined_events_with_prices": int(len(joined)),
        "price_coverage_after_join": (
            float(len(joined) / coverage["joined_events_before_prices"])
            if coverage["joined_events_before_prices"] else 0.0
        ),
        "joined_dates_with_prices": int(joined["date"].nunique()),
        "joined_symbols_with_prices": int(joined["symbol"].nunique()),
    })
    return joined.sort_values(["date", "symbol"]).reset_index(drop=True), coverage


def _daily_ic(group: pd.DataFrame, rank_col: str, minimum: int) -> float:
    valid = group[[rank_col, "future_return_h20"]].dropna()
    if len(valid) < minimum or valid[rank_col].nunique() < 2:
        return np.nan
    return float(valid[rank_col].corr(valid["future_return_h20"], method="spearman"))


def _group_metrics(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, group in frame.groupby(group_column, sort=True):
        daily = summarize_daily(group)
        rows.append({
            group_column: name,
            "events": int(len(group)),
            "dates": int(group["date"].nunique()),
            "long_net": float(daily["long_net"].mean()) if len(daily) else np.nan,
            "short_net": float(daily["short_net"].mean()) if len(daily) else np.nan,
            "long_short_net": float(daily["long_short_net"].mean()) if len(daily) else np.nan,
            "long_lift_vs_oracle": float(daily["long_lift_vs_oracle"].mean()) if len(daily) else np.nan,
            "short_lift_vs_oracle": float(daily["short_lift_vs_oracle"].mean()) if len(daily) else np.nan,
            "ic": float(daily["ic"].mean()) if len(daily) else np.nan,
        })
    return pd.DataFrame(rows)


def summarize_daily(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rank_col = "global_rank_20"
    for date, group in events.groupby("date", sort=True):
        long = group[group["side"].eq("LONG")]
        short = group[group["side"].eq("SHORT")]
        oracle_raw = float(group["future_return_h20"].mean())
        long_raw = float(long["future_return_h20"].mean()) if len(long) else np.nan
        short_raw = float(short["future_return_h20"].mean()) if len(short) else np.nan
        cost = float(
            (group["future_return_h20"] - group["oracle_long_net_h20"]).median()
        )
        rows.append({
            "date": date,
            "events": int(len(group)),
            "long_events": int(len(long)),
            "short_events": int(len(short)),
            "oracle_long_net": oracle_raw - cost,
            "long_net": long_raw - cost if np.isfinite(long_raw) else np.nan,
            "short_underlying_return": short_raw,
            "short_net": -short_raw - cost if np.isfinite(short_raw) else np.nan,
            "long_short_spread_raw": long_raw - short_raw,
            "long_short_net": (long_raw - short_raw) / 2.0 - cost,
            "long_lift_vs_oracle": long_raw - oracle_raw,
            "short_lift_vs_oracle": oracle_raw - short_raw,
            "ic": _daily_ic(group, rank_col, 10),
        })
    return pd.DataFrame(rows)


def summarize_experiment(
    events: pd.DataFrame, coverage: dict[str, Any], config: E11Config
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if events.empty:
        raise ValueError("Aucun evenement E11 apres alignement OOF et prix.")
    daily = summarize_daily(events)
    folds = _group_metrics(events, "oracle_fold")
    semesters = _group_metrics(events, "semester")
    bootstrap = config.bootstrap_config()
    metrics: dict[str, Any] = {
        **coverage,
        "events": int(len(events)),
        "dates": int(events["date"].nunique()),
        "symbols": int(events["symbol"].nunique()),
        "long_events": int(events["side"].eq("LONG").sum()),
        "short_events": int(events["side"].eq("SHORT").sum()),
        "daily_ic": float(daily["ic"].mean()),
        "daily_ic_positive_ratio": float(daily["ic"].gt(0).mean()),
    }
    for column in (
        "oracle_long_net", "long_net", "short_net", "long_short_net",
        "long_lift_vs_oracle", "short_lift_vs_oracle",
    ):
        series = daily[column].dropna()
        low, high = block_bootstrap_mean(series, bootstrap)
        metrics[f"daily_{column}"] = float(series.mean()) if len(series) else np.nan
        metrics[f"daily_{column}_ci95_low"] = low
        metrics[f"daily_{column}_ci95_high"] = high
    for name, table in (("fold", folds), ("semester", semesters)):
        metrics[f"positive_{name}_ic_ratio"] = float(table["ic"].gt(0).mean()) if len(table) else 0.0
        metrics[f"positive_{name}_long_lift_ratio"] = (
            float(table["long_lift_vs_oracle"].gt(0).mean()) if len(table) else 0.0
        )
        metrics[f"positive_{name}_short_lift_ratio"] = (
            float(table["short_lift_vs_oracle"].gt(0).mean()) if len(table) else 0.0
        )
    return metrics, daily, folds, semesters


def evaluate(metrics: dict[str, Any], config: E11Config) -> dict[str, Any]:
    common = {
        "join_coverage_ge_70pct": metrics["join_coverage"] >= config.minimum_join_coverage,
        "long_events_ge_minimum": metrics["long_events"] >= config.minimum_events_per_side,
        "short_events_ge_minimum": metrics["short_events"] >= config.minimum_events_per_side,
    }
    ranking = {
        **common,
        "daily_ic_ge_0_02": metrics["daily_ic"] >= 0.02,
        "positive_fold_ic_ge_75pct": metrics["positive_fold_ic_ratio"] >= 0.75,
        "positive_semester_ic_ge_60pct": metrics["positive_semester_ic_ratio"] >= 0.60,
        "long_short_net_positive": metrics["daily_long_short_net"] > 0,
        "long_short_ci95_above_zero": metrics["daily_long_short_net_ci95_low"] > 0,
    }
    long = {
        **common,
        "long_net_positive": metrics["daily_long_net"] > 0,
        "long_lift_ge_25bps": metrics["daily_long_lift_vs_oracle"] >= 0.0025,
        "long_lift_ci95_above_zero": metrics["daily_long_lift_vs_oracle_ci95_low"] > 0,
        "positive_fold_long_lift_ge_75pct": metrics["positive_fold_long_lift_ratio"] >= 0.75,
        "positive_semester_long_lift_ge_60pct": metrics["positive_semester_long_lift_ratio"] >= 0.60,
    }
    short = {
        **common,
        "short_net_positive": metrics["daily_short_net"] > 0,
        "short_lift_ge_25bps": metrics["daily_short_lift_vs_oracle"] >= 0.0025,
        "short_lift_ci95_above_zero": metrics["daily_short_lift_vs_oracle_ci95_low"] > 0,
        "positive_fold_short_lift_ge_75pct": metrics["positive_fold_short_lift_ratio"] >= 0.75,
        "positive_semester_short_lift_ge_60pct": metrics["positive_semester_short_lift_ratio"] >= 0.60,
    }
    verdicts = {
        "ranking": "GO_RESEARCH" if all(ranking.values()) else "NO_GO",
        "long": "GO_RESEARCH" if all(long.values()) else "NO_GO",
        "short": "GO_RESEARCH" if all(short.values()) else "NO_GO",
    }
    return {
        "verdicts": verdicts,
        "gates": {"ranking": ranking, "long": long, "short": short},
        "promotion_authorized": False,
        "next_step": (
            "independent confirmation then lifecycle replay"
            if "GO_RESEARCH" in verdicts.values() else "close E11"
        ),
    }


def run(
    *, oracle_gate_path: Path, global_rank_path: Path, output_root: Path,
    config: E11Config,
) -> Path:
    oracle, ranking = load_oof_inputs(oracle_gate_path, global_rank_path)
    rank_meta = global_rank_path.parent / "_global_ranking_features.json"
    if not rank_meta.is_file():
        raise ValueError("Metadonnees _global_ranking_features.json absentes.")
    metadata = json.loads(rank_meta.read_text(encoding="utf-8"))
    horizons = {int(value) for value in metadata.get("horizons", [])}
    if config.horizon not in horizons:
        raise ValueError("L'artefact Global Ranking n'atteste pas H20.")

    oracle_top = oracle[
        oracle["directional_oracle_oof_available"].fillna(False)
        & oracle["directional_oracle_eligible"].fillna(False)
    ]
    rank_keys = ranking[["date", "symbol"]].copy()
    rank_keys["date"] = pd.to_datetime(rank_keys["date"], errors="coerce").dt.normalize()
    rank_keys["symbol"] = rank_keys["symbol"].astype(str).str.upper()
    oracle_keys = oracle_top[["date", "symbol"]].copy()
    oracle_keys["date"] = pd.to_datetime(oracle_keys["date"], errors="coerce").dt.normalize()
    oracle_keys["symbol"] = oracle_keys["symbol"].astype(str).str.upper()
    overlap = oracle_keys.merge(rank_keys, on=["date", "symbol"], how="inner")
    if overlap.empty:
        raise ValueError("Aucun recouvrement entre les deux artefacts OOF.")
    symbols = sorted(overlap["symbol"].unique())
    start = pd.Timestamp(overlap["date"].min()).date()
    end = (pd.Timestamp(overlap["date"].max()) + pd.offsets.BDay(25)).date()
    bars = load_universe_bars(get_sqlalchemy_engine(), symbols, start_date=start, end_date=end)
    events, coverage = build_cross_events(oracle, ranking, bars, config)
    metrics, daily, folds, semesters = summarize_experiment(events, coverage, config)
    decision = evaluate(metrics, config)

    run_id = f"oracle-global-rank-cross-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    events.to_parquet(output / "events.parquet", index=False)
    daily.to_csv(output / "daily.csv", index=False)
    folds.to_csv(output / "by_fold.csv", index=False)
    semesters.to_csv(output / "by_semester.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E11_ORACLE_H20_X_GLOBAL_RANKING_H20",
        "status": "complete",
        "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "inputs": {
            "oracle_oof_gate": str(oracle_gate_path),
            "global_ranking_oof_cache": str(global_rank_path),
            "global_ranking_metadata": str(rank_meta),
            "global_rank_history_used": False,
        },
        "contract": {
            "oracle_pool": "Oracle H20 OOF TOP20 amplitude",
            "ranking": "Global Ranking H20 OOF reranked inside Oracle pool",
            "long": "top 20% of Oracle pool",
            "short": "bottom 20% of Oracle pool",
            "abstain": "middle 60%",
            "entry": "adjusted open J+1",
            "exit": "adjusted open J+21",
            "selection_tuning": False,
        },
        "config": asdict(config),
        "global_ranking_metadata": metadata,
        "metrics": metrics,
        "decision": decision,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E11 termine: %s verdicts=%s", output, decision["verdicts"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument("--global-rank-cache", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_global_rank_cross"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate,
        global_rank_path=args.global_rank_cache,
        output_root=args.output_root,
        config=E11Config(bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E11 termine: {output}")
    print(json.dumps(report["decision"]["verdicts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
