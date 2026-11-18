"""Replay-only half sizing driven by causal, immutable internal-rate states."""
import math

import numpy as np
import pandas as pd


def internal_states(rates,shadow_equity,mode):
    if mode not in ('RATE','SHADOW'):raise ValueError('Unknown recovery mode')
    if rates.index.has_duplicates or not rates.index.is_monotonic_increasing:raise ValueError('Ambiguous rate dates')
    shadow=shadow_equity/shadow_equity.shift(20)-1
    shadow=shadow.reindex(rates.index)
    active=False;anchor=np.nan;down=up=0;rows=[]
    for day,row in rates.iterrows():
        transition='';was_active=active;qualified=bool(row.qualified)
        if not active:
            down=down+1 if qualified and row.recent_rate<row.reference_rate-.05 else 0
            up=0
            if down>=3:
                active=True;anchor=float(row.reference_rate);transition='ON';down=up=0
        else:
            condition=(qualified and row.recent_rate>=anchor-.02) if mode=='RATE' else (pd.notna(shadow.loc[day]) and shadow.loc[day]>.05)
            up=up+1 if condition else 0
            down=0
            if up>=5:active=False;transition='OFF';down=up=0
        rows.append(dict(signal_date=day,qualified=qualified,active=active,anchor=anchor,transition=transition,
            rate20=row.recent_rate,reference120=row.reference_rate,shadow_ret20=shadow.loc[day],
            below_count=down,recovery_count=up,previous_active=was_active))
    return pd.DataFrame(rows).set_index('signal_date')


class HalfNewEntry:
    """Half the native-approved integer quantity, rechecked against native limits.

    No position/stop mutation, no equity-scaling shortcut. The amount can be
    slightly below half due to integer rounding/minimum notional. Revalidation
    cannot silently quarter an already-halved quantity: admission calls once.
    """
    def __init__(self,states):self.states=states;self.receipts=[]

    def wrap(self,native):
        def approve(state,version,proposed,snapshot,now,*,context):
            stamp=pd.Timestamp(snapshot['opening_at'])
            if stamp.tzinfo is None:raise ValueError('Aware opening required')
            day=pd.Timestamp(stamp.tz_convert('America/New_York').date())
            before=self.states.index[self.states.index<day]
            if not len(before):raise ValueError('No causal previous signal state')
            signal=before[-1];row=self.states.loc[signal]
            original=native(state,version,proposed,snapshot,now,context=context)
            quantity=int(original['max_quantity'])
            if quantity<0:raise ValueError('Negative native quantity')
            active=bool(row.active);limit=math.floor(quantity*.5) if active else quantity
            result=(native(state,version,min(proposed,limit),snapshot,now,context=context) if active else original)
            final=int(result['max_quantity'])
            if final>limit:raise ValueError('Native recheck increased protected quantity')
            self.receipts.append(dict(time=str(now),signal_date=str(signal.date()),symbol=state['symbol'],
                protection_active=active,rate_qualified=bool(row.qualified),native_quantity=quantity,
                protected_quantity_limit=limit,final_quantity=final,minimum_or_other_native_veto=final<limit))
            return result
        return approve
