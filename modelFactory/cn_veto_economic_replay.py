"""Sprint 11-B: stress économique indicatif du veto D1 CN, sans backtest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from modelFactory.cn_directional_diagnostic import (
    DEFAULT_CONFIG as DIRECTION_CONFIG,
)
from modelFactory.cn_directional_diagnostic import (
    combine_oos,
    policy_masks,
    prepare_pool,
)
from modelFactory.cn_directional_diagnostic import (
    load_protocol as load_direction_protocol,
)
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANKING_CONFIG
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_OUTPUT as RANKING_OUTPUT
from modelFactory.cn_global_ranking_walk_forward import _sha
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH, _sources
from modelFactory.cn_oracle_walk_forward import DEFAULT_CONFIG as ORACLE_CONFIG
from modelFactory.cn_oracle_walk_forward import Protocol as OracleProtocol

DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint11b_veto_economic.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "directional" / "sprint11b"
PREDICTION_COLUMNS = [
    "market_code", "session_date", "instrument_id", "board_code", "cn_breadth_1",
    "target_quality_valid", "oracle_decile", "future_return",
    "execution_data_eligible", "oracle_top20", "baseline_score", "rank_score",
]
LABEL_COLUMNS = [
    "session_date", "instrument_id", "market_code", "target_quality_valid",
    "oracle_decile", "future_return", "entry_open", "exit_close", "exit_date",
    "path_factor_event", "entry_limit_locked", "exit_limit_locked",
    "execution_data_eligible",
]
POLICIES = (
    "oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20",
    "consensus_veto_bottom20",
)


def load_protocol(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    direction = load_direction_protocol(DIRECTION_CONFIG)
    required = {
        "experiment": "cn_veto_economic_sprint11b_v1",
        "market_code": "CN_A",
        "evidence_level": "exploratory_cost_stress_not_executable_backtest",
        "source_protocol": direction["experiment"],
        "source_horizons": direction["source_horizons"],
        "test_semesters": direction["test_semesters"],
        "policies": list(POLICIES),
        "base_comparator": "reversal_veto_bottom20",
        "ticket_cny": 10000,
        "quarantine_factor_event": True,
        "quarantine_unknown_or_locked_entry_exit": True,
        "unresolved_exit_is_not_zero_return": True,
        "serving_enabled": False,
        "backtest_enabled": False,
        "decision_gate": "none_until_independent_CN_period_and_execution_rules",
    }
    for key, value in required.items():
        if raw.get(key) != value:
            raise ValueError(f"Contrat Sprint 11-B invalide: {key}")
    if set(raw.get("cost_scenarios", {})) != {"zero", "base_proxy", "stress_proxy"}:
        raise ValueError("Scénarios de coûts Sprint 11-B incomplets")
    for scenario in raw["cost_scenarios"].values():
        if not (0 <= scenario["bps_per_side"] <= 100
                and 0 <= scenario["minimum_cny_per_side"] <= 100):
            raise ValueError("Coût hypothétique hors bornes")
    if set(raw.get("board_lot_assumptions", {})) != {"SH_MAIN", "SZ_MAIN", "CHINEXT", "STAR"}:
        raise ValueError("Hypothèses de lots CN incomplètes")
    return raw


def merge_labels(pool: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    keys = ["session_date", "instrument_id"]
    if labels.duplicated(keys).any() or set(labels["market_code"]) != {"CN_A"}:
        raise RuntimeError("Labels de replay CN dupliqués ou marché erroné")
    label = labels.rename(columns={name: f"label_{name}" for name in (
        "market_code", "target_quality_valid", "oracle_decile", "future_return",
        "execution_data_eligible",
    )})
    result = pool.merge(label, on=keys, how="left", validate="one_to_one", indicator=True)
    if not result["_merge"].eq("both").all():
        raise RuntimeError("Label de replay manquant pour un candidat Oracle")
    for name in ("market_code", "target_quality_valid", "oracle_decile",
                 "future_return", "execution_data_eligible"):
        try:
            pd.testing.assert_series_equal(result[name], result[f"label_{name}"], check_names=False)
        except AssertionError as exc:
            raise RuntimeError(f"Label de replay différent du fold OOS: {name}") from exc
    return result.drop(columns=["_merge", *[f"label_{name}" for name in (
        "market_code", "target_quality_valid", "oracle_decile",
        "future_return", "execution_data_eligible",
    )]])


def classify_feasibility(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """Sépare les blocages ; aucun non-fill n'est converti en rendement nul."""
    reasons = pd.Series("FILLABLE_PROXY", index=frame.index, dtype="string")
    valid = frame["target_quality_valid"].eq(True) & frame["future_return"].notna()
    reasons.loc[~valid] = "LABEL_INVALID_OR_UNMATURED"
    def mark(condition: pd.Series, reason: str) -> None:
        reasons.loc[reasons.eq("FILLABLE_PROXY") & condition.fillna(True)] = reason

    mark(frame["path_factor_event"].ne(False), "CORPORATE_ACTION_PATH")
    mark(frame["entry_limit_locked"].ne(False), "ENTRY_LOCKED_OR_UNKNOWN")
    mark(frame["exit_limit_locked"].ne(False), "EXIT_LOCKED_OR_UNKNOWN")
    mark(frame["execution_data_eligible"].ne(True), "ENTRY_OR_EXIT_LIMIT_UNKNOWN")
    price_bad = (
        ~np.isfinite(pd.to_numeric(frame["entry_open"], errors="coerce"))
        | ~np.isfinite(pd.to_numeric(frame["exit_close"], errors="coerce"))
        | frame["entry_open"].le(0) | frame["exit_close"].le(0)
    )
    mark(price_bad, "PRICE_MISSING_OR_INVALID")
    mark(pd.to_datetime(frame["exit_date"]) <= pd.to_datetime(frame["session_date"]),
         "T_PLUS_ONE_VIOLATION")
    raw_return = frame["exit_close"] / frame["entry_open"] - 1
    mark((raw_return - frame["future_return"]).abs().gt(0.00001),
         "ADJUSTED_RAW_RETURN_MISMATCH")
    mark(~frame["board_code"].isin(config["board_lot_assumptions"]), "BOARD_LOT_UNKNOWN")
    return reasons


