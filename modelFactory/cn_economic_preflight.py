"""Sprint 13-A : couverture des événements CN sur candidats OOS, sans labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANKING_CONFIG
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_OUTPUT as RANKING_OUTPUT
from modelFactory.cn_global_ranking_walk_forward import _sha
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH

DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint13a_economic_preflight.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "economic" / "sprint13a"
SAFE_COLUMNS = [
    "market_code", "session_date", "instrument_id", "board_code",
    "oracle_top20", "baseline_score", "rank_score",
]
POLICIES = (
    "oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20",
    "lightgbm_long_top20",
)


def load_protocol(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    expected = {
        "experiment": "cn_economic_preflight_sprint13a_v1",
        "market_code": "CN_A", "database_alias": "cn_primary",
        "evidence_level": "previously_inspected_oos_predictions_not_independent_confirmation",
        "source_experiment": "cn_global_ranking_sprint10c_v1",
        "source_horizon": 20, "source_model": "lightgbm",
        "test_semesters": [f"{year}H{half}" for year in range(2022, 2026) for half in (1, 2)],
        "signal_time": "after_close_j",
        "entry_policy": "next_open_only_cancel_if_not_filled",
        "exit_policy": "twenty_full_sessions_after_actual_fill_then_next_open_sell_carry_until_feasible",
        "candidate_policies": list(POLICIES),
        "corporate_action_handling": "quarantine_unclassified_never_synthesize_split_or_dividend",
        "delisting_handling": "unresolved_without_verified_cash_recovery",
        "serving_enabled": False, "live_enabled": False,
        "economic_go_allowed_at_13a": False,
    }
    if any(raw.get(key) != value for key, value in expected.items()):
        raise ValueError("Protocole Sprint 13-A divergent ou incomplet")
    portfolio = raw.get("portfolio") or {}
    if portfolio != {
        "initial_cash_cny": 100000, "ticket_cny": 10000, "max_positions": 8,
        "allow_pyramiding": False, "short_enabled": False,
        "oracle_tie_break": "deterministic_hash_seed_average",
        "tie_break_seeds": [0, 1, 2, 3, 4],
        "no_signal_during_open_position": True,
        "min_oracle_pool_per_session": 20,
    }:
        raise ValueError("Portefeuille CN Sprint 13-A non figé")
    if raw.get("cost_profiles") != ["cn_a_research", "cn_a_research_stress"] or raw.get("fill_scenarios") != ["base", "conservative"]:
        raise ValueError("Coûts/fills Sprint 13-A non figés")
    gate = raw.get("preflight_gate") or {}
    if (gate.get("max_unclassified_action_exposure_fraction") != 0.05
            or gate.get("minimum_full_scheduled_path_fraction") != 0.95
            or gate.get("denominator") != "selected_candidates_with_full_scheduled_path"):
        raise ValueError("Gate Sprint 13-A non figé")
    return raw


def select_policies(frame: pd.DataFrame, *, minimum: int) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """N'utilise que SAFE_COLUMNS, jamais les labels ni la négociabilité future."""
    if set(frame) != set(SAFE_COLUMNS) or frame.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Schéma ou clés OOS CN invalides")
    if set(frame["market_code"]) != {"CN_A"}:
        raise ValueError("Marché OOS autre que CN_A")
    pool = frame.loc[frame["oracle_top20"].eq(True)].copy()
    pool = pool.loc[pool.groupby("session_date")["instrument_id"].transform("size") >= minimum]
    if pool.empty:
        raise ValueError("Pool Oracle TOP20 vide après minimum transversal")
    size = pool.groupby("session_date")["instrument_id"].transform("size")
    masks: dict[str, pd.Series] = {"oracle_all": pd.Series(True, index=pool.index)}
    for name, score in (("reversal", -pool["baseline_score"]),
                        ("lightgbm", pool["rank_score"])):
        sorted_pool = pool.assign(_score=score).sort_values(
            ["session_date", "_score", "instrument_id"],
            ascending=[True, False, True], kind="stable", na_position="last",
        )
        rank = sorted_pool.groupby("session_date", sort=False).cumcount().reindex(pool.index)
        masks[f"{name}_veto_bottom20"] = score.notna() & (rank < size - np.ceil(size * 0.20))
        if name == "lightgbm":
            masks["lightgbm_long_top20"] = score.notna() & (rank < np.ceil(size * 0.20))
    return pool, masks


