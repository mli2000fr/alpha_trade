import pandas as pd
import pytest
from scripts.research import us_legacy_scope_inventory_20261026 as s


def scores():
    return pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol=f'S{i:02}',score=1-i/100,
        rank=i+1,scored_count=60,target_h20=1 if i%2 else 0) for i in range(60)])


def test_topn_is_titles_not_percent_and_precedes_missing_option_filter():
    f=scores();x=pd.DataFrame(dict(day=[pd.Timestamp('2025-01-02')],symbol=['S10']))
    assert len(s.select(f,10))==10 and s.coverage_case(f,x,10)['paired']==0
    assert s.coverage_case(f,x,20)['paired']==1


def test_future_target_is_not_read_or_used():
    f=scores();a=s.select(f,20);f.target_h20=999
    pd.testing.assert_frame_equal(a,s.select(f,20))
    assert 'target_h20' not in a


def test_incomplete_score_universe_not_treated_as_full_top():
    with pytest.raises(ValueError,match='Incomplete'):s.select(scores().iloc[:40],10)


def test_bad_saved_rank_and_duplicates_fail():
    f=scores();f.loc[0,'rank']=2
    with pytest.raises(ValueError,match='rank'):s.select(f,10)
    with pytest.raises(ValueError,match='Duplicate'):s.select(pd.concat([scores(),scores().iloc[:1]]),10)


def test_mentions_are_not_claimed_as_verified_scope():
    r=s.registry_entries('# Register\n## A\nTOP20 % was discussed, not necessarily tested.\n## B\nTOP10 titles')
    assert len(r)==2 and all(x['mentions_are_not_verified_scope'] for x in r)


def test_family_ids_unique_and_no_automatic_source_reactivation():
    ids=[x[0] for x in s.FAMILIES]
    assert len(ids)==len(set(ids))
    assert next(r for r in s.FAMILIES if r[0]=='eps_revisions_yahoo')[2]=='SOURCE_BLOQUEE'
