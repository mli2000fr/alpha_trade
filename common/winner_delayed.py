"""Delayed SIP evidence is never a current quote; price is bounded at broker."""
from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR
import math

from common.winner_pyramiding import WinnerPyramidingConfig, aware, fresh_completed_bars


def delayed_entry(state, kind='ENTRY', config=None):
    policy=WinnerPyramidingConfig(**state['policy'])
    allowed=policy.market_data_delay_seconds>0 and (kind=='ADD' or policy.confirmation_bars>0)
    if allowed and config is not None:
        current=config.winner_pyramiding
        if (current.market_data_delay_seconds != policy.market_data_delay_seconds
                or current.delayed_entry_limit_buffer_pct < policy.delayed_entry_limit_buffer_pct):
            raise ValueError('Politique SIP retardé changée : nouvelle admission nécessaire')
    return allowed


def delayed_snapshot(bars, policy, now):
    """No invented bid, ask or quote timestamp; retain original 5m timestamps."""
    now=aware(now)
    tail=fresh_completed_bars(bars,policy,now=now,count=1)
    return dict(bars=bars,feed='sip',market_data_mode='delayed_sip',ask=None,bid=None,
        data_cutoff=(now-timedelta(seconds=policy.market_data_delay_seconds)).isoformat(),
        received_at=now.isoformat(),delayed_reference_price=float(tail[-1]['close']) if tail else None,
        delayed_reference_end=(aware(tail[-1]['timestamp'])+timedelta(minutes=5)).isoformat() if tail else None)


def delayed_price_limit(state,snapshot,now):
    """Qualify historical evidence and derive a ceiling, never a market price."""
    policy=WinnerPyramidingConfig(**state['policy'])
    now=aware(now)
    if (policy.market_data_delay_seconds<=0 or snapshot.get('feed')!='sip'
            or snapshot.get('market_data_mode')!='delayed_sip'
            or snapshot.get('ask') is not None or snapshot.get('bid') is not None
            or snapshot.get('quote_time') is not None):
        raise ValueError('Preuve SIP retardée explicite requise, sans quote temps réel inventée')
    received=aware(snapshot['received_at'])
    cutoff=aware(snapshot['data_cutoff'])
    if (not 0 <= (now-received).total_seconds() <= 60
            or cutoff != received-timedelta(seconds=policy.market_data_delay_seconds)):
        raise ValueError('Horodatage de réception/cutoff SIP retardé invalide')
    tail=fresh_completed_bars(snapshot['bars'],policy,now=now,count=1)
    if not tail:
        raise ValueError('Dernière bougie SIP retardée manquante ou trop ancienne')
    price=float(tail[-1]['close'])
    end=aware(tail[-1]['timestamp'])+timedelta(minutes=5)
    if (not math.isfinite(price) or price<=0 or price!=snapshot.get('delayed_reference_price')
            or end!=aware(snapshot['delayed_reference_end']) or end>cutoff):
        raise ValueError('Prix de référence SIP retardé incohérent')
    ceiling=Decimal(str(price))*(1+Decimal(str(policy.delayed_entry_limit_buffer_pct)))
    gap=0. if state['lots'] else float(state.get('entry_policy',{}).get('max_entry_gap_pct') or 0.)
    if gap>0:
        ceiling=min(ceiling,Decimal(str(state['target']['entry_price']))*(1+Decimal(str(gap))))
    # The existing campaign entry bridge rounds to cents; never round UP
    # a delayed-price ceiling at that downstream boundary.
    tick=Decimal('.01')
    limit=float(ceiling.quantize(tick,rounding=ROUND_FLOOR))
    if not math.isfinite(limit) or limit<=0:
        raise ValueError('Plafond limite SIP retardé invalide')
    return limit