def audit_exposure(
    candidates: pd.DataFrame, *, sessions: list[date],
    action_dates: dict[int, list[date]], delistings: dict[int, date | None],
) -> dict[str, Any]:
    """Fenêtre ex ante prévue J+1..J+21, pas les positions réellement ouvertes."""
    if candidates.empty:
        return {"selected_candidates": 0, "full_scheduled_path": 0,
                "censored_exit": 0, "action_exposed": 0, "entry_action_exposed": 0,
                "delisting_exposed": 0, "action_exposure_fraction": None,
                "full_path_fraction": None}
    calendar = np.asarray(sessions, dtype="datetime64[D]")
    ordinals = {day: index for index, day in enumerate(sessions)}
    signal_dates = pd.to_datetime(candidates["session_date"]).dt.date
    if not set(signal_dates).issubset(ordinals):
        raise ValueError("Signal OOS absent du calendrier CN")
    indices = signal_dates.map(ordinals).to_numpy(dtype=int)
    full = indices + 21 < len(calendar)
    exposed = np.zeros(len(candidates), dtype=bool)
    entry_exposed = np.zeros(len(candidates), dtype=bool)
    delisted = np.zeros(len(candidates), dtype=bool)
    group_ids = candidates["instrument_id"].to_numpy(dtype=int)
    for instrument_id in np.unique(group_ids):
        positions = np.flatnonzero((group_ids == instrument_id) & full)
        if not len(positions):
            continue
        entry_dates = calendar[indices[positions] + 1]
        exit_dates = calendar[indices[positions] + 21]
        dates = np.asarray(sorted(set(action_dates.get(int(instrument_id), []))), dtype="datetime64[D]")
        if len(dates):
            lower = np.searchsorted(dates, entry_dates, side="left")
            upper = np.searchsorted(dates, exit_dates, side="right")
            exposed[positions] = upper > lower
            entry_exposed[positions] = np.isin(entry_dates, dates)
        delist = delistings.get(int(instrument_id))
        if delist is not None:
            delist_date = np.datetime64(delist)
            delisted[positions] = (entry_dates <= delist_date) & (delist_date <= exit_dates)
    full_count = int(full.sum())
    return {
        "selected_candidates": len(candidates),
        "full_scheduled_path": full_count,
        "censored_exit": int((~full).sum()),
        "action_exposed": int(exposed.sum()),
        "entry_action_exposed": int(entry_exposed.sum()),
        "delisting_exposed": int(delisted.sum()),
        "action_exposure_fraction": round(float(exposed.sum() / full_count), 6) if full_count else None,
        "full_path_fraction": round(float(full_count / len(candidates)), 6),
    }


