"""Sprint 11-A: diagnostic directionnel CN exploratoire, sans entraînement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANKING_CONFIG
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_OUTPUT as RANKING_OUTPUT
from modelFactory.cn_global_ranking_walk_forward import RankingProtocol, _sha
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH

DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint11a_directional_diagnostic.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "directional" / "sprint11a"
SCORES = ("momentum", "reversal", "lightgbm", "catboost", "consensus")
REQUIRED_COLUMNS = [
    "market_code", "session_date", "instrument_id", "board_code", "cn_breadth_1",
    "target_quality_valid", "oracle_decile", "future_return",
    "execution_data_eligible", "oracle_top20", "baseline_score", "rank_score",
]


def load_protocol(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ranking = RankingProtocol.load(RANKING_CONFIG).raw
    expected = {
        "experiment": "cn_directional_diagnostic_sprint11a_v1",
        "market_code": "CN_A",
        "source_experiment": ranking["experiment"],
        "evidence_level": "exploratory_not_independent_confirmation",
        "oracle_pool_rule": "use_sprint10c_oos_top20_before_label_filter",
        "rank_universe": "full_oracle_pool_before_label_filter",
        "score_families": list(SCORES),
        "long_top_fractions": [0.10, 0.20, 0.30],
        "veto_bottom_fraction": 0.20,
        "primary_label": "oracle_decile_D1_D10",
        "eligibility_sensitivity": "execution_data_eligible",
        "decision_gate": "none_exploratory",
        "serving_enabled": False,
        "backtest_enabled": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"Protocole Sprint 11-A invalide: {key}")
    if config.get("source_horizons") != ranking["horizons"] or config.get("test_semesters") != ranking["test_semesters"]:
        raise ValueError("Périodes Sprint 11-A divergentes des artefacts Sprint 10-C")
    if config.get("source_models") != ranking["models"] or int(config.get("minimum_pool_per_session", 0)) < 20:
        raise ValueError("Modèles ou taille minimale du pool Sprint 11-A invalides")
    return config


def combine_oos(lightgbm: pd.DataFrame, catboost: pd.DataFrame) -> pd.DataFrame:
    """Apparie les deux prédictions sans modifier le pool Oracle initial."""
    keys = ["session_date", "instrument_id"]
    for model, frame in (("lightgbm", lightgbm), ("catboost", catboost)):
        if frame.duplicated(keys).any() or set(frame["market_code"]) != {"CN_A"}:
            raise RuntimeError(f"Clés OOS CN invalides: {model}")
    left = lightgbm.rename(columns={"rank_score": "score_lightgbm"})
    right = catboost[keys + [
        "market_code", "target_quality_valid", "oracle_top20", "oracle_decile",
        "future_return", "execution_data_eligible", "baseline_score", "rank_score",
    ]].rename(columns={name: f"other_{name}" for name in [
        "market_code", "target_quality_valid", "oracle_top20", "oracle_decile",
        "future_return", "execution_data_eligible", "baseline_score",
    ]} | {"rank_score": "score_catboost"})
    frame = left.merge(right, on=keys, how="outer", validate="one_to_one", indicator=True)
    if not frame["_merge"].eq("both").all():
        raise RuntimeError("Prédictions LightGBM/CatBoost non appariées")
    for column in ("market_code", "target_quality_valid", "oracle_top20",
                   "oracle_decile", "future_return", "execution_data_eligible", "baseline_score"):
        try:
            pd.testing.assert_series_equal(
                frame[column], frame[f"other_{column}"], check_names=False,
            )
        except AssertionError as exc:
            raise RuntimeError(f"Artefacts OOS incompatibles: {column}") from exc
    return frame.drop(columns=["_merge", *[f"other_{name}" for name in (
        "market_code", "target_quality_valid", "oracle_top20", "oracle_decile",
        "future_return", "execution_data_eligible", "baseline_score",
    )]])


def prepare_pool(frame: pd.DataFrame, *, minimum: int) -> tuple[pd.DataFrame, dict[str, int]]:
    if frame.duplicated(["session_date", "instrument_id"]).any() or set(frame["market_code"]) != {"CN_A"}:
        raise RuntimeError("Pool directionnel CN invalide")
    pool = frame.loc[frame["oracle_top20"]].copy()
    sessions = pool.groupby("session_date")["instrument_id"].transform("size")
    excluded = pool.loc[sessions < minimum]
    pool = pool.loc[sessions >= minimum].copy()
    if pool.empty:
        raise RuntimeError("Aucun pool Oracle TOP20 évaluable")
    pool["score_momentum"] = pool["baseline_score"]
    pool["score_reversal"] = -pool["baseline_score"]
    for model in ("lightgbm", "catboost"):
        score = f"score_{model}"
        # Percentile construit sur tout le pool de J, y compris labels invalides.
        pool[f"pct_{model}"] = pool.groupby("session_date")[score].rank(pct=True, method="first")
    pool["score_consensus"] = (pool["pct_lightgbm"] + pool["pct_catboost"]) / 2
    return pool, {
        "pool_rows_before_minimum": int(frame["oracle_top20"].sum()),
        "pool_rows_excluded_small_session": len(excluded),
        "pool_sessions_excluded_small_session": int(excluded["session_date"].nunique()),
        "pool_rows": len(pool),
        "pool_sessions": int(pool["session_date"].nunique()),
        "valid_label_rows": int(pool["target_quality_valid"].sum()),
        "execution_data_eligible_rows": int(pool["execution_data_eligible"].sum()),
    }


def policy_masks(pool: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.Series]:
    """Sélectionne sur scores PIT seulement, avant filtrage par label."""
    size = pool.groupby("session_date")["instrument_id"].transform("size")
    result = {"oracle_all": pd.Series(True, index=pool.index)}
    for family in SCORES:
        score = f"score_{family}"
        ordered = pool.sort_values(
            ["session_date", score, "instrument_id"],
            ascending=[True, False, True], kind="stable", na_position="last",
        )
        rank = ordered.groupby("session_date", sort=False).cumcount().reindex(pool.index)
        complete = pool[score].notna()
        for fraction in config["long_top_fractions"]:
            pct = int(round(float(fraction) * 100))
            result[f"{family}_long_top{pct}"] = complete & (
                rank < np.ceil(size * float(fraction))
            )
        veto_fraction = float(config["veto_bottom_fraction"])
        result[f"{family}_veto_bottom{int(round(veto_fraction * 100))}"] = complete & (
            rank < size - np.ceil(size * veto_fraction)
        )
    return result


def counts(pool: pd.DataFrame, mask: pd.Series, *, scope: pd.Series | None = None) -> dict[str, float | int | None]:
    if scope is None:
        scope = pd.Series(True, index=pool.index)
    all_rows = pool.loc[scope]
    chosen = pool.loc[scope & mask]
    valid = chosen.loc[chosen["target_quality_valid"] & chosen["future_return"].notna()]
    d1 = int(valid["oracle_decile"].eq(1).sum())
    d10 = int(valid["oracle_decile"].eq(10).sum())
    return {
        "pool": len(all_rows),
        "selected": len(chosen),
        "evaluated": len(valid),
        "d1": d1,
        "d10": d10,
        "positive_return": int(valid["future_return"].gt(0).sum()),
        "return_sum": float(valid["future_return"].sum()),
    }


def metrics(value: dict[str, float | int | None], reference: dict[str, float | int | None]) -> dict[str, float | int | None]:
    def ratio(numerator: float, denominator: float) -> float | None:
        return round(numerator / denominator, 6) if denominator else None

    evaluated = int(value["evaluated"])
    return {
        "pool": int(value["pool"]),
        "selected": int(value["selected"]),
        "evaluated": evaluated,
        "coverage": ratio(float(value["selected"]), float(value["pool"])),
        "label_coverage": ratio(evaluated, float(value["selected"])),
        "d1_count": int(value["d1"]),
        "d10_count": int(value["d10"]),
        "d1_rate": ratio(float(value["d1"]), evaluated),
        "d10_rate": ratio(float(value["d10"]), evaluated),
        "positive_return_rate": ratio(float(value["positive_return"]), evaluated),
        "mean_future_return": ratio(float(value["return_sum"]), evaluated),
        "d1_retention": ratio(float(value["d1"]), float(reference["d1"])),
        "d10_retention": ratio(float(value["d10"]), float(reference["d10"])),
    }


def _sum_counts(values: list[dict[str, float | int | None]]) -> dict[str, float | int | None]:
    return {key: sum(float(item[key]) for item in values) for key in (
        "pool", "selected", "evaluated", "d1", "d10", "positive_return", "return_sum",
    )}


def summarize(folds: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in sorted({int(item["horizon"]) for item in folds}):
        subset = [item for item in folds if item["horizon"] == horizon]
        names = subset[0]["overall"]
        total = {name: _sum_counts([item["overall"][name] for item in subset]) for name in names}
        baseline = total["oracle_all"]
        result[str(horizon)] = {
            "overall": {name: metrics(value, baseline) for name, value in total.items()},
            "by_semester": {
                item["semester"]: {
                    name: metrics(value, item["overall"]["oracle_all"])
                    for name, value in item["overall"].items()
                } for item in subset
            },
            "by_board": {},
            "by_breadth": {},
            "execution_eligible_sensitivity": {},
        }
        for dimension in ("board", "breadth"):
            groups = sorted({group for item in subset for group in item[dimension]})
            for group in groups:
                parts = [item[dimension][group] for item in subset if group in item[dimension]]
                grouped = {name: _sum_counts([part[name] for part in parts]) for name in names}
                reference = grouped["oracle_all"]
                result[str(horizon)][f"by_{dimension}"][group] = {
                    name: metrics(value, reference) for name, value in grouped.items()
                }
        eligible = {
            name: _sum_counts([item["execution_eligible_sensitivity"][name] for item in subset])
            for name in names
        }
        result[str(horizon)]["execution_eligible_sensitivity"] = {
            name: metrics(value, eligible["oracle_all"]) for name, value in eligible.items()
        }
    return result


def evaluate_fold(pool: pd.DataFrame, *, config: dict[str, Any], horizon: int, semester: str) -> dict[str, Any]:
    masks = policy_masks(pool, config)
    result: dict[str, Any] = {
        "horizon": horizon,
        "semester": semester,
        "overall": {name: counts(pool, mask) for name, mask in masks.items()},
        "board": {}, "breadth": {},
        "execution_eligible_sensitivity": {
            name: counts(pool, mask, scope=pool["execution_data_eligible"])
            for name, mask in masks.items()
        },
    }
    groupings = {
        "board": pool["board_code"].fillna("UNKNOWN").astype(str),
        "breadth": pd.Series(
            np.where(pool["cn_breadth_1"].lt(0.5), "below_50pct", "at_least_50pct"),
            index=pool.index,
        ),
    }
    for dimension, values in groupings.items():
        for group in sorted(values.unique()):
            scope = values.eq(group)
            result[dimension][group] = {
                name: counts(pool, mask, scope=scope) for name, mask in masks.items()
            }
    return result


def run(*, config_path: Path = DEFAULT_CONFIG, ranking_root: Path = RANKING_OUTPUT,
        output_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config = load_protocol(config_path)
    from modelFactory import cn_global_ranking_walk_forward as ranking_runner

    source_config_sha = _sha(RANKING_CONFIG)
    source_code_sha = _sha(Path(ranking_runner.__file__))
    audit_sha = _sha(AUDIT_PATH)
    protocol_sha = _sha(config_path)
    code_sha = _sha(Path(__file__))
    digest = hashlib.sha256((protocol_sha + code_sha + source_config_sha + source_code_sha + audit_sha).encode()).hexdigest()[:16]
    destination = output_root / f"sprint11a-{digest}"
    if (destination / "report.json").exists():
        raise RuntimeError(f"Rapport Sprint 11-A existant, écrasement refusé: {destination}")
    folds = []
    provenance = []
    for horizon in config["source_horizons"]:
        for semester in config["test_semesters"]:
            frames = {}
            for model in config["source_models"]:
                item = _find_run(
                    ranking_root, horizon=horizon, semester=semester, model=model,
                    config_sha=source_config_sha, code_sha=source_code_sha, audit_sha=audit_sha,
                )
                if item is None:
                    raise RuntimeError(f"Artefact Sprint 10-C manquant: H{horizon}/{semester}/{model}")
                path, report = item
                frames[model] = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
                provenance.append({
                    "horizon": horizon, "semester": semester, "model": model,
                    "predictions_sha256": report["predictions_sha256"],
                })
            merged = combine_oos(frames["lightgbm"], frames["catboost"])
            pool, audit = prepare_pool(merged, minimum=int(config["minimum_pool_per_session"]))
            fold = evaluate_fold(pool, config=config, horizon=horizon, semester=semester)
            fold["pool_audit"] = audit
            folds.append(fold)
            print(f"Sprint 11-A H{horizon} {semester}: pool={audit['pool_rows']} labels={audit['valid_label_rows']}", flush=True)
    report = {
        "status": "EXPLORATORY_RESEARCH_ONLY", "market_code": "CN_A",
        "evidence_level": config["evidence_level"], "serving_enabled": False,
        "backtest_executed": False, "decision_gate": config["decision_gate"],
        "protocol_sha256": protocol_sha, "code_sha256": code_sha,
        "source_protocol_sha256": source_config_sha, "source_code_sha256": source_code_sha,
        "label_audit_sha256": audit_sha, "source_predictions": provenance,
        "folds": folds, "results": summarize(folds),
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": report["status"], "report": str(destination / "report.json"), "folds": len(folds)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ranking-root", type=Path, default=RANKING_OUTPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(config_path=args.config, ranking_root=args.ranking_root, output_root=args.output_root),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
