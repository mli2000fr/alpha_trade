"""Explicit replay-only sizing policy. Native approval remains authoritative.

Past daily returns forecast the covariance of held/pending positions plus the
candidate. Only candidate quantity may shrink; existing lots/SL/open11 do not
change. This is an entry risk budget, not a continuous portfolio vol guarantee.
"""
import math

import numpy as np
import pandas as pd


from risk_management.portfolio_volatility import portfolio_limit


class PortfolioRiskPolicy:
    def __init__(self,close,target=None,lookback=60):
        self.returns=close.pct_change(fill_method=None)
        self.target=target;self.lookback=lookback;self.receipts=[]

    def wrap(self,native):
        def approve(state,version,proposed,snapshot,now,*,context):
            original=native(state,version,proposed,snapshot,now,context=context)
            native_qty=int(original['max_quantity'])
            if self.target is None or native_qty<=0:return original
            day=pd.Timestamp(snapshot['opening_at']).tz_convert('America/New_York').date()
            prior=self.returns.index[self.returns.index<pd.Timestamp(day)]
            if not len(prior):raise ValueError('No prior session for portfolio covariance')
            common=dict(time=str(now),symbol=state['symbol'],native_quantity=native_qty)
            try:
                decision=portfolio_limit(self.returns,prior_day=prior[-1],positions=context['positions'],
                    pending=context['pending_entries'],symbol=state['symbol'],price=float(
                        snapshot['entry_open'] if snapshot.get('price_source')=='OBSERVED_5M_OPEN' else snapshot['daily_open']),
                    equity=float(context['equity']),proposed=native_qty,target=self.target,lookback=self.lookback)
            except ValueError as exc:
                self.receipts.append(dict(**common,status='UNQUALIFIED_HISTORY',reason=str(exc)))
                raise
            # Reapply the unchanged native minimum-notional/position/cash/risk
            # constraints after reducing size. Never override a native veto.
            result=(native(state,version,min(proposed,decision['quantity']),snapshot,now,context=context)
                if decision['quantity']<native_qty else original)
            if int(result['max_quantity'])>native_qty:raise ValueError('Research sizing increased native quantity')
            self.receipts.append(dict(**common,status='QUALIFIED',**decision,final_quantity=int(result['max_quantity'])))
            return result
        return approve


class RegimeEntryGate:
    """Use prior-session SPY close only, preserving the fixed candidate set."""
    def __init__(self,close,rule,upstream=None):
        self.close=close.sort_index();self.rule=rule;self.upstream=upstream;self.receipts=[]

    def __call__(self,signal_day,rows,cutoff):
        day=pd.Timestamp(signal_day)
        if pd.Timestamp(cutoff).tz_convert('America/New_York').date()<=day.date():
            raise ValueError('Previous-session close required for regime gate')
        history=self.close.loc[:day].tail(self.rule.sma_window)
        if (len(history)!=self.rule.sma_window or history.index[-1]!=day
                or not np.isfinite(history.to_numpy(float)).all() or not history.gt(0).all()):
            raise ValueError('Qualified SPY history required for entry regime')
        allowed=self.rule.is_entry_allowed(self.close,day)
        self.receipts.append(dict(signal_date=str(day.date()),cutoff=str(cutoff),
            spy_close=float(history.iloc[-1]),sma=float(history.mean()),
            entry_allowed=bool(allowed),candidates=len(rows),blocked_candidates=0 if allowed else len(rows)))
        if not allowed:return dict(selected=[],incomplete=False)
        return self.upstream(signal_day,rows,cutoff) if self.upstream else dict(selected=rows.symbol.tolist(),incomplete=False)


def replay_protections(close,*,daily_entry,target=None,lookback=60,regime=False,
                       sma_window=200,bear_threshold=-.02,upstream=None):
    """Construct only the explicit options requested by the replay command."""
    if type(regime) is not bool or type(lookback) is not int or not 2<=lookback<=252:
        raise ValueError('Invalid portfolio-risk lookback/regime flag')
    if target is not None and (not math.isfinite(target) or not 0<target<=1):
        raise ValueError('Portfolio volatility target must be in (0,1]')
    if (target is not None or regime) and not daily_entry:
        raise ValueError('Portfolio budget/regime require daily J+1 entry mode')
    if type(sma_window) is not int or not 2<=sma_window<=500 or not math.isfinite(bear_threshold) or not -.5<=bear_threshold<=.5:
        raise ValueError('Invalid SPY regime settings')
    policy=PortfolioRiskPolicy(close,target=target,lookback=lookback) if target is not None else None
    gate=None
    if regime:
        from backtesting.risk_overlay import RegimeFilterConfig
        if 'SPY' not in close:raise ValueError('SPY required for regime gate')
        gate=RegimeEntryGate(close['SPY'],RegimeFilterConfig(enabled=True,sma_window=sma_window,
            bear_threshold=bear_threshold),upstream=upstream)
    return policy,gate if gate is not None else upstream