def run(*, config_path: Path = DEFAULT_CONFIG, output_root: Path = DEFAULT_OUTPUT,
        ranking_root: Path = RANKING_OUTPUT) -> dict[str, Any]:
    protocol = load_protocol(config_path)
    from modelFactory import cn_global_ranking_walk_forward as ranking_runner

    config_sha, rank_config_sha = _sha(config_path), _sha(RANKING_CONFIG)
    rank_code_sha, label_audit_sha = _sha(Path(ranking_runner.__file__)), _sha(AUDIT_PATH)
    sources = []
    for semester in protocol["test_semesters"]:
        item = _find_run(
            ranking_root, horizon=20, semester=semester, model="lightgbm",
            config_sha=rank_config_sha, code_sha=rank_code_sha, audit_sha=label_audit_sha,
        )
        if item is None:
            raise RuntimeError(f"Prédiction ranking OOS H20 introuvable: {semester}")
        sources.append((semester, *item))
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DATABASE() ")).scalar_one()
            if database != "alpha_trade_cn":
                raise RuntimeError("Audit CN interdit hors alpha_trade_cn")
            sessions = list(conn.execute(text(
                "SELECT session_date FROM market_sessions WHERE market_code='CN_A' "
                "AND session_status IN ('open','half_day','special') "
                "AND session_date BETWEEN '2022-01-01' AND '2025-12-31' "
                "ORDER BY session_date"
            )).scalars())
            rows = conn.execute(text(
                "SELECT instrument_id,ex_date,classification_status,source_payload_hash "
                "FROM cn_corporate_actions WHERE ex_date BETWEEN '2022-01-01' AND '2025-12-31' "
                "ORDER BY instrument_id,ex_date,source_payload_hash"
            )).mappings().all()
            delisting_rows = conn.execute(text(
                "SELECT instrument_id,delisting_date FROM instruments WHERE market_code='CN_A'"
            )).all()
    finally:
        engine.dispose()
    action_dates: dict[int, list[date]] = defaultdict(list)
    classes: dict[str, int] = defaultdict(int)
    action_digest = hashlib.sha256()
    for row in rows:
        action_dates[int(row["instrument_id"])].append(row["ex_date"])
        classes[str(row["classification_status"])] += 1
        action_digest.update(json.dumps(dict(row), sort_keys=True, default=str).encode())
    if set(classes) != {"UNCLASSIFIED_FACTOR_EVENT"}:
        raise RuntimeError("Classification des corporate actions CN modifiée : protocole 13-A à réviser")
    delistings = {int(identifier): value for identifier, value in delisting_rows}
    calendar_sha = hashlib.sha256("|".join(map(str, sessions)).encode()).hexdigest()
    result: dict[str, Any] = {
        "experiment": protocol["experiment"], "status": "INCOMPLETE",
        "evidence_level": protocol["evidence_level"],
        "source_horizon": 20, "source_model": "lightgbm",
        "no_future_label_columns_read": SAFE_COLUMNS,
        "protocol_sha256": config_sha, "audit_code_sha256": _sha(Path(__file__)),
        "source_ranking_config_sha256": rank_config_sha,
        "source_ranking_code_sha256": rank_code_sha,
        "source_label_audit_sha256": label_audit_sha,
        "calendar_sha256": calendar_sha,
        "corporate_action_rows_sha256": action_digest.hexdigest(),
        "corporate_action_rows": len(rows), "corporate_action_classes": dict(classes),
        "corporate_action_instruments": len(action_dates),
        "corporate_action_rows_by_year": {
            str(year): sum(item["ex_date"].year == year for item in rows)
            for year in range(2022, 2026)
        },
        "candidate_level_not_filled_portfolio": True,
        "policy": protocol["portfolio"],
        "semesters": {}, "overall": {}, "provenance": [],
    }
    pooled: dict[str, list[dict[str, Any]]] = {name: [] for name in POLICIES}
    for semester, path, source_report in sources:
        frame = pd.read_parquet(path, columns=SAFE_COLUMNS)
        year, half = int(semester[:4]), int(semester[-1])
        begin = date(year, 1 if half == 1 else 7, 1)
        end = date(year, 6 if half == 1 else 12, 30 if half == 1 else 31)
        dates = pd.to_datetime(frame["session_date"]).dt.date
        if not dates.between(begin, end).all():
            raise RuntimeError(f"Prédiction OOS hors semestre {semester}")
        pool, masks = select_policies(frame, minimum=protocol["portfolio"]["min_oracle_pool_per_session"])
        result["provenance"].append({"semester": semester, "predictions_sha256": source_report["predictions_sha256"]})
        fold = {"pool_candidates": len(pool), "policies": {}}
        for policy in POLICIES:
            selected = pool.loc[masks[policy], ["session_date", "instrument_id", "board_code"]]
            audit = audit_exposure(selected, sessions=sessions, action_dates=action_dates,
                                   delistings=delistings)
            audit["boards"] = {
                str(board): audit_exposure(part, sessions=sessions,
                                           action_dates=action_dates, delistings=delistings)
                for board, part in selected.groupby("board_code", sort=True)
            }
            pooled[policy].append(audit)
            fold["policies"][policy] = audit
        result["semesters"][semester] = fold
        print(f"Sprint 13-A {semester}: pool={len(pool)} actions={fold['policies']['oracle_all']['action_exposed']}", flush=True)
    gate = protocol["preflight_gate"]
    blocked_actions = False
    blocked_horizon = False
    for policy in POLICIES:
        parts = pooled[policy]
        total = sum(part["selected_candidates"] for part in parts)
        full = sum(part["full_scheduled_path"] for part in parts)
        action = sum(part["action_exposed"] for part in parts)
        entry_action = sum(part["entry_action_exposed"] for part in parts)
        delisting = sum(part["delisting_exposed"] for part in parts)
        exposure_fraction = action / full if full else None
        full_fraction = full / total if total else None
        blocked_actions |= exposure_fraction is None or exposure_fraction > gate["max_unclassified_action_exposure_fraction"]
        blocked_horizon |= full_fraction is None or full_fraction < gate["minimum_full_scheduled_path_fraction"]
        result["overall"][policy] = {
            "selected_candidates": total, "full_scheduled_path": full,
            "censored_exit": total - full, "action_exposed": action,
            "entry_action_exposed": entry_action, "delisting_exposed": delisting,
            "action_exposure_fraction": round(exposure_fraction, 6) if exposure_fraction is not None else None,
            "full_path_fraction": round(full_fraction, 6) if full_fraction is not None else None,
        }
        by_board = {}
        for board in sorted({name for part in parts for name in part["boards"]}):
            slices = [part["boards"][board] for part in parts if board in part["boards"]]
            board_total = sum(item["selected_candidates"] for item in slices)
            board_full = sum(item["full_scheduled_path"] for item in slices)
            board_action = sum(item["action_exposed"] for item in slices)
            by_board[board] = {
                "selected_candidates": board_total,
                "full_scheduled_path": board_full,
                "action_exposed": board_action,
                "action_exposure_fraction": round(board_action / board_full, 6) if board_full else None,
            }
        result["overall"][policy]["boards"] = by_board
    result["status"] = (
        "BLOCKED_ACTION_NORMALIZATION" if blocked_actions else
        "BLOCKED_INCOMPLETE_FUTURE_WINDOW" if blocked_horizon else
        "READY_FOR_QUARANTINED_RESEARCH_REPLAY_NOT_ECONOMIC_GO"
    )
    result["gate"] = {
        "max_action_fraction": gate["max_unclassified_action_exposure_fraction"],
        "minimum_full_path_fraction": gate["minimum_full_scheduled_path_fraction"],
        "blocked_actions": blocked_actions, "blocked_horizon": blocked_horizon,
        "economic_go_allowed": False,
    }
    digest = hashlib.sha256(json.dumps({
        "protocol": config_sha, "code": result["audit_code_sha256"],
        "actions": action_digest.hexdigest(), "calendar": calendar_sha,
        "sources": result["provenance"],
    }, sort_keys=True).encode()).hexdigest()[:16]
    destination = output_root / f"sprint13a-{digest}"
    if destination.exists():
        raise FileExistsError(f"Audit Sprint 13-A déjà présent, écrasement refusé: {destination}")
    destination.mkdir(parents=True)
    (destination / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["report_path"] = str(destination / "report.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 13-A : préflight CN sans rendement futur")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(config_path=args.config, output_root=args.output_root)
    print(json.dumps({"status": result["status"], "report_path": result["report_path"],
                      "overall": result["overall"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
