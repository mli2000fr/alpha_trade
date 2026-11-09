import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_rank_fusion_20261109 import fuse,validate_probabilities


def sample():
    return pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02']*6),symbol=list('ABCDEF'),
        oracle_rank=range(1,7),symbol_probability=[.9,.8,.7,.6,.5,.4],
        sector_probability=[.1,.2,.3,.4,.5,.6]))


def test_percentile_fusion_not_probability_average_and_ties_follow_oracle_order():
    data=sample();out=fuse(data)
    assert out.fusion_score.nunique()==1
    assert out[out.selected_fusion].sort_values('fusion_rank').symbol.tolist()==list('ABCDE')
    transformed=data.copy();transformed.sector_probability=transformed.sector_probability**3
    other=fuse(transformed)
    np.testing.assert_allclose(out.fusion_score,other.fusion_score)
    assert out.selected_fusion.tolist()==other.selected_fusion.tolist()


def test_both_models_use_the_identical_observable_cohort_without_missing_score_imputation():
    data=sample();data.loc[0,'sector_probability']=np.nan
    out=fuse(data)
    assert not out.loc[0,'eligible'] and not out.loc[0,'selected_fusion']
    assert out.selected_fusion.sum()==out.selected_relative_symbol.sum()==5
    data.loc[1,'symbol_probability']=np.nan
    assert fuse(data).selected_fusion.sum()==4


def test_relative_rank_does_not_require_absolute_probability_above_half():
    data=sample();data.symbol_probability*=.4;data.sector_probability*=.4
    out=fuse(data)
    assert out.selected_fusion.sum()==5 and out.selected_relative_symbol.sum()==5


def test_each_day_is_ranked_independently_and_invalid_probabilities_fail_closed():
    data=sample();future=sample();future['date']=pd.Timestamp('2025-01-03')
    first=fuse(data);combined=fuse(pd.concat([data,future],ignore_index=True))
    pd.testing.assert_frame_equal(first,combined[combined.date.eq(data.date.iloc[0])].reset_index(drop=True))
    data.loc[0,'symbol_probability']=1.1
    with pytest.raises(ValueError,match='Invalid'):fuse(data)


def test_causal_weights_are_required_before_any_scoring(tmp_path):
    data=pd.DataFrame(dict(symbol=['A'],date=pd.to_datetime(['2025-01-02']),long_probability=[.7],long_model_sha256=['x']))
    records={('A',2025):dict(sha256='x',available='2025-01-02',file=str(tmp_path/'absent.joblib'))}
    with pytest.raises(ValueError,match='Future'):validate_probabilities(data,records)
