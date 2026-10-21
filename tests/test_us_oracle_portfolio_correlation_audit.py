import numpy as np
import pandas as pd

from scripts.research.us_oracle_portfolio_correlation_audit import scalar_pearson, expected_holdings


def test_scalar_pearson_matches_pairwise_deletion_and_constant_history():
    rng = np.random.default_rng(51)
    x = rng.normal(size=40); y = x+.3*rng.normal(size=40)
    x[1:4] = np.nan; y[12:15] = np.nan
    n, r = scalar_pearson(x, y)
    assert n == 34
    assert np.isclose(r, pd.Series(x).corr(pd.Series(y)))
    assert scalar_pearson(x[:10], y[:10]) == (7, None)
    assert scalar_pearson(np.ones(40), np.ones(40)) == (40, None)


def test_held_lifecycle_excludes_open_exits_and_later_simultaneous_entries():
    ts = pd.Timestamp('2026-02-18T15:55:00Z')
    base = dict(oracle_date=pd.Timestamp('2026-02-16'), pair_id=1, rank=2, symbol='C')
    event = dict(time=ts)
    rows = [dict(base, symbol='EARLY', rank=1, entry_timestamp=ts),
            dict(base, symbol='LATER', rank=3, entry_timestamp=ts),
            dict(base, symbol='EXITED', entry_timestamp=ts-pd.Timedelta(days=1), exit_timestamp=ts),
            dict(base, symbol='INTRABAR_EXIT', entry_timestamp=ts-pd.Timedelta(days=1), exit_timestamp=ts+pd.Timedelta(minutes=5))]
    assert set(expected_holdings(rows, event, base)) == {'EARLY', 'INTRABAR_EXIT'}
