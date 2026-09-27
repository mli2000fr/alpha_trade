"""Sprint 13-B : replay économique CN_A des politiques pré-enregistrées.

Recherche uniquement. Les prédictions 2022–2025 ont déjà été inspectées :
ce rapport n'est ni un holdout indépendant, ni une autorisation de live.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_economic_preflight import (
    DEFAULT_CONFIG,
    POLICIES,
    SAFE_COLUMNS,
    load_protocol,
    select_policies,
)
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANK_CONFIG
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_OUTPUT as RANK_OUTPUT
from modelFactory.cn_global_ranking_walk_forward import _sha
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH
from modelFactory.cn_portfolio_replay import load_cn_market, load_verified_action_evidence
from service.market import cn_portfolio_replay as replay_service
from service.market.cn_portfolio_replay import CNIntent, CNPortfolioReplay, ReplayConfig

DEFAULT_EVIDENCE = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13a2" / "evidence.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
POLICY_NAMES = (*POLICIES, "momentum_top20_same_universe")


def _sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def _source(semester: str) -> tuple[Path, dict[str, Any]]:
    from modelFactory import cn_global_ranking_walk_forward as ranking_runner

    item = _find_run(
        RANK_OUTPUT, horizon=20, semester=semester, model="lightgbm",
        config_sha=_sha(RANK_CONFIG), code_sha=_sha(Path(ranking_runner.__file__)),
        audit_sha=_sha(AUDIT_PATH),
    )
    if item is None:
        raise RuntimeError(f"Ranking OOS verrouillé absent : {semester}")
    return item


def select_momentum(frame: pd.DataFrame) -> pd.DataFrame:
    """Benchmark relatif au CSI300, top20 de relative_return_20, sans Oracle."""
    if set(frame) != set(SAFE_COLUMNS) or set(frame["market_code"]) != {"CN_A"}:
        raise ValueError("Frame de benchmark CN invalide")
    ordered = frame.dropna(subset=["baseline_score"]).sort_values(
        ["session_date", "baseline_score", "instrument_id"],
        ascending=[True, False, True], kind="stable",
    )
    rank = ordered.groupby("session_date", sort=False).cumcount()
    size = ordered.groupby("session_date", sort=False)["instrument_id"].transform("size")
    return ordered.loc[(size >= 20) & (rank < np.ceil(size * 0.20))]


def eligible_signal_dates(sessions: list[date], *, horizon: int = 20) -> set[date]:
    """Ne démarre pas une position dont la sortie prévue dépasse le semestre."""
    return set(sessions[:max(0, len(sessions) - horizon - 1)])


def _tie_priority(semester: str, signal_date: date, instrument_id: int, seed: int) -> Decimal:
    payload = f"CN_A|H20|{semester}|{signal_date}|{instrument_id}|{seed}"
    return Decimal(int(hashlib.sha256(payload.encode()).hexdigest()[:14], 16))


def make_intents(selected: pd.DataFrame, *, semester: str, seed: int,
                 valid_dates: set[date], ticket: Decimal, policy: str) -> list[CNIntent]:
    dates = pd.to_datetime(selected["session_date"]).dt.date
    subset = selected.loc[dates.isin(valid_dates), ["session_date", "instrument_id"]]
    if subset.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Signaux économiques CN dupliqués")
    return [CNIntent(
        intent_id=f"{policy}-{seed}-{day}-{identifier}",
        signal_date=day, instrument_id=int(identifier), side="BUY",
        budget_cny=ticket, reason=f"SPRINT13B_{policy}",
        priority=_tie_priority(semester, day, int(identifier), seed),
    ) for day, identifier in zip(pd.to_datetime(subset["session_date"]).dt.date,
                                  subset["instrument_id"], strict=True)]


def _benchmark_csi300(conn: Any, start: date, end: date) -> dict[str, Any]:
    rows = conn.execute(text("""
        SELECT b.`date` day,b.`open`,b.`close` FROM stock_bars_daily b
        JOIN instrument_provider_symbols p ON p.instrument_id=b.instrument_id
        WHERE p.provider='baostock' AND p.provider_symbol='sh.000300'
          AND b.market_code='CN_A' AND b.`date` BETWEEN :start AND :end
        ORDER BY b.`date`
    """), {"start": start, "end": end}).mappings().all()
    if len(rows) < 60 or any(row["open"] is None or row["close"] is None for row in rows):
        raise RuntimeError("Benchmark CSI 300 incomplet")
    opening, closing = Decimal(str(rows[0]["open"])), Decimal(str(rows[-1]["close"]))
    if opening <= 0 or closing <= 0:
        raise RuntimeError("Benchmark CSI 300 invalide")
    return {"sessions": len(rows), "start": str(rows[0]["day"]),
            "end": str(rows[-1]["day"]),
            "raw_price_return": float(closing / opening - 1),
            "costs_and_fill_model": "none; contextual index only; not a tradable ETF"}


def summarize_replay(result: Any, *, capital: Decimal) -> dict[str, Any]:
    daily = result.daily
    values = np.asarray([float(item["equity_mark_cny"]) for item in daily], dtype=float)
    returns = values[1:] / values[:-1] - 1
    valid_marks = np.asarray([bool(item["mark_valid"]) for item in daily], dtype=bool)
    paired_valid = valid_marks[1:] & valid_marks[:-1]
    usable_returns = returns[paired_valid]
    if not np.isfinite(values).all() or (values <= 0).any():
        raise RuntimeError("Valorisation CN non finie ou non positive")
    peak = np.maximum.accumulate(values)
    drawdown = values / peak - 1
    downside = usable_returns[usable_returns < 0]
    sharpe = (float(np.mean(usable_returns) / np.std(usable_returns, ddof=1) * math.sqrt(252))
              if len(usable_returns) > 2 and np.std(usable_returns, ddof=1) > 0 else None)
    sortino = (float(np.mean(usable_returns) / np.sqrt(np.mean(downside ** 2)) * math.sqrt(252))
               if len(downside) and np.mean(downside ** 2) > 0 else None)
    counts = Counter(item["event"] for item in result.journal)
    reasons = Counter(f"{item['event']}:{item['reason']}" for item in result.journal if item.get("reason"))
    fills = [item for item in result.journal if item["event"] == "HYPOTHETICAL_FILL"]
    realized = [Decimal(item["realized_pnl_ex_dividend_cny"]) for item in result.journal
                if item["event"] == "REALIZED_SALE"]
    positives = [value for value in realized if value > 0]
    negatives = [value for value in realized if value < 0]
    exposure = [float(Decimal(item["holdings_mark_cny"]) / Decimal(item["equity_mark_cny"]))
                for item in daily if Decimal(item["equity_mark_cny"]) > 0]
    turnover = sum(Decimal(item["notional_cny"]) for item in fills) / capital
    monthly: dict[str, float] = {}
    for index, value in enumerate(returns, start=1):
        month = daily[index]["session_date"][:7]
        monthly[month] = (1 + monthly.get(month, 0.0)) * (1 + float(value)) - 1
    valid = bool(result.economic_result_valid and valid_marks.all() and not result.pending_intents
                 and not result.lots)
    return {
        "status": "RESEARCH_MARK_VALID" if valid else "BLOCKED_DATA_QUALITY_OR_OPEN_POSITION",
        "economic_result_valid": valid,
        "marked_return_proxy": float(values[-1] / float(capital) - 1),
        "end_equity_cny": str(daily[-1]["equity_mark_cny"]),
        "sharpe_valid_mark_days_only": sharpe,
        "sortino_valid_mark_days_only": sortino,
        "max_drawdown_marked": float(drawdown.min()),
        "average_gross_exposure": float(np.mean(exposure)) if exposure else None,
        "turnover_notional_over_initial_capital": float(turnover),
        "commission_total_cny": str(daily[-1]["commission_cny"]),
        "other_costs_total_cny": str(daily[-1]["other_costs_cny"]),
        "buy_fills": sum(item["side"] == "BUY" for item in fills),
        "sell_fills": sum(item["side"] == "SELL" for item in fills),
        "win_rate_ex_dividend": len(positives) / len(realized) if realized else None,
        "payoff_ex_dividend": (float(np.mean([float(x) for x in positives]) /
                                     abs(np.mean([float(x) for x in negatives])))
                                if positives and negatives else None),
        "profit_factor_ex_dividend": (float(sum(positives) / abs(sum(negatives)))
                                      if negatives else None),
        "invalid_mark_sessions": int((~valid_marks).sum()),
        "unresolved_instruments": result.unresolved,
        "open_lots": {str(key): sum(lot.shares for lot in lots)
                      for key, lots in result.lots.items()},
        "pending_intents": result.pending_intents[:50],
        "event_counts": dict(counts), "reason_counts": dict(reasons),
        "monthly_mark_returns": monthly,
        "dividend_tax": "gross_before_tax_upper_bound_unknown_investor_holding_period",
    }


def aggregate_runs(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Ne publie aucune moyenne économique sur un groupe partiellement invalide."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in runs.values():
        key = row["policy"], row["scenario"], row["cost_profile"]
        grouped.setdefault(key, []).append(row)
    summary = {}
    for (policy, scenario, cost_key), values in sorted(grouped.items()):
        valid = [row for row in values if row["economic_result_valid"]]
        summary[f"{policy}__{scenario}__{cost_key}"] = {
            "runs": len(values), "valid_runs": len(valid),
            "blocked_runs": len(values) - len(valid),
            "all_valid": len(valid) == len(values),
            "mean_semester_marked_return_only_if_all_valid": (
                float(np.mean([row["marked_return_proxy"] for row in valid]))
                if len(valid) == len(values) and valid else None
            ),
            "invalid_reason_counts": dict(Counter(
                "unresolved_position" if row["unresolved_instruments"] else
                "invalid_mark_or_open_position" for row in values
                if not row["economic_result_valid"]
            )),
        }
    return summary


def run(*, output_root: Path = DEFAULT_OUTPUT, evidence_path: Path = DEFAULT_EVIDENCE,
        semesters: list[str] | None = None, policies: list[str] | None = None,
        seeds: list[int] | None = None, scenarios: list[str] | None = None,
        cost_profiles: list[str] | None = None) -> dict[str, Any]:
    protocol = load_protocol(DEFAULT_CONFIG)
    selected_semesters = semesters or protocol["test_semesters"]
    selected_policies = policies or list(POLICY_NAMES)
    selected_seeds = seeds if seeds is not None else protocol["portfolio"]["tie_break_seeds"]
    selected_scenarios = scenarios or protocol["fill_scenarios"]
    selected_costs = cost_profiles or protocol["cost_profiles"]
    if (not set(selected_semesters).issubset(protocol["test_semesters"])
            or not set(selected_policies).issubset(POLICY_NAMES)
            or not set(selected_seeds).issubset(protocol["portfolio"]["tie_break_seeds"])
            or not set(selected_scenarios).issubset(protocol["fill_scenarios"])
            or not set(selected_costs).issubset(protocol["cost_profiles"])):
        raise ValueError("Sous-ensemble Sprint 13-B étranger au protocole gelé")
    evidence = load_verified_action_evidence(evidence_path)
    a2_report = json.loads((evidence_path.parent / "report.json").read_text(encoding="utf-8"))
    if (a2_report["preflight"]["gate_unchanged"] != 0.05
            or not a2_report["preflight"]["all_policies_pass"]):
        raise RuntimeError("Gate A2 non passé ou modifié")
    fingerprint = _sha_json({
        "protocol": _sha(DEFAULT_CONFIG), "evidence": a2_report["evidence_sha256"],
        "code": _sha(Path(__file__)), "engine": _sha(Path(replay_service.__file__)),
        "subset": [selected_semesters, selected_policies, selected_seeds,
                   selected_scenarios, selected_costs],
    })[:16]
    destination = output_root / f"sprint13b-{fingerprint}"
    destination.mkdir(parents=True, exist_ok=True)
    overview: dict[str, Any] = {
        "experiment": "cn_economic_replay_sprint13b_v1", "status": "INCOMPLETE",
        "previously_inspected_oos_not_independent_holdout": True,
        "serving_enabled": False, "live_enabled": False,
        "protocol_sha256": _sha(DEFAULT_CONFIG),
        "evidence_sha256": a2_report["evidence_sha256"],
        "subset": {"semesters": selected_semesters, "policies": selected_policies,
                   "seeds": selected_seeds, "scenarios": selected_scenarios,
                   "cost_profiles": selected_costs},
        "runs": {}, "csi300": {},
    }
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Sprint 13-B interdit hors alpha_trade_cn")
            for semester in selected_semesters:
                path, source = _source(semester)
                frame = pd.read_parquet(path, columns=SAFE_COLUMNS)
                year, half = int(semester[:4]), int(semester[-1])
                start = date(year, 1 if half == 1 else 7, 1)
                end = date(year, 6, 30) if half == 1 else date(year, 12, 31)
                observed = pd.to_datetime(frame["session_date"]).dt.date
                if not observed.between(start, end).all():
                    raise RuntimeError(f"Prédictions hors semestre : {semester}")
                pool, masks = select_policies(frame, minimum=protocol["portfolio"]["min_oracle_pool_per_session"])
                selections = {policy: pool.loc[masks[policy]] for policy in POLICIES}
                selections["momentum_top20_same_universe"] = select_momentum(frame)
                required = sorted({int(value) for policy in selected_policies
                                   for value in selections[policy]["instrument_id"]})
                days, instruments, bars, actions = load_cn_market(
                    conn, start=start, end=end, instrument_ids=required, evidence=evidence,
                )
                valid_dates = eligible_signal_dates(days)
                if len(days) < 60 or not valid_dates:
                    raise RuntimeError(f"Calendrier CN insuffisant: {semester}")
                overview["csi300"][semester] = _benchmark_csi300(conn, start, end)
                for policy in selected_policies:
                    for seed in selected_seeds:
                        intents = make_intents(
                            selections[policy], semester=semester, seed=seed,
                            valid_dates=valid_dates,
                            ticket=Decimal(protocol["portfolio"]["ticket_cny"]), policy=policy,
                        )
                        for scenario in selected_scenarios:
                            for cost_key in selected_costs:
                                key = f"{semester}__{policy}__seed{seed}__{scenario}__{cost_key}"
                                target = destination / key
                                report_path = target / "report.json"
                                if report_path.exists():
                                    report = json.loads(report_path.read_text(encoding="utf-8"))
                                    if report.get("source_predictions_sha256") != source["predictions_sha256"]:
                                        raise RuntimeError(f"Artefact de reprise incompatible : {key}")
                                    overview["runs"][key] = report
                                    continue
                                config = ReplayConfig(
                                    initial_cash_cny=Decimal(protocol["portfolio"]["initial_cash_cny"]),
                                    cost_profile_key=cost_key, scenario=scenario,
                                    pending_policy="cancel_day", max_positions=8,
                                    allow_research_rules=True, allow_research_proxy=True,
                                    auto_exit_after_full_sessions=20,
                                    suppress_signals_during_open_position=True,
                                )
                                result = CNPortfolioReplay(conn, config).run(
                                    sessions=days, instruments=instruments, bars=bars,
                                    intents=intents, actions=actions,
                                )
                                report = summarize_replay(result, capital=config.initial_cash_cny)
                                report.update({"semester": semester, "policy": policy, "seed": seed,
                                               "scenario": scenario, "cost_profile": cost_key,
                                               "signal_count": len(intents),
                                               "source_predictions_sha256": source["predictions_sha256"],
                                               "evidence_sha256": a2_report["evidence_sha256"],
                                               "csi300_contextual": overview["csi300"][semester]})
                                target.mkdir(parents=True, exist_ok=True)
                                with gzip.open(target / "journal.jsonl.gz", "wt", encoding="utf-8") as stream:
                                    for entry in result.journal:
                                        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
                                pd.DataFrame(result.daily).to_parquet(target / "daily.parquet", index=False)
                                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                                overview["runs"][key] = report
                                print(f"Sprint 13-B {key}: {report['status']} return={report['marked_return_proxy']:+.3%}", flush=True)
                (destination / "progress.json").write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        engine.dispose()
    full = (selected_semesters == protocol["test_semesters"]
            and selected_policies == list(POLICY_NAMES)
            and selected_seeds == protocol["portfolio"]["tie_break_seeds"]
            and selected_scenarios == protocol["fill_scenarios"]
            and selected_costs == protocol["cost_profiles"])
    overview["status"] = (
        "COMPLETE_RESEARCH_ALL_VALID" if full and all(row["economic_result_valid"] for row in overview["runs"].values())
        else "COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL"
    )
    overview["aggregate"] = aggregate_runs(overview["runs"])
    overview["economic_go_allowed"] = False
    (destination / "report.json").write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    overview["report_path"] = str(destination / "report.json")
    return overview


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 13-B CN_A : replay économique de recherche")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--semesters", nargs="+")
    parser.add_argument("--policies", nargs="+")
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument("--scenarios", nargs="+")
    parser.add_argument("--cost-profiles", nargs="+")
    args = parser.parse_args()
    report = run(output_root=args.output_root, evidence_path=args.evidence,
                 semesters=args.semesters, policies=args.policies,
                 seeds=args.seeds, scenarios=args.scenarios,
                 cost_profiles=args.cost_profiles)
    print(json.dumps({"status": report["status"], "report_path": report["report_path"],
                      "runs": len(report["runs"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
