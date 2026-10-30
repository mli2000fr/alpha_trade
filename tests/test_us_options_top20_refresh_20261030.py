import pandas as pd
import pytest

from scripts.research.us_options_top20_refresh_20261030 import labels_for_path, qualified_ranking
from service.options_directional.config import OptionsFilterConfig


def prices(high=(105., 112.), low=(99., 102.), dates=('2026-09-15','2026-09-16')):
    return pd.DataFrame(dict(open=[100.,104.],high=high,low=low,close=[104.,106.],
        volume=[1000.,1000.],is_filled=[0,0],instrument_id=[1,1],data_adjustment=['split']*2),
        index=pd.to_datetime(dates))


def window():
    return pd.DataFrame(dict(day=pd.to_datetime(['2026-09-15','2026-09-16'])))


def test_path_peak_not_terminal_close():
    p=prices(high=(130.,112.));p.iloc[-1,p.columns.get_loc('close')]=103.
    r=labels_for_path(p,window())
    assert r['max_up_pct']==pytest.approx(30.)
    assert r['terminal_return_pct']==pytest.approx(3.)
    assert r['dominant_direction']=='LONG'


def test_same_day_two_stops_do_not_invent_peak_sequence():
    r=labels_for_path(prices(high=(125.,112.),low=(85.,102.)),window())
    assert r['status']=='AMBIGUOUS_PATH'
    assert r['long_lower_pct']==0 and r['long_upper_pct']==25


def test_missing_session_and_identity_change_rejected():
    assert labels_for_path(prices().iloc[:1],window())['status']=='INVALID_OR_MISSING_PRICE_IDENTITY'
    p=prices();p.iloc[1,p.columns.get_loc('instrument_id')]=2
    assert labels_for_path(p,window())['status']=='INVALID_OR_MISSING_PRICE_IDENTITY'


def test_coverage_current_90_percent_and_score_creation_separate():
    from tests.test_us_options_oracle_topn_20261026 import fixture_scores
    f,u,m,c=fixture_scores();m={k:dict(profile_hash=v['profile_sha256'],folds=v['folds']) for k,v in m.items()}
    ranked,coverage=qualified_ranking(f.iloc[:92],u,m,OptionsFilterConfig(min_oracle_coverage_ratio=.90),c)
    assert coverage.qualified.all() and len(ranked)==20
    assert not ranked.oracle_created_before_decision.any()
    # Missing options/labels can never promote rank 21 into TOP20.
    assert ranked.symbol.tolist()==u[:20]
