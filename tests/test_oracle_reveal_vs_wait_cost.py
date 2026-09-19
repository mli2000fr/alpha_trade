"""Economic-clock checks for descriptive Oracle J+N research."""

import pandas as pd

from scripts.research.oracle_reveal_vs_wait_cost import policy_rows, summarize


def test_waiting_consumes_upside_and_respects_original_exit() -> None:
    events = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")], "oracle_decile": [10],
        "px_close": [100.0], "entry_open": [100.0], "close_5": [110.0],
        "entry_open_5": [111.0], "exit_open": [120.0],
    })
    frame = policy_rows(events, n=5, threshold=0.005, cost=0.0006)
    assert frame["side"].iat[0] == 1
    assert abs(frame["immediate_long_net"].iat[0] - 0.1994) < 1e-9
    assert abs(frame["delayed_long_net"].iat[0] - (120 / 111 - 1 - 0.0006)) < 1e-9
    assert frame["delayed_long_net"].iat[0] < frame["immediate_long_net"].iat[0]
    row = summarize(frame, 5, "all", 0.005, 0.0006)
    assert row["p_d10_given_long_all"] == 1.0


def test_abstention_is_zero_pnl_but_still_in_coverage() -> None:
    events = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")], "oracle_decile": [1],
        "px_close": [100.0], "entry_open": [100.0], "close_1": [100.2],
        "entry_open_1": [100.2], "exit_open": [90.0],
    })
    frame = policy_rows(events, n=1, threshold=0.005, cost=0.0006)
    row = summarize(frame, 1, "all", 0.005, 0.0006)
    assert row["coverage"] == 0.0
    assert row["signed_delayed_net_equal_date"] == 0.0
