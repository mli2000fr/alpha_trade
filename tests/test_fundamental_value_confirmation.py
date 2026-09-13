import pandas as pd
from modelFactory.fundamental_value_confirmation import E19CConfig, build_gates, hash_partition, holdout_mask, label_windows


def test_locked_holdouts() -> None:
    config = E19CConfig()
    frame = pd.DataFrame({"date": pd.to_datetime(["2018-07-01", "2018-07-02", "2020-07-01", "2020-07-02", "2025-07-09", "2025-07-10", "2025-12-31", "2026-01-01"])})
    selected = frame[holdout_mask(frame, config)].copy(); selected["window"] = label_windows(selected, config)
    assert selected.date.dt.strftime("%Y-%m-%d").tolist() == ["2018-07-02", "2020-07-01", "2025-07-10", "2025-12-31"]
    assert selected.window.tolist() == ["EARLY_HOLDBACK", "EARLY_HOLDBACK", "LATE_HOLDBACK", "LATE_HOLDBACK"]


def test_hash_is_deterministic() -> None:
    assert hash_partition("AAPL", 5) == hash_partition("aapl", 5)


def test_all_gates_block() -> None:
    base = {"cohorts": 30, "ic_mean": .02, "ic_ci95_low": .01, "long_short_return_net": .01, "long_short_ci95_low": .001, "long_excess_spy_net": .01, "long_excess_universe_net": .01, "bottom_underperformance_universe_net": .01, "windows": {"EARLY_HOLDBACK": {"long_short_return_net": .01}, "LATE_HOLDBACK": {"long_short_return_net": .01}}}
    hashes = pd.DataFrame({"horizon": [60] * 5 + [120] * 5, "long_short_return_net": [.01] * 10})
    assert all(build_gates({"h60": dict(base), "h120": dict(base)}, hashes).values())
    broken = dict(base); broken["long_short_ci95_low"] = -.001
    assert not build_gates({"h60": broken, "h120": dict(base)}, hashes)["h60_spread_ci95_positive"]
