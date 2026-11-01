"""Observed risk inputs for the whole trading universe, never a stock selector.

Only local canonical daily prices and dated cap observations are used. Repairs
are recorded at their actual observation time, never backdated into score history.
"""
from datetime import UTC, date, datetime, timedelta
import argparse
import hashlib
import json
import logging
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, select, text

from common.daily_bar_sources import select_daily_bars
from common.market_calendar import get_market_calendar
from common.universe_files import load_universe_file_symbols
from database.risk_factor_inputs import snapshots, require_schema
from selector.config import AlphaScannerConfig
from selector.factors import compute_factor_frame

PROTOCOL = 'daily-risk-inputs-qualified-provider-fallback-v3'
UNIVERSE = 'universe-file:config/univers_batch/univers_filtred_tradable.txt'
HISTORY_SESSIONS = 272
CAP_MAX_AGE_DAYS = 30
LOG=logging.getLogger(__name__)


def qualified_daily_rows(frame):
    numbers=frame[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    return (np.isfinite(numbers.to_numpy(dtype=float)).all(axis=1) & numbers.gt(0).all(axis=1)
        & numbers.high.ge(numbers[['open','close']].max(axis=1))
        & numbers.low.le(numbers[['open','close']].min(axis=1))
        & pd.to_numeric(frame.is_filled,errors='coerce').eq(0))


def select_factor_bars(frame, *, config=None):
    """Preferred complete row first; a qualified known alternative if invalid.

    Does not modify canonical bars or mix one provider's prices with another's
    volume. The same declared adjustment is required for any substitution.
    Ambiguous duplicates still fail in the shared selector.
    """
    selected=select_daily_bars(frame,config=config)
    fallbacks={}
    if selected.empty or 'data_source' not in frame or 'data_adjustment' not in frame:
        return selected,fallbacks
    for index,row in selected.loc[~qualified_daily_rows(selected)].iterrows():
        if row.data_source not in ('alpaca_sip','eodhd_eod') or row.data_adjustment!='split':
            continue
        alternative=frame.loc[frame.symbol.eq(row.symbol) & frame.date.eq(row.date)
            & frame.data_source.isin(['alpaca_sip','eodhd_eod']) & frame.data_source.ne(row.data_source)
            & frame.data_adjustment.eq(row.data_adjustment)]
        alternative=alternative.loc[qualified_daily_rows(alternative)]
        if len(alternative)!=1:
            continue
        replacement=alternative.iloc[0]
        selected.loc[index,:]=replacement[selected.columns]
        receipt=dict(date=pd.Timestamp(row.date).date().isoformat(),
            rejected_source=row.data_source,selected_source=replacement.data_source,
            reason='PREFERRED_DAILY_OHLCV_OR_FILL_INVALID')
        fallbacks.setdefault(row.symbol,[]).append(receipt)
        LOG.warning('Facteurs %s %s : ligne %s invalide ; ligne complète %s qualifiée utilisée',
            row.symbol,receipt['date'],row.data_source,replacement.data_source)
    return selected,fallbacks


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('Explicit UTC cutoff required')
    return value.astimezone(UTC)


def universe(required=()):
    return sorted(set(load_universe_file_symbols(UNIVERSE)) | {str(s).strip().upper() for s in required})


def universe_hash(symbols):
    return hashlib.sha256((PROTOCOL+'|'+','.join(sorted(set(symbols)))).encode()).hexdigest()


def expected_sessions(asof):
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    days = [s.session_date for s in cal.sessions(asof-timedelta(days=800), asof) if s.is_open]
    if not days or days[-1] != asof or len(days) < HISTORY_SESSIONS:
        raise ValueError('Qualified US sessions required for factor inputs')
    return days[-HISTORY_SESSIONS:]


def select_caps(rows, asof, cutoff, *, allow_reconstructed=False):
    """No metadata fallback: dated currency/provenance/availability are required."""
    cutoff = utc(cutoff)
    valid = []
    for raw in rows:
        row = dict(raw)
        stamp = row['computed_at']
        stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else utc(stamp)
        available=stamp
        if row.get('evidence_kind')=='RECONSTRUCTED_SEC_FACT':
            if allow_reconstructed is not True:
                continue
            available=utc(row['input_available_at'])
        if (row['source'] not in ('SEC_X_CLOSE', 'FINNHUB') or row['currency'] != 'USD'
                or not 0 <= (asof-row['observation_date']).days <= CAP_MAX_AGE_DAYS
                or row['available_date'] > cutoff.date() or available > cutoff
                or not np.isfinite(float(row['market_cap'])) or row['market_cap'] <= 0):
            continue
        valid.append(row)
    valid.sort(key=lambda r: (r['observation_date'], r['available_date'],
        r['source'] == 'SEC_X_CLOSE', r['computed_at'], r['id']), reverse=True)
    selected = {}
    for row in valid:
        selected.setdefault(row['symbol'], row)
    return selected


def calculate_inputs(bars, cap_rows, symbols, asof, cutoff, sessions, *, config=None,require_market_cap=True,
                     allow_reconstructed_caps=False):
    """Pure feature computation, before any Alpha Scanner eligibility filter."""
    data = bars.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.loc[data['date'].dt.date.le(asof)]
    data,bar_fallbacks = select_factor_bars(data, config=config)
    data = data.loc[data['date'].dt.date.isin(sessions)].sort_values(['symbol','date'])
    caps = select_caps(cap_rows, asof, cutoff,allow_reconstructed=allow_reconstructed_caps) if require_market_cap else {}
    spy = data.loc[data.symbol.eq('SPY')].set_index('date')['close'].astype(float)
    spy_filled = data.loc[data.symbol.eq('SPY'),'is_filled']
    if (list(spy.index.date) != list(sessions) or not np.isfinite(spy).all() or (spy <= 0).any()
            or spy_filled.isna().any() or spy_filled.astype(bool).any()):
        raise ValueError('Complete qualified SPY factor benchmark required')
    benchmark = spy.pct_change(fill_method=None).rename('spy_return').reset_index()
    groups = {s: f for s, f in data.groupby('symbol', sort=False)}
    qualified_frames, reasons = [], {}
    for symbol in symbols:
        frame = groups.get(symbol)
        errors = []
        if frame is None or list(frame['date'].dt.date) != list(sessions):
            errors.append('INCOMPLETE_DAILY_SESSIONS')
        elif frame['is_filled'].isna().any() or frame['is_filled'].astype(bool).any():
            errors.append('FILLED_OR_UNQUALIFIED_DAILY_BAR')
        else:
            numbers = frame[['open','high','low','close','volume']].astype(float)
            if (not np.isfinite(numbers.to_numpy()).all() or (numbers <= 0).any().any()
                    or (numbers.high < numbers[['open','close']].max(axis=1)).any()
                    or (numbers.low > numbers[['open','close']].min(axis=1)).any()):
                errors.append('INVALID_DAILY_BAR')
            else:
                qualified_frames.append(frame)
        if require_market_cap and symbol not in caps:
            errors.append('DATED_CAP_UNAVAILABLE')
        reasons[symbol] = errors
    if qualified_frames:
        features = compute_factor_frame(pd.concat(qualified_frames, ignore_index=True), benchmark, AlphaScannerConfig())
        features = features.set_index('symbol')
    else:
        features = pd.DataFrame()
    output = []
    for symbol in symbols:
        errors = reasons[symbol]
        beta, trend = None, None
        if symbol in features.index:
            beta = float(features.loc[symbol, 'beta_126'])
            trend = float(features.loc[symbol, 'trend_score'])
            if not np.isfinite(beta) or not np.isfinite(trend) or not 0 <= trend <= 1:
                errors.append('NONFINITE_TECHNICAL_FACTORS')
                beta, trend = None, None
        elif not errors:
            errors.append('TECHNICAL_FACTORS_UNAVAILABLE')
        cap = caps.get(symbol)
        frame = groups.get(symbol)
        prices_hash = (hashlib.sha256(pd.util.hash_pandas_object(frame, index=False).values.tobytes()).hexdigest()
                       if frame is not None else None)
        details = dict(protocol=PROTOCOL, reasons=errors, sessions=len(sessions), price_hash=prices_hash,
            daily_bar_fallbacks=bar_fallbacks.get(symbol,[]),
            benchmark_hash=hashlib.sha256(pd.util.hash_pandas_object(spy,index=True).values.tobytes()).hexdigest(),
            cap_record_id=cap['id'] if cap else None, cap_source=cap['source'] if cap else None,
            cap_available_date=str(cap['available_date']) if cap else None,
            cap_observation_date=str(cap['observation_date']) if cap else None,
            cap_evidence_kind=cap.get('evidence_kind','OBSERVED') if cap else None,
            cap_input_sha256=cap.get('input_sha256') if cap else None)
        output.append(dict(symbol=symbol, beta_126=beta, trend_score=trend,
            market_cap=float(cap['market_cap']) if cap else None, quality='INCOMPLETE' if errors else 'QUALIFIED',
            details_json=json.dumps(details,sort_keys=True), input_sha256=hashlib.sha256(
                json.dumps(dict(details=details,beta=beta,trend=trend),sort_keys=True).encode()).hexdigest()))
    return output


def load_inputs(engine, symbols, asof, cutoff):
    require_schema(engine)
    digest = universe_hash(symbols)
    with engine.connect() as conn:
        run = conn.execute(select(snapshots.c.run_id).where(snapshots.c.asof_date == asof,
            snapshots.c.universe_sha256 == digest, snapshots.c.observed_at <= utc(cutoff).replace(tzinfo=None))
            .order_by(snapshots.c.observed_at.desc(),snapshots.c.id.desc()).limit(1)).scalar_one_or_none()
        if run is None:
            return pd.DataFrame()
        rows = conn.execute(select(snapshots).where(snapshots.c.run_id == run)).mappings().all()
    frame = pd.DataFrame(rows)
    if set(frame.symbol) != set(symbols) or frame.symbol.duplicated().any():
        raise ValueError('Incomplete risk-factor publication')
    return frame


def refresh_inputs(engine, asof, *, required=(), symbols=None, cutoff=None, force=False):
    cutoff = utc(cutoff or datetime.now(UTC))
    asof = date.fromisoformat(str(asof))
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    session = next((s for s in cal.sessions(asof, asof) if s.is_open), None)
    if session is None or session.close_at_utc > cutoff:
        raise ValueError('Factor input date must be a completed US session')
    symbols = universe(required) if symbols is None else sorted(set(symbols) | set(required))
    require_schema(engine)
    cached = load_inputs(engine, symbols, asof, cutoff)
    if not force and not cached.empty:
        return cached
    sessions = expected_sessions(asof)
    query = text('SELECT symbol,date,open,high,low,close,volume,data_source,is_filled,data_adjustment FROM stock_bars_daily '
        'WHERE symbol IN :symbols AND date BETWEEN :start AND :end').bindparams(bindparam('symbols', expanding=True))
    caps_query = text('SELECT id,symbol,market_cap,source,currency,observation_date,available_date,computed_at '
        'FROM stock_market_cap_daily WHERE symbol IN :symbols AND observation_date BETWEEN :start AND :end '
        'AND available_date<=:available AND computed_at<=:cutoff').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(query, dict(symbols=sorted(set(symbols)|{'SPY'}),start=sessions[0],end=asof)).mappings().all()
        caps = conn.execute(caps_query,dict(symbols=symbols,start=asof-timedelta(days=CAP_MAX_AGE_DAYS),end=asof,
            available=cutoff.date(),cutoff=cutoff.replace(tzinfo=None))).mappings().all()
    prepared = calculate_inputs(pd.DataFrame(rows), caps, symbols, asof, cutoff, sessions)
    observed = max(cutoff, datetime.now(UTC)).replace(tzinfo=None)
    run_id = 'risk-inputs-'+uuid.uuid4().hex
    digest = universe_hash(symbols)
    records = [dict(row,run_id=run_id,asof_date=asof,observed_at=observed,universe_sha256=digest) for row in prepared]
    with engine.begin() as conn:
        conn.execute(snapshots.insert(), records)
    # New facts are only servable at actual publication time, not the initial
    # cutoff if computation took time. Never mutate historical score snapshots.
    return pd.DataFrame(records)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asof', required=True, type=date.fromisoformat)
    p.add_argument('--install-schema', action='store_true')
    p.add_argument('--force', action='store_true')
    args = p.parse_args()
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    if args.install_schema:
        from database.risk_factor_inputs import install_schema
        install_schema(engine)
    frame = refresh_inputs(engine,args.asof,force=args.force)
    print(json.dumps(dict(run_id=frame.run_id.iloc[0],asof=str(args.asof),rows=len(frame),
        qualified=int(frame.quality.eq('QUALIFIED').sum()),incomplete=int(frame.quality.ne('QUALIFIED').sum()))))
