"""Sprint 9-A : pilote supervisé Oracle H5 France, pas de serving ni confirmation 2026."""

from __future__ import annotations

import argparse
import hashlib
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
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from modelFactory.fr_feature_profile_freeze import FEATURES
from modelFactory.fr_labels_review import phase_mask
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256

LOGGER = logging.getLogger(__name__)


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    fixed = {
        "schema_version": 1,
        "profile": "fr_oracle_h5_pilot_v1",
        "market_code": "FR_EQ",
        "horizon": 5,
        "folds": [4, 5, 6],
        "development_end": "2025-12-31",
        "selection_fraction": 0.2,
        "min_cross_section": 20,
        "seed": 17,
        "threads": 2,
        "champion_selection": "validation_average_precision",
        "calibration": "none",
        "canonical_writes_enabled": False,
        "serving_enabled": False,
        "logistic": {"C": 1.0, "max_iter": 500},
        "trees": {
            "max_iter": 100,
            "learning_rate": 0.05,
            "max_leaf_nodes": 7,
            "max_depth": 3,
            "min_samples_leaf": 100,
            "l2_regularization": 1.0,
        },
        "pilot_gates": {
            "min_mean_daily_precision_delta": 0.02,
            "min_average_precision_delta": 0.01,
            "min_daily_lift": 1.10,
            "min_positive_folds": 2,
        },
    }
    # Explicit research extension; the original v1 contract remains frozen.
    if cfg.get("profile") == "fr_oracle_h5_fold7_repaired_v1":
        fixed.update(profile="fr_oracle_h5_fold7_repaired_v1", folds=[4, 5, 6, 7])
    if any(cfg.get(k) != v for k, v in fixed.items()):
        raise ValueError("Protocole du pilote figé : créer une autre expérience pour le modifier")
    return cfg


def deterministic_score(day: str, uid: str, seed: int) -> float:
    return int.from_bytes(hashlib.sha256(f"{seed}|{day}|{uid}".encode()).digest()[:8], "big") / 2**64


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame[list(FEATURES)].astype(float).copy()
    if not np.isfinite(x.to_numpy()).all() or x["traded_value_mean20_eur"].lt(0).any():
        raise ValueError("Features incomplètes/invalides dans le fit")
    x["traded_value_mean20_eur"] = np.log1p(x["traded_value_mean20_eur"])
    return x


def select_phase(frame: pd.DataFrame, fold: dict, phase: str, cfg: dict) -> pd.DataFrame:
    mask = (
        phase_mask(frame, fold, phase, cfg["development_end"])
        & frame["profile_row_ready"]
        & frame["oracle_extreme"].notna()
    )
    selected = frame.loc[mask].copy()
    count = selected.groupby("decision_session_date")["research_uid"].transform("size")
    return (
        selected.loc[count.ge(cfg["min_cross_section"])]
        .sort_values(["decision_session_date", "research_uid"], kind="stable")
        .reset_index(drop=True)
    )


def score_metrics(frame: pd.DataFrame, score: np.ndarray, cfg: dict) -> tuple[dict, pd.DataFrame]:
    if len(frame) != len(score) or not np.isfinite(score).all():
        raise ValueError("Scores absents ou non finis")
    working = frame[["decision_session_date", "research_uid", "oracle_extreme"]].copy()
    working["score"] = score
    working["tie"] = [
        deterministic_score(d, u, cfg["seed"])
        for d, u in zip(working["decision_session_date"], working["research_uid"], strict=True)
    ]
    daily = []
    for day, group in working.groupby("decision_session_date", sort=True):
        ordered = group.sort_values(["score", "tie", "research_uid"], ascending=[False, False, True], kind="stable")
        k = int(np.ceil(len(group) * cfg["selection_fraction"]))
        hits = int(ordered.iloc[:k]["oracle_extreme"].sum())
        positives = int(group["oracle_extreme"].sum())
        prevalence = positives / len(group)
        daily.append(
            {
                "day": day,
                "rows": len(group),
                "selected": k,
                "hits": hits,
                "precision": hits / k,
                "recall": hits / positives if positives else None,
                "prevalence": prevalence,
                "lift": hits / k / prevalence if prevalence else None,
            }
        )
    y = frame["oracle_extreme"].astype(int)
    days = pd.DataFrame(daily)
    result = {
        "rows": len(frame),
        "days": len(days),
        "positive_count": int(y.sum()),
        "prevalence": float(y.mean()),
        "auc": float(roc_auc_score(y, score)) if y.nunique() == 2 else None,
        "average_precision": float(average_precision_score(y, score)),
        "mean_daily_precision": float(days["precision"].mean()),
        "mean_daily_recall": float(days["recall"].mean()),
        "mean_daily_lift": float(days["lift"].mean()),
        "pooled_precision": float(days["hits"].sum() / days["selected"].sum()),
        "score_quantiles": {str(q): float(np.quantile(score, q)) for q in (0, 0.1, 0.5, 0.9, 1)},
    }
    return result, days


