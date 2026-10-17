"""Frozen 0.5 threshold, date weights, block intervals, no false no-trade win."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_profit_tp15_sl7_fit as study


def panel():
    dates=pd.bdate_range('2022-01-03',periods=130)
    return pd.DataFrame([dict(date=d,symbol=str(k),label=float(k>=2),net_return=.14 if k>=2 else -.075)
                         for d in dates for k in range(4)])


def spec():return study.data.plan.resolve_spec()


def test_weights_equal_dates_not_most_populated_day():
    f=panel().iloc[:7];w=study.equal_date_weights(f)
    assert w[:4].sum()==pytest.approx(w[4:].sum())


def test_no_acceptance_is_failure_not_gain_from_avoided_losses():
    f=panel();result=study.metrics(f,np.full(len(f),.49),.5,spec())
    assert not result['all_gates_pass'] and result['accepted_rows']==0
    assert result['accepted_date_matched_net_lift'] is None and result['lift_block_interval']['low'] is None
    assert result['no_acceptance_dates']==130


def test_frozen_threshold_and_conditional_daily_auc():
    f=panel();probability=np.where(f.label.eq(1),.8,.2)
    result=study.metrics(f,probability,.5,spec())
    assert result['mean_daily_auc']==1 and result['auc_dates']==130
    assert result['accepted_fraction']==.5 and result['all_gates_pass']
    exact=study.metrics(f,np.full(len(f),.5),.5,spec())
    assert exact['accepted_rows']==len(f) and not exact['checks']['accepted_fraction']


def test_no_acceptance_dates_are_not_imputed_zero_trades():
    f=panel();p=np.where(f.label.eq(1),.8,.2)
    p[:4]=.3
    result=study.metrics(f,p,.5,spec())
    assert result['no_acceptance_dates']==1 and result['accepted_dates']==129
    assert result['accepted_date_matched_net_lift']==pytest.approx(.14-(.14-.075)/2)


def test_block_interval_repeatable_and_missing_safe():
    x=np.tile([np.nan,.01,.02,.03],40)
    assert study.block_interval(x)==study.block_interval(x)
    assert study.block_interval([np.nan]*10)['valid_draws']==0


def test_invalid_probability_cannot_be_silently_dropped():
    with pytest.raises(ValueError):study.metrics(panel(),[.4],.5,spec())
    x=np.full(len(panel()),.4);x[0]=np.nan
    with pytest.raises(ValueError):study.metrics(panel(),x,.5,spec())
