from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory import oracle_amplitude_audit as amplitude


def _bars(*, jump: float = 0.01, periods: int = 35, gap_at: int | None = None) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    close = 100.0 * np.power(1.0 + jump, np.arange(periods))
    open_ = close.copy()
    if gap_at is not None:
        open_[gap_at] = close[gap_at - 1] * 1.10
    return pd.DataFrame({
        "date": dates, "symbol": "AAA", "open": open_,
        "high": np.maximum(open_, close) * 1.005,
        "low": np.minimum(open_, close) * 0.995, "close": close,
    })


def test_amplitude_panel_is_direction_neutral_and_uses_entry_open() -> None:
    config = amplitude.AmplitudeAuditConfig(horizons=(3,), atr_window=3)
    rising = amplitude.build_amplitude_panel(_bars(jump=0.01), config)
    falling = amplitude.build_amplitude_panel(_bars(jump=-0.01), config)
    rise = rising.iloc[5]
    fall = falling.iloc[5]
    assert rise["h3_terminal_return"] > 0
    assert fall["h3_terminal_return"] < 0
    assert rise["h3_abs_terminal_return"] == pytest.approx(
        abs(rise["h3_terminal_return"])
    )
    assert fall["h3_abs_terminal_return"] == pytest.approx(
        abs(fall["h3_terminal_return"])
    )
    assert rise["h3_max_abs_excursion"] >= rise["h3_abs_terminal_return"]
    assert fall["h3_max_abs_excursion"] >= fall["h3_abs_terminal_return"]
    assert rise["h3_max_abs_excursion_capped_100pct"] <= 1.0


def test_amplitude_panel_filters_large_entry_gap_and_censors_tail() -> None:
    config = amplitude.AmplitudeAuditConfig(horizons=(3, 5), atr_window=3)
    panel = amplitude.build_amplitude_panel(_bars(gap_at=7), config)
    # Signal index 6 entre à l'open index 7: gap de 10 %, donc inéligible.
    row = panel.iloc[6]
    assert not bool(row["amplitude_entry_eligible"])
    assert pd.isna(row["h3_max_abs_excursion"])
    assert panel.iloc[-2]["amplitude_entry_eligible"]
    assert pd.isna(panel.iloc[-2]["h3_max_abs_excursion"])


def test_amplitude_panel_censors_corporate_price_discontinuity() -> None:
    bars = _bars(periods=35)
    bars.loc[12:, ["open", "high", "low", "close"]] *= 10.0
    config = amplitude.AmplitudeAuditConfig(horizons=(5,), atr_window=3)
    panel = amplitude.build_amplitude_panel(bars, config)
    # Le signal index 7 entre à 8 et sa fenêtre traverse le facteur 10 à 12.
    assert pd.isna(panel.iloc[7]["h5_max_abs_excursion"])
    # Une fenêtre entièrement située après le changement reste mesurable.
    assert pd.notna(panel.iloc[13]["h5_max_abs_excursion"])


def _events(dates: int = 4, universe: int = 100) -> pd.DataFrame:
    rows = []
    for date in pd.date_range("2024-01-02", periods=dates, freq="B"):
        for rank in range(universe):
            pct = (rank + 1) / universe
            rows.append({
                "date": date, "symbol": f"S{rank:03d}",
                amplitude.SCORE_COL: pct,
                amplitude.ELIGIBLE_COL: pct >= 0.8,
                amplitude.OOF_COL: True,
                "h20_max_abs_excursion": 0.02 + 0.08 * pct,
                "h20_max_abs_excursion_capped_100pct": 0.02 + 0.08 * pct,
                "h20_barrier_hit": float(pct >= 0.8),
            })
    return pd.DataFrame(rows)


def test_daily_comparison_detects_monotonic_amplitude_lift() -> None:
    config = amplitude.AmplitudeAuditConfig(horizons=(20,))
    events = amplitude.assign_groups(_events(), config)
    daily = amplitude.build_daily_comparisons(
        events, "h20_max_abs_excursion", min_daily_universe=20
    )
    summary = amplitude.summarize_daily_comparison(daily)
    assert len(daily) == 4
    assert summary["mean_lift_vs_rest80"] > 0
    assert summary["mean_relative_lift_vs_rest80"] > 0.10
    assert summary["positive_day_rate"] == 1.0
    assert summary["mean_daily_spearman"] > 0.99


def test_decile_table_preserves_oracle_monotonicity() -> None:
    table = amplitude.decile_table(_events(), ["h20_max_abs_excursion"])
    assert table["oracle_decile"].tolist() == list(range(1, 11))
    assert table["h20_max_abs_excursion"].is_monotonic_increasing


def test_load_gate_rejects_non_oof_and_validates_contract(tmp_path: Path) -> None:
    gate = _events(dates=1, universe=100)[
        ["date", "symbol", amplitude.SCORE_COL, amplitude.ELIGIBLE_COL, amplitude.OOF_COL]
    ]
    gate.loc[0, amplitude.OOF_COL] = False
    path = tmp_path / "gate.parquet"
    gate.to_parquet(path, index=False)
    loaded, diagnostics = amplitude.load_oof_gate(path, amplitude.AmplitudeAuditConfig())
    assert len(loaded) == 99
    assert diagnostics["dates"] == 1
    broken = gate.copy()
    broken[amplitude.ELIGIBLE_COL] = False
    broken.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="incohérent"):
        amplitude.load_oof_gate(path, amplitude.AmplitudeAuditConfig())


def test_attach_amplitude_requires_unique_keys() -> None:
    gate = _events(dates=1, universe=2)[
        ["date", "symbol", amplitude.SCORE_COL, amplitude.ELIGIBLE_COL, amplitude.OOF_COL]
    ]
    panel = pd.DataFrame({
        "date": [gate.iloc[0]["date"]], "symbol": [gate.iloc[0]["symbol"]],
        "amplitude_entry_eligible": [True], "h20_max_abs_excursion": [0.1],
    })
    result = amplitude.attach_amplitude(gate, panel)
    assert len(result) == 2
    duplicated = pd.concat([panel, panel], ignore_index=True)
    with pytest.raises(pd.errors.MergeError):
        amplitude.attach_amplitude(gate, duplicated)
