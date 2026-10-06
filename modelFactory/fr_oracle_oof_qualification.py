"""Qualification de support uniquement : aucun fit ni score Oracle nouveau."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from modelFactory.fr_labels_review import fold_support, phase_mask
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256


def rolling_folds(folds: list[dict], sessions: list[str], window: int) -> list[dict]:
    if window < 1 or sessions != sorted(set(sessions)):
        raise ValueError("Calendrier ou fenêtre invalide")
    output = []
    for fold in folds:
        preceding = [s for s in sessions if fold["train_start"] <= s <= fold["train_end"]]
        if len(preceding) < window:
            raise ValueError("Historique inférieur à la fenêtre train")
        output.append({**fold, "train_start": preceding[-window]})
    return output


def complete_folds(support: list[dict]) -> list[int]:
    ids = sorted({r["fold"] for r in support})
    return [
        f
        for f in ids
        if all(
            len(rows := [r for r in support if r["fold"] == f and r["phase"] == p]) == 1
            and rows[0]["state"] == "GO_DATA_SUPPORT_ONLY"
            for p in ("train", "validation", "test")
        )
    ]


def potential_history(frame: pd.DataFrame, folds: list[dict], admitted: list[int], cfg: dict) -> pd.DataFrame:
    """Dates candidates couvertes, PAS les événements TOP20 d'un Oracle entraîné."""
    parts = []
    for fold in folds:
        if fold["fold"] not in admitted:
            continue
        for phase in ("validation", "test"):
            selected = frame.loc[
                phase_mask(frame, fold, phase, cfg["development_end"])
                & frame.profile_row_ready
                & frame.oracle_extreme.notna()
            ].copy()
            counts = selected.groupby("decision_session_date").size()
            usable = counts.index[counts.ge(cfg["min_cross_section"])]
            selected = selected.loc[selected.decision_session_date.isin(usable)]
            parts.append(selected[["decision_session_date", "research_uid"]])
    if not parts:
        return pd.DataFrame(columns=["decision_session_date", "candidate_rows"])
    candidates = pd.concat(parts).drop_duplicates()
    return candidates.groupby("decision_session_date").size().rename("candidate_rows").reset_index()


def gap_details(frame: pd.DataFrame, folds: list[dict], sessions: list[str], cfg: dict) -> pd.DataFrame:
    rows = []
    for fold in folds:
        for phase in ("train", "validation", "test"):
            expected = [s for s in sessions if fold[f"{phase}_start"] <= s <= fold[f"{phase}_end"]]
            bounded = frame.loc[frame.decision_session_date.isin(expected)]
            mature = bounded.loc[phase_mask(bounded, fold, phase, cfg["development_end"])]
            ready = mature.loc[mature.profile_row_ready]
            known = ready.loc[ready.oracle_extreme.notna()]
            counts = [g.groupby("decision_session_date").size().to_dict() for g in (bounded, mature, ready, known)]
            for day in expected:
                n = [int(c.get(day, 0)) for c in counts]
                if n[-1] < cfg["min_cross_section"]:
                    rows.append(
                        {
                            "fold": fold["fold"],
                            "phase": phase,
                            "session_date": day,
                            "label_rows": n[0],
                            "valid_mature_rows": n[1],
                            "price_profile_ready_rows": n[2],
                            "oracle_known_ready_rows": n[3],
                        }
                    )
    return pd.DataFrame(rows)


