"""Causal research-only switch; no mutation of production or existing risk rules."""
import numpy as np
import pandas as pd

from backtesting.winner_portfolio_budget import PortfolioRiskPolicy,RegimeEntryGate
from backtesting.risk_overlay import RegimeFilterConfig


def switch_states(close,window,*,entry_buffer=-.02,exit_buffer=.01,on_sessions=2,off_sessions=5):
    if type(window) is not int or not 2<=window<=252:raise ValueError('Invalid switch window')
    if type(on_sessions) is not int or type(off_sessions) is not int or min(on_sessions,off_sessions)<1:
        raise ValueError('Invalid confirmation count')
    if not np.isfinite([entry_buffer,exit_buffer]).all() or not -.5<entry_buffer<exit_buffer<.5:
        raise ValueError('Invalid hysteresis buffers')
    s=close.sort_index().astype(float)
    if not isinstance(s.index,pd.DatetimeIndex) or s.index.tz is not None or s.index.has_duplicates or s.index.hasnans:
        raise ValueError('Unique naive exchange dates required')
    if not np.isfinite(s.to_numpy()).all() or not s.gt(0).all():raise ValueError('Unqualified SPY close')
    ma=s.rolling(window,min_periods=window).mean();active=False;down=up=0;rows=[]
    for day,value in s.items():
        average=ma.loc[day];qualified=bool(np.isfinite(average));transition=''
        if qualified:
            distance=value/average-1.
            down=down+1 if distance<entry_buffer else 0
            up=up+1 if distance>exit_buffer else 0
            if not active and down>=on_sessions:active=True;transition='ON';down=up=0
            elif active and up>=off_sessions:active=False;transition='OFF';down=up=0
        else:distance=np.nan
        rows.append(dict(signal_date=day,spy_close=value,sma=average,distance=distance,qualified=qualified,
            active=active,transition=transition,below_count=down,above_count=up))
    return pd.DataFrame(rows).set_index('signal_date')


def state_at(states,day):
    day=pd.Timestamp(day)
    if day not in states.index or not bool(states.loc[day,'qualified']):raise ValueError('Qualified prior SPY state required')
    return states.loc[day]


class SwitchedRegime:
    def __init__(self,close,states):
        self.states=states;self.receipts=[]
        self.defensive=RegimeEntryGate(close['SPY'],RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02))

    def __call__(self,signal_day,rows,cutoff):
        day=pd.Timestamp(signal_day);stamp=pd.Timestamp(cutoff)
        if stamp.tzinfo is None or stamp.tz_convert('America/New_York').date()<=day.date():
            raise ValueError('Signal close must precede entry session')
        state=state_at(self.states,day);active=bool(state.active)
        result=self.defensive(day,rows,cutoff) if active else dict(selected=rows.symbol.tolist(),incomplete=False)
        self.receipts.append(dict(signal_date=str(day.date()),cutoff=str(cutoff),protection_active=active,
            candidates=len(rows),selected=len(result['selected']),blocked=len(rows)-len(result['selected'])))
        return result


class SwitchedBudget:
    def __init__(self,close,states):
        self.states=states;self.receipts=[];self.defensive=PortfolioRiskPolicy(close,target=.20,lookback=60)

    def wrap(self,native):
        protected=self.defensive.wrap(native)
        def approve(state,version,proposed,snapshot,now,*,context):
            stamp=pd.Timestamp(snapshot['opening_at'])
            if stamp.tzinfo is None:raise ValueError('Aware opening required')
            entry_day=pd.Timestamp(stamp.tz_convert('America/New_York').date())
            days=self.states.index[self.states.index<entry_day]
            if not len(days):raise ValueError('Prior SPY state missing')
            day=days[-1];active=bool(state_at(self.states,day).active)
            first=len(self.defensive.receipts)
            result=(protected if active else native)(state,version,proposed,snapshot,now,context=context)
            details=self.defensive.receipts[first:]
            self.receipts.append(dict(time=str(now),signal_date=str(day.date()),symbol=state['symbol'],
                protection_active=active,final_quantity=int(result['max_quantity']),
                budget_called=bool(details),budget_status=details[-1].get('status') if details else None))
            return result
        return approve
