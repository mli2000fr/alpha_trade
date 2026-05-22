from __future__ import annotations

from datetime import date

import pandas as pd

from backtesting.parity import compare_decisions


def test_compare_decisions_golden_dataset_is_stable() -> None:
    live = pd.DataFrame(
        [
            {"symbol": "AAPL", "decision": "BUY", "approved_shares": 10, "target_weight": 0.10, "conviction_score": 0.80, "run_id": "live-001"},
            {"symbol": "MSFT", "decision": "HOLD", "approved_shares": 0, "target_weight": 0.00, "conviction_score": 0.20, "run_id": "live-001"},
        ]
    )
    replay = pd.DataFrame(
        [
            {"symbol": "AAPL", "decision": "BUY", "approved_shares": 10, "target_weight": 0.10, "conviction_score": 0.80, "run_id": "replay-001"},
            {"symbol": "MSFT", "decision": "SELL", "approved_shares": 0, "target_weight": 0.00, "conviction_score": 0.25, "run_id": "replay-001"},
        ]
    )

    report = compare_decisions(
        live,
        replay,
        trade_date=date(2026, 5, 5),
        account_id="paper-parity",
    )

    assert report.to_dict() == {
        "trade_date": "2026-05-05",
        "account_id": "paper-parity",
        "live_run_id": "live-001",
        "replay_run_id": "replay-001",
        "n_symbols_live": 2,
        "n_symbols_replay": 2,
        "n_matched": 1,
        "n_divergent": 1,
        "divergence_score": 0.5,
        "qty_tolerance_pct": 0.05,
        "qty_tolerance_abs": 1.0,
        "generated_at": report.generated_at,
        "rows": [
            {
                "symbol": "AAPL",
                "live_decision": "BUY",
                "replay_decision": "BUY",
                "live_qty": 10.0,
                "replay_qty": 10.0,
                "live_weight": 0.1,
                "replay_weight": 0.1,
                "live_conviction": 0.8,
                "replay_conviction": 0.8,
                "divergence_kind": "match",
            },
            {
                "symbol": "MSFT",
                "live_decision": "HOLD",
                "replay_decision": "SELL",
                "live_qty": 0.0,
                "replay_qty": 0.0,
                "live_weight": 0.0,
                "replay_weight": 0.0,
                "live_conviction": 0.2,
                "replay_conviction": 0.25,
                "divergence_kind": "action_mismatch",
            },
        ],
    }