def run(config_path: Path, output_root: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "profile": "fr_oracle_oof_qualification_v1",
        "market_code": "FR_EQ",
        "horizon": 5,
        "development_end": "2025-12-31",
        "rolling_train_sessions": 504,
        "min_cross_section": 20,
        "min_session_coverage": 0.8,
        "min_usable_sessions": 40,
        "canonical_writes_enabled": False,
        "serving_enabled": False,
        "training_enabled": False,
    }
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise ValueError("Contrat de qualification figé modifié")
    report_path = ROOT / cfg["labels_report"]
    labels_path = report_path.with_name("labels.parquet")
    price_path = ROOT / cfg["price_panel"]
    if _sha256(labels_path) != cfg["labels_sha256"] or _sha256(price_path) != cfg["price_sha256"]:
        raise ValueError("Sources divergentes du gel")
    source = json.loads(report_path.read_text(encoding="utf-8"))
    labels = pd.read_parquet(labels_path)
    labels = labels.loc[labels.horizon.eq(5) & labels.decision_session_date.le(cfg["development_end"])].copy()
    price = pd.read_parquet(price_path)
    keys = ["decision_session_date", "research_uid"]
    if labels.duplicated(keys).any() or price.duplicated(keys).any():
        raise ValueError("Clés dupliquées")
    if (pd.to_datetime(price.max_input_available_at, utc=True) > pd.to_datetime(price.decision_at, utc=True)).any():
        raise ValueError("Feature après décision")
    frame = labels.merge(price[keys + ["profile_row_ready"]], on=keys, validate="one_to_one", how="left")
    if frame.profile_row_ready.isna().any():
        raise ValueError("Label sans feature")
    # Alias pour réutiliser exactement le contrôle existant, sans introduire un profil benchmark.
    frame["common_row_ready"] = frame.profile_row_ready
    sessions = [
        s.session_date.isoformat()
        for s in get_market_calendar("FR_EQ").sessions(
            date.fromisoformat(frame.decision_session_date.min()), date(2025, 12, 31)
        )
        if s.is_open
    ]
    original = source["fold_plan"]
    rolling = rolling_folds(original, sessions, cfg["rolling_train_sessions"])
    results = {}
    timelines = {}
    gaps = {}
    for name, folds in (("expanding_original", original), ("rolling_504", rolling)):
        support = [r for r in fold_support(frame, folds, sessions, cfg) if r["profile"] == "price_only"]
        for row in support:
            row["minimum_sessions_required"] = max(
                cfg["min_usable_sessions"], math.ceil(row["expected_sessions"] * cfg["min_session_coverage"])
            )
            row["session_deficit"] = max(0, row["minimum_sessions_required"] - row["usable_sessions"])
        admitted = complete_folds(support)
        timeline = potential_history(frame, folds, admitted, cfg)
        plans = []
        for outer in original:
            train_dates = timeline.decision_session_date.between(outer["train_start"], outer["train_end"])
            # H5 maturité : conservative, utiliser les disponibilités de labels originales.
            mature_days = set(
                frame.loc[phase_mask(frame, outer, "train", cfg["development_end"]), "decision_session_date"]
            )
            n = int((train_dates & timeline.decision_session_date.isin(mature_days)).sum())
            plans.append(
                {
                    "fold": outer["fold"],
                    "potential_oof_train_dates": n,
                    "date_gate_126_possible": n >= 126,
                    "directional_class_support": "UNKNOWN_UNTIL_ORACLE_OOF_GENERATED",
                }
            )
        results[name] = {
            "fold_plan": folds,
            "support": support,
            "admitted_oracle_folds": admitted,
            "potential_oof_dates": len(timeline),
            "first_potential_date": None if timeline.empty else timeline.decision_session_date.min(),
            "last_potential_date": None if timeline.empty else timeline.decision_session_date.max(),
            "directional_date_capacity": plans,
        }
        timelines[name] = timeline
        gaps[name] = gap_details(frame, folds, sessions, cfg)
    fingerprint = _fingerprint(
        {
            "cfg": cfg,
            "code": _sha256(Path(__file__)),
            "support_code": _sha256(Path(__file__).with_name("fr_labels_review.py")),
            "labels_report": _sha256(report_path),
        }
    )
    destination = output_root / f"fr-oracle-oof-qualification-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=False)
    for name, timeline in timelines.items():
        timeline.to_parquet(destination / f"{name}_potential_dates.parquet", index=False)
        gaps[name].to_parquet(destination / f"{name}_missing_sessions.parquet", index=False)
    report = {
        "fingerprint": fingerprint,
        "config": cfg,
        "results": results,
        "verdict": "QUALIFIED_DATA_SUPPORT_ONLY_NOT_ORACLE_OOF",
        "new_models_trained": 0,
        "new_oof_predictions": 0,
        "confirmation_2026_evaluated": False,
        "artifact_dir": str(destination.relative_to(ROOT)),
    }
    _atomic_json(destination / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/research_fr/oracle_oof_qualification_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/research/oracle_oof_qualification")
    args = parser.parse_args()
    report = run(args.config, args.output_root)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
