"""E3-D research-only: direction par asymétrie OOF du tail-risk.

Le module ne réentraîne aucun modèle. Il compare, pour chaque événement Oracle,
les rangs quotidiens des risques LONG et SHORT produits par E3-A2. Le côté le
moins risqué est choisi seulement si l'écart dépasse une marge préfixée.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL
from modelFactory.path_aware_utility import LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL

LOGGER = logging.getLogger(__name__)

LONG_RISK_RANK_COL = "long_tail_risk_daily_rank"
SHORT_RISK_RANK_COL = "short_tail_risk_daily_rank"
RISK_DIRECTION_SCORE_COL = "tail_risk_direction_score"
DECISION_COL = "tail_risk_direction_decision"
CHOSEN_RETURN_COL = "tail_risk_chosen_net_return"
PRIMARY_MARGIN = 0.20
DIAGNOSTIC_MARGINS = (0.0, 0.10, PRIMARY_MARGIN, 0.30)


@dataclass(frozen=True, slots=True)
class RiskDirectionConfig:
    primary_margin: float = PRIMARY_MARGIN
    catastrophic_loss_threshold: float = -0.20
    min_coverage: float = 0.30
    min_return_lift: float = 0.0025
    min_side_share: float = 0.10

    def __post_init__(self) -> None:
        if not 0 <= self.primary_margin < 1:
            raise ValueError("primary_margin doit être dans [0, 1[.")
        if self.catastrophic_loss_threshold >= 0:
            raise ValueError("catastrophic_loss_threshold doit être négatif.")
        if not 0 < self.min_coverage <= 1 or not 0 <= self.min_side_share < 0.5:
            raise ValueError("Gates de couverture E3-D invalides.")


def add_daily_risk_asymmetry(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalise les deux risques dans chaque journée avant comparaison."""
    result = frame.copy()
    result[LONG_RISK_RANK_COL] = result.groupby("date")[LONG_TAIL_RISK_COL].rank(
        method="average", pct=True
    )
    result[SHORT_RISK_RANK_COL] = result.groupby("date")[SHORT_TAIL_RISK_COL].rank(
        method="average", pct=True
    )
    # Positif signifie que SHORT est relativement plus dangereux : LONG est préféré.
    result[RISK_DIRECTION_SCORE_COL] = (
        result[SHORT_RISK_RANK_COL] - result[LONG_RISK_RANK_COL]
    )
    return result


def apply_direction_policy(frame: pd.DataFrame, margin: float) -> pd.DataFrame:
    if not 0 <= margin < 1:
        raise ValueError("La marge E3-D doit être dans [0, 1[.")
    result = frame.copy()
    score = pd.to_numeric(result[RISK_DIRECTION_SCORE_COL], errors="coerce")
    if margin == 0:
        long_mask = score.gt(0)
        short_mask = score.lt(0)
    else:
        long_mask = score.ge(margin)
        short_mask = score.le(-margin)
    result[DECISION_COL] = "ABSTAIN"
    result.loc[long_mask, DECISION_COL] = "LONG"
    result.loc[short_mask, DECISION_COL] = "SHORT"
    result[CHOSEN_RETURN_COL] = np.nan
    result.loc[long_mask, CHOSEN_RETURN_COL] = result.loc[long_mask, LONG_NET_RETURN_COL]
    result.loc[short_mask, CHOSEN_RETURN_COL] = result.loc[short_mask, SHORT_NET_RETURN_COL]
    return result


def _cvar(values: pd.Series, fraction: float = 0.05) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if numeric.empty:
        return None
    count = max(1, math.ceil(len(numeric) * fraction))
    return float(numeric.iloc[:count].mean())


def _concentration(selected: pd.DataFrame) -> dict[str, Any]:
    if selected.empty:
        return {"top1_positive_contribution_share": None, "top5_positive_contribution_share": None}
    totals = selected.groupby("symbol")[CHOSEN_RETURN_COL].sum().sort_values(ascending=False)
    positive_total = float(totals.clip(lower=0).sum())
    return {
        "top1_positive_contribution_share": (
            float(max(0.0, totals.iloc[0]) / positive_total) if positive_total > 0 else None
        ),
        "top5_positive_contribution_share": (
            float(totals.head(5).clip(lower=0).sum() / positive_total) if positive_total > 0 else None
        ),
        "top_profit_symbols": [str(symbol) for symbol in totals.head(5).index],
    }