def proxy_returns(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    result["feasibility"] = classify_feasibility(result, config)
    price = pd.to_numeric(result["entry_open"], errors="coerce")
    minimum = result["board_code"].map({
        board: rule["minimum_shares"] for board, rule in config["board_lot_assumptions"].items()
    })
    increment = result["board_code"].map({
        board: rule["increment_shares"] for board, rule in config["board_lot_assumptions"].items()
    })
    with np.errstate(divide="ignore", invalid="ignore"):
        quantity = np.floor(float(config["ticket_cny"]) / price / increment) * increment
    affordable = quantity.ge(minimum) & np.isfinite(quantity)
    result.loc[result["feasibility"].eq("FILLABLE_PROXY") & ~affordable, "feasibility"] = "LOT_NOT_AFFORDABLE"
    result["quantity_proxy"] = quantity.where(result["feasibility"].eq("FILLABLE_PROXY"))
    notional_buy = result["quantity_proxy"] * price
    notional_sell = result["quantity_proxy"] * result["exit_close"]
    for name, scenario in config["cost_scenarios"].items():
        rate = float(scenario["bps_per_side"]) / 10_000
        minimum_fee = float(scenario["minimum_cny_per_side"])
        buy_fee = np.maximum(minimum_fee, notional_buy * rate)
        sell_fee = np.maximum(minimum_fee, notional_sell * rate)
        result[f"net_return_{name}"] = (
            (notional_sell - sell_fee - notional_buy - buy_fee) / (notional_buy + buy_fee)
        ).where(result["feasibility"].eq("FILLABLE_PROXY"))
    return result


def policy_summary(frame: pd.DataFrame, mask: pd.Series, config: dict[str, Any]) -> dict[str, Any]:
    selected = frame.loc[mask]
    fillable = selected.loc[selected["feasibility"].eq("FILLABLE_PROXY")]
    result: dict[str, Any] = {
        "selected": len(selected),
        "label_valid_selected": int(selected["target_quality_valid"].sum()),
        "fillable_proxy": len(fillable),
        "fillable_fraction_selected": round(len(fillable) / len(selected), 6) if len(selected) else None,
        "blockers": selected["feasibility"].value_counts().to_dict(),
        "d1_rate_fillable": round(float(fillable["oracle_decile"].eq(1).mean()), 6) if len(fillable) else None,
        "d10_rate_fillable": round(float(fillable["oracle_decile"].eq(10).mean()), 6) if len(fillable) else None,
        "mean_gross_return_fillable": round(float(fillable["future_return"].mean()), 6) if len(fillable) else None,
    }
    for scenario in config["cost_scenarios"]:
        values = fillable[f"net_return_{scenario}"]
        result[f"mean_net_return_{scenario}"] = round(float(values.mean()), 6) if len(values) else None
        result[f"positive_net_fraction_{scenario}"] = round(float(values.gt(0).mean()), 6) if len(values) else None
    return result


def _aggregate_metrics(parts: list[pd.DataFrame], config: dict[str, Any]) -> dict[str, Any]:
    frame = pd.concat(parts, ignore_index=True)
    summaries = {}
    for policy in POLICIES:
        selected = frame.loc[frame[f"policy_{policy}"]]
        summaries[policy] = policy_summary(
            selected, pd.Series(True, index=selected.index), config,
        )
    return summaries


def run(*, config_path: Path = DEFAULT_CONFIG, ranking_root: Path = RANKING_OUTPUT,
        output_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config = load_protocol(config_path)
    from modelFactory import cn_global_ranking_walk_forward as runner

    rank_config_sha = _sha(RANKING_CONFIG)
    rank_code_sha = _sha(Path(runner.__file__))
    audit_sha = _sha(AUDIT_PATH)
    source, label_audit = _sources(OracleProtocol.load(ORACLE_CONFIG))
    digest = hashlib.sha256((_sha(config_path) + _sha(Path(__file__))
                             + rank_config_sha + rank_code_sha + audit_sha).encode()).hexdigest()[:16]
    destination = output_root / f"sprint11b-{digest}"
    if (destination / "report.json").exists():
        raise RuntimeError(f"Rapport Sprint 11-B existant, écrasement refusé: {destination}")
    all_folds = []
    provenance = []
    horizon_results: dict[str, Any] = {}
    for horizon in config["source_horizons"]:
        horizon_parts: list[pd.DataFrame] = []
        fold_reports = []
        for year in range(2022, 2026):
            label_path = source[year][1] / f"h{horizon}.parquet"
            expected = label_audit["yearly"][year - 2018]["horizons"][str(horizon)]["sha256"]
            if _sha(label_path) != expected:
                raise RuntimeError(f"Labels CN altérés: {label_path}")
            labels = pd.read_parquet(label_path, columns=LABEL_COLUMNS)
            for semester in (f"{year}H1", f"{year}H2"):
                frames = {}
                for model in ("lightgbm", "catboost"):
                    item = _find_run(
                        ranking_root, horizon=horizon, semester=semester, model=model,
                        config_sha=rank_config_sha, code_sha=rank_code_sha, audit_sha=audit_sha,
                    )
                    if item is None:
                        raise RuntimeError(f"Ranking OOS CN manquant: H{horizon}/{semester}/{model}")
                    path, source_report = item
                    frames[model] = pd.read_parquet(path, columns=PREDICTION_COLUMNS)
                    provenance.append({
                        "horizon": horizon, "semester": semester, "model": model,
                        "predictions_sha256": source_report["predictions_sha256"],
                    })
                pool, pool_audit = prepare_pool(
                    combine_oos(frames["lightgbm"], frames["catboost"]), minimum=20,
                )
                pool = merge_labels(pool, labels)
                masks = policy_masks(pool, load_direction_protocol(DIRECTION_CONFIG))
                replay = proxy_returns(pool, config)
                fold = {
                    "horizon": horizon, "semester": semester, "pool_audit": pool_audit,
                    "policies": {
                        name: policy_summary(replay, masks[name], config) for name in POLICIES
                    },
                }
                fold_reports.append(fold)
                for name in POLICIES:
                    replay[f"policy_{name}"] = masks[name].to_numpy()
                horizon_parts.append(replay[[
                    "feasibility", "target_quality_valid", "oracle_decile",
                    "future_return", *[f"net_return_{name}" for name in config["cost_scenarios"]],
                    *[f"policy_{name}" for name in POLICIES],
                ]].copy())
                print(f"Sprint 11-B H{horizon} {semester}: pool={len(pool)} fillable={int(replay['feasibility'].eq('FILLABLE_PROXY').sum())}", flush=True)
        all_folds.extend(fold_reports)
        # Agrégation seulement après validation complète des 8 folds de l'horizon.
        horizon_results[str(horizon)] = {
            "overall": _aggregate_metrics(horizon_parts, config),
            "by_semester": {part["semester"]: part["policies"] for part in fold_reports},
        }
    report = {
        "status": "INDICATIVE_COST_STRESS_ONLY", "market_code": "CN_A",
        "evidence_level": config["evidence_level"], "serving_enabled": False,
        "backtest_executed": False, "decision_gate": config["decision_gate"],
        "execution_rules_source": "fixed_research_assumptions_not_market_execution_rules",
        "protocol_sha256": _sha(config_path), "code_sha256": _sha(Path(__file__)),
        "rank_protocol_sha256": rank_config_sha, "rank_code_sha256": rank_code_sha,
        "label_audit_sha256": audit_sha, "sources": provenance,
        "folds": all_folds, "results": horizon_results,
    }
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": report["status"], "folds": len(all_folds), "report": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ranking-root", type=Path, default=RANKING_OUTPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(config_path=args.config, ranking_root=args.ranking_root,
                         output_root=args.output_root), ensure_ascii=False))


if __name__ == "__main__":
    main()
