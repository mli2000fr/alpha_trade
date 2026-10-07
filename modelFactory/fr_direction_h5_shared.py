"""FR Sprint 10-B: small shared ternary model on causal archived Oracle events."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from modelFactory.fr_direction_h5_audit import KEYS, evaluate, rank_selection
from modelFactory.fr_feature_profile_freeze import FEATURES
from modelFactory.fr_labels_review import phase_mask
from modelFactory.fr_oracle_h5_pilot import deterministic_score, feature_matrix, select_phase
from modelFactory.fr_oracle_h5_pilot import load_config as load_oracle_config
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256

LOG = logging.getLogger(__name__)


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "profile": "fr_direction_h5_shared_v1",
        "market_code": "FR_EQ",
        "horizon": 5,
        "oracle_branch": "trees",
        "oracle_phases": ["validation", "test"],
        "outer_folds": [4, 5, 6],
        "development_end": "2025-12-31",
        "oracle_fraction": 0.2,
        "side_fraction": 0.2,
        "seed": 17,
        "threads": 2,
        "target": "d1_middle_d10",
        "champion_selection": "validation_tail_auc",
        "calibration": "none",
        "support": {
            "min_train_dates": 126,
            "min_train_per_class": 100,
            "min_evaluation_dates": 40,
            "min_evaluation_tail_per_class": 30,
            "min_evaluation_session_coverage": 0.8,
        },
        "gates": {
            "min_oos_folds": 2,
            "min_mean_tail_auc": 0.53,
            "min_auc_delta_vs_momentum20": 0.01,
            "min_mean_daily_ic": 0.03,
            "min_mean_daily_spread": 0.002,
        },
        "canonical_writes_enabled": False,
        "serving_enabled": False,
        "confirmation_evaluated": False,
    }
    # Only the outer-fold set changes after independently verified price proofs.
    if cfg.get("profile") == "fr_direction_h5_fold7_repaired_v1":
        expected.update(profile="fr_direction_h5_fold7_repaired_v1", outer_folds=[4, 5, 6, 7])
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise ValueError("Frozen 10-B protocol changed")
    return cfg


def ternary_target(deciles: pd.Series) -> pd.Series:
    if not deciles.dropna().between(1, 10).all():
        raise ValueError("Invalid deciles")
    out = pd.Series(pd.NA, index=deciles.index, dtype="Int64")
    known = deciles.notna()
    out.loc[known] = 1
    out.loc[deciles.eq(1).fillna(False)] = 0
    out.loc[deciles.eq(10).fillna(False)] = 2
    return out


def causal_oracle_history(predictions: pd.DataFrame, source_folds: list[dict], cfg: dict) -> pd.DataFrame:
    """Fixed branch only, never source champion; latest *available* fit wins."""
    parts = []
    for record in source_folds:
        fold = record["fold"]
        cutoff = record["dates"]["validation_start"]
        group = predictions[predictions.fold.eq(fold) & predictions.phase.isin(cfg["oracle_phases"])].copy()
        if group.empty or group.duplicated(KEYS).any():
            raise ValueError("Missing/duplicate archived Oracle phase")
        if group.decision_session_date.lt(cutoff).any():
            raise ValueError("Oracle model not available at prediction date")
        group["oracle_model_available_session"] = cutoff
        group["oracle_score"] = group[f"score_{cfg['oracle_branch']}"]
        if not group.oracle_score.between(0, 1).all():
            raise ValueError("Invalid Oracle probabilities")
        group = group.rename(columns={"fold": "oracle_fold", "phase": "oracle_phase"})
        parts.append(group)
    work = pd.concat(parts, ignore_index=True)
    work = work.sort_values(KEYS + ["oracle_model_available_session", "oracle_fold"], kind="stable")
    return work.drop_duplicates(KEYS, keep="last").reset_index(drop=True)


def support_for(frame: pd.DataFrame, phase: str, expected_sessions: int, cfg: dict) -> dict:
    known = ternary_target(frame.decile).dropna()
    count = {str(i): int(known.eq(i).sum()) for i in range(3)}
    dates = int(frame.decision_session_date.nunique())
    reasons = []
    gates = cfg["support"]
    if phase == "train":
        if dates < gates["min_train_dates"]:
            reasons.append("OOF_TRAIN_DATES_BELOW_126")
        if min(count.values()) < gates["min_train_per_class"]:
            reasons.append("OOF_TRAIN_CLASS_BELOW_100")
    else:
        if dates < gates["min_evaluation_dates"]:
            reasons.append("EVALUATION_DATES_BELOW_40")
        if dates / expected_sessions < gates["min_evaluation_session_coverage"]:
            reasons.append("EVALUATION_SESSION_COVERAGE_BELOW_80PCT")
        if min(count["0"], count["2"]) < gates["min_evaluation_tail_per_class"]:
            reasons.append("EVALUATION_TAIL_CLASS_BELOW_30")
    return {
        "rows": len(frame),
        "dates": dates,
        "known_classes": count,
        "unknown_deciles": int(frame.decile.isna().sum()),
        "expected_sessions": expected_sessions,
        "coverage": dates / expected_sessions if expected_sessions else None,
        "state": "ADMITTED" if not reasons else "BLOCKED_DIRECTION_SUPPORT",
        "reasons": reasons,
    }


def choose_champion(validation: dict) -> str:
    if any(validation[n]["tail_auc"] is None for n in ("logistic", "trees")):
        raise ValueError("Validation tail AUC missing")
    return max(("logistic", "trees"), key=lambda name: validation[name]["tail_auc"])


def probability_score(model, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if list(model.classes_) != [0, 1, 2]:
        raise ValueError("Directional class order mismatch")
    probs = model.predict_proba(features)
    if not np.isfinite(probs).all() or (probs < 0).any() or (probs > 1).any() or not np.allclose(probs.sum(axis=1), 1):
        raise ValueError("Invalid ternary probabilities")
    return probs, probs[:, 2] - probs[:, 0]


def verdict(folds: list[dict], cfg: dict) -> dict:
    completed = [f for f in folds if f["status"] == "COMPLETED_LIMITED_RESEARCH"]
    if not completed:
        return {"verdict": "BLOCKED_DIRECTION_SUPPORT", "completed_folds": 0}
    champion = [f["test"][f["champion"]] for f in completed]
    baseline = [f["test"]["return_20"] for f in completed]
    means = {
        "tail_auc": float(np.mean([m["tail_auc"] for m in champion])),
        "auc_delta_vs_momentum20": float(
            np.mean([m["tail_auc"] - b["tail_auc"] for m, b in zip(champion, baseline, strict=True)])
        ),
        "daily_ic": float(np.mean([m["means"]["ic"] for m in champion])),
        "daily_spread": float(np.mean([m["means"]["spread"] for m in champion])),
    }
    if len(completed) < cfg["gates"]["min_oos_folds"]:
        status = "LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS"
    else:
        passed = all(
            means[k] >= cfg["gates"][f"min_{'mean_' if k != 'auc_delta_vs_momentum20' else ''}{k}"] for k in means
        )
        status = "PILOT_SIGNAL_REQUIRES_CONFIRMATION" if passed else "NO_GO_DIRECTIONAL_PILOT"
    return {"verdict": status, "completed_folds": len(completed), "mean_fold_metrics": means}


def run(path: Path, output_root: Path) -> dict:
    cfg = load_config(path)
    oracle_cfg = load_oracle_config(ROOT / cfg["oracle_profile"])
    if cfg["profile"] == "fr_direction_h5_fold7_repaired_v1" and oracle_cfg["profile"] != "fr_oracle_h5_fold7_repaired_v1":
        raise ValueError("La confirmation réparée requiert son Oracle OOF versionné")
    source = ROOT / cfg["oracle_source"]
    source_report = json.loads((source / "report.json").read_text(encoding="utf-8"))
    pred_path = source / "predictions.parquet"
    if (
        source_report["config"] != oracle_cfg
        or _sha256(pred_path) != cfg["oracle_prediction_sha256"]
        or source_report["prediction_sha256"] != cfg["oracle_prediction_sha256"]
        or source_report.get("confirmation_evaluated") is not False
    ):
        raise ValueError("Oracle source changed")
    label_report_path = ROOT / oracle_cfg["labels_report"]
    label_path = label_report_path.with_name("labels.parquet")
    price_path = ROOT / oracle_cfg["price_panel"]
    if _sha256(label_path) != oracle_cfg["labels_sha256"] or _sha256(price_path) != oracle_cfg["price_sha256"]:
        raise ValueError("Label/feature source changed")
    label_report = json.loads(label_report_path.read_text(encoding="utf-8"))
    labels = pd.read_parquet(label_path)
    labels = labels[labels.horizon.eq(5) & labels.decision_session_date.le(cfg["development_end"])]
    price = pd.read_parquet(price_path)
    price = price[price.decision_session_date.le(cfg["development_end"])]
    if (pd.to_datetime(price.max_input_available_at, utc=True) > pd.to_datetime(price.decision_at, utc=True)).any():
        raise ValueError("Feature leakage")
    if labels.duplicated(KEYS).any() or price.duplicated(KEYS).any():
        raise ValueError("Duplicate label/feature keys")
    full = labels.merge(price[KEYS + list(FEATURES) + ["profile_row_ready"]], on=KEYS, validate="one_to_one")
    source_support = json.loads((ROOT / oracle_cfg["support_report"]).read_text(encoding="utf-8"))
    if (
        source_support["source_hashes"]["labels"] != oracle_cfg["labels_sha256"]
        or source_support["source_hashes"]["price"] != oracle_cfg["price_sha256"]
    ):
        raise ValueError("Source Oracle support hash mismatch")
    # Confirm source train support and maturity, without looking at source validation AP.
    for record in source_report["folds"]:
        train = select_phase(full, record["dates"], "train", oracle_cfg)
        expected = next(
            r
            for r in source_support["fold_support"]
            if r["fold"] == record["fold"]
            and r["horizon"] == 5
            and r["phase"] == "train"
            and r["profile"] == "price_only"
        )
        if len(train) != expected["oracle_rows"] or train.empty:
            raise ValueError("Source Oracle train support mismatch")
        if train.label_available_session_date.ge(record["dates"]["validation_start"]).any():
            raise ValueError("Source Oracle train label leakage")
    history = causal_oracle_history(pd.read_parquet(pred_path), source_report["folds"], cfg)
    if history.decision_session_date.gt(cfg["development_end"]).any():
        raise ValueError("Reserved dates in history")
    frame = history.merge(
        full[
            KEYS
            + list(FEATURES)
            + [
                "profile_row_ready",
                "decile",
                "decile_state",
                "future_return",
                "path_state",
                "label_available_session_date",
            ]
        ],
        on=KEYS,
        validate="one_to_one",
        how="left",
    )
    if frame[list(FEATURES) + ["future_return"]].isna().any().any() or not frame.profile_row_ready.eq(True).all():
        raise ValueError("Incomplete OOF history join")
    if (frame.decile.isna() & ~frame.decile_state.eq("TIE_BOUNDARY")).any():
        raise ValueError("Unexpected unknown directional label")
    pool = rank_selection(frame, "oracle_score", cfg["oracle_fraction"], cfg["seed"])
    if pool.groupby("decision_session_date").size().min() < 4:
        raise ValueError("Insufficient daily Oracle pool")
    plans = []
    for identifier in cfg["outer_folds"]:
        fold = next(f for f in label_report["fold_plan"] if f["fold"] == identifier)
        phases = {
            p: pool[phase_mask(pool, fold, p, cfg["development_end"])].copy() for p in ("train", "validation", "test")
        }
        support = {p: support_for(data, p, 126 if p != "train" else 0, cfg) for p, data in phases.items()}
        plans.append(
            {
                "fold": identifier,
                "dates": fold,
                "support": support,
                "status": "ADMITTED"
                if all(s["state"] == "ADMITTED" for s in support.values())
                else "BLOCKED_DIRECTION_SUPPORT",
            }
        )
    hashes = {
        "oracle_predictions": _sha256(pred_path),
        "labels": _sha256(label_path),
        "price": _sha256(price_path),
        "oracle_report": _sha256(source / "report.json"),
        "code": _sha256(Path(__file__)),
    }
    fingerprint = _fingerprint(
        {
            "cfg": cfg,
            "hashes": hashes,
            "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        }
    )
    destination = output_root / f"fr-shared-direction-h5-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=False)
    _atomic_json(
        destination / "protocol.json",
        {"cfg": cfg, "hashes": hashes, "fingerprint": fingerprint, "features": list(FEATURES), "plans": plans},
    )
    pool.to_parquet(destination / "oracle_oof_pool.parquet", index=False)
    metrics_cfg = {
        "side_fraction": cfg["side_fraction"],
        "seed": cfg["seed"],
        "support": {"min_dates": 40, "min_tail_per_class": 30},
    }
    predictions, daily_parts, curves_parts = [], [], []
    with threadpool_limits(limits=cfg["threads"]):
        for plan in plans:
            LOG.info("fold=%s status=%s support=%s", plan["fold"], plan["status"], plan["support"])
            if plan["status"] != "ADMITTED":
                continue
            phases = {
                p: pool[phase_mask(pool, plan["dates"], p, cfg["development_end"])].copy()
                for p in ("train", "validation", "test")
            }
            target = ternary_target(phases["train"].decile)
            known = target.notna()
            models = {
                "logistic": make_pipeline(
                    StandardScaler(), LogisticRegression(**oracle_cfg["logistic"], random_state=cfg["seed"])
                ),
                "trees": HistGradientBoostingClassifier(
                    **oracle_cfg["trees"], early_stopping=False, random_state=cfg["seed"]
                ),
            }
            for name, model in models.items():
                model.fit(feature_matrix(phases["train"].loc[known]), target[known].astype(int))
                joblib.dump(model, destination / f"fold{plan['fold']}_{name}.joblib")
            for phase in ("validation", "test"):
                data = phases[phase].copy()
                data["random"] = [
                    deterministic_score(d, u, cfg["seed"] + 1)
                    for d, u in zip(data.decision_session_date, data.research_uid, strict=True)
                ]
                for name, model in models.items():
                    probs, score = probability_score(model, feature_matrix(data))
                    data[name] = score
                    for i, label in enumerate(("d1", "middle", "d10")):
                        data[f"{name}_p_{label}"] = probs[:, i]
                phase_metrics = {}
                for name in ("random", "return_5", "return_20", "logistic", "trees"):
                    metrics, daily, curves = evaluate(data, name, metrics_cfg)
                    phase_metrics[name] = metrics
                    daily["outer_fold"], daily["phase"], daily["score"] = plan["fold"], phase, name
                    daily_parts.append(daily)
                    curves["outer_fold"], curves["phase"], curves["score"] = plan["fold"], phase, name
                    curves_parts.append(curves)
                plan[phase] = phase_metrics
                data["outer_fold"], data["direction_phase"] = plan["fold"], phase
                predictions.append(data)
            plan["champion"] = choose_champion(plan["validation"])
            plan["status"] = "COMPLETED_LIMITED_RESEARCH"
    if predictions:
        pd.concat(predictions, ignore_index=True).to_parquet(destination / "direction_predictions.parquet", index=False)
        pd.concat(daily_parts, ignore_index=True).to_parquet(destination / "daily_metrics.parquet", index=False)
        pd.concat(curves_parts, ignore_index=True).to_parquet(destination / "score_quintiles.parquet", index=False)
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "source_hashes": hashes,
        "pool_rows": len(pool),
        "pool_dates": int(pool.decision_session_date.nunique()),
        "pool_sha256": _sha256(destination / "oracle_oof_pool.parquet"),
        "plans": plans,
        **verdict(plans, cfg),
        "confirmation_evaluated": False,
        "canonical_writes": False,
        "serving_enabled": False,
        "trained_models": 2 * sum(p["status"] == "COMPLETED_LIMITED_RESEARCH" for p in plans),
        "limitations": [
            "DEVELOPMENT_PREVIOUSLY_INSPECTED",
            "FIXED_ORACLE_BRANCH_NOT_CHAMPION_10A",
            "LIMITED_OOF_HISTORY",
            "RAW_RETURNS_NO_COSTS",
            "H5_PRICE_ONLY",
            "RELATIVE_DECILE_NOT_ABSOLUTE_DIRECTION",
            "RESEARCH_J1_ASSUMPTION",
        ],
    }
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/research_fr/direction_h5_shared_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/research/direction_h5_shared")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run(args.profile, args.output_root)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("artifact_directory", "verdict", "trained_models", "completed_folds", "mean_fold_metrics")
                if k in report
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
