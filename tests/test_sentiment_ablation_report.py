from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backtesting.attribution import run_attribution


def _build_panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    dates = pd.date_range("2026-01-05", periods=4, freq="B")
    symbols = ["AAPL", "MSFT", "NVDA", "AMD"]
    for index, trade_date in enumerate(dates):
        regime = "bull" if index < 2 else "bear"
        for rank, symbol in enumerate(symbols, start=1):
            base = 0.05 * rank
            rows.append(
                {
                    "date": trade_date,
                    "symbol": symbol,
                    "market_regime": regime,
                    "quant_score": base,
                    "sentiment_score": base + (0.20 if regime == "bull" else -0.05),
                    "ml_score": base + (0.10 if symbol in {"AAPL", "NVDA"} else -0.02),
                    "fwd_return": 0.001 * rank + (0.002 if regime == "bull" else -0.001),
                }
            )
    return pd.DataFrame(rows)


def test_run_attribution_persists_regime_breakdown(tmp_path: Path) -> None:
    report = run_attribution(_build_panel(), top_n=2, output_dir=tmp_path, regime_column="market_regime")

    assert report.metadata["n_regimes"] == 2
    assert set(report.regime_results) == {"bear", "bull"}
    assert {result.scenario for result in report.regime_results["bull"]} == {
        "quant_only",
        "ml_only",
        "sentiment_only",
        "full",
    }

    summary = json.loads((tmp_path / "attribution_summary.json").read_text(encoding="utf-8"))
    assert "regime_results" in summary
    assert set(summary["regime_results"]) == {"bear", "bull"}

    regime_df = pd.read_csv(tmp_path / "attribution_by_regime.csv")
    assert set(regime_df["regime"]) == {"bear", "bull"}
    assert set(regime_df["scenario"]) == {"quant_only", "ml_only", "sentiment_only", "full"}