def choose_champion(validation: dict) -> str:
    # Dict ordre fixe, priorité logistique en cas d'égalité.
    return max(("logistic", "trees"), key=lambda name: validation[name]["average_precision"])


def verdict(folds: list[dict], cfg: dict) -> dict:
    gates = cfg["pilot_gates"]
    deltas = {}
    for baseline in ("atr", "volatility"):
        deltas[baseline] = {
            "precision_delta": float(
                np.mean(
                    [
                        f["test"][f["champion"]]["mean_daily_precision"] - f["test"][baseline]["mean_daily_precision"]
                        for f in folds
                    ]
                )
            ),
            "ap_delta": float(
                np.mean(
                    [
                        f["test"][f["champion"]]["average_precision"] - f["test"][baseline]["average_precision"]
                        for f in folds
                    ]
                )
            ),
        }
    positive = sum(
        all(
            f["test"][f["champion"]]["mean_daily_precision"] > f["test"][b]["mean_daily_precision"]
            for b in ("atr", "volatility")
        )
        for f in folds
    )
    lift = float(np.mean([f["test"][f["champion"]]["mean_daily_lift"] for f in folds]))
    passed = (
        positive >= gates["min_positive_folds"]
        and lift >= gates["min_daily_lift"]
        and all(
            d["precision_delta"] >= gates["min_mean_daily_precision_delta"]
            and d["ap_delta"] >= gates["min_average_precision_delta"]
            for d in deltas.values()
        )
    )
    return {
        "verdict": "PILOT_SIGNAL_REQUIRES_CONFIRMATION" if passed else "NO_GO_INCREMENTAL_PILOT",
        "mean_deltas": deltas,
        "positive_folds_against_both": positive,
        "mean_daily_lift": lift,
    }


