"""Replay-only daily OHLC fallback. Never fabricate a five-minute price path."""
from copy import deepcopy
import math

import pandas as pd

from common.winner_pyramiding import WinnerPyramidingConfig,regular_bounds,observe_completed_bar
from execution_engine.models import IntentRole
from execution_engine.winner_broker import make_intent
from execution_engine.winner_runtime import WinnerCampaignRuntime


def daily_value(frame,day,symbol):
    if frame is None or symbol not in frame or pd.Timestamp(day) not in frame.index:return None
    value=float(frame.loc[pd.Timestamp(day),symbol])
    return value if math.isfinite(value) and value>0 else None


def prepare_protection_day(day,symbols,groups,*,open_df,high,low,close):
    """Resolution choice changes protection precision, never candidate membership."""
    opening,closing=regular_bounds(day)
    expected=pd.date_range(opening,closing,freq='5min',inclusive='left')
    intraday,fallback={},{}
    for symbol in symbols:
        group=groups.get(symbol)
        op=daily_value(open_df,day,symbol)
        reason='MISSING_OR_INCOMPLETE_5M_SESSION'
        complete=group is not None and group.index.equals(expected)
        if complete:
            values=group[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
            complete=(values.map(lambda v:math.isfinite(v) and v>0).all().all()
                and values.low.le(values[['open','close']].min(axis=1)).all()
                and values.high.ge(values[['open','close']].max(axis=1)).all())
            if not complete:reason='INVALID_5M_OHLCV'
        if complete and op is not None:
            if abs(op/float(group.iloc[0]['open'])-1)<=.01+1e-12:
                intraday[symbol]=group;continue
            reason='DAILY_RAW_PRICE_BASIS_MISMATCH'
        elif op is None:reason='DAILY_OPEN_MISSING'
        bar=dict(open=op,high=daily_value(high,day,symbol),low=daily_value(low,day,symbol),
                 close=daily_value(close,day,symbol))
        valid=all(v is not None for v in bar.values())
        valid=valid and bar['low']<=min(bar['open'],bar['close'])<=max(bar['open'],bar['close'])<=bar['high']
        fallback[symbol]=dict(reason=reason,open=op,bar=bar if valid else None)
    return intraday,fallback


def opening_prints(fallback):
    # Only the opening is known at this instant. No day's high/low/close leaks.
    return {s:dict(open=r['open'],high=r['open'],low=r['open'],close=r['open'])
            for s,r in fallback.items() if r['open'] is not None}


def tighten_after_daily_close(store,repo,book,execution,symbols,day,closing):
    """Resolve the day's OLD stop first; today's high tightens only for next open."""
    for record in store.rows():
        state=record['state'];symbol=state['symbol']
        if symbol not in symbols:continue
        rt=WinnerCampaignRuntime(store,repo,book,execution,market=lambda *_:{},risk=lambda *_:{},
            now=closing,lifecycle_only=True)
        rt.state,rt.version=state,record['version']
        rt.reconcile();rt.reconcile_lots()
        policy=WinnerPyramidingConfig(**rt.state['policy'])
        for i,lot in enumerate(rt.state['lots']):
            if not lot['remaining']:continue
            updated=deepcopy(lot)
            observe_completed_bar(updated,symbols[symbol]['high'],policy)
            updated['last_bar_end']=closing.isoformat()
            if updated['stop']>lot['stop']:
                intent=make_intent(rt.state,lot['parent_id']+'-daily-trail-'+str(updated['stop']),
                    quantity=lot['remaining'],side='sell',role=IntentRole.INITIAL_STOP,
                    order_type='stop',stop=updated['stop'],parent=lot['parent_intent_id'])
                operation=rt.reserve('TIGHTEN',intent,lot_index=i,old_stop=lot['stop'],
                    evidence_source='DAILY_OHLC',evidence_session=str(day))
                order=book.tighten(rt.state,lot,intent)
                lot.update(stop_order_id=order.broker_order_id,stop=updated['stop'])
                operation.update(status='DONE',broker_id=order.broker_order_id)
                book.events.append(dict(time=closing,symbol=symbol,event='DAILY_TRAILING_UPDATE',
                    stop=lot['stop'],effective_from='NEXT_SESSION_OPEN',price_source='CANONICAL_DAILY_OHLC'))
            lot.update(peak=updated['peak'],last_bar_end=updated['last_bar_end'])
            rt.save()
