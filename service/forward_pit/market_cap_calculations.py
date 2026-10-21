"""Compute and persist prospective caps from local inputs, never Yahoo.

No provider requests; no overwrite/backdating of SEC facts. Known split or
share-class ambiguities are delegated to the configured Finnhub fallback.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from common.instrument_policy import excluded_collective_instrument_reason
from common.market_calendar import get_market_calendar
from common.market_cap import compute_sec_market_cap
from database.market_cap_snapshots import require_schema, store


def as_day(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def positive(value):
    try:
        value = float(value)
        return value if isfinite(value) and value > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def reference_session(now, *, delay_minutes=30):
    if now.tzinfo is None or delay_minutes < 0:
        raise ValueError('Heure UTC consciente et délai positif ou nul requis')
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    eligible = [s.session_date for s in calendar.sessions(day-timedelta(days=21),day)
                if s.is_open and s.close_at_utc+timedelta(minutes=delay_minutes) <= now]
    if not eligible:
        raise RuntimeError('Aucune clôture NYSE qualifiée dans les 21 derniers jours')
    return max(eligible)


def source_rows(engine, symbols, source, as_of, max_age_days, observed_at):
    """Keep latest positive, available source record; never trust an old estimate field."""
    if not symbols:
        return {}
    query = text('''SELECT id,symbol,trade_date,available_date,fetched_at,shares_outstanding,
        market_cap,fiscal_period_end,accession_number FROM stock_fundamentals_daily
        WHERE symbol IN :symbols AND UPPER(source)=:source
          AND trade_date BETWEEN :min_date AND :as_of
          AND fetched_at<=:observed
        ORDER BY trade_date DESC, fetched_at DESC, id DESC''').bindparams(bindparam('symbols',expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(query,dict(symbols=sorted(set(symbols)),source=source,
            min_date=as_of-timedelta(days=max_age_days),as_of=as_of,
            observed=observed_at.astimezone(UTC).replace(tzinfo=None))).mappings().all()
    selected = {}
    for raw in rows:
        row = dict(raw)
        symbol = row['symbol']
        if symbol in selected:
            continue
        try:
            day = as_day(row['trade_date'])
            basis = day if source=='SEC_EDGAR' else as_day(row['fetched_at'])
            available = max(as_day(row['available_date']) if row['available_date'] else basis+timedelta(days=1),
                            basis+timedelta(days=1))
        except (ValueError,TypeError):
            continue
        value = positive(row['shares_outstanding'] if source=='SEC_EDGAR' else row['market_cap'])
        if available <= as_of and value is not None:
            row['source_available'] = available
            row['value'] = value
            selected[symbol] = row
    return selected


def context(engine, symbols, price_date, now):
    if not symbols:
        return {},{},[]
    with engine.connect() as conn:
        prices = conn.execute(text('''SELECT symbol,`close`,is_filled,data_source FROM stock_bars_daily
            WHERE symbol IN :symbols AND `date`=:day''').bindparams(bindparam('symbols',expanding=True)),
            dict(symbols=sorted(set(symbols)),day=price_date)).mappings().all()
        names = {row[0]:row[1] for row in conn.execute(text('SELECT symbol,company_name FROM stock_metadata WHERE symbol IN :symbols')
            .bindparams(bindparam('symbols',expanding=True)),dict(symbols=sorted(set(symbols)))).all()}
        # This is a conservative known-event guard, not a claim of complete CA coverage.
        splits = conn.execute(text('''SELECT symbol,ex_date FROM corporate_actions_events
            WHERE symbol IN :symbols AND ca_type IN ('split','reverse_split')
              AND LOWER(provider) IN ('alpaca','eodhd') AND ex_date<=:day
              AND ingested_at<=:observed''').bindparams(bindparam('symbols',expanding=True)),
            dict(symbols=sorted(set(symbols)),day=price_date,observed=now.astimezone(UTC).replace(tzinfo=None))).mappings().all()
    return {p['symbol']:dict(p) for p in prices},names,splits


def build_row(symbol, raw, now, run_id, *, source, cap, price_date=None, close=None, price_source=None):
    observation = now.astimezone(UTC).date()
    basis = as_day(raw.get('fiscal_period_end') or raw['trade_date'])
    row = dict(symbol=symbol,observation_date=observation,
        available_date=max(observation+timedelta(days=1),raw['source_available']),
        computed_at=now.astimezone(UTC).replace(tzinfo=None),source=source,market_cap=cap,currency='USD',
        shares_outstanding=raw['value'] if source=='SEC_X_CLOSE' else None,
        reference_close=close,price_date=price_date,price_source=price_source,
        source_record_id=int(raw['id']),source_trade_date=as_day(raw['trade_date']),
        source_available_date=raw['source_available'],shares_basis_date=basis if source=='SEC_X_CLOSE' else None,
        accession_number=raw['accession_number'],run_id=run_id,
        details_json=json.dumps(dict(method='reported_SEC_shares_x_canonical_close' if source=='SEC_X_CLOSE' else 'normalized_Finnhub_snapshot',
            price_convention='canonical_close_not_dividend_adjusted' if source=='SEC_X_CLOSE' else None,
            valuation_status='ESTIMATE_NOT_OFFICIAL',currency_basis='existing_US_EQ_contract',
            share_identity='known_ADR_class_and_split_guard_not_exhaustive' if source=='SEC_X_CLOSE' else None),sort_keys=True))
    identity = {k:v for k,v in row.items() if k not in ('computed_at','run_id')}
    row['input_hash'] = hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
    return row


def calculate_sec(engine, symbols, *, as_of, max_age_days, price_date, now, run_id):
    require_schema(engine)
    raw = source_rows(engine,symbols,'SEC_EDGAR',as_of,max_age_days,now)
    prices,names,splits = context(engine,list(raw),price_date,now)
    prepared, reasons = [],Counter()
    rejected = {}
    for symbol, record in raw.items():
        price = prices.get(symbol)
        name = str(names.get(symbol) or '')
        basis = as_day(record.get('fiscal_period_end') or record['trade_date'])
        source = str((price or {}).get('data_source') or '').lower()
        reason = None
        if not name:
            reason = 'MISSING_INSTRUMENT_METADATA'
        elif excluded_collective_instrument_reason(name):
            reason = 'COLLECTIVE_INSTRUMENT'
        elif '.' in symbol or ' ADR' in (' '+name.upper()) or 'DEPOSITARY' in name.upper() or 'DEPOSITORY' in name.upper():
            reason = 'AMBIGUOUS_ADR_OR_SHARE_CLASS'
        elif price is None:
            reason = 'MISSING_REFERENCE_CLOSE'
        elif price['is_filled'] != 0 or positive(price['close']) is None:
            reason = 'UNQUALIFIED_REFERENCE_CLOSE'
        elif source not in ('eodhd','eodhd_eod','alpaca_sip'):
            reason = 'UNQUALIFIED_PRICE_SOURCE'
        elif any(s['symbol']==symbol and basis < as_day(s['ex_date']) <= price_date for s in splits):
            reason = 'KNOWN_SPLIT_SINCE_SHARE_BASIS'
        cap = None if reason else compute_sec_market_cap(price['close'],record['value'])
        if cap is None:
            reason = reason or 'INVALID_PRODUCT'
            reasons[reason] += 1
            rejected[symbol] = reason
        else:
            prepared.append(build_row(symbol,record,now,run_id,source='SEC_X_CLOSE',cap=cap,
                price_date=price_date,close=float(price['close']),price_source=source))
    count = store(engine,prepared)
    return dict(symbols={r['symbol'] for r in prepared if r['available_date']<=as_of},persisted=count,
                details=dict(shares_eligible=len(raw),calculated_symbols=len(prepared),
                    snapshots_inserted=count,price_date=price_date.isoformat(),rejection_counts=dict(reasons),
                    rejected_symbols=rejected,coverage_basis='computed_and_stored_market_cap_not_shares_only'))


def calculate_finnhub(engine, symbols, *, as_of, max_age_days, now, run_id):
    raw = source_rows(engine,symbols,'FINNHUB',as_of,max_age_days,now)
    prepared=[build_row(symbol,r,now,run_id,source='FINNHUB',cap=r['value']) for symbol,r in raw.items()]
    count=store(engine,prepared)
    return dict(symbols={r['symbol'] for r in prepared if r['available_date']<=as_of},persisted=count,
                details=dict(snapshots_inserted=count,available_symbols=len(raw)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols-file',default='config/univers_batch/stock_bars_daily.txt')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Dossier neuf requis')
    from database.connection import get_sqlalchemy_engine
    from service.forward_pit.batch import _symbols
    engine=get_sqlalchemy_engine()
    require_schema(engine)
    now=datetime.now(UTC)
    as_of=now.date()+timedelta(days=1)
    day=reference_session(now)
    symbols=_symbols({'symbols_file':args.symbols_file})
    run_id='market-cap-local-'+now.strftime('%Y%m%d%H%M%S')
    sec=calculate_sec(engine,symbols,as_of=as_of,max_age_days=365,price_date=day,now=now,run_id=run_id)
    fh=calculate_finnhub(engine,sorted(set(symbols)-sec['symbols']),as_of=as_of,max_age_days=365,now=now,run_id=run_id)
    covered=sec['symbols']|fh['symbols']
    report=dict(run_id=run_id,mode='LOCAL_CALCULATION_ONLY_NOT_COLLECTION_RUN',provider_calls=0,
        observed_at=now.isoformat(),available_date_cutoff=as_of.isoformat(),price_date=day.isoformat(),
        requested=len(symbols),covered=len(covered),coverage_ratio=len(covered)/len(symbols),
        inserted=sec['persisted']+fh['persisted'],sec=sec['details'],finnhub=fh['details'],
        covered_symbols=sorted(covered),missing_symbols=sorted(set(symbols)-covered))
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sec','covered_symbols','missing_symbols')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
