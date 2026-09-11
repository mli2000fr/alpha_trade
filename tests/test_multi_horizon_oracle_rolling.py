from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.multi_horizon_oracle_rolling import (
    HORIZONS,
    RollingConfig,
    align_predictions,
    attach_benchmark_paths,
    attach_paths,
    block_bootstrap_mean,
    build_event_study,
    build_price_panel,
    build_s6_ls,
    deduplicate_entries,
    evaluate_verdict,
    read_universe,
    validate_batch_horizons,
)


def _predictions(horizon: int, *, omit: tuple[pd.Timestamp, str] | None = None) -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2024-01-02", periods=30)
    for date in dates:
        for index, symbol in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE")):
            if omit == (date, symbol):
                continue
            rows.append({
                "date": date, "symbol": symbol,
                "proba_extreme": (index + 1) / 10 + horizon / 1_000,
                "fold_start": "2023-01-01",
            })
    return pd.DataFrame(rows)


def _bars() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2024-01-02", periods=60)
    for symbol_index, symbol in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE")):
        for day, date in enumerate(dates):
            close = 100 + symbol_index * 5 + day
            rows.append({
                "symbol": symbol, "date": date,
                "open": close - 0.25, "close": close,
                "adj_close": close,
            })
    return pd.DataFrame(rows)


def test_read_universe_accepts_commas_and_lines(tmp_path: Path) -> None:
    path = tmp_path / "universe.txt"
    path.write_text("aaa, BBB\nAAA,ccc", encoding="utf-8")
    assert read_universe(path) == ["AAA", "BBB", "CCC"]


def test_validate_batch_horizons_rejects_wrong_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "modelFactory.multi_horizon_oracle_rolling.resolve_oracle_artifact_horizon",
        lambda batch_id, root: 10 if batch_id == "bad" else int(batch_id[1:]),
    )
    with pytest.raises(ValueError, match="attendu H5"):
        validate_batch_horizons({5: "bad", 10: "h10", 15: "h15", 20: "h20"}, Path("x"))


def test_alignment_uses_common_intersection_and_defines_mh3() -> None:
    missing = (pd.Timestamp("2024-01-02"), "AAA")
    frames = {h: _predictions(h, omit=missing if h == 5 else None) for h in HORIZONS}
    aligned, coverage = align_predictions(frames, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    assert len(aligned) == 149
    assert coverage["intersection_share_of_smallest"] == 1.0
    first_day = aligned[aligned["date"].eq(pd.Timestamp("2024-01-02"))]
    assert first_day["mh3"].sum() == 1
    assert first_day.loc[first_day["mh3"], "symbol"].tolist() == ["EEE"]
    assert all(column in aligned for column in ("remaining_rank_5", "remaining_rank_10", "remaining_rank_15"))


def test_price_clock_and_path_returns_are_causal() -> None:
    frames = {h: _predictions(h) for h in HORIZONS}
    aligned, _ = align_predictions(frames, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    prices = build_price_panel(_bars())
    events = attach_paths(aligned, prices, round_trip_cost=0.001)
    row = events[(events["date"].eq(pd.Timestamp("2024-01-02"))) & events["symbol"].eq("EEE")].iloc[0]
    assert row["entry_date"] == pd.Timestamp("2024-01-03")
    assert row["cp5_date"] == pd.Timestamp("2024-01-09")
    assert row["terminal_date"] == pd.Timestamp("2024-01-31")
    assert row["cp5_long_net"] == pytest.approx(row["cp5_close"] / row["entry_open"] - 1 - 0.001)
    assert row["cp5_oracle_confirmed"]


def test_event_study_and_s6_are_generated() -> None:
    frames = {h: _predictions(h) for h in HORIZONS}
    aligned, _ = align_predictions(frames, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    config = RollingConfig(bootstrap_samples=20, bootstrap_block_sessions=2)
    events = attach_paths(aligned, build_price_panel(_bars()), config.round_trip_cost)
    spy = _bars()[lambda frame: frame["symbol"].eq("AAA")].assign(symbol="SPY")
    events = attach_benchmark_paths(events, build_price_panel(spy))
    study = build_event_study(events, config)
    assert set(study["variant"]) == {"MH0", "MH1", "MH2", "MH3"}
    assert set(study["checkpoint"]) == {5, 10, 15}
    s6, summary = build_s6_ls(events, config)
    assert not s6.empty
    assert summary["events"] == len(s6)
    assert set(s6["direction"]) == {"LONG"}


def test_deduplication_prevents_overlapping_positions() -> None:
    frames = {h: _predictions(h) for h in HORIZONS}
    aligned, _ = align_predictions(frames, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    events = attach_paths(aligned, build_price_panel(_bars()), 0.0)
    selected = deduplicate_entries(events, "mh3")
    eee = selected[selected["symbol"].eq("EEE")].sort_values("date")
    assert len(eee) == 2
    assert eee.iloc[1]["date"] > eee.iloc[0]["terminal_date"]


def test_block_bootstrap_is_deterministic() -> None:
    values = pd.Series(np.linspace(-0.01, 0.02, 100))
    config = RollingConfig(bootstrap_samples=50, bootstrap_block_sessions=5)
    assert block_bootstrap_mean(values, config) == block_bootstrap_mean(values, config)


def test_verdict_requires_positive_incremental_confidence_interval() -> None:
    frames = {h: _predictions(h) for h in HORIZONS}
    aligned, _ = align_predictions(frames, ["AAA", "BBB", "CCC", "DDD", "EEE"])
    config = RollingConfig(bootstrap_samples=20, bootstrap_block_sessions=2)
    events = attach_paths(aligned, build_price_panel(_bars()), config.round_trip_cost)
    study = build_event_study(events, config)
    result = evaluate_verdict(study, events, config)
    assert "incremental_paired_daily_ci95_above_zero" in result["gates"]
    assert result["verdict"] != "GO_RESEARCH"
