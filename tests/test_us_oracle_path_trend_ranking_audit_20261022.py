import numpy as np
import pytest
from scripts.research.us_oracle_path_trend_ranking_20261022 import path_metrics
from scripts.research.us_oracle_path_trend_ranking_audit_20261022 import scalar_metrics, corr


def test_scalar_matches_vector_for_hundred_seeded_paths():
    rng = np.random.default_rng(728)
    for _ in range(100):
        c = 100*np.exp(np.cumsum(rng.normal(0, .04, 20)))
        o = np.r_[100., c[:-1]]
        h = np.maximum(o,c)*(1+rng.uniform(0,.02,20))
        l = np.minimum(o,c)*(1-rng.uniform(0,.02,20))
        bars = np.column_stack([o,h,l,c])
        a,b = path_metrics(bars),scalar_metrics(bars.tolist())
        assert set(a)==set(b)
        for k in a:
            assert a[k]==pytest.approx(b[k],abs=1e-10)


def test_scalar_ties_constant_and_reverse_rank():
    assert corr([1,1,1],[2,3,4]) is None
    assert corr([1,2,3],[3,2,1]) == pytest.approx(-1)
    assert corr([1,1,3],[1,1,3]) == pytest.approx(1)


def test_intraday_same_bar_keeps_interval():
    bars = [[100.,105.,95.,100.]]*20
    bars[0]=[100.,130.,70.,100.]
    r=scalar_metrics(bars)
    assert r['long_adverse_before_high_day_lower_pct']==0
    assert r['long_adverse_before_high_day_upper_pct']==pytest.approx(30)
