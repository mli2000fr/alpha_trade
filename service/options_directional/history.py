"""Shared SELECT-only options evidence, for pipeline and historical replay."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import bindparam, text

from common.daily_bar_sources import select_daily_bars
from .features import build_features


def read_options_evidence(conn, symbols, day, cutoff):
    if cutoff.tzinfo is None:
        raise ValueError('Cutoff options UTC explicite requis')
    start=datetime.combine(day,datetime.min.time(),ZoneInfo('America/New_York')).astimezone(timezone.utc)
    params=dict(symbols=list(symbols),start=start.replace(tzinfo=None),
        end=(start+timedelta(days=1)).replace(tzinfo=None),
        cutoff=cutoff.astimezone(timezone.utc).replace(tzinfo=None),day=day)
    queries={
        'snapshots': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
            option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
            FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'volumes': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
            bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
            FROM stock_option_bars_delayed WHERE provider='alpaca' AND timeframe='30Min'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND bar_timestamp>=:start AND bar_timestamp<:end AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'prices': '''SELECT symbol,date,close,is_filled,data_source FROM stock_bars_daily
            WHERE symbol IN :symbols AND date=:day AND data_source IN ('eodhd_eod','alpaca_sip')''',
    }
    raw={}
    for key,sql in queries.items():
        raw[key]=[dict(r) for r in conn.execute(text(sql).bindparams(
            bindparam('symbols',expanding=True)),params).mappings()] if symbols else []
    prices=select_daily_bars(pd.DataFrame(raw['prices'])) if raw['prices'] else pd.DataFrame()
    spots={} if prices.empty else {r.symbol:float(r.close) for r in prices.itertuples()
        if not r.is_filled and pd.notna(r.close) and r.close>0}
    features=build_features(pd.DataFrame(raw['snapshots']),pd.DataFrame(raw['volumes']),
        spots,day,pd.Timestamp(cutoff))
    return features,raw
