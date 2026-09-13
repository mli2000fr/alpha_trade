from __future__ import annotations

import json

import pandas as pd
import pytest

import modelFactory.oracle_opening_price_backfill as backfill
from modelFactory.oracle_opening_price_backfill import (
    BackfillConfig,
    build_event_schedule,
    load_or_create_state,
    normalize_alpaca_pages,
)
from modelFactory.oracle_opening_price_confirmation import load_price_features


def test_schedule_targets_only_frozen_oracle_events(monkeypatch, tmp_path) -> None:
    oracle = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-03", "2025-01-06"]),
        "symbol": ["AAA", "AAA", "BBB", "AAA"],
    })
    monkeypatch.setattr(backfill, "load_oracle_events", lambda _path: oracle)
    result = build_event_schedule(tmp_path / "oracle.parquet")
    assert set(result.loc[result["target_session"].eq(pd.Timestamp("2025-01-06")), "symbol"]) == {"AAA", "BBB"}
    assert pd.Timestamp("2025-01-02") not in set(result["target_session"])


def test_normalization_ignores_volume_trade_count_and_vwap() -> None:
    payload = {"bars": {"AAA": [{
        "t": "2026-09-14T13:30:00Z", "o": 100, "h": 101,
        "l": 99, "c": 100.5, "v": 999999, "n": 777, "vw": 42,
    }]}}
    result = normalize_alpaca_pages([(payload, 200)], session_date=pd.Timestamp("2026-09-14"))
    assert result["symbol"].tolist() == ["AAA"]
    assert result["minute_of_day"].tolist() == [570]
    assert not {"v", "n", "vw", "volume", "trade_count"}.intersection(result.columns)


def test_normalization_rejects_post_checkpoint_bar() -> None:
    payload = {"bars": {"AAA": [{
        "t": "2026-09-14T14:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100,
    }]}}
    assert normalize_alpaca_pages(
        [(payload, 200)], session_date=pd.Timestamp("2026-09-14")
    ).empty


def test_resume_state_rejects_another_oracle(tmp_path) -> None:
    oracle = tmp_path / "oracle.parquet"
    oracle.write_bytes(b"first")
    schedule = pd.DataFrame({
        "target_session": [pd.Timestamp("2025-01-03")], "symbol": ["AAA"]
    })
    state_path = tmp_path / "state.json"
    state = load_or_create_state(
        state_path, batch_id="batch", horizon=20, oracle_path=oracle,
        schedule=schedule, config=BackfillConfig(),
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    oracle.write_bytes(b"changed")
    with pytest.raises(ValueError, match="incompatible"):
        load_or_create_state(
            state_path, batch_id="batch", horizon=20, oracle_path=oracle,
            schedule=schedule, config=BackfillConfig(),
        )


def test_confirmation_loads_partial_backfill_after_interruption(tmp_path) -> None:
    partitions = tmp_path / "session_features"
    partitions.mkdir()
    pd.DataFrame({
        "session_date": [pd.Timestamp("2025-01-03")], "symbol": ["AAA"],
        "return_30m": [0.01],
    }).to_parquet(partitions / "2025-01-03.parquet", index=False)
    result = load_price_features(tmp_path)
    assert result[["symbol", "return_30m"]].to_dict("records") == [
        {"symbol": "AAA", "return_30m": 0.01}
    ]