def _policy_metrics(
    policy_frame: pd.DataFrame,
    config: RiskDirectionConfig,
) -> dict[str, Any]:
    selected = policy_frame.loc[policy_frame[DECISION_COL].ne("ABSTAIN")].copy()
    if selected.empty:
        return {"rows": 0, "coverage": 0.0}
    chosen = pd.to_numeric(selected[CHOSEN_RETURN_COL], errors="coerce")
    long_returns = pd.to_numeric(selected[LONG_NET_RETURN_COL], errors="coerce")
    short_returns = pd.to_numeric(selected[SHORT_NET_RETURN_COL], errors="coerce")
    random_expected = (long_returns + short_returns) / 2.0
    always_long = float(long_returns.mean())
    always_short = float(short_returns.mean())
    best_static = max(always_long, always_short)
    decisions = selected[DECISION_COL]
    long_count = int(decisions.eq("LONG").sum())
    short_count = int(decisions.eq("SHORT").sum())
    chosen_is_better = np.where(
        decisions.eq("LONG"), long_returns.gt(short_returns), short_returns.gt(long_returns)
    )
    random_cat_rate = float(
        (
            long_returns.le(config.catastrophic_loss_threshold).astype(float)
            + short_returns.le(config.catastrophic_loss_threshold).astype(float)
        ).mean() / 2.0
    )
    random_distribution = pd.concat([long_returns, short_returns], ignore_index=True)
    chosen_mean = float(chosen.mean())
    return {
        "rows": int(len(selected)),
        "coverage": float(len(selected) / len(policy_frame)),
        "dates": int(selected["date"].nunique()), "symbols": int(selected["symbol"].nunique()),
        "long_count": long_count, "short_count": short_count,
        "long_share": float(long_count / len(selected)), "short_share": float(short_count / len(selected)),
        "mean_net_return": chosen_mean, "median_net_return": float(chosen.median()),
        "success_rate": float(chosen.gt(0).mean()),
        "chosen_side_better_rate": float(np.mean(chosen_is_better)),
        "always_long_return": always_long, "always_short_return": always_short,
        "random_50_50_expected_return": float(random_expected.mean()),
        "best_static_side_return": best_static,
        "lift_vs_random_50_50": float(chosen_mean - random_expected.mean()),
        "lift_vs_best_static_side": float(chosen_mean - best_static),
        "catastrophic_loss_rate": float(chosen.le(config.catastrophic_loss_threshold).mean()),
        "random_50_50_catastrophic_rate": random_cat_rate,
        "catastrophic_rate_delta_vs_random": float(
            chosen.le(config.catastrophic_loss_threshold).mean() - random_cat_rate
        ),
        "cvar_05": _cvar(chosen), "random_50_50_cvar_05": _cvar(random_distribution),
        "cvar_delta_vs_random": float(_cvar(chosen) - _cvar(random_distribution)),
        "worst_return": float(chosen.min()), "concentration": _concentration(selected),
    }


def evaluate_risk_direction(
    frame: pd.DataFrame,
    config: RiskDirectionConfig | None = None,
    margins: tuple[float, ...] = DIAGNOSTIC_MARGINS,
) -> dict[str, Any]:
    cfg = config or RiskDirectionConfig()
    required = [
        "date", "symbol", "fold_index", LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
        LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL,
    ]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Prédictions E3-D incomplètes: {missing}")
    work = frame.dropna(subset=required).copy()
    work = add_daily_risk_asymmetry(work)
    policies: dict[str, Any] = {}
    for margin in margins:
        policies[f"{margin:.2f}"] = _policy_metrics(apply_direction_policy(work, margin), cfg)
    return {"rows": int(len(work)), "policies": policies}


def _stability(frame: pd.DataFrame, config: RiskDirectionConfig) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for fold_index, group in frame.groupby("fold_index", sort=True):
        scored = add_daily_risk_asymmetry(group)
        metrics = _policy_metrics(apply_direction_policy(scored, config.primary_margin), config)
        folds.append({"fold_index": int(fold_index), **metrics})
    positive_lift = sum(
        fold.get("lift_vs_random_50_50") is not None and fold["lift_vs_random_50_50"] > 0
        for fold in folds
    )
    positive_return = sum(
        fold.get("mean_net_return") is not None and fold["mean_net_return"] > 0
        for fold in folds
    )
    beats_static = sum(
        fold.get("lift_vs_best_static_side") is not None and fold["lift_vs_best_static_side"] > 0
        for fold in folds
    )
    tail_better = sum(
        fold.get("catastrophic_rate_delta_vs_random") is not None
        and fold["catastrophic_rate_delta_vs_random"] <= 0 for fold in folds
    )
    return {
        "folds": folds, "positive_lift_folds": int(positive_lift),
        "positive_return_folds": int(positive_return),
        "beats_best_static_folds": int(beats_static),
        "tail_risk_not_worse_folds": int(tail_better),
    }


