"""Sprint 10-B: Oracle amplitude CN_A walk-forward, research-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, roc_auc_score

from modelFactory.cn_feature_panel import ROOT

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint10b_oracle.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "oracle" / "sprint10b"
FEATURE_ROOT = ROOT / "artifacts" / "cn" / "features" / "cn_price_v1"
LABEL_ROOT = ROOT / "artifacts" / "cn" / "labels" / "cn_oracle_labels_v1"
AUDIT_PATH = ROOT / "artifacts" / "cn" / "labels" / "sprint10a_audit_2018_2025.json"
META = ["market_code", "session_date", "instrument_id", "decision_at", "board_code"]
LABEL = ["session_date", "instrument_id", "available_at_utc", "target_quality_valid",
         "target_quality_reason", "oracle_extreme20", "oracle_decile", "future_return",
         "execution_data_eligible"]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Protocol:
    raw: dict[str, Any]
    path: Path

    @classmethod
    def load(cls, path: Path) -> Protocol:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        expected = {
            "experiment": "cn_oracle_sprint10b_v1", "market_code": "CN_A",
            "feature_profile": "cn_price_v1", "label_profile": "cn_oracle_labels_v1",
        }
        if any(raw.get(key) != value for key, value in expected.items()):
            raise ValueError("Protocole Sprint 10-B CN_A invalide")
        if raw.get("years") != list(range(2018, 2026)) or raw.get("horizons") != [5, 10, 15, 20]:
            raise ValueError("Années ou horizons hors protocole CN")
        if raw.get("models") != ["lightgbm", "catboost"] or len(set(raw.get("features", []))) != len(raw.get("features", [])):
            raise ValueError("Modèles ou features CN invalides")
        if raw.get("baseline_score") not in raw["features"]:
            raise ValueError("Baseline absente du panel")
        if int(raw["min_rank_cross_section"]) < 20 or int(raw["max_train_rows"]) < 1000:
            raise ValueError("Taille de coupe ou entraînement CN invalide")
        return cls(raw=raw, path=path)


def _report_for_year(folder: Path, year: int, implementation_sha: str) -> tuple[Path, dict[str, Any]]:
    matches = []
    for path in folder.glob(f"*-{year}0101-{year}1231-*/report.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("implementation_sha256") == implementation_sha:
            matches.append((path, report))
    if len(matches) != 1:
        raise RuntimeError(f"{year}: {len(matches)} rapports CN pour le code courant, attendu 1")
    return matches[0]


def _sources(protocol: Protocol) -> tuple[dict[int, tuple[Path, Path]], dict[str, Any]]:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_LABELS_PRICE_ONLY" or audit.get("years_found") != 8:
        raise RuntimeError("Gate Sprint 10-A non validé")
    if audit.get("implementation_sha256") != _sha(ROOT / "modelFactory" / "cn_oracle_labels.py"):
        raise RuntimeError("Code de labels différent de l'audit")
    feat_sha = _sha(ROOT / "modelFactory" / "cn_feature_panel.py")
    result = {}
    for year in protocol.raw["years"]:
        feature_report, feature = _report_for_year(FEATURE_ROOT, year, feat_sha)
        label_report, label = _report_for_year(LABEL_ROOT, year, audit["implementation_sha256"])
        if feature["panel_sha256"] != label["feature_panel_sha256"]:
            raise RuntimeError(f"{year}: features et labels CN ne correspondent pas")
        if int(feature["rows"]) != int(label["candidate_rows"]):
            raise RuntimeError(f"{year}: population feature/label différente")
        feature_path = feature_report.parent / "panel.parquet"
        if _sha(feature_path) != feature["panel_sha256"]:
            raise RuntimeError(f"{year}: SHA features différent")
        result[year] = feature_path, label_report.parent
    return result, audit


def semester_bounds(name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if len(name) != 6 or name[4] != "H" or name[-1] not in "12":
        raise ValueError(f"Semestre invalide: {name}")
    year = int(name[:4])
    if year not in range(2022, 2026):
        raise ValueError("Sprint 10-B limité aux tests 2022–2025")
    return ((pd.Timestamp(year, 1, 1), pd.Timestamp(year, 6, 30)) if name[-1] == "1"
            else (pd.Timestamp(year, 7, 1), pd.Timestamp(year, 12, 31)))


def _training_sample(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    if len(frame) <= limit:
        return frame
    keys = pd.util.hash_pandas_object(frame[["session_date", "instrument_id"]], index=False).to_numpy(dtype="uint64")
    positions = np.argpartition(keys, limit - 1)[:limit]
    return frame.iloc[np.sort(positions)].copy()


def split_fold(frame: pd.DataFrame, *, test_semester: str, validation_sessions: int,
               min_train_sessions: int, max_train_rows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    start, end = semester_bounds(test_semester)
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(frame["session_date"]).unique()))
    prior = dates[dates < start]
    if len(prior) < validation_sessions + min_train_sessions:
        raise RuntimeError("Historique CN insuffisant avant le semestre test")
    val_start = prior[-validation_sessions]
    test = frame.loc[frame["session_date"].between(start, end)].copy()
    val = frame.loc[frame["session_date"].between(val_start, start - pd.Timedelta(nanoseconds=1))].copy()
    train = frame.loc[frame["session_date"] < val_start].copy()
    if test.empty or val["session_date"].nunique() < validation_sessions:
        raise RuntimeError("Test ou validation CN incomplet")
    train_boundary = pd.to_datetime(val["decision_at"]).min()
    val_boundary = pd.to_datetime(test["decision_at"]).min()
    train = train.loc[train["target_quality_valid"] & (train["available_at_utc"] < train_boundary)]
    val = val.loc[val["target_quality_valid"] & (val["available_at_utc"] < val_boundary)]
    if train["session_date"].nunique() < min_train_sessions or val.empty:
        raise RuntimeError("Purge des labels: entraînement/validation CN insuffisants")
    train = _training_sample(train, max_train_rows)
    if not (train["available_at_utc"] < train_boundary).all() or not (val["available_at_utc"] < val_boundary).all():
        raise RuntimeError("Fuite temporelle de labels CN")
    return train, val, test, {
        "test_semester": test_semester, "validation_start": str(val_start.date()),
        "test_start": str(start.date()), "test_end": str(end.date()),
        "train_rows": len(train), "validation_rows": len(val), "test_rows": len(test),
        "train_label_max_available_at": str(train["available_at_utc"].max()),
        "validation_label_max_available_at": str(val["available_at_utc"].max()),
    }


def _load_frame(sources: dict[int, tuple[Path, Path]], *, horizon: int,
                features: list[str], semester: str, max_train_rows: int,
                validation_sessions: int) -> pd.DataFrame:
    test_start, test_end = semester_bounds(semester)
    last_year = int(semester[:4])
    prior_dates = set()
    for year in range(2018, last_year + 1):
        dates = pd.read_parquet(sources[year][0], columns=["session_date"])["session_date"]
        prior_dates.update(pd.to_datetime(dates.loc[dates < test_start]).unique())
    ordered_dates = sorted(prior_dates)
    if len(ordered_dates) < validation_sessions:
        raise RuntimeError("Pas assez de séances CN avant le test")
    val_start = ordered_dates[-validation_sessions]
    train_years = max(1, last_year - 2018 + 1)
    per_year_cap = max(1000, math.ceil(max_train_rows / train_years))
    pieces = []
    for year in range(2018, last_year + 1):
        feature_path, labels_folder = sources[year]
        feature = pd.read_parquet(feature_path, columns=META + features)
        label = pd.read_parquet(labels_folder / f"h{horizon}.parquet", columns=LABEL)
        if len(feature) != len(label):
            raise RuntimeError(f"{year} H{horizon}: population différente")
        part = feature.merge(label, on=["session_date", "instrument_id"], validate="one_to_one")
        if len(part) != len(feature) or set(part["market_code"]) != {"CN_A"}:
            raise RuntimeError(f"{year} H{horizon}: jointure CN incorrecte")
        train = part.loc[part["session_date"] < val_start]
        remaining = part.loc[part["session_date"].between(val_start, test_end)]
        pieces.append(pd.concat([_training_sample(train, per_year_cap), remaining], ignore_index=True))
    frame = pd.concat(pieces, ignore_index=True)
    for name in ("session_date", "decision_at", "available_at_utc"):
        frame[name] = pd.to_datetime(frame[name])
    if (frame["available_at_utc"].notna() & (frame["available_at_utc"] <= frame["decision_at"])).any():
        raise RuntimeError("Label CN déjà disponible à la décision")
    return frame


def _matrix(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    values = frame[features].apply(pd.to_numeric, errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).astype("float32")


def _fit(model_name: str, train: pd.DataFrame, val: pd.DataFrame,
         test: pd.DataFrame, protocol: Protocol, model_path: Path) -> np.ndarray:
    features = protocol.raw["features"]
    x_train, x_val, x_test = (_matrix(part, features) for part in (train, val, test))
    y_train = train["oracle_extreme20"].astype(int).to_numpy()
    y_val = val["oracle_extreme20"].astype(int).to_numpy()
    if len(np.unique(y_train)) < 2 or len(np.unique(y_val)) < 2:
        raise RuntimeError("Une classe Oracle manque au train ou à la validation")
    if model_name == "lightgbm":
        import lightgbm as lgb

        params = protocol.raw["lightgbm"].copy()
        stop = int(params.pop("early_stopping_rounds"))
        model = lgb.LGBMClassifier(
            **params, random_state=protocol.raw["seed"], n_jobs=4,
            verbosity=-1, deterministic=True, force_col_wise=True,
        )
        model.fit(x_train, y_train, eval_set=[(x_val, y_val)], eval_metric="auc",
                  callbacks=[lgb.early_stopping(stop, verbose=False)])
        model.booster_.save_model(str(model_path.with_suffix(".txt")))
    elif model_name == "catboost":
        from catboost import CatBoostClassifier

        params = protocol.raw["catboost"].copy()
        stop = int(params.pop("early_stopping_rounds"))
        model = CatBoostClassifier(
            **params, loss_function="Logloss", eval_metric="AUC",
            random_seed=protocol.raw["seed"], thread_count=4,
            od_type="Iter", od_wait=stop, verbose=False,
            allow_writing_files=False,
        )
        model.fit(x_train, y_train, eval_set=(x_val, y_val), use_best_model=True)
        model.save_model(str(model_path.with_suffix(".cbm")))
    else:
        raise ValueError(f"Modèle non pré-enregistré: {model_name}")
    return model.predict_proba(x_test)[:, 1].astype("float32")


def _top_rows(frame: pd.DataFrame, score: str, top_pct: float) -> pd.DataFrame:
    ordered = frame.sort_values(["session_date", score, "instrument_id"],
                                ascending=[True, False, True], kind="stable")
    rank = ordered.groupby("session_date", sort=False).cumcount()
    size = ordered.groupby("session_date", sort=False)["instrument_id"].transform("size")
    return ordered.loc[rank < np.maximum(1, np.ceil(size * top_pct).astype(int))]


def score_metrics(frame: pd.DataFrame, *, score: str, top_pct: float) -> dict[str, Any]:
    valid = frame.loc[frame["target_quality_valid"] & frame[score].notna()].copy()
    if valid.empty:
        raise RuntimeError("Aucune prédiction CN évaluable")
    y = valid["oracle_extreme20"].astype(int)
    selected = _top_rows(valid, score, top_pct)
    return {
        "rows": len(valid), "sessions": int(valid["session_date"].nunique()),
        "auc": round(float(roc_auc_score(y, valid[score])), 6) if y.nunique() == 2 else None,
        "average_precision": round(float(average_precision_score(y, valid[score])), 6),
        "prevalence": round(float(y.mean()), 6),
        "precision_top20": round(float(selected["oracle_extreme20"].astype(int).mean()), 6),
        "lift_top20": round(float(selected["oracle_extreme20"].astype(int).mean() / y.mean()), 6),
        "mean_abs_return_top20": round(float(selected["future_return"].abs().mean()), 6),
        "selected": len(selected),
        "d1_selected": int(selected["oracle_decile"].eq(1).sum()),
        "d10_selected": int(selected["oracle_decile"].eq(10).sum()),
    }


def fold_metrics(frame: pd.DataFrame, protocol: Protocol) -> dict[str, Any]:
    top = float(protocol.raw["evaluation"]["top_pct"])
    paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()].copy()
    metrics = {"model": score_metrics(paired, score="oracle_score", top_pct=top),
               "baseline_atr": score_metrics(paired, score="baseline_score", top_pct=top)}
    metrics["precision_uplift"] = round(
        metrics["model"]["precision_top20"] - metrics["baseline_atr"]["precision_top20"], 6
    )
    minimum = int(protocol.raw["evaluation"]["min_subgroup_rows"])
    valid = paired
    groups = {
        "board": valid["board_code"],
        "year": valid["session_date"].dt.year.astype(str),
        "semester": valid["session_date"].dt.year.astype(str) + "H" +
                    np.where(valid["session_date"].dt.month.le(6), "1", "2"),
        "breadth_regime": np.where(valid["cn_breadth_1"].lt(0.5), "breadth_below_50pct", "breadth_at_least_50pct"),
    }
    for name, grouping in groups.items():
        subgroup = {}
        for value, sub in valid.groupby(grouping, sort=True):
            if len(sub) >= minimum and sub["session_date"].nunique() >= 10:
                subgroup[str(value)] = score_metrics(sub, score="oracle_score", top_pct=top)
        metrics[name] = subgroup
    metrics["valid_coverage"] = round(float(frame["target_quality_valid"].mean()), 6)
    metrics["paired_evaluation_coverage"] = round(float(len(paired) / len(frame)), 6)
    metrics["prediction_coverage"] = round(float(frame["oracle_score"].notna().mean()), 6)
    metrics["execution_eligible_fraction"] = round(float(frame["execution_data_eligible"].mean()), 6)
    return metrics


def run(*, config_path: Path = DEFAULT_CONFIG, output_root: Path = DEFAULT_OUTPUT,
        horizon: int, semester: str, model_name: str) -> dict[str, Any]:
    protocol = Protocol.load(config_path)
    if horizon not in protocol.raw["horizons"] or semester not in protocol.raw["test_semesters"] or model_name not in protocol.raw["models"]:
        raise ValueError("Horizon, semestre ou modèle non pré-enregistré")
    sources, audit = _sources(protocol)
    source_hashes = [audit["implementation_sha256"], *(
        audit["yearly"][year - 2018]["horizons"][str(horizon)]["sha256"]
        for year in range(2018, int(semester[:4]) + 1)
    )]
    fingerprint = hashlib.sha256((
        _sha(config_path) + _sha(Path(__file__)) + "".join(source_hashes)
    ).encode()).hexdigest()[:16]
    folder = output_root / f"{protocol.raw['experiment']}-{fingerprint}" / f"h{horizon}" / semester / model_name
    if (folder / "predictions.parquet").exists() or (folder / "report.json").exists():
        raise RuntimeError(f"Artefact OOS existant, écrasement refusé: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    frame = _load_frame(sources, horizon=horizon, features=protocol.raw["features"],
                        semester=semester, max_train_rows=int(protocol.raw["max_train_rows"]),
                        validation_sessions=int(protocol.raw["validation_sessions"]))
    train, val, test, split = split_fold(
        frame, test_semester=semester,
        validation_sessions=int(protocol.raw["validation_sessions"]),
        min_train_sessions=int(protocol.raw["min_train_sessions"]),
        max_train_rows=int(protocol.raw["max_train_rows"]),
    )
    LOGGER.info("CN Oracle H%s %s %s train=%d val=%d test=%d", horizon, semester,
                model_name, len(train), len(val), len(test))
    scores = _fit(model_name, train, val, test, protocol, folder / "model")
    predictions = test[["market_code", "session_date", "instrument_id", "board_code",
                        "cn_breadth_1", "target_quality_valid", "target_quality_reason",
                        "oracle_extreme20", "oracle_decile", "future_return",
                        "execution_data_eligible"]].copy()
    predictions["oracle_score"] = scores
    predictions["baseline_score"] = pd.to_numeric(test[protocol.raw["baseline_score"]], errors="coerce").to_numpy()
    predictions["horizon"] = horizon
    predictions["test_semester"] = semester
    predictions["model_name"] = model_name
    predictions["market_code"] = "CN_A"
    if predictions["oracle_score"].isna().any():
        raise RuntimeError("Score Oracle manquant dans le test CN")
    metrics = fold_metrics(predictions, protocol)
    report = {
        "status": "OOS_RESEARCH_ONLY", "market_code": "CN_A", "horizon": horizon,
        "test_semester": semester, "model_name": model_name,
        "protocol_sha256": _sha(config_path), "code_sha256": _sha(Path(__file__)),
        "label_audit_sha256": _sha(AUDIT_PATH), "fingerprint": fingerprint,
        "split": split, "metrics": metrics, "training_oracle_only": True,
        "serving_enabled": False, "backtest_executed": False,
    }
    prediction_path, report_path = folder / "predictions.parquet", folder / "report.json"
    if prediction_path.exists() or report_path.exists():
        raise RuntimeError(f"Artefact OOS existant, écrasement refusé: {folder}")
    predictions.to_parquet(prediction_path, index=False)
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
    result = run(config_path=args.config, output_root=args.output_root,
                 horizon=args.horizon, semester=args.test_semester, model_name=args.model)
    print(json.dumps({"status": result["status"], "horizon": result["horizon"],
                      "test_semester": result["test_semester"], "model": result["model_name"],
                      "precision_uplift": result["metrics"]["precision_uplift"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
