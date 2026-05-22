from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backtesting.fidelity import build_compare_to_live_summary


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def test_compare_to_live_summary_aligns_full_stack_across_sessions() -> None:
    research_signals_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "symbol": ["AAPL", "MSFT"],
            "selected": [True, True],
            "rank": [1.0, 1.0],
            "score": [0.91, 0.88],
            "score_source": ["final_score_walk_forward", "final_score_walk_forward"],
            "conviction": [0.93, 0.89],
            "conviction_source": ["core.conviction:score_plus_prediction", "core.conviction:score_plus_prediction"],
            "predicted_proba": [0.72, 0.68],
        }
    )

    risk_entries = [
        _ns(
            symbol="AAPL",
            score_snapshot_date=date(2025, 1, 2),
            approved_shares=10,
            target_weight=0.20,
            conviction_score=0.93,
            predicted_proba=0.72,
            decision="ACCEPTED",
            decision_reason="OK",
            decision_reason_code="ok",
            score_source="final_score_walk_forward",
            selector_signal_mode="strict",
            selection_explanation="sentiment+ml+macro",
        ),
        _ns(
            symbol="MSFT",
            score_snapshot_date=date(2025, 1, 3),
            approved_shares=8,
            target_weight=0.16,
            conviction_score=0.89,
            predicted_proba=0.68,
            decision="ACCEPTED",
            decision_reason="OK",
            decision_reason_code="ok",
            score_source="final_score_walk_forward",
            selector_signal_mode="strict",
            selection_explanation="sentiment+ml+macro",
        ),
    ]

    execution_targets = [
        _ns(symbol="AAPL", trade_date=date(2025, 1, 2), target_shares=10, target_weight=0.20, conviction_score=0.93, risk_run_id="bt-risk-2025-01-02"),
        _ns(symbol="MSFT", trade_date=date(2025, 1, 3), target_shares=8, target_weight=0.16, conviction_score=0.89, risk_run_id="bt-risk-2025-01-03"),
    ]

    execution_fills = [
        _ns(symbol="AAPL", filled_qty=10.0, avg_fill_price=100.0, fill_timestamp=pd.Timestamp("2025-01-02 14:30:00", tz="UTC"), intent_role="entry", exec_run_id="bt-exec-2025-01-02"),
        _ns(symbol="MSFT", filled_qty=8.0, avg_fill_price=200.0, fill_timestamp=pd.Timestamp("2025-01-03 14:30:00", tz="UTC"), intent_role="entry", exec_run_id="bt-exec-2025-01-03"),
    ]

    exit_signals_df = pd.DataFrame(
        {
            "execution_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "symbol": ["AAPL", "MSFT"],
            "filled_qty": [10.0, 8.0],
            "fill_price": [100.0, 200.0],
            "replay_exit_date": pd.to_datetime(["2025-01-08", "2025-01-09"]),
            "replay_exit_price": [108.0, 212.0],
            "replay_exit_reason": ["take_profit", "take_profit"],
        }
    )

    live_risk_decisions = {
        "2025-01-02": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "decision": ["BUY"],
                "approved_shares": [10],
                "target_weight": [0.20],
                "conviction_score": [0.93],
                "predicted_proba": [0.72],
                "run_id": ["live-risk-2025-01-02"],
            }
        ),
        "2025-01-03": pd.DataFrame(
            {
                "symbol": ["MSFT"],
                "decision": ["BUY"],
                "approved_shares": [8],
                "target_weight": [0.16],
                "conviction_score": [0.89],
                "predicted_proba": [0.68],
                "run_id": ["live-risk-2025-01-03"],
            }
        ),
    }

    live_portfolio_targets = {
        "2025-01-02": [_ns(symbol="AAPL", target_shares=10, target_weight=0.20, conviction_score=0.93, risk_run_id="live-risk-2025-01-02")],
        "2025-01-03": [_ns(symbol="MSFT", target_shares=8, target_weight=0.16, conviction_score=0.89, risk_run_id="live-risk-2025-01-03")],
    }

    live_execution_targets = {
        "2025-01-02": [_ns(symbol="AAPL", target_shares=10, target_weight=0.20, conviction_score=0.93, risk_run_id="live-exec-2025-01-02")],
        "2025-01-03": [_ns(symbol="MSFT", target_shares=8, target_weight=0.16, conviction_score=0.89, risk_run_id="live-exec-2025-01-03")],
    }

    live_execution_fills = {
        "2025-01-02": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "side": ["buy"],
                "filled_qty": [10.0],
                "avg_fill_price": [100.0],
                "intent_role": ["entry"],
                "fill_timestamp": pd.to_datetime(["2025-01-02 14:30:00"]),
                "run_id": ["live-exec-2025-01-02"],
            }
        ),
        "2025-01-03": pd.DataFrame(
            {
                "symbol": ["MSFT"],
                "side": ["buy"],
                "filled_qty": [8.0],
                "avg_fill_price": [200.0],
                "intent_role": ["entry"],
                "fill_timestamp": pd.to_datetime(["2025-01-03 14:30:00"]),
                "run_id": ["live-exec-2025-01-03"],
            }
        ),
    }

    live_position_lots = {
        "2025-01-02": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "closed_qty": [10.0],
                "exit_price": [108.0],
                "closed_at": pd.to_datetime(["2025-01-08 15:45:00"]),
                "close_intent_role": ["take_profit"],
                "realized_pnl": [80.0],
                "run_id": ["live-close-2025-01-02"],
            }
        ),
        "2025-01-03": pd.DataFrame(
            {
                "symbol": ["MSFT"],
                "closed_qty": [8.0],
                "exit_price": [212.0],
                "closed_at": pd.to_datetime(["2025-01-09 15:45:00"]),
                "close_intent_role": ["take_profit"],
                "realized_pnl": [96.0],
                "run_id": ["live-close-2025-01-03"],
            }
        ),
    }

    live_compare_context = {
        "2025-01-02": {"risk_run_id": "live-risk-2025-01-02", "exec_run_id": "live-exec-2025-01-02", "match_basis": "risk_run_id"},
        "2025-01-03": {"risk_run_id": "live-risk-2025-01-03", "exec_run_id": "live-exec-2025-01-03", "match_basis": "risk_run_id"},
    }

    summary = build_compare_to_live_summary(
        fidelity_manifest={
            "engine_mode": "pipeline",
            "requested_window": {"start_date": "2025-01-02", "end_date": "2025-01-03"},
        },
        research_signals_df=research_signals_df,
        risk_entries=risk_entries,
        execution_targets=execution_targets,
        execution_fills=execution_fills,
        exit_signals_df=exit_signals_df,
        live_risk_decisions=live_risk_decisions,
        live_portfolio_targets=live_portfolio_targets,
        live_execution_targets=live_execution_targets,
        live_execution_fills=live_execution_fills,
        live_position_lots=live_position_lots,
        live_compare_context=live_compare_context,
        account_id="default",
        phase2_mode="risk_execution",
    )

    assert summary["session_count"] == 2
    assert summary["live_session_count"] == 2
    assert summary["global_scores"]["candidate_alignment_score"] == 1.0
    assert summary["global_scores"]["risk_alignment_score"] == 1.0
    assert summary["global_scores"]["portfolio_alignment_score"] == 1.0
    assert summary["global_scores"]["execution_alignment_score"] == 1.0
    assert summary["global_scores"]["fills_alignment_score"] == 1.0
    assert summary["global_scores"]["exits_alignment_score"] == 1.0
    assert summary["global_scores"]["pnl_alignment_score"] == 1.0
    assert summary["global_scores"]["fidelity_score"] == 1.0

    for session in summary["sessions"]:
        assert session["candidate_compare"]["status"] == "aligned"
        assert session["risk_compare"]["status"] == "aligned"
        assert session["portfolio_compare"]["status"] == "aligned"
        assert session["execution_compare"]["status"] == "aligned"
        assert session["fills_compare"]["status"] == "aligned"
        assert session["exits_compare"]["status"] == "aligned"
        assert session["pnl_compare"]["status"] == "aligned"
        assert session["fidelity_score"] == 1.0

