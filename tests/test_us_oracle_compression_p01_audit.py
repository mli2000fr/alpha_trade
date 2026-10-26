import pandas as pd

from scripts.research import us_oracle_compression_p01_audit as audit
from tests.test_us_oracle_compression_p01 import session


def test_independent_scan_matches_known_compression_release():
    f=session([100.]*23+[105.,106.,106.])
    r=audit.first_signals(f,101.)
    assert set(r)=={'WINNER','WARMUP_CONTROL','P01'}
    assert r['P01']==f.bar_timestamp.iloc[25]


def test_independent_scan_never_accepts_two_squeeze_bars():
    f=session([100.]*21+[105.,106.,106.])
    assert 'P01' not in audit.first_signals(f,101.)


def test_independent_unit_does_not_use_same_bar_high_for_stop():
    f=session([100.,110.]); f.loc[0,['high','low']]=[120.,99.]
    px,ts=audit.scalar_outcome(f,100.,f.bar_timestamp.iloc[1])
    assert px==110. and ts==pd.Timestamp('2026-01-05 14:35Z')


def test_half_cent_regression_follows_existing_contract_not_decimal_rewrite():
    f=session([151.5,140.]); f.loc[0,'low']=140.
    assert audit.scalar_outcome(f,151.5,f.bar_timestamp.iloc[1])[0] == 140.89
