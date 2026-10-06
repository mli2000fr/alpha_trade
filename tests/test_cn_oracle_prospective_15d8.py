"""Fail-closed contracts for the research-only prospective CN Oracle export."""

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest
import yaml

from modelFactory import cn_oracle_prospective_15d8 as d8
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar
from service.market.cn_dragon_tiger_matched_15d7 import load_candidates, load_protocol


def _calendar():
    return load_calendar(d8.ROOT / "config/research_cn/sprint15d6_cn_calendar_2026.yaml")


def test_frozen_model_artifact_and_feature_order_are_valid():
    contract = d8.load_contract()
    assert contract["trained_through"] == date(2025, 6, 30)
    assert contract["report"]["status"] == "OOS_RESEARCH_ONLY"
    assert contract["protocol"].raw["features"]


def test_changed_model_hash_fails_closed_before_database(monkeypatch, tmp_path):
    raw = yaml.safe_load(d8.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["model_file_sha256"] = "0" * 64
    config = tmp_path / "contract.yaml"
    config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact changed"):
        d8.load_contract(config)


def test_preopen_window_accepts_previous_close_and_rejects_late_or_closed():
    ready = d8.decision_window(
        date(2026, 9, 30), now=datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc),
        calendar=_calendar(),
    )
    assert ready["previous_day"] == date(2026, 9, 29)
    assert ready["cutoff_utc"] == datetime(2026, 9, 30, 1, 15, tzinfo=timezone.utc)
    with pytest.raises(RuntimeError, match="retroactive export forbidden"):
        d8.decision_window(date(2026, 9, 30),
                           now=datetime(2026, 9, 30, 1, 15, tzinfo=timezone.utc),
                           calendar=_calendar())
    with pytest.raises(ValueError, match="not a verified open"):
        d8.decision_window(date(2026, 10, 1),
                           now=datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc),
                           calendar=_calendar())


def test_late_run_never_opens_database(monkeypatch, tmp_path):
    monkeypatch.setattr(d8, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    with pytest.raises(RuntimeError, match="retroactive export forbidden"):
        d8.run(decision_day=date(2026, 9, 30),
               now=datetime(2026, 9, 30, 2, 0, tzinfo=timezone.utc),
               output_root=tmp_path)
    assert not (tmp_path / "2026-09-30").exists()


def test_read_only_preflight_flags_missing_previous_session(tmp_path):
    raw = yaml.safe_load(d8.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["output_root"] = str(tmp_path / "prospective")
    config = tmp_path / "contract.yaml"
    config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    class Result:
        def __init__(self, value):
            self.value = value
        def scalar(self):
            return self.value
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def execute(self, query, _params):
            return Result(None if "market_sessions" in str(query) else 0)
    class Engine:
        url = type("URL", (), {"database": "alpha_trade_cn"})()
        def connect(self):
            return Connection()
    report = d8.check(decision_day=date(2026, 10, 8),
                      now=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
                      engine=Engine(), contract_path=config)
    assert report["status"] == "BLOCKED"
    assert set(report["reasons"]) == {
        "PREVIOUS_CN_SESSION_NOT_CLOSED_OR_MISSING",
        "PREVIOUS_CN_EQUITY_BARS_MISSING",
        "PREVIOUS_CSI300_BAR_MISSING",
    }
    assert report["database_modified"] is False


def test_known_factor_late_backfill_is_masked_only_in_future_frame():
    original = pd.DataFrame({
        "instrument_id": [1], "date": [date(2026, 9, 15)],
        "available_at": [datetime(2026, 9, 30, 0, 0)],
    })
    adapted, late = d8._known_factors_for_future(original)
    assert late == 1
    assert adapted["available_at"].iloc[0] == pd.Timestamp("2026-09-16")
    assert original["available_at"].iloc[0] == datetime(2026, 9, 30)


def test_top20_uses_only_valid_cross_section_with_stable_ties():
    frame = pd.DataFrame({
        "instrument_id": list(range(1, 11)),
        "provider_symbol": [f"sh.{number:06d}" for number in range(1, 11)],
        "board_code": ["SH_MAIN"] * 10,
        "return_5": [0.01] * 10,
        "mask_price20": [1] * 10,
        "mask_benchmark": [1] * 10,
        "max_input_available_at": [pd.Timestamp("2026-09-29")] * 10,
    })
    selected, quality = d8.top20_candidates(
        frame, np.array([0.7, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0]),
        top_pct=0.20, minimum_count=2, minimum_coverage=0.95,
    )
    assert selected["instrument_id"].tolist() == [1, 2]
    assert quality["top20"] == 2
    frame.loc[0, "return_5"] = np.nan
    with pytest.raises(RuntimeError, match="coverage insufficient"):
        d8.top20_candidates(frame, np.ones(10), top_pct=0.20,
                            minimum_count=2, minimum_coverage=0.95)


def test_published_export_is_accepted_by_d7_contract(monkeypatch, tmp_path):
    frozen_features = d8.load_contract()["protocol"].raw["features"]
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 8, 0, 30, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    class FakeModel:
        def __init__(self, **_kwargs):
            pass
        def feature_name(self):
            return frozen_features
        def predict(self, matrix):
            return np.arange(len(matrix), dtype=float)
    monkeypatch.setattr(d8, "datetime", FrozenDateTime)
    monkeypatch.setattr("lightgbm.Booster", FakeModel)
    monkeypatch.setattr(d8, "_load_market", lambda *_args, **_kwargs: {
        "factors": pd.DataFrame(), "bars": pd.DataFrame(),
        "benchmark": pd.DataFrame(), "limits": pd.DataFrame(),
    })
    monkeypatch.setattr(d8, "_preopen_members", lambda *_args, **_kwargs: (pd.DataFrame(),
                        {"instruments": 20, "candidates": 20, "exclusion_reasons": {}}))
    monkeypatch.setattr(d8, "compute_symbol_features", lambda frame, *_args: frame)
    panel = pd.DataFrame({name: np.zeros(20) for name in frozen_features})
    panel["instrument_id"] = range(1, 21)
    panel["provider_symbol"] = [f"sh.{n:06d}" for n in range(1, 21)]
    panel["board_code"] = "SH_MAIN"
    panel["return_5"] = 0.01
    panel["mask_price20"] = 1
    panel["mask_benchmark"] = 1
    panel["max_input_available_at"] = pd.Timestamp("2026-09-30 12:00:00")
    monkeypatch.setattr(d8, "assemble_candidate_panel", lambda *_args, **_kwargs: panel)
    engine = type("Engine", (), {"url": type("URL", (), {"database": "alpha_trade_cn"})()})()
    report = d8.run(decision_day=date(2026, 10, 8),
                    now=datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc),
                    engine=engine, output_root=tmp_path)
    assert report["quality"]["top20"] == 4
    assert report["database_modified"] is False
    protocol = load_protocol(d8.ROOT / "config/research_cn/sprint15d7_dragon_tiger_protocol.yaml")
    cutoff = datetime(2026, 10, 8, 1, 15, tzinfo=timezone.utc)
    candidates = load_candidates(tmp_path / "2026-10-08" / "oracle_top20.parquet",
                                 protocol, {"2026-10-08": {"cutoff_utc": cutoff,
                                                         "event_symbols": set()}})
    assert len(candidates) == 4
    with pytest.raises(FileExistsError, match="already exists"):
        d8.run(decision_day=date(2026, 10, 8),
               now=datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc),
               engine=engine, output_root=tmp_path)
