"""Agrégation OOS et gate pré-enregistré du ranking CN Sprint 10-C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.cn_global_ranking_walk_forward import (
    DEFAULT_CONFIG,
    DEFAULT_OUTPUT,
    RankingProtocol,
    _sha,
    _tails,
    ranking_metrics,
)
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH


def _find_run(root: Path, *, horizon: int, semester: str, model: str,
              config_sha: str, code_sha: str, audit_sha: str) -> tuple[Path, dict[str, Any]] | None:
    matches = []
    for report_path in root.glob(f"cn_global_ranking_sprint10c_v1-*/h{horizon}/{semester}/{model}/report.json"):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("protocol_sha256") == config_sha
                and report.get("code_sha256") == code_sha
                and report.get("label_audit_sha256") == audit_sha):
            prediction = report_path.parent / "predictions.parquet"
            if not prediction.exists() or _sha(prediction) != report.get("predictions_sha256"):
                raise RuntimeError(f"Prédictions ranking CN absentes ou altérées: {prediction}")
            matches.append((prediction, report))
    if len(matches) > 1:
        raise RuntimeError(f"Plusieurs runs ranking CN pour H{horizon}/{semester}/{model}")
    return matches[0] if matches else None


def _monthly_bootstrap(frame: pd.DataFrame, *, tail_pct: float,
                       repetitions: int, alpha: float, seed: int) -> dict[str, float | int]:
    paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()
                       & frame["oracle_top20"]].copy()
    grouped = {}
    for score in ("rank_score", "baseline_score"):
        top, bottom = _tails(paired, score, tail_pct)
        top = top.assign(month=top["session_date"].dt.to_period("M"))
        bottom = bottom.assign(month=bottom["session_date"].dt.to_period("M"))
        numerator = top.assign(success=top["oracle_decile"].eq(10).astype(int)).groupby("month")["success"].sum()
        numerator = numerator.add(
            bottom.assign(success=bottom["oracle_decile"].eq(1).astype(int)).groupby("month")["success"].sum(),
            fill_value=0,
        )
        denominator = top.groupby("month").size().add(bottom.groupby("month").size(), fill_value=0)
        grouped[score] = pd.DataFrame({"success": numerator, "count": denominator})
    model = grouped["rank_score"]
    baseline = grouped["baseline_score"]
    if not model.index.equals(baseline.index) or not model["count"].equals(baseline["count"]):
        raise RuntimeError("Ranking et baseline non appariés pour le bootstrap CN")
    differences = model["success"].to_numpy(dtype=float) - baseline["success"].to_numpy(dtype=float)
    counts = model["count"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(counts), size=(repetitions, len(counts)))
    samples = differences[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {
        "months": len(counts), "repetitions": repetitions,
        "uplift": float(differences.sum() / counts.sum()),
        "lower_fwer_bound": float(np.quantile(samples, alpha / 2)),
        "upper_fwer_bound": float(np.quantile(samples, 1 - alpha / 2)),
    }


def _subgroups(frame: pd.DataFrame, *, tail_pct: float) -> dict[str, Any]:
    oracle = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()
                       & frame["oracle_top20"]].copy()
    grouping = {
        "board": oracle["board_code"],
        "year": oracle["session_date"].dt.year.astype(str),
        "breadth_regime": np.where(oracle["cn_breadth_1"].lt(0.5), "below_50pct", "at_least_50pct"),
    }
    result = {}
    for name, values in grouping.items():
        result[name] = {}
        for value, part in oracle.groupby(values, sort=True):
            if len(part) < 500 or part["session_date"].nunique() < 10:
                continue
            model = ranking_metrics(part, score="rank_score", tail_pct=tail_pct)
            baseline = ranking_metrics(part, score="baseline_score", tail_pct=tail_pct)
            result[name][str(value)] = {
                "rows": len(part), "model_symmetric_tail_precision": model["symmetric_tail_precision"],
                "baseline_symmetric_tail_precision": baseline["symmetric_tail_precision"],
                "uplift": round(model["symmetric_tail_precision"] - baseline["symmetric_tail_precision"], 6),
                "model_wrong_d1_top": model["wrong_d1_in_top"],
                "model_wrong_d10_bottom": model["wrong_d10_in_bottom"],
            }
    return result


def aggregate(*, config_path: Path = DEFAULT_CONFIG, root: Path = DEFAULT_OUTPUT,
              require_complete: bool = False) -> dict[str, Any]:
    protocol = RankingProtocol.load(config_path)
    from modelFactory import cn_global_ranking_walk_forward as runner

    config_sha, code_sha, audit_sha = _sha(config_path), _sha(Path(runner.__file__)), _sha(AUDIT_PATH)
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_LABELS_PRICE_ONLY":
        raise RuntimeError("Labels Oracle CN non audités")
    evaluation = protocol.raw["evaluation"]
    alpha = float(evaluation["familywise_alpha"]) / int(evaluation["hypotheses"])
    result: dict[str, Any] = {
        "status": "INCOMPLETE", "market_code": "CN_A",
        "protocol_sha256": config_sha, "code_sha256": code_sha,
        "label_audit_sha256": audit_sha,
        "multiple_testing_method": "Bonferroni 4 horizons x 2 modèles",
        "effective_alpha_per_hypothesis": alpha,
        "serving_enabled": False, "backtest_executed": False,
        "missing": [], "results": {},
    }
    for horizon in protocol.raw["horizons"]:
        result["results"][str(horizon)] = {}
        for model in protocol.raw["models"]:
            frames, reports = [], []
            for semester in protocol.raw["test_semesters"]:
                item = _find_run(root, horizon=horizon, semester=semester, model=model,
                                 config_sha=config_sha, code_sha=code_sha, audit_sha=audit_sha)
                if item is None:
                    result["missing"].append(f"H{horizon}/{semester}/{model}")
                    continue
                path, report = item
                frame = pd.read_parquet(path)
                if (set(frame["market_code"]) != {"CN_A"} or not frame["test_semester"].eq(semester).all()
                        or frame.duplicated(["session_date", "instrument_id"]).any()):
                    raise RuntimeError(f"Fold ranking OOS CN corrompu: {path}")
                frames.append(frame)
                reports.append(report)
            if len(frames) != len(protocol.raw["test_semesters"]):
                continue
            frame = pd.concat(frames, ignore_index=True)
            if frame.duplicated(["session_date", "instrument_id"]).any():
                raise RuntimeError("Folds ranking OOS CN chevauchants")
            paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()]
            oracle = paired.loc[paired["oracle_top20"]]
            global_pct = float(evaluation["global_tail_pct"])
            conditional_pct = float(evaluation["conditional_tail_pct"])
            global_model = ranking_metrics(paired, score="rank_score", tail_pct=global_pct)
            global_baseline = ranking_metrics(paired, score="baseline_score", tail_pct=global_pct)
            conditional_model = ranking_metrics(oracle, score="rank_score", tail_pct=conditional_pct)
            conditional_baseline = ranking_metrics(oracle, score="baseline_score", tail_pct=conditional_pct)
            bootstrap = _monthly_bootstrap(
                frame, tail_pct=conditional_pct,
                repetitions=int(evaluation["bootstrap_months"]),
                alpha=alpha, seed=int(protocol.raw["seed"]) + horizon,
            )
            positive_semesters = sum(
                report["metrics"]["oracle_top20"]["tail_precision_uplift"] > 0 for report in reports
            )
            min_coverage = min(
                float(year["horizons"][str(horizon)]["valid_fraction_among_matured"])
                for year in audit["yearly"]
            )
            enough_sessions = all(
                report["metrics"]["oracle_top20"]["model"]["sessions"] >= int(evaluation["min_test_sessions"])
                for report in reports
            )
            gate = (
                min_coverage >= float(evaluation["min_matured_label_coverage"])
                and enough_sessions
                and positive_semesters >= int(evaluation["min_positive_semesters"])
                and bootstrap["uplift"] >= float(evaluation["min_conditional_tail_uplift"])
                and bootstrap["lower_fwer_bound"] > 0
            )
            result["results"][str(horizon)][model] = {
                "verdict": "GO_RESEARCH_ONLY" if gate else "NO_GO",
                "global": {"model": global_model, "baseline_momentum": global_baseline},
                "oracle_top20": {"model": conditional_model, "baseline_momentum": conditional_baseline},
                "conditional_tail_uplift": bootstrap["uplift"],
                "monthly_block_bootstrap": bootstrap,
                "positive_semesters": positive_semesters, "folds": len(reports),
                "fold_sessions_valid": enough_sessions,
                "minimum_matured_label_coverage": min_coverage,
                "per_semester": {
                    report["test_semester"]: report["metrics"]["oracle_top20"]["tail_precision_uplift"]
                    for report in reports
                },
                "subgroups": _subgroups(frame, tail_pct=conditional_pct),
            }
    if not result["missing"]:
        result["status"] = "COMPLETE_RESEARCH_ONLY"
    elif require_complete:
        raise RuntimeError(f"Campagne ranking CN incomplète: {len(result['missing'])} folds absents")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = aggregate(config_path=args.config, root=args.output_root,
                       require_complete=args.require_complete)
    target = args.output_root / "sprint10c_global_ranking_summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "missing": len(report["missing"]),
                      "verdicts": {h: {m: v["verdict"] for m, v in models.items()}
                                   for h, models in report["results"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
