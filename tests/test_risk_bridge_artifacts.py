from __future__ import annotations

from datetime import date, datetime, timezone
import json

import pandas as pd

from backtesting.risk_bridge import RiskBridgeResult, save_phase2_risk_artifacts
from risk_management.decision_fingerprint import AuditLogEntry, DecisionAuditLog, build_decision_fingerprint


def test_save_phase2_risk_artifacts_exports_market_regimes_csv(tmp_path) -> None:
    result = RiskBridgeResult(
        entries=[],
        signals_df=pd.DataFrame(),
        diagnostics={"snapshot_dates": 1},
        regime_snapshots={
            date(2025, 1, 2): {
                "trade_date": "2025-01-02",
                "as_of": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
                "mode": "capital_preservation",
                "raw_mode": "capital_preservation",
                "allow_new_entries": True,
                "risk_multiplier": 0.85,
                "effective_max_positions": 3,
                "soft_signal_count": 2,
                "hard_triggered": False,
                "transition_action": "enter_defensive",
                "data_quality": {"macro": "ok"},
                "mode_why": {
                    "summary": "VIX élevé",
                    "primary_source": "vix_high",
                },
            }
        },
    )

    artifacts = save_phase2_risk_artifacts(result, tmp_path)

    assert "market_regimes" in artifacts
    market_regimes_path = tmp_path / "market_regimes.csv"
    assert market_regimes_path.exists()

    exported_df = pd.read_csv(market_regimes_path)
    assert exported_df["trade_date"].tolist() == ["2025-01-02"]
    assert exported_df["market_regime"].tolist() == ["capital_preservation"]
    assert exported_df["summary"].tolist() == ["VIX élevé"]
    assert exported_df["primary_source"].tolist() == ["vix_high"]


def test_save_phase2_risk_artifacts_exports_decision_audit_log(tmp_path) -> None:
    trade_date = date(2025, 1, 2)
    fingerprint = build_decision_fingerprint(
        trade_date,
        "backtest-2025-01-02",
        config_fingerprint="config-fingerprint",
        model_run_id="ml-run-1",
        universe_fingerprint="AAPL",
        candidate_count=1,
    )
    audit_log = DecisionAuditLog(
        trade_date=trade_date,
        run_id=fingerprint.run_id,
        decision_fingerprint=fingerprint,
        entries=[AuditLogEntry(
            trade_date=trade_date,
            timestamp=datetime(2025, 1, 2),
            run_id=fingerprint.run_id,
            symbol="AAPL",
            side="long",
            decision="ACCEPTED",
            reason="OK",
            proposed_shares=10,
            approved_shares=10,
            entry_price=100.0,
            fingerprint="position-fingerprint",
        )],
    )
    result = RiskBridgeResult(
        entries=[],
        signals_df=pd.DataFrame(),
        diagnostics={},
        decision_audit_logs={trade_date: audit_log},
    )

    artifacts = save_phase2_risk_artifacts(result, tmp_path)

    assert "phase2_risk_decision_audit_json" in artifacts
    with (tmp_path / "phase2_risk_decision_audit.json").open(encoding="utf-8") as handle:
        exported = json.load(handle)
    assert exported["2025-01-02"]["decision_fingerprint"]["fingerprint"] == fingerprint.fingerprint
    assert exported["2025-01-02"]["entries"][0]["fingerprint"] == "position-fingerprint"

