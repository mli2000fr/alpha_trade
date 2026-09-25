"""Sprint 10-C: ranking signé CN_A, évalué sur l'univers et Oracle OOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_oracle_aggregate import _find_run
from modelFactory.cn_oracle_walk_forward import (
    AUDIT_PATH,
    _load_frame,
    _matrix,
    _sha,
    _sources,
    split_fold,
)
from modelFactory.cn_oracle_walk_forward import (
    DEFAULT_CONFIG as ORACLE_CONFIG,
)
from modelFactory.cn_oracle_walk_forward import (
    DEFAULT_OUTPUT as ORACLE_OUTPUT,
)
from modelFactory.cn_oracle_walk_forward import (
    Protocol as OracleProtocol,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint10c_global_ranking.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "ranking" / "sprint10c"


@dataclass(frozen=True)
class RankingProtocol:
    raw: dict[str, Any]
    path: Path

    @classmethod
    def load(cls, path: Path) -> RankingProtocol:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        contract = {
            "experiment": "cn_global_ranking_sprint10c_v1", "market_code": "CN_A",
            "source_feature_profile": "cn_price_v1", "source_label_profile": "cn_oracle_labels_v1",
            "oracle_oos_profile": "cn_oracle_sprint10b_v1",
            "oracle_pool_rule": "mean_lightgbm_catboost_scores_top20_before_label_filter",
            "target": "oracle_decile_minus_one", "features_source": "sprint10b_oracle.yaml",
        }
        if any(raw.get(key) != expected for key, expected in contract.items()):
            raise ValueError("Contrat ranking CN Sprint 10-C invalide")
        oracle = OracleProtocol.load(ORACLE_CONFIG)
        for key in ("years", "horizons", "test_semesters", "validation_sessions", "min_train_sessions", "max_train_rows"):
            if raw.get(key) != oracle.raw.get(key):
                raise ValueError(f"Découpage ranking non aligné avec Oracle: {key}")
        if raw.get("models") != ["lightgbm", "catboost"] or raw.get("baseline_score") not in oracle.raw["features"]:
            raise ValueError("Modèles ou baseline ranking non conformes")
        if raw["evaluation"]["global_tail_pct"] != 0.10 or raw["evaluation"]["conditional_tail_pct"] != 0.20:
            raise ValueError("Seuils de classement non pré-enregistrés")
        return cls(raw, path)


def _attach_oracle_pool(test: pd.DataFrame, *, horizon: int, semester: str,
                        root: Path = ORACLE_OUTPUT) -> tuple[pd.DataFrame, list[str]]:
    from modelFactory import cn_oracle_walk_forward as oracle_runner

    config_sha = _sha(ORACLE_CONFIG)
    code_sha = _sha(Path(oracle_runner.__file__))
    audit_sha = _sha(AUDIT_PATH)
    frame = test.copy()
    hashes = []
    for model in ("lightgbm", "catboost"):
        item = _find_run(root, horizon=horizon, semester=semester, model=model,
                         config_sha=config_sha, code_sha=code_sha, audit_sha=audit_sha)
        if item is None:
            raise RuntimeError(f"Oracle OOS manquant: H{horizon} {semester} {model}")
        path, report = item
        prediction = pd.read_parquet(path, columns=["session_date", "instrument_id", "market_code",
                                                    "target_quality_valid", "oracle_score"])
        if prediction.duplicated(["session_date", "instrument_id"]).any() or set(prediction["market_code"]) != {"CN_A"}:
            raise RuntimeError("Oracle OOS CN dupliqué ou marché erroné")
        score_name = f"oracle_{model}_score"
        frame = frame.merge(prediction[["session_date", "instrument_id", "target_quality_valid", "oracle_score"]].rename(
            columns={"target_quality_valid": f"oracle_{model}_valid", "oracle_score": score_name}
        ), on=["session_date", "instrument_id"], how="left", validate="one_to_one")
        if (frame[score_name].isna().any()
                or not frame[f"oracle_{model}_valid"].eq(frame["target_quality_valid"]).all()):
            raise RuntimeError("Oracle OOS incomplet ou incompatible avec les labels CN")
        hashes.append(report["predictions_sha256"])
    frame["oracle_ensemble_score"] = (
        frame["oracle_lightgbm_score"] + frame["oracle_catboost_score"]
    ) / 2
    ordered = frame.sort_values(["session_date", "oracle_ensemble_score", "instrument_id"],
                                ascending=[True, False, True], kind="stable")
    rank = ordered.groupby("session_date", sort=False).cumcount()
    size = ordered.groupby("session_date", sort=False)["instrument_id"].transform("size")
    selected = ordered.loc[rank < np.maximum(1, np.ceil(size * 0.20).astype(int)),
                           ["session_date", "instrument_id"]].assign(oracle_top20=True)
    frame = frame.merge(selected, on=["session_date", "instrument_id"], how="left", validate="one_to_one")
    frame["oracle_top20"] = frame["oracle_top20"].eq(True)
    return frame, hashes


def _fit(model_name: str, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame,
         *, protocol: RankingProtocol, features: list[str], model_path: Path) -> np.ndarray:
    x_train, x_val, x_test = (_matrix(part, features) for part in (train, val, test))
    y_train = train["oracle_decile"].astype(int).to_numpy() - 1
    y_val = val["oracle_decile"].astype(int).to_numpy() - 1
    if len(np.unique(y_train)) < 10 or len(np.unique(y_val)) < 10:
        raise RuntimeError("Déciles incomplets au train ou à la validation")
    if model_name == "lightgbm":
        import lightgbm as lgb

        params = protocol.raw["lightgbm"].copy()
        stop = int(params.pop("early_stopping_rounds"))
        model = lgb.LGBMRegressor(**params, random_state=int(protocol.raw["seed"]),
                                  n_jobs=4, verbosity=-1, deterministic=True, force_col_wise=True)
        model.fit(x_train, y_train, eval_set=[(x_val, y_val)], eval_metric="l2",
                  callbacks=[lgb.early_stopping(stop, verbose=False)])
        model.booster_.save_model(str(model_path.with_suffix(".txt")))
    elif model_name == "catboost":
        from catboost import CatBoostRegressor

        params = protocol.raw["catboost"].copy()
        stop = int(params.pop("early_stopping_rounds"))
        model = CatBoostRegressor(
            **params, loss_function="RMSE", random_seed=int(protocol.raw["seed"]),
            thread_count=4, od_type="Iter", od_wait=stop,
            verbose=False, allow_writing_files=False,
        )
        model.fit(x_train, y_train, eval_set=(x_val, y_val), use_best_model=True)
        model.save_model(str(model_path.with_suffix(".cbm")))
    else:
        raise ValueError(f"Modèle ranking non pré-enregistré: {model_name}")
    return np.asarray(model.predict(x_test), dtype="float32")


def _tails(frame: pd.DataFrame, score: str, pct: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values(["session_date", score, "instrument_id"],
                                ascending=[True, False, True], kind="stable")
    rank = ordered.groupby("session_date", sort=False).cumcount()
    size = ordered.groupby("session_date", sort=False)["instrument_id"].transform("size")
    keep = np.maximum(1, np.ceil(size * pct).astype(int))
    return ordered.loc[rank < keep], ordered.loc[rank >= size - keep]


def ranking_metrics(frame: pd.DataFrame, *, score: str, tail_pct: float) -> dict[str, Any]:
    valid = frame.loc[frame["target_quality_valid"] & frame[score].notna()].copy()
    if valid.empty:
        raise RuntimeError("Aucun label de ranking CN évaluable")
    top, bottom = _tails(valid, score, tail_pct)
    # IC de Spearman calculé par séance ; la moyenne égale-pondérée évite qu'une
    # journée plus peuplée domine l'estimation.
    daily_ic = valid.groupby("session_date", sort=False).apply(
        lambda part: part[score].corr(part["future_return"], method="spearman"),
        include_groups=False,
    ).dropna()
    d10 = float(top["oracle_decile"].eq(10).mean())
    d1 = float(bottom["oracle_decile"].eq(1).mean())
    return {
        "rows": len(valid), "sessions": int(valid["session_date"].nunique()),
        "ic_spearman_mean": round(float(daily_ic.mean()), 6) if not daily_ic.empty else None,
        "ic_positive_session_fraction": round(float(daily_ic.gt(0).mean()), 6) if not daily_ic.empty else None,
        "d10_top_precision": round(d10, 6), "d1_bottom_precision": round(d1, 6),
        "symmetric_tail_precision": round((d10 + d1) / 2, 6),
        "wrong_d1_in_top": round(float(top["oracle_decile"].eq(1).mean()), 6),
        "wrong_d10_in_bottom": round(float(bottom["oracle_decile"].eq(10).mean()), 6),
        "top_mean_return": round(float(top["future_return"].mean()), 6),
        "bottom_mean_return": round(float(bottom["future_return"].mean()), 6),
        "long_short_spread": round(float(top["future_return"].mean() - bottom["future_return"].mean()), 6),
        "selected_top": len(top), "selected_bottom": len(bottom),
    }


def fold_metrics(frame: pd.DataFrame, protocol: RankingProtocol) -> dict[str, Any]:
    paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()].copy()
    evaluation = protocol.raw["evaluation"]
    global_pct = float(evaluation["global_tail_pct"])
    conditional_pct = float(evaluation["conditional_tail_pct"])
    oracle = paired.loc[paired["oracle_top20"]].copy()
    if oracle.empty or oracle["session_date"].nunique() < int(evaluation["min_test_sessions"]):
        raise RuntimeError("Pool Oracle OOS CN insuffisant")
    result = {
        "global": {
            "model": ranking_metrics(paired, score="rank_score", tail_pct=global_pct),
            "baseline": ranking_metrics(paired, score="baseline_score", tail_pct=global_pct),
        },
        "oracle_top20": {
            "model": ranking_metrics(oracle, score="rank_score", tail_pct=conditional_pct),
            "baseline": ranking_metrics(oracle, score="baseline_score", tail_pct=conditional_pct),
        },
        "valid_coverage": round(float(frame["target_quality_valid"].mean()), 6),
        "paired_coverage": round(float(len(paired) / len(frame)), 6),
        "oracle_pool_fraction_before_label_filter": round(float(frame["oracle_top20"].mean()), 6),
        "oracle_pool_evaluable_fraction": round(float(len(oracle) / max(1, int(frame["oracle_top20"].sum()))), 6),
        "prediction_coverage": round(float(frame["rank_score"].notna().mean()), 6),
    }
    for scope in ("global", "oracle_top20"):
        result[scope]["tail_precision_uplift"] = round(
            result[scope]["model"]["symmetric_tail_precision"]
            - result[scope]["baseline"]["symmetric_tail_precision"], 6
        )
    return result


def run(*, horizon: int, semester: str, model_name: str,
        config_path: Path = DEFAULT_CONFIG, output_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    protocol = RankingProtocol.load(config_path)
    oracle_protocol = OracleProtocol.load(ORACLE_CONFIG)
    if horizon not in protocol.raw["horizons"] or semester not in protocol.raw["test_semesters"] or model_name not in protocol.raw["models"]:
        raise ValueError("Horizon, semestre ou modèle ranking non pré-enregistré")
    sources, audit = _sources(oracle_protocol)
    source_hashes = [audit["implementation_sha256"], *(
        audit["yearly"][year - 2018]["horizons"][str(horizon)]["sha256"]
        for year in range(2018, int(semester[:4]) + 1)
    )]
    from modelFactory import cn_oracle_walk_forward as oracle_runner

    fingerprint = hashlib.sha256((
        _sha(config_path) + _sha(Path(__file__)) + _sha(ORACLE_CONFIG)
        + _sha(Path(oracle_runner.__file__)) + "".join(source_hashes)
    ).encode()).hexdigest()[:16]
    folder = output_root / f"{protocol.raw['experiment']}-{fingerprint}" / f"h{horizon}" / semester / model_name
    if (folder / "predictions.parquet").exists() or (folder / "report.json").exists():
        raise RuntimeError(f"Artefact ranking CN existant, écrasement refusé: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    frame = _load_frame(
        sources, horizon=horizon, features=oracle_protocol.raw["features"],
        semester=semester, max_train_rows=int(protocol.raw["max_train_rows"]),
        validation_sessions=int(protocol.raw["validation_sessions"]),
    )
    train, val, test, split = split_fold(
        frame, test_semester=semester,
        validation_sessions=int(protocol.raw["validation_sessions"]),
        min_train_sessions=int(protocol.raw["min_train_sessions"]),
        max_train_rows=int(protocol.raw["max_train_rows"]),
    )
    if not train["oracle_decile"].between(1, 10).all() or not val["oracle_decile"].between(1, 10).all():
        raise RuntimeError("Déciles de train/validation CN invalides")
    test, oracle_hashes = _attach_oracle_pool(test, horizon=horizon, semester=semester)
    LOGGER.info("CN Ranking H%s %s %s train=%d val=%d test=%d", horizon, semester,
                model_name, len(train), len(val), len(test))
    scores = _fit(model_name, train, val, test, protocol=protocol,
                  features=oracle_protocol.raw["features"], model_path=folder / "model")
    prediction = test[["market_code", "session_date", "instrument_id", "board_code", "cn_breadth_1",
                       "target_quality_valid", "target_quality_reason", "oracle_decile", "future_return",
                       "execution_data_eligible", "oracle_top20"]].copy()
    prediction["rank_score"] = scores
    prediction["baseline_score"] = pd.to_numeric(test[protocol.raw["baseline_score"]], errors="coerce").to_numpy()
    prediction["horizon"] = horizon
    prediction["test_semester"] = semester
    prediction["model_name"] = model_name
    if prediction["rank_score"].isna().any() or set(prediction["market_code"]) != {"CN_A"}:
        raise RuntimeError("Prédiction ranking CN absente ou contaminée")
    metrics = fold_metrics(prediction, protocol)
    report = {
        "status": "OOS_RESEARCH_ONLY", "market_code": "CN_A", "horizon": horizon,
        "test_semester": semester, "model_name": model_name,
        "protocol_sha256": _sha(config_path), "code_sha256": _sha(Path(__file__)),
        "oracle_protocol_sha256": _sha(ORACLE_CONFIG),
        "oracle_code_sha256": _sha(Path(oracle_runner.__file__)),
        "oracle_prediction_hashes": oracle_hashes,
        "label_audit_sha256": _sha(AUDIT_PATH), "fingerprint": fingerprint,
        "split": split, "metrics": metrics,
        "serving_enabled": False, "backtest_executed": False,
    }
    prediction_path, report_path = folder / "predictions.parquet", folder / "report.json"
    prediction.to_parquet(prediction_path, index=False)
    report["predictions_sha256"] = _sha(prediction_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--test-semester", required=True)
    parser.add_argument("--model", choices=["lightgbm", "catboost"], required=True)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    report = run(horizon=args.horizon, semester=args.test_semester,
                 model_name=args.model, config_path=args.config, output_root=args.output_root)
    print(json.dumps({"status": report["status"], "horizon": report["horizon"],
                      "semester": report["test_semester"], "model": report["model_name"],
                      "conditional_tail_uplift": report["metrics"]["oracle_top20"]["tail_precision_uplift"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
