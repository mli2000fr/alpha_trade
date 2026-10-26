"""Synthetic veto tests; no GPT, database, model inference or broker."""
from copy import deepcopy

import pandas as pd
import pytest

from scripts.research import us_winner_gpt_veto_august_2026 as study


def inputs():
    candidates=[];answers=[]
    for day in pd.bdate_range('2026-08-03','2026-08-31'):
        for rank in range(1,21):
            symbol=f'S{rank:02d}'
            candidates.append(dict(date=day,symbol=symbol,oracle_rank=rank,score=1-rank/100))
            answers.append(dict(date=str(day.date()),symbol=symbol,status='VALID',assessment={'direction_score':5}))
    return pd.DataFrame(candidates),answers


def test_only_valid_low_scores_are_vetoed_unknowns_retained():
    frame,answers=inputs()
    for i,score in enumerate([1,2,3,4,None,3]):answers[i]['assessment']['direction_score']=score
    answers[5]['status']='INVALID'
    result=study.freeze_veto(frame,answers)
    assert result.gpt_veto.sum()==3
    assert list(result.head(6).gpt_veto)==[True,True,True,False,False,False]
    assert len(result)==420 and result.head(20).oracle_rank.tolist()==list(range(1,21))


@pytest.mark.parametrize('fault',['missing_answer','duplicate_answer','duplicate_candidate','bad_rank','bool','out_of_range'])
def test_malformed_archives_refused(fault):
    frame,answers=inputs()
    if fault=='missing_answer':answers.pop()
    elif fault=='duplicate_answer':answers[-1]=deepcopy(answers[0])
    elif fault=='duplicate_candidate':frame.loc[len(frame)-1]=frame.iloc[0]
    elif fault=='bad_rank':frame.loc[0,'oracle_rank']=21
    elif fault=='bool':answers[0]['assessment']['direction_score']=True
    else:answers[0]['assessment']['direction_score']=11
    with pytest.raises(ValueError):study.freeze_veto(frame,answers)


def test_matched_cohort_original_ranking_and_long_only_are_preserved():
    frame,answers=inputs()
    answers[0]['assessment']['direction_score']=3
    answers[1]['assessment']['direction_score']=2
    cohort=study.freeze_veto(frame,answers);cohort['selected']=True
    cohort.loc[0,'selected']=False
    base=study.arm_signals(cohort,'WINNER_ONLY')
    filtered=study.arm_signals(cohort,'WINNER_GPT_VETO_1_3')
    assert base.selected.sum()==419 and filtered.selected.sum()==418
    assert filtered['rank'].equals(base['rank'])
    pd.testing.assert_frame_equal(filtered.drop(columns='selected'),base.drop(columns='selected'))
    assert filtered.side.eq('long').all() and not filtered.loc[1,'selected']
    assert len(filtered)==420  # Veto does not replace by TOP21 or erase provenance.


def test_unrecognized_arm_rejected():
    with pytest.raises(ValueError):study.arm_signals(pd.DataFrame(),'reversed_gpt')
