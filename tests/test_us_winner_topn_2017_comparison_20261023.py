import pandas as pd
import pytest
from scripts.research import us_winner_topn_2017_comparison_20261023 as study


def samples():
    f=pd.DataFrame(dict(date=[pd.Timestamp('2017-06-02')]*100,symbol=[f'S{i:03}' for i in range(1,101)],
        rank=range(1,101),score=[1-i/101 for i in range(100)],model_available_date=[pd.Timestamp('2017-05-31')]*100))
    return f,f.iloc[:10].copy()


@pytest.mark.parametrize('n',[20,50])
def test_original_order_and_top10_preserved(n):
    f,r=samples();a=study.select_scores(f.sample(frac=1,random_state=1),n,r)
    assert len(a)==n and a['rank'].tolist()==list(range(1,n+1))
    pd.testing.assert_frame_equal(a.iloc[:10],r)


def test_reject_reranking_and_missing_rank():
    f,r=samples();f.loc[0,'symbol']='WRONG'
    with pytest.raises(AssertionError):study.select_scores(f,20,r)
    f,r=samples()
    with pytest.raises(ValueError,match='Incomplete'):study.select_scores(f[f['rank'].ne(18)],20,r)


def test_reject_noncausal_and_unauthorized():
    f,r=samples();f.loc[19,'model_available_date']=pd.Timestamp('2017-06-02')
    with pytest.raises(ValueError,match='Noncausal'):study.select_scores(f,20,r)
    with pytest.raises(ValueError):study.select_scores(f,100,r)


def test_original_risk_half_fees_and_cap_unchanged():
    p=study.read_json(study.REFERENCE/'protocol.json')
    cfg=study.grid.configuration(p,2017,study.grid.profiles()[0])
    assert p['effective_gross_cap']==cfg.risk_config.max_gross_exposure==1
    assert cfg.risk_config.max_positions==8
    assert cfg.exec_config.winner_pyramiding.initial_position_fraction==.5
    assert not cfg.exec_config.winner_pyramiding.reinforcement_enabled
    assert cfg.cost_round_trip_bps==16


def test_merge_rejects_replacing_frozen_common_rows():
    old=pd.DataFrame(dict(symbol=['A'],date=[pd.Timestamp('2017-06-02')],close=[3.]))
    with pytest.raises(ValueError,match='Duplicate'):study.combined_frame(old,old,'daily.parquet')
    added=old.assign(symbol='B');merged=study.combined_frame(old,added,'daily.parquet')
    pd.testing.assert_frame_equal(merged.iloc[:1],old)
