import numpy as np
import pandas as pd
import pytest
from scripts.research.q051_global_rank_selection import select,POLICIES


def frame():
    return pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'),symbol=[f'S{i:02}' for i in range(25)],
        proba_extreme=np.linspace(1,0,25),long_probability=np.linspace(.95,.51,25),
        global_rank_10=np.linspace(0,1,25),long_auc=.7,long_auc_available_date='2024-12-31'))


def test_same_oracle_pool_and_gates_but_different_rankers():
    f=frame()
    reference=select(f,'Q051_REFERENCE',oracle_top_n=20)
    global_only=select(f,'GLOBAL_H10',oracle_top_n=20)
    assert reference[reference.selected].symbol.tolist()==['S00','S01','S02','S03','S04']
    assert global_only[global_only.selected].symbol.tolist()==['S15','S16','S17','S18','S19']
    assert not global_only[global_only.selected].symbol.isin(['S20','S21']).any()


@pytest.mark.parametrize('policy',POLICIES)
def test_thresholds_applied_after_top5_without_refill(policy):
    f=frame();first=select(f,policy,oracle_top_n=20)
    winner=first[first.selected].sort_values('rank').iloc[0].symbol
    f.loc[f.symbol.eq(winner),'long_auc']=.49
    out=select(f,policy,oracle_top_n=20)
    assert out.selected.sum()==4 and not out[out.selected].symbol.eq(winner).any()


def test_missing_global_is_not_neutral_but_real_median_is_valid():
    f=frame();f['global_rank_10']=np.nan;f.loc[0,'global_rank_10']=.5
    assert select(f,'GLOBAL_H10').selected.sum()==1
    assert select(f,'FUSION_50_50').selected.sum()==1
    assert select(f,'Q051_REFERENCE').selected.sum()==5


def test_future_auc_not_used_even_if_score_is_high():
    f=frame();f.loc[0,'long_auc_available_date']='2025-01-02'
    out=select(f,'Q051_REFERENCE')
    assert out.selected.sum()==4 and out.loc[0,'reason']=='MISSING_OR_FUTURE_CALIBRATION_AUC'


def test_fusion_uses_equal_weighted_relative_ranks_in_same_cohort():
    f=frame();f['global_rank_10']=f.long_probability**3
    out=select(f,'FUSION_50_50',oracle_top_n=20)
    assert out[out.selected].symbol.tolist()==['S00','S01','S02','S03','S04']
