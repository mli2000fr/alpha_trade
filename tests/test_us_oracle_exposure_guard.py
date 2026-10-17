from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backtesting.oracle_portfolio_session import OraclePortfolioSession
from modelFactory.oracle_barrier import SCORES
from scripts.research.us_oracle_exposure_guard import ExposureState, ExposureSession, build_policy_tape


def fixture():
    days=pd.bdate_range('2024-01-02',periods=16)
    symbols=[f'S{i:02d}' for i in range(50)]
    scores=pd.DataFrame([dict(date=day,symbol=s,**{SCORES['long']:1-i/100})
        for day in days for i,s in enumerate(symbols)])
    prices=pd.DataFrame([dict(date=day,symbol=s,close=100*(.99**j if s!='SPY' else 1.),
        volume=100.,is_filled=0) for j,day in enumerate(days) for s in [*symbols,'SPY']])
    return days,scores,prices


def test_weakness_reduces_then_improvement_rearms():
    state=ExposureState()
    assert [state.update(True) for _ in range(4)]==[1.,.5,.5,.25]
    assert [state.update(False) for _ in range(4)]==[.25,.5,.5,1.]


def test_alternating_days_do_not_accumulate_confirmation():
    state=ExposureState()
    assert [state.update(v) for v in [True,False,True,False,True]]==[1.]*5


def test_unknown_is_not_good_news_or_forward_filled():
    state=ExposureState(weak_streak=3)
    assert state.update(None)==.25
    assert state.weak_streak==state.improving_streak==0
    assert state.update(False)==.25
    assert state.update(False)==.5


def test_basket_membership_is_previous_session_not_current_rank():
    days,scores,prices=fixture()
    extra=pd.DataFrame([dict(date=d,symbol='NEW',**{SCORES['long']:2.}) for d in days[7:]])
    extra_prices=pd.DataFrame([dict(date=d,symbol='NEW',close=100*(10**j),volume=100,is_filled=0)
        for j,d in enumerate(days)])
    before=build_policy_tape(scores,prices,days)
    after=build_policy_tape(pd.concat([scores,extra]),pd.concat([prices,extra_prices]),days)
    # NEW enters the ranking at J7, so it cannot influence the J7 return.
    assert after.loc[7,'basket_return']==before.loc[7,'basket_return']
    assert after.loc[8,'basket_return']!=before.loc[8,'basket_return']
    # First synthetic session has no preceding calendar day: explicit warmup.
    assert (pd.to_datetime(after.membership_date.iloc[1:])<after.date.iloc[1:]).all()


def test_future_scores_prices_and_labels_cannot_change_prefix():
    days,scores,prices=fixture()
    original=build_policy_tape(scores,prices,days)
    changed=scores.copy()
    changed.loc[changed.date>days[8],SCORES['long']]=.2
    changed['future_pnl']=9999
    altered=prices.copy()
    altered.loc[altered.date>days[8],'close']=99999
    result=build_policy_tape(changed,altered,days)
    pd.testing.assert_frame_equal(original.iloc[:9],result.iloc[:9])


def test_warmup_requires_five_contiguous_observations():
    days,scores,prices=fixture()
    result=build_policy_tape(scores,prices,days)
    assert result.loc[:4,'status'].eq('UNKNOWN_OR_WARMUP').all()
    assert result.loc[5,'weak'] is True or result.loc[5,'weak']==True
    assert result.loc[5,'exposure_scale']==.25


def test_exact_90_percent_coverage_is_qualified_but_more_missing_is_unknown():
    days,scores,prices=fixture()
    missing=prices.date.eq(days[7])&prices.symbol.isin([f'S{i:02d}' for i in range(5)])
    prices.loc[missing,'is_filled']=1
    result=build_policy_tape(scores,prices,days)
    assert result.loc[7,'coverage']==.9 and result.loc[7,'status']=='QUALIFIED'
    prices.loc[prices.date.eq(days[7])&prices.symbol.eq('S05'),'volume']=0
    result=build_policy_tape(scores,prices,days)
    assert result.loc[7,'coverage']==.88
    assert result.loc[7:12,'status'].eq('UNKNOWN_OR_WARMUP').all()
    assert result.loc[13,'status']=='QUALIFIED'


def test_spy_missing_is_unknown_not_neutral():
    days,scores,prices=fixture()
    prices.loc[prices.date.eq(days[7])&prices.symbol.eq('SPY'),'close']=np.nan
    result=build_policy_tape(scores,prices,days)
    assert result.loc[7,'weak'] is None
    assert result.loc[7,'exposure_scale']==.25


def test_duplicate_prices_rejected():
    days,scores,prices=fixture()
    with pytest.raises(ValueError,match='Duplicate'):
        build_policy_tape(scores,pd.concat([prices,prices.iloc[:1]]),days)


def test_positive_basket_underperforming_spy_is_not_weakness():
    days,scores,prices=fixture()
    for j,day in enumerate(days):
        prices.loc[prices.date.eq(day)&prices.symbol.ne('SPY'),'close']=100*1.01**j
        prices.loc[prices.date.eq(day)&prices.symbol.eq('SPY'),'close']=100*1.02**j
    result=build_policy_tape(scores,prices,days)
    assert result.loc[5:,'weak'].eq(False).all()
    assert result.loc[8:,'exposure_scale'].eq(1.).all()


def test_partial_report_cannot_pass_result_audit(tmp_path):
    from scripts.research.us_oracle_exposure_guard_audit import audit
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    atomic_json(tmp_path/'exposure-protocol.json',{})
    atomic_json(tmp_path/'report.json',dict(status='RUNNING',years=[]))
    with pytest.raises(ValueError,match='three completed'):
        audit(tmp_path)


@pytest.mark.parametrize('scale',[1.,.5,.25])
def test_session_cap_is_multiplicative_and_restores_base_config(monkeypatch,tmp_path,scale):
    from risk_management.config import RiskConfig
    tape=pd.DataFrame(dict(date=[pd.Timestamp('2024-01-03')],exposure_scale=[scale],status=['QUALIFIED']))
    config=RiskConfig(risk_multiplier=.8)
    session=ExposureSession(config,sector_map={},account_long_only=False,policy_tape=tape,
        audit_path=tmp_path/'audit.json')
    seen=[]
    def native(self,day,**kwargs):
        seen.append(self.config.risk_multiplier)
        self.resolved_config=self.config.with_overrides(risk_multiplier=self.config.risk_multiplier*.1)
        return []
    monkeypatch.setattr(OraclePortfolioSession,'decide',native)
    session.decide(pd.Timestamp('2024-01-03').date(),scores=pd.DataFrame(),
        regime=SimpleNamespace(allowed_long_entries=False))
    assert seen==[.8*scale]
    assert session.config is config
    assert session.resolved_config.risk_multiplier==pytest.approx(.8*scale*.1)
    assert session.audit_rows[-1]['allow_long'] is False


def test_session_restores_config_when_native_raises(monkeypatch,tmp_path):
    from risk_management.config import RiskConfig
    tape=pd.DataFrame(dict(date=[pd.Timestamp('2024-01-03')],exposure_scale=[.25],status=['QUALIFIED']))
    config=RiskConfig()
    session=ExposureSession(config,sector_map={},account_long_only=False,policy_tape=tape,
        audit_path=tmp_path/'audit.json')
    def broken(*args,**kwargs):
        raise RuntimeError('native risk failure')
    monkeypatch.setattr(OraclePortfolioSession,'decide',broken)
    with pytest.raises(RuntimeError,match='native risk failure'):
        session.decide(pd.Timestamp('2024-01-03').date())
    assert session.config is config
