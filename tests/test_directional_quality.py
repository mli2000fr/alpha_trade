from __future__ import annotations

from types import SimpleNamespace

import pandas as pd


def test_load_directional_quality_gate_builds_independent_side_sets(monkeypatch, tmp_path):
    from ihm.services import ml_artifacts
    from modelFactory.directional_quality import load_directional_quality_gate

    selection = {
        "scanned_symbols": 4,
        "strict": {
            "long_only": ["AAA"],
            "short_only": ["BBB"],
            "long_short": ["BOTH"],
        },
        "discovery": {
            "long_only": ["AAA", "NEWL"],
            "short_only": ["BBB"],
            "long_short": ["BOTH"],
        },
        "audit_df": pd.DataFrame({"symbol": ["AAA", "BBB", "BOTH", "NEWL"]}),
    }
    monkeypatch.setattr(
        ml_artifacts,
        "build_batch_directional_candidate_selection",
        lambda *_args, **_kwargs: selection,
    )

    gate = load_directional_quality_gate("batch-1", tmp_path, level="strict")

    assert gate.allowed_long == frozenset({"AAA", "BOTH"})
    assert gate.allowed_short == frozenset({"BBB", "BOTH"})
    assert gate.scanned_symbols == 4


def test_directional_quality_gate_flattens_only_the_rejected_side():
    from modelFactory.directional_quality import (
        DirectionalQualityGate,
        apply_directional_quality_gate,
    )

    gate = DirectionalQualityGate(
        batch_id="batch-1",
        level="strict",
        scanned_symbols=3,
        allowed_long=frozenset({"LONG_OK", "BOTH"}),
        allowed_short=frozenset({"SHORT_OK", "BOTH"}),
        audit_df=pd.DataFrame(),
    )
    frame = pd.DataFrame(
        {
            "symbol": ["LONG_OK", "SHORT_OK", "BOTH", "BOTH"],
            "predicted_side": ["long", "long", "short", "flat"],
            "cascade_score": [0.8, 0.9, 0.7, 0.0],
        }
    )

    result, counts = apply_directional_quality_gate(frame, gate)

    assert result["predicted_side"].tolist() == ["long", "flat", "short", "flat"]
    assert result["cascade_score"].tolist() == [0.8, 0.0, 0.7, 0.0]
    assert counts == {
        "long_before": 2,
        "short_before": 1,
        "long_rejected": 1,
        "short_rejected": 0,
    }


def test_trade_export_prefers_executed_portfolio_truth_over_pipeline_candidates():
    from backtesting.report import build_trade_export_bundle

    portfolio = SimpleNamespace(
        closed_trades_df=pd.DataFrame(
            [{"symbol": "AAA", "entry_date": "2024-01-02", "exit_date": "2024-01-05", "pnl": 10.0}]
        )
    )
    candidates = pd.DataFrame(
        [
            {"symbol": "AAA", "side": "buy", "execution_date": "2024-01-02"},
            {"symbol": "BBB", "side": "buy", "execution_date": "2024-01-03"},
        ]
    )

    exported, summary = build_trade_export_bundle(
        portfolio,
        pipeline_signals_df=candidates,
    )

    assert exported["symbol"].tolist() == ["AAA"]
    assert summary["source"] == "closed_trades_df"
    assert summary["row_count"] == 1
    assert summary["pipeline_signal_rows"] == 2
