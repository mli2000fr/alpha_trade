from dataclasses import replace
from datetime import datetime,timezone,date
from types import SimpleNamespace
import pytest
from common.winner_pyramiding import WinnerPyramidingConfig
from common.market_calendar import get_market_calendar
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget
from scripts.research import us_winner_bottom_rank_filter_whole_shares_20261022 as s


def test_zero_half_share_is_rejected_without_budget_increase(monkeypatch):
    cfg=ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True,initial_position_fraction=.5,stop_loss_pct=.07))
    a=ExecutionTarget('risk',date(2025,1,3),'S',1,400.,.1,'Sector',1.,'fixed',None,risk_budget_dollars=50.,side='long')
    observed=[]
    monkeypatch.setattr(s,'ORIGINAL_STAGE',lambda st,t,*a,**kw:observed.extend(t))
    monkeypatch.setattr(s,'REFUSALS',[])
    s.stage_whole_shares(None,[a],cfg,'exec',now=datetime(2025,1,3,22,tzinfo=timezone.utc),calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False))
    assert observed==[] and len(s.REFUSALS)==1
    assert s.REFUSALS[0]['initial_quantity']==0 and a.target_shares==1


def test_other_errors_are_not_swallowed(monkeypatch):
    cfg=ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True))
    target=SimpleNamespace(side='long')
    monkeypatch.setattr(s,'plan_from_target',lambda *a,**k:(_ for _ in ()).throw(ValueError('invalid lineage')))
    with pytest.raises(ValueError,match='invalid lineage'):
        s.stage_whole_shares(None,[target],cfg,'exec')


def test_calendar_cache_preserves_official_sessions_and_independent_list():
    original=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    cached=s.CachedCalendar(original)
    expected=original.sessions(date(2025,1,1),date(2025,2,1))
    actual=cached.sessions(date(2025,1,1),date(2025,2,1))
    assert actual==expected
    actual.clear()
    assert cached.sessions(date(2025,1,1),date(2025,2,1))==expected