def _gates(
    primary: dict[str, Any], stability: dict[str, Any], config: RiskDirectionConfig
) -> dict[str, Any]:
    concentration = primary["concentration"]["top1_positive_contribution_share"]
    gates = {
        "coverage_gte_0_30": bool(primary["coverage"] >= config.min_coverage),
        "both_sides_share_gte_0_10": bool(
            min(primary["long_share"], primary["short_share"]) >= config.min_side_share
        ),
        "mean_net_return_positive": bool(primary["mean_net_return"] > 0),
        "lift_vs_random_gte_0_0025": bool(
            primary["lift_vs_random_50_50"] >= config.min_return_lift
        ),
        "beats_best_static_side": bool(primary["lift_vs_best_static_side"] > 0),
        "positive_lift_folds_gte_7": bool(stability["positive_lift_folds"] >= 7),
        "positive_return_folds_gte_7": bool(stability["positive_return_folds"] >= 7),
        "beats_best_static_folds_gte_7": bool(stability["beats_best_static_folds"] >= 7),
        "tail_risk_not_worse_folds_gte_7": bool(stability["tail_risk_not_worse_folds"] >= 7),
        "cvar_not_worse_than_random": bool(primary["cvar_delta_vs_random"] >= 0),
        "top1_positive_contribution_lte_0_35": bool(
            concentration is not None and concentration <= 0.35
        ),
    }
    return {"values": gates, "all_gates_passed": bool(all(gates.values()))}


def _semesters(frame: pd.DataFrame, config: RiskDirectionConfig) -> dict[str, Any]:
    work = add_daily_risk_asymmetry(frame)
    labels = pd.to_datetime(work["date"]).map(
        lambda value: f"{value.year}H{1 if value.month <= 6 else 2}"
    )
    return {
        str(label): _policy_metrics(apply_direction_policy(group, config.primary_margin), config)
        for label, group in work.groupby(labels, sort=True)
    }


def run_risk_direction_campaign(
    utility_artifact: Path,
    *,
    output_root: Path | None = None,
    config: RiskDirectionConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    cfg = config or RiskDirectionConfig()
    oof_path = utility_artifact / "oof_predictions.parquet"
    if not oof_path.exists():
        raise FileNotFoundError(f"OOF E3-A2 absent: {oof_path}")
    frame = pd.read_parquet(oof_path)
    evaluation = evaluate_risk_direction(frame, cfg)
    stability = _stability(frame, cfg)
    primary = evaluation["policies"][f"{cfg.primary_margin:.2f}"]
    gates = _gates(primary, stability, cfg)
    output_root = output_root or utility_artifact.parent
    run_id = f"shared-path-risk-direction-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E3_D_tail_risk_asymmetry_direction_v1",
        "status": "completed", "research_only": True, "serving_ready": False,
        "source_utility_artifact": str(utility_artifact),
        "contract": {
            "config": asdict(cfg), "diagnostic_margins": list(DIAGNOSTIC_MARGINS),
            "primary_policy": "daily tail-risk rank difference >= 0.20",
            "score": "rank(P(short catastrophic))-rank(P(long catastrophic))",
            "positive_score_direction": "LONG", "tie_policy": "ABSTAIN",
            "threshold_optimization": False,
        },
        "evaluation": evaluation, "fold_stability": stability,
        "gates": gates, "semesters": _semesters(frame, cfg),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output, report


def _summary(path: Path, report: dict[str, Any]) -> str:
    cfg = report["contract"]["config"]
    primary = report["evaluation"]["policies"][f"{cfg['primary_margin']:.2f}"]
    return "\n".join([
        f"E3-D tail-risk direction terminé: {path}",
        f"coverage={primary['coverage']:.1%} LONG={primary['long_share']:.1%} "
        f"SHORT={primary['short_share']:.1%}",
        f"net={primary['mean_net_return']:+.2%} "
        f"lift_random={primary['lift_vs_random_50_50']:+.2%} "
        f"lift_static={primary['lift_vs_best_static_side']:+.2%}",
        f"catastrophic={primary['catastrophic_loss_rate']:.2%} "
        f"CVaR5={primary['cvar_05']:+.2%} gates={report['gates']['all_gates_passed']}",
        "Serving désactivé: diagnostic OOF sans réentraînement.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utility-artifact", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    path, report = run_risk_direction_campaign(
        args.utility_artifact, output_root=args.output_root
    )
    print(_summary(path, report))


if __name__ == "__main__":
    main()
