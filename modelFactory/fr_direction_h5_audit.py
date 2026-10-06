"""Sprint 10-A: frozen price-only directional references inside FR Oracle OOF TOP20."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

from modelFactory.fr_labels_review import phase_mask
from modelFactory.fr_oracle_h5_pilot import choose_champion, deterministic_score
from modelFactory.fr_oracle_h5_pilot import load_config as load_oracle_config
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256

LOG = logging.getLogger(__name__)
KEYS = ["decision_session_date", "research_uid"]


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    fixed = {
        "schema_version": 1,
        "profile": "fr_direction_h5_audit_v1",
        "market_code": "FR_EQ",
        "horizon": 5,
        "folds": [4, 5, 6],
        "development_end": "2025-12-31",
        "oracle_fraction": 0.2,
        "side_fraction": 0.2,
        "seed": 17,
        "scores": ["random", "return_5", "return_20"],
        "support": {"min_dates": 30, "min_tail_per_class": 30},
        "gates": {
            "min_mean_tail_auc": 0.53,
            "min_mean_daily_ic": 0.03,
            "min_mean_daily_spread": 0.002,
            "min_positive_folds": 2,
        },
        "canonical_writes_enabled": False,
        "serving_enabled": False,
        "confirmation_evaluated": False,
    }
    if any(cfg.get(k) != v for k, v in fixed.items()):
        raise ValueError("Frozen Sprint 10-A protocol changed")
    return cfg


def rank_selection(
    frame: pd.DataFrame, column: str, fraction: float, seed: int, ascending: bool = False
) -> pd.DataFrame:
    if not 0 < fraction <= 1 or frame.duplicated(KEYS).any():
        raise ValueError("Invalid fraction or duplicate date/UID")
    if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite ranking score")
    work = frame.copy()
    work["_tie"] = [
        deterministic_score(d, u, seed) for d, u in zip(work.decision_session_date, work.research_uid, strict=True)
    ]
    parts = []
    for _, group in work.groupby("decision_session_date", sort=True):
        k = int(np.ceil(len(group) * fraction))
        order = group.sort_values(
            [column, "_tie", "research_uid"], ascending=[ascending, ascending, not ascending], kind="stable"
        )
        parts.append(order.iloc[:k].drop(columns="_tie"))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[:0].copy()


def safe_auc(target: pd.Series, scores: pd.Series) -> float | None:
    return float(roc_auc_score(target.astype(int), scores.astype(float))) if target.nunique() == 2 else None


def evaluate(pool: pd.DataFrame, column: str, cfg: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    long = rank_selection(pool, column, cfg["side_fraction"], cfg["seed"])
    short = rank_selection(pool, column, cfg["side_fraction"], cfg["seed"], ascending=True)
    if set(map(tuple, long[KEYS].to_numpy())) & set(map(tuple, short[KEYS].to_numpy())):
        raise ValueError("LONG/SHORT selections overlap: insufficient pool or tied scores")
    records = []
    for day, group in pool.groupby("decision_session_date", sort=True):
        selected_long = long[long.decision_session_date.eq(day)]
        s = short[short.decision_session_date.eq(day)]
        ic = (
            group[column].corr(group.future_return, method="spearman")
            if group[column].nunique() > 1 and group.future_return.nunique() > 1
            else None
        )
        long_return, short_return = float(selected_long.future_return.mean()), float(-s.future_return.mean())
        known, known_long, known_short = group.decile.dropna(), selected_long.decile.dropna(), s.decile.dropna()
        records.append(
            {
                "day": day,
                "candidates": len(group),
                "long_count": len(selected_long),
                "short_count": len(s),
                "decile_known": len(known),
                "long_decile_known": len(known_long),
                "short_decile_known": len(known_short),
                "base_d10": float(known.eq(10).mean()) if len(known) else None,
                "base_d1": float(known.eq(1).mean()) if len(known) else None,
                "base_long_return": float(group.future_return.mean()),
                "base_short_return": float(-group.future_return.mean()),
                "precision_d10": float(known_long.eq(10).mean()) if len(known_long) else None,
                "precision_d1": float(known_short.eq(1).mean()) if len(known_short) else None,
                "long_positive_fraction": float(selected_long.future_return.gt(0).mean()),
                "short_positive_fraction": float(s.future_return.lt(0).mean()),
                "long_return": long_return,
                "short_return": short_return,
                "spread": long_return + short_return,
                "ic": ic,
            }
        )
    daily = pd.DataFrame(records)
    tails = pool[pool.decile.isin([1, 10])]
    labelled = pool[pool.decile.notna()]
    support = {
        "dates": int(pool.decision_session_date.nunique()),
        "candidates": len(pool),
        "d1": int(pool.decile.eq(1).sum()),
        "d10": int(pool.decile.eq(10).sum()),
        "unknown_deciles": int(pool.decile.isna().sum()),
    }
    admitted = (
        support["dates"] >= cfg["support"]["min_dates"]
        and min(support["d1"], support["d10"]) >= cfg["support"]["min_tail_per_class"]
    )
    metrics = {
        "support": support,
        "support_admitted": admitted,
        "tail_auc": safe_auc(tails.decile.eq(10), tails[column]),
        "d10_vs_rest_auc": safe_auc(labelled.decile.eq(10), labelled[column]),
        "d1_vs_rest_auc": safe_auc(labelled.decile.eq(1), -labelled[column]),
        "daily_ic_valid_days": int(daily.ic.notna().sum()),
        "means": {c: float(daily[c].mean()) if daily[c].notna().any() else None for c in records[0] if c != "day"},
        "top_long_symbols": long.provider_symbol.value_counts().head(10).to_dict(),
        "top_short_symbols": short.provider_symbol.value_counts().head(10).to_dict(),
    }
    curves = []
    ranked = pool[column].rank(method="average", pct=True)
    bins = np.minimum(np.ceil(ranked * 5), 5).astype(int)
    for bucket, group in pool.groupby(bins):
        curves.append(
            {
                "bucket": int(bucket),
                "rows": len(group),
                "decile_known": int(group.decile.notna().sum()),
                "d10_rate": float(group.decile.dropna().eq(10).mean()) if group.decile.notna().any() else None,
                "d1_rate": float(group.decile.dropna().eq(1).mean()) if group.decile.notna().any() else None,
                "positive_return_rate": float(group.future_return.gt(0).mean()),
                "mean_return": float(group.future_return.mean()),
                "score_min": float(group[column].min()),
                "score_max": float(group[column].max()),
            }
        )
    # Scores are rankings, not calibrated probabilities; bins are descriptive quintiles.
    return metrics, daily, pd.DataFrame(curves)


def verdict(results: list[dict], cfg: dict) -> dict:
    output = {}
    for score in cfg["scores"]:
        rows = [r for r in results if r["score"] == score]
        if len(rows) != len(cfg["folds"]) or not all(r["metrics"]["support_admitted"] for r in rows):
            output[score] = {"verdict": "BLOCKED_DIRECTION_SUPPORT"}
            continue
        aucs = [r["metrics"]["tail_auc"] for r in rows]
        ics = [r["metrics"]["means"]["ic"] for r in rows]
        spreads = [r["metrics"]["means"]["spread"] for r in rows]
        if any(v is None for v in aucs + ics + spreads):
            output[score] = {"verdict": "BLOCKED_DIRECTION_METRICS"}
            continue
        means = {
            "tail_auc": float(np.mean(aucs)),
            "daily_ic": float(np.mean(ics)),
            "daily_spread": float(np.mean(spreads)),
        }
        positive = sum(a > 0.5 and i > 0 and s > 0 for a, i, s in zip(aucs, ics, spreads, strict=True))
        gate = cfg["gates"]
        passed = (
            means["tail_auc"] >= gate["min_mean_tail_auc"]
            and means["daily_ic"] >= gate["min_mean_daily_ic"]
            and means["daily_spread"] >= gate["min_mean_daily_spread"]
            and positive >= gate["min_positive_folds"]
        )
        output[score] = {
            "verdict": "HEURISTIC_SIGNAL_REQUIRES_CONFIRMATION" if passed else "NO_GO_FROZEN_REFERENCE",
            "mean_fold_metrics": means,
            "positive_folds": positive,
        }
    return output


def run(path: Path, output_root: Path) -> dict:
    cfg = load_config(path)
    oracle_cfg = load_oracle_config(ROOT / cfg["oracle_profile"])
    source = ROOT / cfg["oracle_source"]
    source_report = json.loads((source / "report.json").read_text(encoding="utf-8"))
    if source_report["config"] != oracle_cfg or source_report.get("confirmation_evaluated") is not False:
        raise ValueError("Oracle source protocol differs from frozen development-only pilot")
    predictions_path = source / "predictions.parquet"
    if (
        _sha256(predictions_path) != cfg["oracle_prediction_sha256"]
        or source_report["prediction_sha256"] != cfg["oracle_prediction_sha256"]
    ):
        raise ValueError("Oracle predictions differ from frozen source")
    label_report_path = ROOT / oracle_cfg["labels_report"]
    label_path, price_path = label_report_path.with_name("labels.parquet"), ROOT / oracle_cfg["price_panel"]
    if _sha256(label_path) != oracle_cfg["labels_sha256"] or _sha256(price_path) != oracle_cfg["price_sha256"]:
        raise ValueError("Frozen label/price source changed")
    labels_report = json.loads(label_report_path.read_text(encoding="utf-8"))
    labels = pd.read_parquet(label_path)
    labels = labels[labels.horizon.eq(5) & labels.decision_session_date.le(cfg["development_end"])]
    prices = pd.read_parquet(price_path)
    prices = prices[prices.decision_session_date.le(cfg["development_end"])]
    if (pd.to_datetime(prices.max_input_available_at, utc=True) > pd.to_datetime(prices.decision_at, utc=True)).any():
        raise ValueError("Future feature availability")
    predictions = pd.read_parquet(predictions_path)
    predictions = predictions[predictions.phase.eq("test")].copy()
    if predictions.duplicated(KEYS).any() or labels.duplicated(KEYS).any() or prices.duplicated(KEYS).any():
        raise ValueError("Duplicate source keys")
    if set(predictions.fold.unique()) != set(cfg["folds"]):
        raise ValueError("Unexpected Oracle test folds")
    frame = predictions.merge(
        labels[KEYS + ["future_return", "decile", "decile_state", "path_state", "label_available_session_date"]],
        on=KEYS,
        validate="one_to_one",
        how="left",
    )
    frame = frame.merge(
        prices[KEYS + ["return_5", "return_20", "profile_row_ready"]], on=KEYS, validate="one_to_one", how="left"
    )
    if (
        frame[["future_return", "return_5", "return_20"]].isna().any().any()
        or not frame.profile_row_ready.eq(True).all()
    ):
        raise ValueError("Incomplete directional join; do not silently change Oracle pool")
    if (frame.decile.isna() & ~frame.decile_state.eq("TIE_BOUNDARY")).any():
        raise ValueError("Unexpected unknown decile state")
    fingerprint = _fingerprint(
        {
            "cfg": cfg,
            "code": _sha256(Path(__file__)),
            "oracle_report": _sha256(source / "report.json"),
            "labels": oracle_cfg["labels_sha256"],
            "price": oracle_cfg["price_sha256"],
        }
    )
    destination = output_root / f"fr-direction-h5-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=False)
    _atomic_json(destination / "protocol.json", {"cfg": cfg, "fingerprint": fingerprint})
    results, daily_parts, curves_parts, pool_parts = [], [], [], []
    for identifier in cfg["folds"]:
        fold = next(f for f in labels_report["fold_plan"] if f["fold"] == identifier)
        data = frame[frame.fold.eq(identifier)].copy()
        if not phase_mask(data, fold, "test", cfg["development_end"]).all():
            raise ValueError("Outside frozen/mature test fold")
        if data.groupby("decision_session_date").size().min() < 20:
            raise ValueError("Oracle universe below frozen minimum")
        source_fold = next(f for f in source_report["folds"] if f["fold"] == identifier)
        selected_model = source_fold["champion"]
        if selected_model != choose_champion(source_fold["validation"]):
            raise ValueError("Oracle champion not selected from validation")
        if len(data) != source_fold["test"][selected_model]["rows"]:
            raise ValueError("Oracle test support changed")
        data["oracle_score"] = data[f"score_{selected_model}"]
        pool = rank_selection(data, "oracle_score", cfg["oracle_fraction"], cfg["seed"])
        if pool.groupby("decision_session_date").size().min() < 4:
            raise ValueError("Oracle pool too small for disjoint directional tails")
        pool["random"] = [
            deterministic_score(d, u, cfg["seed"] + 1)
            for d, u in zip(pool.decision_session_date, pool.research_uid, strict=True)
        ]
        pool_parts.append(pool)
        LOG.info(
            "fold=%s Oracle champion=%s candidates=%s D1=%s D10=%s",
            identifier,
            selected_model,
            len(pool),
            pool.decile.eq(1).sum(),
            pool.decile.eq(10).sum(),
        )
        for score in cfg["scores"]:
            metrics, daily, curves = evaluate(pool, score, cfg)
            results.append({"fold": identifier, "score": score, "oracle_champion": selected_model, "metrics": metrics})
            for table in (daily, curves):
                table["fold"], table["score"] = identifier, score
            daily_parts.append(daily)
            curves_parts.append(curves)
    pools = pd.concat(pool_parts, ignore_index=True)
    pools.to_parquet(destination / "oracle_pool.parquet", index=False)
    pd.concat(daily_parts, ignore_index=True).to_parquet(destination / "daily_direction_metrics.parquet", index=False)
    pd.concat(curves_parts, ignore_index=True).to_parquet(destination / "score_quintiles.parquet", index=False)
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "folds": results,
        "verdicts": verdict(results, cfg),
        "pool_rows": len(pools),
        "dates": int(pools.decision_session_date.nunique()),
        "symbols": int(pools.research_uid.nunique()),
        "pool_sha256": _sha256(destination / "oracle_pool.parquet"),
        "source_hashes": {
            "oracle_predictions": cfg["oracle_prediction_sha256"],
            "labels": oracle_cfg["labels_sha256"],
            "price": oracle_cfg["price_sha256"],
        },
        "trained_models": 0,
        "confirmation_evaluated": False,
        "economic_validation": False,
        "canonical_writes": False,
        "serving_enabled": False,
        "limitations": [
            "PREVIOUSLY_INSPECTED_DEVELOPMENT_FOLDS",
            "H5_PRICE_ONLY_LIMITED_COVERAGE",
            "ORACLE_INCREMENTAL_GATE_FAILED_SPRINT9",
            "RESEARCH_J1_ASSUMPTION",
            "RAW_RETURNS_NO_COSTS_NO_FILLS",
            "DECILES_RELATIVE_NOT_RETURN_SIGN",
            "NO_SECTOR_OR_SIZE_NEUTRALIZATION",
            "LIMITED_DELISTED_SUPPORT",
        ],
    }
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/research_fr/direction_h5_audit_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/research/direction_h5_audit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run(args.profile, args.output_root)
    print(json.dumps({k: report[k] for k in ["artifact_directory", "pool_rows", "verdicts"]}, indent=2))


if __name__ == "__main__":
    main()
