"""Separate dataset audit rejects altered membership, timing and cash flows."""
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_profit_tp15_sl7_audit as study


def sample():
    days=pd.bdate_range('2020-12-01','2021-03-01');day=pd.Timestamp('2021-01-04');j=days.get_loc(day)
    rows=[]
    for k,price in enumerate([115.,93.,100.]):
        outlay=1600*1.0008;proceeds=16*price*.9992
        known=k<2
        rows.append(dict(date=day,symbol=f'S{k}',score=.9-k*.1,oracle_rank=k+1,
            fold_start=pd.Timestamp('2020-07-07'),reason='' if known else 'NO_FILL_ENTRY_GAP',
            label=float(proceeds>outlay) if known else np.nan,
            net_return=(proceeds-outlay)/1600 if known else np.nan,
            J_qualified=True,entry_date=days[j+1] if known else pd.NaT,
            exit_date=days[j+1] if known else pd.NaT,label_available=days[j+22],
            entry_price=100.,exit_price=price,quantity=16.,entry_notional=1600.,
            entry_outlay=outlay,exit_proceeds=proceeds,native_pnl=proceeds-outlay,
            reference_financing=0.,split='FIT' if known else 'UNKNOWN_LABEL',
            exit_reason='take_profit' if k==0 else 'initial_stop',intrabar_ambiguous=False))
    frame=pd.DataFrame(rows);spec=study.data.plan.resolve_spec()
    for col in spec['features']:
        if col not in frame:frame[col]=0.
    pool=frame[['date','symbol','score','oracle_rank','fold_start']].copy()
    return frame,pool,spec,days


def test_original_candidate_unknown_and_accounting_pass():
    result=study.verify_rows(*sample(),per_leg=.0008)
    assert result['known_labels']==2 and result['unknown_labels']==1


@pytest.mark.parametrize('fault',['rank','early_availability','cash','unknown_as_loss'])
def test_tampered_inputs_fail(fault):
    frame,pool,spec,days=sample()
    if fault=='rank':frame.loc[0,'oracle_rank']=5
    if fault=='early_availability':frame.loc[0,'label_available']=frame.loc[0,'exit_date']
    if fault=='cash':frame.loc[0,'entry_outlay']+=1
    if fault=='unknown_as_loss':frame.loc[2,'label']=0.
    with pytest.raises(ValueError):study.verify_rows(frame,pool,spec,days,per_leg=.0008)
