from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.fr_feature_panel import (
    NUMERIC_FEATURES,
    assemble_panel,
    compute_symbol_features,
    load_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def _bars(count=280):
    dates = pd.bdate_range("2024-01-02", periods=count)
    close = np.arange(count, dtype=float) + 100
    return pd.DataFrame(
        {
            "source_session_date": dates,
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000 + np.arange(count),
        }
    ), [d.date() for d in dates]


def test_formulas_windows_and_first_complete_observation():
    bars, sessions = _bars()
    result = compute_symbol_features(bars, sessions)
    assert len(NUMERIC_FEATURES) == 18
    assert result.loc[20, "return_20"] == pytest.approx(120 / 100 - 1)
    assert result.loc[19, "return_20"] != result.loc[19, "return_20"]
    assert result.loc[20, "atr20_pct"] == pytest.approx(2 / 120)
    assert result.loc[20, "overnight_gap"] == pytest.approx(119.5 / 119 - 1)
    assert result.loc[251, "position_52w"] == pytest.approx((351 - 99) / (352 - 99))
    assert result.loc[250, "position_52w"] != result.loc[250, "position_52w"]


def test_future_bar_cannot_change_prefix():
    bars, sessions = _bars()
    original = compute_symbol_features(bars, sessions)
    changed = bars.copy()
    changed.loc[270:, ["open", "high", "low", "close"]] *= 100
    future = compute_symbol_features(changed, sessions)
    pd.testing.assert_frame_equal(original.iloc[:270], future.iloc[:270])
    prefix = compute_symbol_features(bars.iloc[:270], sessions[:270])
    pd.testing.assert_frame_equal(original.iloc[:270].reset_index(drop=True), prefix)


def test_missing_session_invalidates_all_crossing_return_windows():
    bars, sessions = _bars()
    incomplete = bars.drop(index=260)
    result = compute_symbol_features(incomplete, sessions)
    assert result.loc[261, "return_1"] != result.loc[261, "return_1"]
    assert pd.isna(result.loc[270, "return_20"])
    assert pd.isna(result.loc[270, "sma20_distance"])
    assert result.loc[262, "return_1"] == pytest.approx(362 / 361 - 1)


def test_invalid_ohlcv_and_duplicates_fail_closed():
    bars, sessions = _bars()
    invalid = bars.copy()
    invalid.loc[20, "high"] = 1
    with pytest.raises(ValueError, match="Barre invalide"):
        compute_symbol_features(invalid, sessions)
    with pytest.raises(ValueError, match="dupliquée"):
        compute_symbol_features(pd.concat([bars, bars.iloc[[0]]]), sessions)


def test_flat_range_is_missing_not_infinite_or_zero():
    bars, sessions = _bars()
    bars[["open", "high", "low", "close"]] = 10
    result = compute_symbol_features(bars, sessions)
    assert pd.isna(result.loc[251, "range20_position"])
    assert pd.isna(result.loc[251, "position_52w"])
    assert not np.isinf(result[list(NUMERIC_FEATURES)].to_numpy()).any()


def test_panel_enforces_next_session_and_keeps_missing_masks():
    profile = load_profile(ROOT / "config/features_fr/fr_price_v1.yaml")
    candidates = pd.DataFrame(
        [
            {
                "provider_symbol": "A.PA",
                "source_session_date": "2024-06-03",
                "decision_session_date": "2024-06-04",
                "training_state": "ELIGIBLE",
                "mic": "XPAR",
            }
        ]
    )
    features = pd.DataFrame(
        [{"provider_symbol": "A.PA", "source_session_date": "2024-06-03", **dict.fromkeys(NUMERIC_FEATURES, np.nan)}]
    )
    ids = {"A.PA": {"research_uid": "research-a"}}
    times = {"2024-06-04": {"open": "2024-06-04T07:00:00+00:00", "previous": "2024-06-03"}}
    result = assemble_panel(candidates, features, ids, times, profile)
    assert result.loc[0, "return_20_missing"] == 1
    assert not result.loc[0, "research_ready"]
    assert pd.isna(result.loc[0, "instrument_id"])
    assert result.loc[0, "source_available_at"] == result.loc[0, "decision_at"]
    bad = {"2024-06-04": {"open": "2024-06-04T07:00:00+00:00", "previous": "2024-05-31"}}
    with pytest.raises(ValueError, match="prochaine séance"):
        assemble_panel(candidates, features, ids, bad, profile)


def test_profile_blocks_foreign_or_sector_features(tmp_path):
    source = (ROOT / "config/features_fr/fr_price_v1.yaml").read_text(encoding="utf-8")
    path = tmp_path / "profile.yaml"
    path.write_text(source.replace("sector_features_enabled: false", "sector_features_enabled: true"), encoding="utf-8")
    with pytest.raises(ValueError, match="prix"):
        load_profile(path)
    path.write_text(source.replace("FR_EQ", "US_EQ"), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible"):
        load_profile(path)
