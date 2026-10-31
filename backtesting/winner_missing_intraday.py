"""Explicit POST-HOC availability screen, never a causal trading signal.

Screen potential campaign windows before replay. An excluded ticker is removed
from the entire run, not from an already-held portfolio. Original ranks stay.
"""
from datetime import timedelta
import hashlib
import json
import logging

import pandas as pd
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import regular_bounds

LOG=logging.getLogger(__name__)


def required_windows(selected,end,policy):
    """Merged potential entry/holding windows, not years before a ticker's signal."""
    if selected.empty:return {}
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    first=pd.to_datetime(selected.trade_date).min().date()
    days=[s.session_date for s in calendar.sessions(first,end) if s.is_open]
    indices={day:i for i,day in enumerate(days)}
    windows={}
    for symbol,rows in selected.groupby('symbol',sort=True):
        ranges=[]
        for day in pd.to_datetime(rows.trade_date).dt.date:
            if day not in indices:raise ValueError('Oracle signal outside official screening sessions')
            start=indices[day]
            last=(len(days)-1 if policy.horizon_sessions is None else
                min(len(days)-1,start+policy.entry_valid_sessions+policy.horizon_sessions))
            ranges.append((start,last))
        merged=[]
        for start,last in sorted(ranges):
            if merged and start<=merged[-1][1]+1:
                merged[-1]=(merged[-1][0],max(last,merged[-1][1]))
            else:merged.append((start,last))
        windows[symbol]=[(days[start],days[last]) for start,last in merged]
    return windows


def classify_missing(windows,counts):
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    seen={}
    for r in counts:
        key=(r['symbol'],pd.Timestamp(r['trade_date']).date())
        if key in seen:raise ValueError('Duplicate intraday coverage aggregates')
        seen[key]=r
    missing=[]
    for symbol,ranges in sorted(windows.items()):
        for first,last in ranges:
            for session in calendar.sessions(first,last):
                if not session.is_open:continue
                day=session.session_date
                opening,closing=session.open_at_utc,session.close_at_utc
                expected=int((closing-opening).total_seconds()/300)
                row=seen.get((symbol,day),{})
                actual=int(row.get('bars') or 0)
                first_bar=pd.to_datetime(row.get('first_bar'),utc=True)
                last_bar=pd.to_datetime(row.get('last_bar'),utc=True)
                if (actual!=expected or first_bar!=opening or last_bar!=closing-timedelta(minutes=5)):
                    missing.append(dict(symbol=symbol,date=day.isoformat(),expected_bars=expected,
                        qualified_bars=actual,missing_bars=max(0,expected-actual),
                        reason='MISSING_OR_UNQUALIFIED_INTRADAY_SESSION',
                        first_bar=None if pd.isna(first_bar) else first_bar.isoformat(),
                        last_bar=None if pd.isna(last_bar) else last_bar.isoformat()))
    return missing


def screen_missing_intraday(conn,selected,end,policy,*,progress=None,batch_size=32):
    windows=required_windows(selected,end,policy)
    symbols=sorted(windows)
    counts=[]
    # Counts only qualified raw SIP regular 5m rows, on the official candle grid.
    # MIN/MAX + unique count proves every grid point inside the session exists.
    if conn.dialect.name=='sqlite':
        timing="""AND strftime('%S',bar_timestamp)='00'
            AND strftime('%f',bar_timestamp)='00.000'
            AND CAST(strftime('%M',bar_timestamp) AS INTEGER)%5=0
            AND CAST(strftime('%s',bar_end_timestamp) AS INTEGER)-CAST(strftime('%s',bar_timestamp) AS INTEGER)=300"""
    else:
        timing="""AND SECOND(bar_timestamp)=0 AND MICROSECOND(bar_timestamp)=0
            AND MOD(MINUTE(bar_timestamp),5)=0
            AND TIMESTAMPDIFF(MICROSECOND,bar_timestamp,bar_end_timestamp)=300000000"""
    for offset in range(0,len(symbols),batch_size):
        batch=symbols[offset:offset+batch_size]
        clauses=[];params={}
        for i,symbol in enumerate(batch):
            clauses.append(f'(symbol=:symbol{i} AND bar_timestamp>=:first{i} AND bar_timestamp<:last{i})')
            params.update({f'symbol{i}':symbol,
                f'first{i}':regular_bounds(windows[symbol][0][0])[0].replace(tzinfo=None),
                f'last{i}':regular_bounds(windows[symbol][-1][1])[1].replace(tzinfo=None)})
        query=text('SELECT symbol,trade_date,COUNT(DISTINCT bar_timestamp) AS bars, '
            'MIN(bar_timestamp) AS first_bar,MAX(bar_timestamp) AS last_bar FROM stock_bars_intraday '
            "WHERE interval_code='5m' AND data_source='alpaca_sip' AND provider='alpaca' AND market_code='US_EQ' "
            "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 "
            "AND payload_hash IS NOT NULL AND payload_hash<>'' AND volume>0 "
            'AND open>0 AND close>0 AND low>0 AND high>=open AND high>=close AND low<=open AND low<=close '
            +timing+' AND ('+' OR '.join(clauses)+') GROUP BY symbol,trade_date')
        counts.extend(dict(r) for r in conn.execute(query,params).mappings())
        checked=min(offset+len(batch),len(symbols))
        LOG.info('Contrôle préalable intraday : %d/%d titres Oracle',checked,len(symbols))
        if progress:progress(checked,len(symbols))
    gaps=classify_missing(windows,counts)
    return dict(enabled=True,status='POST_HOC_DATA_COVERAGE_SCREEN',
        symbols_checked=len(symbols),excluded_symbols=sorted({r['symbol'] for r in gaps}),
        missing_sessions=len(gaps),gaps=gaps,
        scope='POTENTIAL_CAMPAIGN_WINDOWS_SIGNAL_ENTRY_VALIDITY_HOLDING_BOUNDED_BY_REPLAY_END',
        coverage_sha256=hashlib.sha256(json.dumps(dict(windows=windows,
            counts=sorted(counts,key=lambda r:(r['symbol'],str(r['trade_date'])))),sort_keys=True,default=str).encode()).hexdigest(),
        exclusion_policy='WHOLE_RUN_AFTER_ORACLE_TOP_N_NO_REFILL',
        uses_future_data_availability=True,live_compatible=False)


def log_missing_summary(report):
    LOG.warning('Bilan titres ignorés pour données intraday absentes : %d/%d titres ; %d séances incomplètes',
        len(report['excluded_symbols']),report['symbols_checked'],report['missing_sessions'])
    for symbol in report['excluded_symbols']:
        dates=[r['date'] for r in report['gaps'] if r['symbol']==symbol]
        LOG.warning('Titre ignoré : %s ; %d séances incomplètes ; premières dates : %s ; détail dans missing-intraday.csv',
            symbol,len(dates),', '.join(dates[:5]))