def run(config_path: Path, output_root: Path) -> dict:
    cfg = load_config(config_path)
    report_path = ROOT / cfg["labels_report"]
    labels_report = json.loads(report_path.read_text(encoding="utf-8"))
    support_path = ROOT / cfg["support_report"]
    support = json.loads(support_path.read_text(encoding="utf-8"))
    label_path, price_path = report_path.with_name("labels.parquet"), ROOT / cfg["price_panel"]
    if _sha256(label_path) != cfg["labels_sha256"] or _sha256(price_path) != cfg["price_sha256"]:
        raise ValueError("Sources différentes du gel")
    if support["complete_data_support_folds"]["price_only"]["5"] != cfg["folds"]:
        raise ValueError("Folds admissibles différents du contrat")
    if (
        support["source_hashes"]["labels"] != cfg["labels_sha256"]
        or support["source_hashes"]["price"] != cfg["price_sha256"]
    ):
        raise ValueError("Provenances du support divergentes")
    labels = pd.read_parquet(label_path)
    # Filtre avant toute sélection, statistique ou fit. Pas de résultat de confirmation 2026.
    labels = labels.loc[labels["horizon"].eq(5) & labels["decision_session_date"].le(cfg["development_end"])].copy()
    price = pd.read_parquet(price_path)
    price = price.loc[price["decision_session_date"].le(cfg["development_end"])]
    keys = ["decision_session_date", "research_uid"]
    if labels.duplicated(keys).any() or price.duplicated(keys).any():
        raise ValueError("Clés pilote dupliquées")
    if (
        pd.to_datetime(price["max_input_available_at"], utc=True) > pd.to_datetime(price["decision_at"], utc=True)
    ).any():
        raise ValueError("Fuite feature")
    frame = labels.merge(
        price[keys + list(FEATURES) + ["profile_row_ready"]], on=keys, validate="one_to_one", indicator=True
    )
    if not frame["_merge"].eq("both").all():
        raise ValueError("Labels sans features")
    fingerprint = _fingerprint(
        {
            "cfg": cfg,
            "code": _sha256(Path(__file__)),
            "support": _sha256(support_path),
            "labels_report": _sha256(report_path),
            "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        }
    )
    destination = output_root / f"fr-oracle-h5-{fingerprint[:12]}"
    if destination.exists():
        raise ValueError(f"Run déjà présent, conservé : {destination}")
    destination.mkdir(parents=True)
    _atomic_json(destination / "protocol.json", {"cfg": cfg, "features": list(FEATURES), "fingerprint": fingerprint})
    fold_results, predictions, daily_records = [], [], []
    with threadpool_limits(limits=cfg["threads"]):
        for identifier in cfg["folds"]:
            fold = next(f for f in labels_report["fold_plan"] if f["fold"] == identifier)
            phases = {phase: select_phase(frame, fold, phase, cfg) for phase in ("train", "validation", "test")}
            for phase, data in phases.items():
                expected = next(
                    r
                    for r in support["fold_support"]
                    if r["fold"] == identifier
                    and r["horizon"] == 5
                    and r["phase"] == phase
                    and r["profile"] == "price_only"
                )
                if (
                    len(data) != expected["oracle_rows"]
                    or data["decision_session_date"].nunique() != expected["usable_sessions"]
                ):
                    raise ValueError("Support effectif divergent de 8-B")
            LOGGER.info(
                "fold=%s train=%s validation=%s test=%s",
                identifier,
                *(len(phases[p]) for p in ("train", "validation", "test")),
            )
            models = {
                "logistic": make_pipeline(
                    StandardScaler(), LogisticRegression(**cfg["logistic"], random_state=cfg["seed"])
                ),
                "trees": HistGradientBoostingClassifier(**cfg["trees"], early_stopping=False, random_state=cfg["seed"]),
            }
            for name, model in models.items():
                model.fit(feature_matrix(phases["train"]), phases["train"]["oracle_extreme"].astype(int))
                joblib.dump(model, destination / f"fold{identifier}_{name}.joblib")
            phase_metrics = {}
            for phase in ("validation", "test"):
                data = phases[phase]
                scores = {
                    "atr": data["atr20_pct"].to_numpy(),
                    "volatility": data["realized_vol20"].to_numpy(),
                    "random": np.array(
                        [
                            deterministic_score(d, u, cfg["seed"])
                            for d, u in zip(data["decision_session_date"], data["research_uid"], strict=True)
                        ]
                    ),
                }
                scores.update({name: model.predict_proba(feature_matrix(data))[:, 1] for name, model in models.items()})
                phase_metrics[phase] = {}
                for name, score in scores.items():
                    metrics, days = score_metrics(data, score, cfg)
                    phase_metrics[phase][name] = metrics
                    days["fold"], days["phase"], days["model"] = identifier, phase, name
                    daily_records.append(days)
                pred = data[keys + ["provider_symbol", "oracle_extreme", "label_available_at"]].copy()
                pred["fold"], pred["phase"] = identifier, phase
                for name, score in scores.items():
                    pred[f"score_{name}"] = score
                predictions.append(pred)
            champion = choose_champion(phase_metrics["validation"])
            fold_results.append({"fold": identifier, "dates": fold, "champion": champion, **phase_metrics})
            _atomic_json(destination / f"fold{identifier}_metrics.json", fold_results[-1])
            LOGGER.info(
                "fold=%s champion=%s test_precision=%.4f",
                identifier,
                champion,
                phase_metrics["test"][champion]["mean_daily_precision"],
            )
    pd.concat(predictions, ignore_index=True).to_parquet(destination / "predictions.parquet", index=False)
    pd.concat(daily_records, ignore_index=True).to_parquet(destination / "daily_metrics.parquet", index=False)
    summary = verdict(fold_results, cfg)
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "features": list(FEATURES),
        "folds": fold_results,
        **summary,
        "confirmation_evaluated": False,
        "serving_enabled": False,
        "canonical_writes": False,
        "economic_validation": False,
        "prediction_sha256": _sha256(destination / "predictions.parquet"),
        "limitations": [
            "DEVELOPMENT_OOF_ONLY",
            "RESEARCH_J1_ASSUMPTION",
            "RAW_RETURNS_NO_COSTS",
            "LIMITED_DELISTED_SUPPORT",
            "DOCUMENTARY_REVIEW_PENDING",
        ],
    }
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/research_fr/oracle_h5_pilot_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/research/oracle_h5_pilot")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run(args.profile, args.output_root)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "artifact_directory",
                    "verdict",
                    "mean_deltas",
                    "positive_folds_against_both",
                    "mean_daily_lift",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
