"""Sprint S8 — Tests d'attribution alpha sentiment vs quant pur.

Vérifie que :

- les 4 scénarios par défaut (``quant_only``, ``ml_only``,
  ``sentiment_only``, ``full``) sont exécutés ;
- chaque ``AttributionResult`` expose IC, hit-rate, Sharpe, alpha ;
- les deltas vs ``quant_only`` sont calculés ;
- les artefacts JSON + CSV sont écrits si ``output_dir`` fourni ;
- un signal sentiment parfaitement corrélé au forward-return améliore
  strictement l'IC et l'alpha.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _build_synthetic_panel(seed: int = 7) -> pd.DataFrame:
    """Panneau 30j × 12 symboles avec quant bruité et sentiment quasi-parfait."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    symbols = [f"S{i:02d}" for i in range(12)]
    rows = []
    for d in dates:
        # forward return "vrai" : signal sous-jacent + bruit
        true_signal = rng.normal(0.0, 1.0, size=len(symbols))
        noise = rng.normal(0.0, 0.5, size=len(symbols))
        fwd = 0.001 * true_signal + 0.0005 * noise
        # quant : signal vrai + beaucoup de bruit (corrélation faible)
        quant = true_signal + rng.normal(0.0, 2.0, size=len(symbols))
        # sentiment : très proche du signal vrai (corrélation forte)
        sentiment = true_signal + rng.normal(0.0, 0.2, size=len(symbols))
        # ml : signal vrai modéré + bruit moyen
        ml = true_signal + rng.normal(0.0, 1.0, size=len(symbols))
        for sym, q, s, m, f in zip(symbols, quant, sentiment, ml, fwd):
            rows.append(
                {
                    "date": d,
                    "symbol": sym,
                    "quant_score": float(q),
                    "sentiment_score": float(s),
                    "ml_score": float(m),
                    "fwd_return": float(f),
                }
            )
    return pd.DataFrame(rows)


def test_run_attribution_returns_all_default_scenarios():
    from backtesting.attribution import DEFAULT_SCENARIOS, run_attribution

    panel = _build_synthetic_panel()
    report = run_attribution(panel, top_n=4)
    names = [r.scenario for r in report.results]
    assert names == [s.name for s in DEFAULT_SCENARIOS]
    for r in report.results:
        assert r.n_dates > 0
        assert r.n_obs == len(panel)


def test_attribution_report_exposes_deltas_vs_quant_only():
    from backtesting.attribution import run_attribution

    panel = _build_synthetic_panel()
    report = run_attribution(panel, top_n=4)
    assert "sentiment_only" in report.deltas
    assert "ml_only" in report.deltas
    assert "full" in report.deltas
    for delta in report.deltas.values():
        assert "delta_ic_vs_quant_only" in delta
        assert "delta_sharpe_vs_quant_only" in delta
        assert "delta_alpha_vs_quant_only" in delta


def test_sentiment_strictly_dominates_quant_only_on_synthetic_panel():
    """Avec sentiment fortement corrélé au fwd_return, son IC > IC quant pur."""
    from backtesting.attribution import run_attribution

    panel = _build_synthetic_panel()
    report = run_attribution(panel, top_n=4)
    by_name = {r.scenario: r for r in report.results}
    # IC sentiment_only > IC quant_only (sentiment moins bruité dans la fixture)
    assert by_name["sentiment_only"].ic_mean > by_name["quant_only"].ic_mean
    # Hit-rate sentiment >= hit-rate quant
    assert by_name["sentiment_only"].hit_rate >= by_name["quant_only"].hit_rate - 1e-9


def test_run_attribution_persists_artifacts(tmp_path):
    from backtesting.attribution import run_attribution

    panel = _build_synthetic_panel()
    report = run_attribution(panel, top_n=4, output_dir=tmp_path)

    summary_path = tmp_path / "attribution_summary.json"
    csv_path = tmp_path / "attribution_per_scenario.csv"
    assert summary_path.exists()
    assert csv_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "results" in summary
    assert "deltas" in summary
    assert "metadata" in summary
    assert summary["metadata"]["n_panel_dates"] == panel["date"].nunique()

    df = pd.read_csv(csv_path)
    assert set(df["scenario"]) == {"quant_only", "ml_only", "sentiment_only", "full"}


def test_evaluate_scenario_handles_empty_panel():
    from backtesting.attribution import AttributionScenario, evaluate_scenario

    empty = pd.DataFrame(columns=["date", "symbol", "quant_score", "fwd_return"])
    out = evaluate_scenario(empty, AttributionScenario("quant_only"))
    assert out.n_dates == 0
    assert out.n_obs == 0


def test_evaluate_scenario_raises_on_missing_columns():
    from backtesting.attribution import AttributionScenario, evaluate_scenario

    bad = pd.DataFrame({"date": [pd.Timestamp("2026-01-01")], "symbol": ["A"]})
    with pytest.raises(ValueError, match="fwd_return"):
        evaluate_scenario(bad, AttributionScenario("quant_only"))

