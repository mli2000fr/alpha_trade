"""Gate de fin de backfill de l'univers quotidien CN_A."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_universe_pit import CNUniversePolicy, _fingerprint

ROOT = Path(__file__).resolve().parents[1]


def audit(*, start: date, end: date, config: Path) -> dict:
    policy = CNUniversePolicy.from_yaml(config)
    policy_hash = _fingerprint(asdict(policy))
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    with engine.connect() as conn:
        sessions = set(conn.execute(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date BETWEEN :start AND :end"
        ), {"start": start, "end": end}).scalars())
        runs = [dict(row) for row in conn.execute(text(
            "SELECT universe_run_id,session_date,instrument_count,candidate_count,audited_count "
            "FROM cn_universe_runs WHERE market_code='CN_A' AND policy_fingerprint=:policy "
            "AND session_date BETWEEN :start AND :end AND status='COMPLETED'"
        ), {"policy": policy_hash, "start": start, "end": end}).mappings()]
        run_ids = [row["universe_run_id"] for row in runs]
        by_date: dict[date, int] = {}
        for row in runs:
            by_date[row["session_date"]] = by_date.get(row["session_date"], 0) + 1
        # Les agrégats ne balayent que les runs de la politique demandée.
        decision_counts = dict(conn.execute(text(
            "SELECT d.universe_run_id,COUNT(*) FROM cn_universe_decisions d "
            "JOIN cn_universe_runs r ON r.universe_run_id=d.universe_run_id "
            "WHERE r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end "
            "GROUP BY d.universe_run_id"
        ), {"policy": policy_hash, "start": start, "end": end}).all())
        audit_counts = dict(conn.execute(text(
            "SELECT a.universe_run_id,COUNT(*) FROM cn_universe_execution_audit a "
            "JOIN cn_universe_runs r ON r.universe_run_id=a.universe_run_id "
            "WHERE r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end "
            "GROUP BY a.universe_run_id"
        ), {"policy": policy_hash, "start": start, "end": end}).all())
        bad_temporal = conn.execute(text(
            "SELECT COUNT(*) FROM cn_universe_decisions d JOIN cn_universe_runs r "
            "ON r.universe_run_id=d.universe_run_id WHERE r.policy_fingerprint=:policy "
            "AND r.session_date BETWEEN :start AND :end "
            "AND (d.last_bar_date>=r.session_date OR d.source_available_at>r.decision_at)"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        bad_lifecycle = conn.execute(text(
            "SELECT COUNT(*) FROM cn_universe_decisions d JOIN cn_universe_runs r "
            "ON r.universe_run_id=d.universe_run_id JOIN instruments i ON i.instrument_id=d.instrument_id "
            "WHERE r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end "
            "AND d.decision_state='CANDIDATE' "
            "AND (i.listing_date IS NULL OR i.listing_date>r.session_date OR i.delisting_date<r.session_date)"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        source_conflicts = conn.execute(text(
            "SELECT COUNT(*) FROM stock_bars_daily FORCE INDEX(ix_cn_daily_status_date) "
            "WHERE trading_status LIKE 'SUSPENDED%SOURCE_CONFLICT%' AND date BETWEEN :start AND :end"
        ), {"start": start, "end": end}).scalar_one()
        source_unknown_limits = conn.execute(text(
            "SELECT COUNT(*) FROM cn_daily_price_limits FORCE INDEX(ix_cn_limits_policy_date) "
            "WHERE policy_code='OBSERVED_OUTSIDE_DERIVED_LIMIT_V1' AND session_date BETWEEN :start AND :end"
        ), {"start": start, "end": end}).scalar_one()
        audited_conflicts = conn.execute(text(
            "SELECT COUNT(*) FROM stock_bars_daily b FORCE INDEX(ix_cn_daily_status_date) "
            "STRAIGHT_JOIN cn_universe_runs r ON r.session_date=b.date AND r.market_code='CN_A' "
            "STRAIGHT_JOIN cn_universe_execution_audit a "
            "ON a.universe_run_id=r.universe_run_id AND a.instrument_id=b.instrument_id "
            "WHERE b.trading_status LIKE 'SUSPENDED%SOURCE_CONFLICT%' "
            "AND r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        audited_unknown_limits = conn.execute(text(
            "SELECT COUNT(*) FROM cn_daily_price_limits l FORCE INDEX(ix_cn_limits_policy_date) "
            "STRAIGHT_JOIN cn_universe_runs r ON r.session_date=l.session_date AND r.market_code='CN_A' "
            "STRAIGHT_JOIN cn_universe_execution_audit a "
            "ON a.universe_run_id=r.universe_run_id AND a.instrument_id=l.instrument_id "
            "WHERE l.policy_code='OBSERVED_OUTSIDE_DERIVED_LIMIT_V1' "
            "AND r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        bad_conflicts = conn.execute(text(
            "SELECT COUNT(*) FROM stock_bars_daily b FORCE INDEX(ix_cn_daily_status_date) "
            "STRAIGHT_JOIN cn_universe_runs r ON r.session_date=b.date AND r.market_code='CN_A' "
            "STRAIGHT_JOIN cn_universe_execution_audit a "
            "ON a.universe_run_id=r.universe_run_id AND a.instrument_id=b.instrument_id "
            "WHERE b.trading_status LIKE 'SUSPENDED%SOURCE_CONFLICT%' "
            "AND r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end "
            "AND a.audit_state<>'EXCLUDED'"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        bad_limits = conn.execute(text(
            "SELECT COUNT(*) FROM cn_daily_price_limits l FORCE INDEX(ix_cn_limits_policy_date) "
            "STRAIGHT_JOIN cn_universe_runs r ON r.session_date=l.session_date AND r.market_code='CN_A' "
            "STRAIGHT_JOIN cn_universe_execution_audit a "
            "ON a.universe_run_id=r.universe_run_id AND a.instrument_id=l.instrument_id "
            "WHERE l.policy_code='OBSERVED_OUTSIDE_DERIVED_LIMIT_V1' "
            "AND r.policy_fingerprint=:policy AND r.session_date BETWEEN :start AND :end "
            "AND a.audit_state<>'UNVERIFIABLE'"
        ), {"policy": policy_hash, "start": start, "end": end}).scalar_one()
        terminal = conn.execute(text(
            "SELECT COUNT(*) total,"
            "SUM(CASE WHEN d.decision_state='CANDIDATE' THEN 1 ELSE 0 END) candidates,"
            "SUM(CASE WHEN d.decision_state='CANDIDATE' AND "
            "(a.audit_reason IS NULL OR a.audit_reason<>'NO_SESSION_BAR') THEN 1 ELSE 0 END) bad_audits "
            "FROM instruments i STRAIGHT_JOIN market_sessions s "
            "ON s.market_code='CN_A' AND s.session_date=i.delisting_date AND s.session_status='open' "
            "LEFT JOIN stock_bars_daily b ON b.instrument_id=i.instrument_id AND b.date=i.delisting_date "
            "JOIN cn_universe_runs r ON r.market_code='CN_A' AND r.session_date=i.delisting_date "
            "JOIN cn_universe_decisions d ON d.universe_run_id=r.universe_run_id "
            "AND d.instrument_id=i.instrument_id "
            "LEFT JOIN cn_universe_execution_audit a ON a.universe_run_id=r.universe_run_id "
            "AND a.instrument_id=i.instrument_id "
            "WHERE i.market_code='CN_A' AND i.instrument_type='equity' "
            "AND i.delisting_date BETWEEN :start AND :end AND b.instrument_id IS NULL "
            "AND r.policy_fingerprint=:policy"
        ), {"policy": policy_hash, "start": start, "end": end}).mappings().one()
    missing = sorted(sessions - set(by_date))
    duplicate_dates = sorted(day for day, count in by_date.items() if count != 1)
    count_mismatches = [row["session_date"] for row in runs if
                        decision_counts.get(row["universe_run_id"], 0) != row["instrument_count"] or
                        audit_counts.get(row["universe_run_id"], 0) != row["candidate_count"] or
                        row["audited_count"] != row["candidate_count"]]
    result = {
        "start": start.isoformat(), "end": end.isoformat(), "policy_fingerprint": policy_hash,
        "expected_sessions": len(sessions), "completed_runs": len(run_ids),
        "missing_sessions": [day.isoformat() for day in missing],
        "duplicate_session_runs": [day.isoformat() for day in duplicate_dates],
        "count_mismatch_sessions": [day.isoformat() for day in count_mismatches],
        "future_data_decisions": int(bad_temporal), "invalid_lifecycle_candidates": int(bad_lifecycle),
        "source_conflicts": int(source_conflicts), "candidate_conflicts_audited": int(audited_conflicts),
        "source_unknown_limits": int(source_unknown_limits),
        "candidate_unknown_limits_audited": int(audited_unknown_limits),
        "conflicts_not_excluded": int(bad_conflicts), "unknown_limits_not_unverifiable": int(bad_limits),
        "terminal_no_bar": int(terminal["total"] or 0),
        "candidate_terminal_no_bar": int(terminal["candidates"] or 0),
        "terminal_no_bar_bad_audits": int(terminal["bad_audits"] or 0),
    }
    result["status"] = "PASS" if (
        sessions and not missing and not duplicate_dates and not count_mismatches and
        bad_temporal == bad_lifecycle == bad_conflicts == bad_limits == 0 and
        int(terminal["bad_audits"] or 0) == 0
    ) else "INCOMPLETE"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditer le backfill univers CN_A")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "universe_cn.yaml")
    args = parser.parse_args()
    result = audit(start=args.start_date, end=args.end_date, config=args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
