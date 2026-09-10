"""Pré-gate d'un portefeuille relatif dans le pool Oracle TOP20.

Consomme uniquement les scores OOF du ranker conditionnel. Les rendements
forward servent à l'évaluation, jamais à la sélection. Ce module ne simule pas
les fills : il décide si un replay portefeuille OHLC plus coûteux est justifié.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.conditional_oracle_ranker import RANK_SCORE_COL


@dataclass(frozen=True, slots=True)
class RelativePortfolioConfig:
    selection_fraction: float = 0.20
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_fee_annual: float = 0.003
    min_positive_fold_ratio: float = 0.75
    min_positive_semester_ratio: float = 0.60
    min_mean_net_cohort_return: float = 0.001

    def __post_init__(self) -> None:
        if not 0 < self.selection_fraction < 0.5:
            raise ValueError("selection_fraction doit être dans ]0, 0.5[.")
        if min(self.commission_bps, self.slippage_bps, self.borrow_fee_annual) < 0:
            raise ValueError("Les coûts doivent être positifs ou nuls.")


def _semester(value: pd.Timestamp) -> str:
    ts = pd.Timestamp(value)
    return f"{ts.year}H{1 if ts.month <= 6 else 2}"


def _daily_cohorts(
    oof: pd.DataFrame,
    *,
    horizon: int,
    config: RelativePortfolioConfig,
) -> pd.DataFrame:
    required = {"date", "symbol", "future_return", RANK_SCORE_COL, "fold_index"}
    missing = sorted(required - set(oof.columns))
    if missing:
        raise ValueError(f"Colonnes OOF absentes: {','.join(missing)}")
    frame = oof.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    frame[RANK_SCORE_COL] = pd.to_numeric(frame[RANK_SCORE_COL], errors="coerce")
    frame = frame.dropna(subset=["date", "symbol", "future_return", RANK_SCORE_COL])

    round_trip_cost = 2.0 * (config.commission_bps + config.slippage_bps) / 10_000.0
    borrow_cost = 0.5 * config.borrow_fee_annual * float(horizon) / 252.0
    rows: list[dict[str, Any]] = []
    for date, group in frame.groupby("date", sort=True):
        ordered = group.sort_values([RANK_SCORE_COL, "symbol"], ascending=[False, True])
        count = max(1, math.ceil(len(ordered) * config.selection_fraction))
        long_leg = ordered.head(count)
        short_leg = ordered.tail(count)
        long_return = float(long_leg["future_return"].mean())
        short_return = float(short_leg["future_return"].mean())
        spread = long_return - short_return
        gross = 0.5 * spread
        rows.append({
            "date": date,
            "fold_index": int(ordered["fold_index"].mode().iloc[0]),
            "pool_size": int(len(ordered)),
            "leg_size": int(count),
            "long_return": long_return,
            "short_return": short_return,
            "spread_return": spread,
            "portfolio_gross_return": gross,
            "round_trip_cost": round_trip_cost,
            "borrow_cost": borrow_cost,
            "portfolio_net_return": gross - round_trip_cost - borrow_cost,
            "semester": _semester(date),
        })
    return pd.DataFrame(rows)


def _group_metrics(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(column, sort=True):
        rows.append({
            column: int(key) if column == "fold_index" else str(key),
            "dates": int(len(group)),
            "mean_gross_return": float(group["portfolio_gross_return"].mean()),
            "mean_net_return": float(group["portfolio_net_return"].mean()),
            "positive_net": bool(group["portfolio_net_return"].mean() > 0),
        })
    return rows


def evaluate_relative_portfolio(
    oof: pd.DataFrame,
    *,
    horizon: int,
    config: RelativePortfolioConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    daily = _daily_cohorts(oof, horizon=horizon, config=config)
    if daily.empty:
        raise ValueError("Aucune cohorte OOF évaluable.")
    folds = _group_metrics(daily, "fold_index")
    semesters = _group_metrics(daily, "semester")
    positive_folds = sum(bool(row["positive_net"]) for row in folds)
    positive_semesters = sum(bool(row["positive_net"]) for row in semesters)
    fold_ratio = positive_folds / len(folds) if folds else 0.0
    semester_ratio = positive_semesters / len(semesters) if semesters else 0.0
    mean_net = float(daily["portfolio_net_return"].mean())
    gates = {
        "mean_net_cohort_return_ge_min": mean_net >= config.min_mean_net_cohort_return,
        "positive_fold_ratio_ge_min": fold_ratio >= config.min_positive_fold_ratio,
        "positive_semester_ratio_ge_min": semester_ratio >= config.min_positive_semester_ratio,
    }
    gates["replay_authorized"] = bool(all(gates.values()))
    report = {
        "horizon": int(horizon),
        "daily_cohorts": int(len(daily)),
        "mean_long_return": float(daily["long_return"].mean()),
        "mean_short_return": float(daily["short_return"].mean()),
        "mean_spread_return": float(daily["spread_return"].mean()),
        "mean_portfolio_gross_return": float(daily["portfolio_gross_return"].mean()),
        "mean_portfolio_net_return": mean_net,
        "positive_fold_ratio": fold_ratio,
        "positive_semester_ratio": semester_ratio,
        "folds": folds,
        "semesters": semesters,
        "gates": gates,
    }
    return daily, report


def run(artifact: Path, output: Path, config: RelativePortfolioConfig) -> dict[str, Any]:
    results: dict[str, Any] = {}
    output.mkdir(parents=True, exist_ok=False)
    for horizon_dir in sorted(artifact.glob("h*")):
        try:
            horizon = int(horizon_dir.name[1:])
        except ValueError:
            continue
        oof_path = horizon_dir / "oof_predictions.parquet"
        if not oof_path.exists():
            continue
        daily, report = evaluate_relative_portfolio(
            pd.read_parquet(oof_path), horizon=horizon, config=config,
        )
        horizon_output = output / horizon_dir.name
        horizon_output.mkdir()
        daily.to_parquet(horizon_output / "daily_cohorts.parquet", index=False)
        (horizon_output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        results[str(horizon)] = report
    if not results:
        raise ValueError("Aucun artefact OOF Hx trouvé.")
    campaign = {
        "schema_version": 1,
        "experiment": "oracle_top20_relative_dollar_neutral_precheck",
        "status": "complete",
        "research_only": True,
        "execution_replay": False,
        "source_ranker_artifact": str(artifact),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "results": results,
        "replay_authorized": bool(all(
            result["gates"]["replay_authorized"] for result in results.values()
        )),
    }
    (output / "report.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return campaign


def main() -> None:
    parser = argparse.ArgumentParser(description="Pré-gate portefeuille relatif Oracle TOP20.")
    parser.add_argument("--ranker-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--selection-fraction", type=float, default=0.20)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--borrow-fee-annual", type=float, default=0.003)
    args = parser.parse_args()
    output = args.output or Path("artifacts/research/oracle_relative_portfolio") / (
        f"relative-precheck-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    )
    campaign = run(
        args.ranker_artifact,
        output,
        RelativePortfolioConfig(
            selection_fraction=args.selection_fraction,
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
            borrow_fee_annual=args.borrow_fee_annual,
        ),
    )
    print(json.dumps({
        "output": str(output),
        "replay_authorized": campaign["replay_authorized"],
        "results": {
            horizon: result["gates"] for horizon, result in campaign["results"].items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
