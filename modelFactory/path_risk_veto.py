"""E3-R research-only: veto OOF des pertes extrêmes après Oracle.

Le module ne réentraîne aucun modèle. Il recharge les probabilités OOF de
tail-risk produites par E3-A2, les applique comme veto quotidien à plusieurs
politiques candidates et mesure leur effet marginal sur rendement et risque.
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

import pandas as pd

from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL
from modelFactory.path_aware_utility import LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, P_LONG_COL, P_SHORT_COL, _tail

LOGGER = logging.getLogger(__name__)

PRIMARY_VETO_FRACTION = 0.20
DIAGNOSTIC_VETO_FRACTIONS = (0.0, 0.10, PRIMARY_VETO_FRACTION, 0.30)


@dataclass(frozen=True, slots=True)
class RiskVetoConfig:
    catastrophic_loss_threshold: float = -0.20
    primary_veto_fraction: float = PRIMARY_VETO_FRACTION
    candidate_top_fraction: float = 0.10
    max_return_degradation: float = 0.001
    min_catastrophic_reduction: float = 0.40
    min_cvar_improvement: float = 0.0025

    def __post_init__(self) -> None:
        if self.catastrophic_loss_threshold >= 0:
            raise ValueError("catastrophic_loss_threshold doit être négatif.")
        if not 0 < self.primary_veto_fraction < 0.5:
            raise ValueError("primary_veto_fraction doit être dans ]0, 0.5[.")
        if not 0 < self.candidate_top_fraction < 0.5:
            raise ValueError("candidate_top_fraction doit être dans ]0, 0.5[.")
        if self.max_return_degradation < 0 or not 0 <= self.min_catastrophic_reduction <= 1:
            raise ValueError("Gates E3-R invalides.")


def _cvar(values: pd.Series, fraction: float = 0.05) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if numeric.empty:
        return None
    count = max(1, math.ceil(len(numeric) * fraction))
    return float(numeric.iloc[:count].mean())


def _veto_mask(frame: pd.DataFrame, risk_column: str, fraction: float) -> pd.Series:
    """Retourne un masque vrai pour les lignes rejetées, date par date."""
    if fraction <= 0:
        return pd.Series(False, index=frame.index, dtype=bool)
    ordered = frame[["date", "symbol", risk_column]].copy()
    ordered["_index"] = ordered.index
    ordered = ordered.sort_values(
        ["date", risk_column, "symbol"], ascending=[True, False, True]
    )
    ordered["_position"] = ordered.groupby("date").cumcount()
    ordered["_veto_count"] = ordered.groupby("date")[risk_column].transform(
        lambda values: math.ceil(len(values) * fraction)
    )
    rejected = ordered["_position"].lt(ordered["_veto_count"])
    result = pd.Series(False, index=frame.index, dtype=bool)
    result.loc[ordered["_index"].to_numpy()] = rejected.to_numpy()
    return result


def add_daily_risk_vetoes(
    frame: pd.DataFrame,
    fractions: tuple[float, ...] = DIAGNOSTIC_VETO_FRACTIONS,
) -> pd.DataFrame:
    result = frame.copy()
    for side, risk_column in (("long", LONG_TAIL_RISK_COL), ("short", SHORT_TAIL_RISK_COL)):
        for fraction in fractions:
            result[f"{side}_veto_{fraction:.2f}"] = _veto_mask(result, risk_column, fraction)
    return result


def _concentration(frame: pd.DataFrame, return_column: str) -> dict[str, Any]:
    if frame.empty:
        return {"top1_positive_contribution_share": None, "top5_positive_contribution_share": None}
    totals = frame.groupby("symbol")[return_column].sum().sort_values(ascending=False)
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


def _metrics(frame: pd.DataFrame, return_column: str, config: RiskVetoConfig) -> dict[str, Any]:
    values = pd.to_numeric(frame[return_column], errors="coerce").dropna()
    if values.empty:
        return {
            "rows": 0, "dates": 0, "symbols": 0, "mean_net_return": None,
            "median_net_return": None, "success_rate": None,
            "catastrophic_loss_rate": None, "catastrophic_loss_count": 0,
            "cvar_05": None, "worst_return": None,
            "concentration": _concentration(frame, return_column),
        }
    return {
        "rows": int(len(values)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_net_return": float(values.mean()), "median_net_return": float(values.median()),
        "success_rate": float(values.gt(0).mean()),
        "catastrophic_loss_rate": float(values.le(config.catastrophic_loss_threshold).mean()),
        "catastrophic_loss_count": int(values.le(config.catastrophic_loss_threshold).sum()),
        "cvar_05": _cvar(values), "worst_return": float(values.min()),
        "concentration": _concentration(frame, return_column),
    }


def _comparison(
    baseline: pd.DataFrame,
    selected: pd.DataFrame,
    return_column: str,
    config: RiskVetoConfig,
) -> dict[str, Any]:
    before = _metrics(baseline, return_column, config)
    after = _metrics(selected, return_column, config)
    if before["rows"] == 0:
        return {"baseline": before, "after_veto": after, "coverage": 0.0}
    baseline_cat = before["catastrophic_loss_rate"]
    after_cat = after["catastrophic_loss_rate"]
    if baseline_cat:
        reduction = 1.0 if after_cat is None else float((baseline_cat - after_cat) / baseline_cat)
    else:
        reduction = None
    return_delta = (
        float(after["mean_net_return"] - before["mean_net_return"])
        if after["mean_net_return"] is not None else None
    )
    catastrophic_delta = (
        float(after_cat - baseline_cat) if after_cat is not None else float(-baseline_cat)
    )
    cvar_delta = (
        float(after["cvar_05"] - before["cvar_05"])
        if after["cvar_05"] is not None else None
    )
    return {
        "baseline": before, "after_veto": after,
        "coverage": float(after["rows"] / before["rows"]),
        "return_delta": return_delta,
        "catastrophic_rate_delta": catastrophic_delta,
        "catastrophic_relative_reduction": reduction,
        "cvar_delta": cvar_delta,
    }


def _candidate_sets(frame: pd.DataFrame, top_fraction: float) -> dict[str, dict[str, pd.DataFrame]]:
    sets: dict[str, dict[str, pd.DataFrame]] = {
        "oracle_pool": {"long": frame, "short": frame},
        "oracle_top": {
            "long": _tail(frame, ORACLE_GATE_SCORE_COL, top_fraction, ascending=False),
            "short": _tail(frame, ORACLE_GATE_SCORE_COL, top_fraction, ascending=False),
        },
    }
    if P_LONG_COL in frame.columns and P_SHORT_COL in frame.columns:
        sets["path_probability_top"] = {
            "long": _tail(frame, P_LONG_COL, top_fraction, ascending=False),
            "short": _tail(frame, P_SHORT_COL, top_fraction, ascending=False),
        }
    return sets


def evaluate_risk_veto(
    frame: pd.DataFrame,
    config: RiskVetoConfig | None = None,
    fractions: tuple[float, ...] = DIAGNOSTIC_VETO_FRACTIONS,
) -> dict[str, Any]:
    cfg = config or RiskVetoConfig()
    required = [
        "date", "symbol", "fold_index", ORACLE_GATE_SCORE_COL,
        LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL, LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL,
    ]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Prédictions E3-R incomplètes: {missing}")
    work = frame.dropna(subset=required).copy()
    policies: dict[str, Any] = {}
    for policy, sides in _candidate_sets(work, cfg.candidate_top_fraction).items():
        policy_result: dict[str, Any] = {}
        for side, baseline in sides.items():
            return_column = LONG_NET_RETURN_COL if side == "long" else SHORT_NET_RETURN_COL
            risk_column = LONG_TAIL_RISK_COL if side == "long" else SHORT_TAIL_RISK_COL
            fractions_result: dict[str, Any] = {}
            for fraction in fractions:
                selected = baseline.loc[~_veto_mask(baseline, risk_column, fraction)].copy()
                fractions_result[f"{fraction:.2f}"] = _comparison(
                    baseline, selected, return_column, cfg
                )
            policy_result[side] = fractions_result
        policies[policy] = policy_result
    return {"rows": int(len(work)), "policies": policies}


def _stability_for_policy(
    frame: pd.DataFrame,
    policy: str,
    side: str,
    config: RiskVetoConfig,
) -> dict[str, Any]:
    fold_results: list[dict[str, Any]] = []
    for fold_index, fold in frame.groupby("fold_index", sort=True):
        candidates = _candidate_sets(fold, config.candidate_top_fraction)[policy][side]
        risk_column = LONG_TAIL_RISK_COL if side == "long" else SHORT_TAIL_RISK_COL
        return_column = LONG_NET_RETURN_COL if side == "long" else SHORT_NET_RETURN_COL
        comparison = _comparison(
            candidates,
            candidates.loc[~_veto_mask(candidates, risk_column, config.primary_veto_fraction)],
            return_column, config,
        )
        fold_results.append({"fold_index": int(fold_index), **comparison})
    cat_better = sum(
        result.get("catastrophic_rate_delta") is not None
        and result["catastrophic_rate_delta"] < 0 for result in fold_results
    )
    cvar_better = sum(
        result.get("cvar_delta") is not None and result["cvar_delta"] > 0
        for result in fold_results
    )
    return_preserved = sum(
        result.get("return_delta") is not None
        and result["return_delta"] >= -config.max_return_degradation
        for result in fold_results
    )
    return {
        "folds": fold_results,
        "catastrophic_rate_improved_folds": int(cat_better),
        "cvar_improved_folds": int(cvar_better),
        "return_preserved_folds": int(return_preserved),
    }


def _gates(
    primary: dict[str, Any],
    stability: dict[str, Any],
    config: RiskVetoConfig,
) -> dict[str, Any]:
    after = primary["after_veto"]
    concentration = after["concentration"]["top1_positive_contribution_share"]
    reduction = primary["catastrophic_relative_reduction"]
    gates = {
        "coverage_gte_0_70": bool(primary["coverage"] >= 0.70),
        "catastrophic_reduction_gte_0_40": bool(
            reduction is not None and reduction >= config.min_catastrophic_reduction
        ),
        "cvar_improvement_gte_0_0025": bool(primary["cvar_delta"] >= config.min_cvar_improvement),
        "return_degradation_lte_0_001": bool(
            primary["return_delta"] >= -config.max_return_degradation
        ),
        "catastrophic_rate_improved_folds_gte_7": bool(
            stability["catastrophic_rate_improved_folds"] >= 7
        ),
        "cvar_improved_folds_gte_7": bool(stability["cvar_improved_folds"] >= 7),
        "return_preserved_folds_gte_7": bool(stability["return_preserved_folds"] >= 7),
        "top1_positive_contribution_lte_0_35": bool(
            concentration is not None and concentration <= 0.35
        ),
    }
    return {"values": gates, "all_gates_passed": bool(all(gates.values()))}


def _semester_results(frame: pd.DataFrame, config: RiskVetoConfig) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for semester, group in frame.groupby(
        pd.to_datetime(frame["date"]).map(
            lambda value: f"{value.year}H{1 if value.month <= 6 else 2}"
        ), sort=True,
    ):
        candidates = _candidate_sets(group, config.candidate_top_fraction)
        output[str(semester)] = {}
        for policy, sides in candidates.items():
            output[str(semester)][policy] = {}
            for side, baseline in sides.items():
                return_column = LONG_NET_RETURN_COL if side == "long" else SHORT_NET_RETURN_COL
                risk_column = LONG_TAIL_RISK_COL if side == "long" else SHORT_TAIL_RISK_COL
                output[str(semester)][policy][side] = _comparison(
                    baseline,
                    baseline.loc[~_veto_mask(baseline, risk_column, config.primary_veto_fraction)],
                    return_column, config,
                )
    return output


def load_oof_inputs(utility_artifact: Path, directional_artifact: Path | None) -> pd.DataFrame:
    utility_path = utility_artifact / "oof_predictions.parquet"
    if not utility_path.exists():
        raise FileNotFoundError(f"OOF E3-A2 absent: {utility_path}")
    frame = pd.read_parquet(utility_path)
    if directional_artifact is None:
        return frame
    directional_path = directional_artifact / "oof_predictions.parquet"
    if not directional_path.exists():
        raise FileNotFoundError(f"OOF E3-A absent: {directional_path}")
    directional = pd.read_parquet(directional_path)[["date", "symbol", P_LONG_COL, P_SHORT_COL]]
    if directional.duplicated(["date", "symbol"]).any():
        raise ValueError("Prédictions E3-A non uniques par date/symbole.")
    return frame.merge(directional, on=["date", "symbol"], how="left", validate="one_to_one")


def run_risk_veto_campaign(
    utility_artifact: Path,
    *,
    directional_artifact: Path | None = None,
    output_root: Path | None = None,
    config: RiskVetoConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    cfg = config or RiskVetoConfig()
    frame = load_oof_inputs(utility_artifact, directional_artifact)
    frame = frame.dropna(subset=[LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL]).copy()
    evaluation = evaluate_risk_veto(frame, cfg)
    stability: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    for policy in evaluation["policies"]:
        stability[policy] = {}
        gates[policy] = {}
        for side in ("long", "short"):
            side_stability = _stability_for_policy(frame, policy, side, cfg)
            primary = evaluation["policies"][policy][side][f"{cfg.primary_veto_fraction:.2f}"]
            stability[policy][side] = side_stability
            gates[policy][side] = _gates(primary, side_stability, cfg)
    output_root = output_root or utility_artifact.parent
    run_id = f"shared-path-risk-veto-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E3_R_path_tail_risk_veto_v1",
        "status": "completed", "research_only": True, "serving_ready": False,
        "source_utility_artifact": str(utility_artifact),
        "source_directional_artifact": str(directional_artifact) if directional_artifact else None,
        "contract": {
            "config": asdict(cfg), "veto_fractions": list(DIAGNOSTIC_VETO_FRACTIONS),
            "primary_policy": "daily top 20% predicted tail-risk within final candidates rejected without refill",
            "veto_scope": "candidate_policy_after_direction_selection",
            "direction_choice": "unchanged; veto cannot create or reverse a direction",
            "threshold_optimization": False,
        },
        "evaluation": evaluation, "fold_stability": stability,
        "gates": gates, "semesters": _semester_results(frame, cfg),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output, report


def _summary(path: Path, report: dict[str, Any]) -> str:
    lines = [f"E3-R Risk Veto terminé: {path}"]
    primary = f"{report['contract']['config']['primary_veto_fraction']:.2f}"
    for policy, sides in report["evaluation"]["policies"].items():
        for side in ("long", "short"):
            result = sides[side][primary]
            lines.append(
                f"{policy}/{side.upper()} coverage={result['coverage']:.1%} "
                f"return_delta={result['return_delta']:+.2%} "
                f"cat_reduction={result['catastrophic_relative_reduction']:+.1%} "
                f"cvar_delta={result['cvar_delta']:+.2%} "
                f"gates={report['gates'][policy][side]['all_gates_passed']}"
            )
    lines.append("Serving désactivé: veto évalué en recherche uniquement.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utility-artifact", type=Path, required=True)
    parser.add_argument("--directional-artifact", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    path, report = run_risk_veto_campaign(
        args.utility_artifact, directional_artifact=args.directional_artifact,
        output_root=args.output_root,
    )
    print(_summary(path, report))


if __name__ == "__main__":
    main()
