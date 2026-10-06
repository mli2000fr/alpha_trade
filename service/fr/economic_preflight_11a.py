"""Préflight des références économiques FR : aucun fill ni PnL inventé."""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from modelFactory.fr_fold7_rebuild import sha
from service.fr.universe_contract_6a import ROOT

KEYS = ["decision_session_date", "research_uid"]


def score_candidates(candidates: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Frozen fits score every decision-time candidate, including unknown outcomes."""
    from modelFactory.fr_oracle_h5_pilot import feature_matrix
    output = candidates.copy()
    output["score_oracle_research"] = np.nan
    for fold, group in output.groupby("fold", sort=True):
        score = models[fold].predict_proba(feature_matrix(group))[:, 1]
        if not np.isfinite(score).all() or ((score < 0) | (score > 1)).any():
            raise ValueError("Scores Oracle invalides")
        known = group.score_trees.notna()
        if not np.allclose(score[known.to_numpy()], group.loc[known, "score_trees"], rtol=0, atol=1e-12):
            raise ValueError("Scores gelés divergents ; modèle précédent conservé")
        output.loc[group.index, "score_oracle_research"] = score
    if output.score_oracle_research.isna().any():
        raise ValueError("Candidat non scoré")
    return output


def selection_ledger(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Candidate intent only: no cash/fill/tax assumption, no executed positions."""
    from modelFactory.fr_oracle_h5_pilot import deterministic_score
    records = []
    for (fold, day), group in frame.groupby(["fold", "decision_session_date"], sort=True):
        working = group.copy()
        working["tie"] = [deterministic_score(day, uid, cfg["seed"]) for uid in working.research_uid]
        k = int(np.ceil(len(group) * cfg["selection_fraction"]))
        for policy, column, pool_size in (("atr_top20_long", "atr20_pct", k),
                                          ("oracle_top20_long", "score_oracle_research", k),
                                          ("uniform_control_long", "tie", len(group))):
            selected = working.sort_values([column, "tie", "research_uid"] if column != "tie" else ["tie", "research_uid"],
                                           ascending=[False, False, True] if column != "tie" else [False, True], kind="stable").iloc[:pool_size]
            for rank, row in enumerate(selected.itertuples(), start=1):
                records.append({"fold": fold, "decision_session_date": day, "policy": policy,
                                "research_uid": row.research_uid, "provider_symbol": row.provider_symbol,
                                "candidate_rank": rank, "daily_pool_size": pool_size,
                                "execution_state": "INTENT_NOT_FILL", "future_label_used": False})
    return pd.DataFrame(records)


def load_protocol(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    fixed = {"schema_version": 1, "profile": "fr_economic_references_11a_v1", "market_code": "FR_EQ",
             "folds": [6, 7], "phase": "test", "development_end": "2025-12-31", "reserved_confirmation_start": "2026-01-01",
             "oracle_branch": "trees", "horizon": 5, "selection_fraction": .2, "min_cross_section": 20, "seed": 17,
             "selection_uses_future_labels": False, "entry": "decision_session_open", "exit": "decision_plus_5_sessions_close",
             "policies": ["atr_top20_long", "oracle_top20_long", "uniform_control_long"],
             "descriptive_reference": "full_eligible_universe_equal_weight", "stress_multiplier": 2.0,
             "economic_go_allowed": False, "canonical_writes_enabled": False, "serving_enabled": False}
    if any(cfg.get(k) != v for k, v in fixed.items()):
        raise ValueError("Contrat 11-A figé modifié")
    if cfg["portfolio"] != {"currency": "EUR", "initial_equity": 4000.0, "max_positions": 8, "max_gross_exposure": 1.0,
                            "leverage": False, "short_enabled": False, "fractional_shares": False, "allocation": "equal_notional_at_entry",
                            "duplicate_symbol_policy": "no_stacking", "reentry": "next_session_after_exit", "intraday_cash_reuse": False,
                            "exit_rule": "fixed_horizon_no_stop_tp_trailing_optimization"}:
        raise ValueError("Contrat portefeuille 11-A modifié")
    return cfg


def candidate_audit(panel: pd.DataFrame, predictions: pd.DataFrame, folds: list[dict], cfg: dict) -> tuple[pd.DataFrame, list]:
    if panel.duplicated(KEYS).any() or predictions.duplicated(KEYS + ["fold", "phase"]).any():
        raise ValueError("Clés de candidats/scores dupliquées")
    if (pd.to_datetime(panel.max_input_available_at, utc=True) > pd.to_datetime(panel.decision_at, utc=True)).any():
        raise ValueError("Features disponibles après décision")
    parts, records = [], []
    for number in cfg["folds"]:
        fold = next(f for f in folds if f["fold"] == number)
        dates = fold["dates"]
        if dates["test_end"] > cfg["development_end"]:
            raise ValueError("Confirmation réservée interdite")
        # No forward label, realized return, path-state or whole-period gate.
        candidates = panel.loc[panel.decision_session_date.between(dates["test_start"], dates["test_end"]) & panel.profile_row_ready].copy()
        size = candidates.groupby("decision_session_date")["research_uid"].transform("size")
        candidates = candidates.loc[size.ge(cfg["min_cross_section"])].copy()
        scores = predictions.loc[predictions.fold.eq(number) & predictions.phase.eq("test"), KEYS + ["score_trees"]]
        merged = candidates.merge(scores, on=KEYS, how="left", validate="one_to_one", indicator=True)
        if not scores.merge(candidates[KEYS], on=KEYS, how="left", indicator=True)["_merge"].eq("both").all():
            raise ValueError("Score sans candidat causal")
        merged["oracle_score_missing"] = merged["_merge"].ne("both") | merged.score_trees.isna()
        merged["fold"] = number
        records.append({"fold": number, "test_start": dates["test_start"], "test_end": dates["test_end"],
                        "causal_candidate_rows": len(merged), "candidate_dates": int(merged.decision_session_date.nunique()),
                        "archived_score_rows": len(scores), "missing_score_rows": int(merged.oracle_score_missing.sum()),
                        "dates_with_missing_scores": int(merged.loc[merged.oracle_score_missing, "decision_session_date"].nunique()),
                        "archived_scoring_filter": "profile_row_ready AND future oracle_extreme known AND future path VALID"})
        parts.append(merged.drop(columns="_merge"))
    return pd.concat(parts, ignore_index=True), records


def readiness_checks(missing_scores: int, evidence: dict, costs: dict) -> list[dict]:
    return [
        {"name": "oracle_scores_without_future_selection", "passed": missing_scores == 0, "missing_rows": missing_scores},
        {"name": "historical_pit_verified", "passed": evidence["historical_pit_missing"] == 0, "missing_rows": evidence["historical_pit_missing"]},
        {"name": "corporate_actions_economic_verified", "passed": evidence["corporate_action_missing"] == 0, "missing_rows": evidence["corporate_action_missing"]},
        {"name": "economic_return_ready", "passed": evidence["economic_return_missing"] == 0, "missing_rows": evidence["economic_return_missing"]},
        {"name": "commission_spread_slippage_qualified", "passed": costs.get("evidence_state") == "QUALIFIED" and all(costs.get(k) is not None for k in ("commission", "spread", "slippage"))},
        {"name": "instrument_date_tax_schedule_qualified", "passed": costs.get("evidence_state") == "QUALIFIED" and costs.get("instrument_date_tax_schedule") is not None},
    ]


def audit(cfg: dict) -> tuple[dict, pd.DataFrame]:
    root = ROOT / cfg["rebuild_root"]
    qualification = json.loads((root / "rebuild_report.json").read_text(encoding="utf-8"))["qualification"]
    sources = qualification["config"]
    oracle = json.loads((root / "confirmation/report.json").read_text(encoding="utf-8"))["oracle"]
    if any(oracle["config"][key] != sources[key] for key in ("price_panel", "price_sha256", "labels_report", "labels_sha256")):
        raise ValueError("Provenance Oracle/reconstruction divergente")
    panel_path = ROOT / sources["price_panel"]
    predictions_path = ROOT / oracle["artifact_directory"] / "predictions.parquet"
    if sha(panel_path) != sources["price_sha256"] or sha(predictions_path) != oracle["prediction_sha256"]:
        raise ValueError("Artefacts modifiés")
    source = json.loads((root / "source/report.json").read_text(encoding="utf-8"))
    manifest = ROOT / source["manifest"]["path"]
    if sha(manifest) != source["manifest"]["sha256"]:
        raise ValueError("Manifeste modifié")
    candidates, folds = candidate_audit(pd.read_parquet(panel_path), pd.read_parquet(predictions_path), oracle["folds"], cfg)
    pairs = set(zip(candidates.provider_symbol, candidates.source_session_date, strict=True))
    evidence = Counter(matched_source_rows=0, historical_pit_missing=0, corporate_action_missing=0, economic_return_missing=0)
    matched = set()
    with gzip.open(manifest, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            pair = (row["symbol"], row["session_date"])
            if pair not in pairs:
                continue
            if pair in matched:
                raise ValueError("Barre source dupliquée")
            matched.add(pair)
            evidence["matched_source_rows"] += 1
            for name, field in (("historical_pit_missing", "historical_pit_verified"),
                                ("corporate_action_missing", "corporate_action_verified"), ("economic_return_missing", "economic_return_ready")):
                evidence[name] += row.get(field) is not True
    if matched != pairs:
        raise ValueError("Candidat sans barre source du manifeste")
    checks = readiness_checks(int(candidates.oracle_score_missing.sum()), evidence, cfg["costs"])
    return {"profile": cfg["profile"], "protocol": cfg, "folds": folds, "evidence": dict(evidence), "checks": checks,
            "verdict": "BLOCKED_ECONOMIC_REPLAY" if not all(c["passed"] for c in checks) else "READY_FOR_EXECUTION_CONTRACT_REVIEW",
            "net_return": None, "sharpe": None, "drawdown": None, "trades_executed": 0,
            "source_hashes": {"price": sha(panel_path), "oracle_predictions": sha(predictions_path), "manifest": sha(manifest),
                              "oracle_report": sha(root / "confirmation/report.json"), "implementation": sha(Path(__file__))},
            "confirmation_2026_evaluated": False, "canonical_writes": False, "serving_enabled": False,
            "limitations": ["NO_PNL_WITH_UNQUALIFIED_COSTS_OR_CORPORATE_ACTIONS", "CURRENT_UNIVERSE_RESEARCH_J1_NOT_CANONICAL_PIT",
                            "OOF_METRIC_SCORES_NOT_FULL_CAUSAL_CANDIDATE_SCORING", "FULL_EW_INDEX_IS_NOT_8_POSITION_PORTFOLIO"]}, candidates
