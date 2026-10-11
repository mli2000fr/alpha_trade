import pandas as pd

from scripts.research.analyst_restored_directional_audit import balance, qualify_snapshots


def test_revision_balance_no_activity_and_missing():
    result = balance(pd.Series([3.,0.,None,-1.]),pd.Series([1.,0.,1.,2.]))
    assert result.iloc[0] == .5
    assert result.iloc[1] == 0.
    assert result.iloc[2:].isna().all()


def test_pit_requires_real_next_close_not_same_day_after_close():
    frame = pd.DataFrame({"observed_at":["2026-09-04 20:01:00"]*2,
                          "available_at":["2026-09-08 20:00:00", "2026-09-04 20:00:00"]})
    valid, rejected = qualify_snapshots(frame)
    assert list(valid.index) == [0]
    assert rejected == 1
