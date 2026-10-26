import numpy as np
import pandas as pd
import pytest
from scripts.research import us_options_equal_mix_20261026 as b
from scripts.research import us_options_equal_mix_amended_20261026 as s
from tests.test_us_options_equal_mix_20261026 import cal,candidates,prices


def raw_options():
    common=dict(symbol='A',expiration_date='2026-10-02',strike=100,
        available_at='2026-09-14T21:00Z',observed_at='2026-09-14T21:00Z',provider='alpaca')
    oi=pd.DataFrame([{**common,'contract_symbol':'A261002'+side+'00100000','option_type':side,
        'payload_hash':side,'open_interest':v} for side,v in [('C',300),('P',100)]])
    flow=pd.DataFrame([{**common,'contract_symbol':'A261002'+side+'00100000','option_type':side,
        'payload_hash':side+str(i),'volume':v,'bar_timestamp':f'2026-09-14T{hour}:00Z'}
        for side,v in [('C',10),('P',20)] for i,hour in enumerate(['14:00','14:30'])])
    spot=pd.DataFrame([dict(symbol='A',date=pd.Timestamp('2026-09-14'),close=100.,is_filled=0)])
    return oi,flow,spot


def test_full_feature_pipeline_same_date_expiry_and_aggregated_volume():
    oi,flow,spot=raw_options()
    f,a=b.build_features(oi,flow,spot,cal())
    assert len(f)==1 and a['same_expiry_candidates']==1
    assert f[b.FEATURES[0]].iloc[0]==pytest.approx(np.log1p(20)-np.log1p(40))
    assert f[b.FEATURES[1]].iloc[0]==pytest.approx(np.log1p(300)-np.log1p(100))
    assert f.entry_day.iloc[0]=='2026-09-15'


def test_no_put_no_imputed_zero_and_negative_volume_invalidates_side():
    oi,flow,spot=raw_options()
    f,a=b.build_features(oi[oi.option_type.eq('C')],flow,spot,cal())
    assert f.empty
    flow.loc[0,'volume']=-1
    f,a=b.build_features(oi,flow,spot,cal())
    assert f.empty


def test_source_separation_no_renaming_or_fallback():
    score=b.score_candidates(candidates().iloc[:1])
    p=prices().assign(data_source='eodhd_eod')
    labels=s.make_labels(score,p,cal(),pd.Timestamp('2026-11-01T21:00Z'),'eodhd_eod')
    assert labels.status.eq('LABEL').all()
    with pytest.raises(ValueError,match='Mixed source'):
        s.make_labels(score,p,cal(),pd.Timestamp('2026-11-01T21:00Z'),'alpaca_sip')


def test_maturity_never_replaced_by_partial_horizon():
    score=b.score_candidates(candidates().iloc[:1])
    labels=s.make_labels(score,prices(),cal(),pd.Timestamp('2026-09-22T21:00Z'),'alpaca_sip')
    assert labels[labels.horizon.eq(20)].status.iloc[0]=='NOT_MATURE'


def test_empty_cohort_has_explicit_empty_metrics():
    scored=b.score_candidates(candidates().iloc[:0])
    labels=s.make_labels(scored,prices(),cal(),pd.Timestamp('2026-11-01T21:00Z'),'alpaca_sip')
    assert labels.empty and b.metrics(labels)['valid_n']==0
