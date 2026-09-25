"""Agrégation verrouillée des prédictions OOS Oracle CN du Sprint 10-B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.cn_oracle_walk_forward import (
    AUDIT_PATH,
    DEFAULT_CONFIG,
    DEFAULT_OUTPUT,
    Protocol,
    _sha,
    _top_rows,
    score_metrics,
)


def _find_run(root: Path, *, horizon: int, semester: str, model: str,
              config_sha: str, code_sha: str, audit_sha: str) -> tuple[Path, dict[str, Any]] | None:
    matches = []
    for report_path in root.glob(f"cn_oracle_sprint10b_v1-*/h{horizon}/{semester}/{model}/report.json"):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("protocol_sha256") == config_sha
                and report.get("code_sha256") == code_sha
                and report.get("label_audit_sha256") == audit_sha):
            predictions = report_path.parent / "predictions.parquet"
            if not predictions.exists() or _sha(predictions) != report.get("predictions_sha256"):
                raise RuntimeError(f"Prédictions OOS CN absentes ou altérées: {predictions}")
            matches.append((predictions, report))
    if len(matches) > 1:
        raise RuntimeError(f"Plusieurs runs CN pour H{horizon}/{semester}/{model}")
    return matches[0] if matches else None


def _monthly_bootstrap(frame: pd.DataFrame, *, top_pct: float, repetitions: int,
                       alpha: float, seed: int) -> dict[str, float | int]:
    paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()].copy()
    model = _top_rows(paired, "oracle_score", top_pct)
    baseline = _top_rows(paired, "baseline_score", top_pct)
    model_month = model.assign(month=model["session_date"].dt.to_period("M")).groupby("month").agg(
        successes=("oracle_extreme20", "sum"), selections=("oracle_extreme20", "size")
    )
    base_month = baseline.assign(month=baseline["session_date"].dt.to_period("M")).groupby("month").agg(
        successes=("oracle_extreme20", "sum"), selections=("oracle_extreme20", "size")
    )
    if not model_month.index.equals(base_month.index) or not model_month["selections"].equals(base_month["selections"]):
        raise RuntimeError("Bootstrap Oracle et baseline sur populations distinctes")
    counts = model_month["selections"].to_numpy(dtype=float)
    differences = model_month["successes"].to_numpy(dtype=float) - base_month["successes"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(counts), size=(repetitions, len(counts)))
    gains = differences[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {
        "months": len(counts), "repetitions": repetitions,
        "uplift": float(differences.sum() / counts.sum()),
        "lower_fwer_bound": float(np.quantile(gains, alpha / 2)),
        "upper_fwer_bound": float(np.quantile(gains, 1 - alpha / 2)),
    }


def aggregate(*, config_path: Path = DEFAULT_CONFIG, root: Path = DEFAULT_OUTPUT,
              require_complete: bool = False) -> dict[str, Any]:
    protocol = Protocol.load(config_path)
    config_sha = _sha(config_path)
    from modelFactory import cn_oracle_walk_forward as runner

    code_sha = _sha(Path(runner.__file__))
    audit_sha = _sha(AUDIT_PATH)
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_LABELS_PRICE_ONLY":
        raise RuntimeError("Audit des labels CN non valide")
    evaluation = protocol.raw["evaluation"]
    family_alpha = float(evaluation["familywise_alpha"]) / int(evaluation["multiple_testing_hypotheses"])
    result: dict[str, Any] = {
        "status": "INCOMPLETE", "market_code": "CN_A", "protocol_sha256": config_sha,
        "code_sha256": code_sha, "label_audit_sha256": audit_sha,
        "multiple_testing_method": "Bonferroni family-wise one family of 4 horizons x 2 models",
        "effective_alpha_per_hypothesis": family_alpha,
        "serving_enabled": False, "backtest_executed": False,
        "missing": [], "results": {},
    }
    for horizon in protocol.raw["horizons"]:
        result["results"][str(horizon)] = {}
        for model in protocol.raw["models"]:
            frames = []
            fold_reports = []
            for semester in protocol.raw["test_semesters"]:
                item = _find_run(root, horizon=horizon, semester=semester, model=model,
                                 config_sha=config_sha, code_sha=code_sha, audit_sha=audit_sha)
                if item is None:
                    result["missing"].append(f"H{horizon}/{semester}/{model}")
                    continue
                path, report = item
                frame = pd.read_parquet(path)
                if set(frame["market_code"]) != {"CN_A"} or not frame["test_semester"].eq(semester).all():
                    raise RuntimeError(f"OOS CN mal identifiées: {path}")
                if frame.duplicated(["session_date", "instrument_id"]).any():
                    raise RuntimeError(f"OOS CN dupliquées: {path}")
                frames.append(frame)
                fold_reports.append(report)
            if len(frames) != len(protocol.raw["test_semesters"]):
                continue
            combined = pd.concat(frames, ignore_index=True)
            if combined.duplicated(["session_date", "instrument_id"]).any():
                raise RuntimeError("Folds OOS CN qui se chevauchent")
            paired = combined.loc[combined["target_quality_valid"] & combined["baseline_score"].notna()]
            top_pct = float(evaluation["top_pct"])
            model_metrics = score_metrics(paired, score="oracle_score", top_pct=top_pct)
            baseline_metrics = score_metrics(paired, score="baseline_score", top_pct=top_pct)
            ci = _monthly_bootstrap(
                combined, top_pct=top_pct,
                repetitions=int(evaluation["bootstrap_repetitions"]),
                alpha=family_alpha, seed=int(protocol.raw["seed"]) + horizon,
            )
            positives = sum(report["metrics"]["precision_uplift"] > 0 for report in fold_reports)
            min_sessions = int(evaluation["min_test_sessions"])
            fold_sessions_valid = all(report["metrics"]["model"]["sessions"] >= min_sessions for report in fold_reports)
            matured_coverage = min(
                float(year["horizons"][str(horizon)]["valid_fraction_among_matured"])
                for year in audit["yearly"]
            )
            meets_gate = (
                fold_sessions_valid
                and matured_coverage >= float(protocol.raw["min_matured_label_coverage"])
                and positives >= int(evaluation["min_positive_semesters"])
                and ci["uplift"] >= float(evaluation["min_precision_uplift"])
                and ci["lower_fwer_bound"] > 0
            )
            result["results"][str(horizon)][model] = {
                "verdict": "GO_RESEARCH_ONLY" if meets_gate else "NO_GO",
                "model": model_metrics, "baseline_atr": baseline_metrics,
                "precision_uplift": ci["uplift"], "monthly_block_bootstrap": ci,
                "positive_semesters": positives, "folds": len(fold_reports),
                "fold_sessions_valid": fold_sessions_valid,
                "minimum_matured_label_coverage": matured_coverage,
                "per_semester": {report["test_semester"]: report["metrics"]["precision_uplift"]
                                 for report in fold_reports},
            }
    if not result["missing"]:
        result["status"] = "COMPLETE_RESEARCH_ONLY"
    elif require_complete:
        raise RuntimeError(f"Campagne CN incomplète: {len(result['missing'])} runs absents")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = aggregate(config_path=args.config, root=args.output_root,
                       require_complete=args.require_complete)
    target = args.output_root / "sprint10b_oracle_summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "missing": len(report["missing"]),
                      "results": report["results"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
