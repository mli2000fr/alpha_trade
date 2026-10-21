import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_persistent_trend import trend_features, replay_sources, REFERENCE
from scripts.research.us_oracle_persistent_trend_audit import scalar_gate


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_independent_scalar_matches_features_on_random_and_trending_prices(side):
    for seed in range(12):
        rng = np.random.default_rng(seed)
        c = 100*np.exp(np.cumsum(rng.normal((seed-6)*.001, .02, 130)))
        g = pd.DataFrame(dict(open=c, close=c, high=c*1.02, low=c*.98, volume=10000., is_filled=0),
                         index=pd.bdate_range('2025-01-01', periods=130))
        f = trend_features(g).iloc[-1]
        qualified, passed, numbers = scalar_gate(g, side)
        assert qualified == f.qualified
        assert passed == f['long_pass' if side == 'buy' else 'short_pass']
        np.testing.assert_allclose(numbers, f[['close', 'ema20', 'ema50', 'ema20_5ago', 'adx14']].to_numpy(float), atol=1e-8)


def test_source_guard_preserves_original_snapshot_instead_of_silently_waiving_change():
    from scripts.research.us_intraday_protection_grid import READ
    sources, drift = replay_sources(READ(REFERENCE/'protocol.json'))
    assert drift
    for row in drift:
        assert sources[row['source']] == row['replay_sha256']
        assert sources[row['historical_snapshot']] == row['historical_sha256']
    with pytest.raises(ValueError, match='Unqualified source'):
        replay_sources({'sources': {'modelFactory/features.py': 'unverified'}})
