import pandas as pd
import pytest

from scripts.research import us_news_gpt_q1_2025_evaluate as study


def window(rows):
    return pd.DataFrame(rows,columns=['open','high','low','close'],index=pd.date_range('2025-01-03',periods=len(rows)))


def test_stop_wins_intraday_ambiguity():
    day,price,reason=study.unit_path(window([[100,125,90,110]]),101)
    assert price==95 and reason=='initial_stop'


def test_gap_stop_can_lose_more_than_five_percent():
    day,price,reason=study.unit_path(window([[100,102,98,100],[90,91,88,89]]),100)
    assert price==90 and reason=='initial_stop_gap_open'


def test_tp_gap_conservative_limit_not_higher_open():
    day,price,reason=study.unit_path(window([[100,102,98,100],[130,135,129,131]]),100)
    assert price==120 and reason=='take_profit_gap_limit'


def test_no_barrier_expires_next_open():
    day,price,reason=study.unit_path(window([[100,102,98,100],[101,102,99,101]]),103)
    assert day is None and price==103 and reason=='expiry_open'


def test_monthly_returns_use_continuous_equity_not_reset():
    daily=pd.DataFrame({'date':pd.to_datetime(['2025-01-31','2025-02-28']),'equity':[4400,4180]})
    actual=study.monthly_curves(daily,pd.DataFrame())
    assert actual[0]['return_pct']==pytest.approx(10)
    assert actual[1]['return_pct']==pytest.approx(-5)


def test_veto_attribution_matches_next_open_not_the_decision_day():
    dates=pd.date_range('2025-01-02',periods=3)
    candidates=pd.DataFrame({'date':[dates[0],dates[1]],'symbol':['A','B'],
        'oracle_rank':[1,2],'veto_long':[True,True]})
    executions=[{'date':str(dates[1]),'opened':['A','B']}]
    trades=pd.DataFrame({'symbol':['A','A','B'],'entry_date':[dates[1]]*3,'pnl':[-10,-5,30]})
    rows=study.veto_attribution(candidates,dates,executions,trades)
    assert rows[0]['baseline_opened'] and rows[0]['baseline_position_pnl_usd']==-15
    assert not rows[1]['baseline_opened'] and rows[1]['baseline_position_pnl_usd'] is None


def test_veto_attribution_requires_complete_position():
    dates=pd.date_range('2025-01-02',periods=2)
    candidates=pd.DataFrame({'date':[dates[0]],'symbol':['A'],'oracle_rank':[1],'veto_long':[True]})
    with pytest.raises(ValueError,match='fully closed'):
        study.veto_attribution(candidates,dates,[{'date':str(dates[1]),'opened':['A']}],pd.DataFrame())
