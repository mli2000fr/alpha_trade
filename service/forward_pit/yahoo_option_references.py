"""Bounded Yahoo recovery of US option-discovery prices, never execution quotes.

Only current, exact-session USD daily closes for missing tradable underlyings.
No yfinance retries, impersonation, alternate host or SIP relabelling. SQL raw
receipts are a shared short-transaction cache, outside the long option import.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import logging
import math
from pathlib import Path
import random
import re
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import text

LOGGER=logging.getLogger(__name__)
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL='option-yahoo-reference-v1'
ENDPOINT='/v8/finance/chart'
PROVIDER='yahoo_finance'


@dataclass(frozen=True)
class RecoveryConfig:
    # Old callers/snapshots remain unchanged; both scheduled YAML jobs opt in.
    enabled: bool=False
    symbols_file: str='config/univers_batch/univers_filtred_tradable.txt'
    pause_min_seconds: float=1.
    pause_max_seconds: float=5.
    timeout_seconds: float=20.

    def __post_init__(self):
        if type(self.enabled) is not bool:raise ValueError('yahoo_reference_recovery.enabled doit être booléen')
        for key in ('pause_min_seconds','pause_max_seconds','timeout_seconds'):
            value=getattr(self,key)
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError(key+' doit être fini')
        if not 1<=self.pause_min_seconds<=self.pause_max_seconds<=5:
            raise ValueError('Pauses Yahoo : 1 <= minimum <= maximum <= 5 secondes')
        if not 1<=self.timeout_seconds<=60:raise ValueError('Timeout Yahoo entre 1 et 60 secondes')
        if not isinstance(self.symbols_file,str) or not self.symbols_file.strip():raise ValueError('Univers Yahoo requis')


def normalize_daily_reference(payload,symbol,day,received):
    """Validate Yahoo close without treating adjclose or a latest quote as J."""
    chart=payload.get('chart') if isinstance(payload,dict) else None
    if not isinstance(chart,dict):raise ValueError('YAHOO_MALFORMED_CHART')
    if chart.get('error'):return None
    results=chart.get('result') or []
    if not results:return None
    if len(results)!=1:raise ValueError('YAHOO_AMBIGUOUS_CHART')
    data=results[0];meta=data.get('meta') or {}
    provider_symbol=symbol.replace('.','-')
    if str(meta.get('symbol','')).upper()!=provider_symbol:raise ValueError('YAHOO_SYMBOL_MISMATCH')
    if meta.get('currency')!='USD':raise ValueError('YAHOO_NON_USD_REFERENCE')
    if meta.get('exchangeTimezoneName')!='America/New_York':raise ValueError('YAHOO_MARKET_TIMEZONE_UNQUALIFIED')
    if meta.get('instrumentType') not in ('EQUITY','ETF'):raise ValueError('YAHOO_INSTRUMENT_UNQUALIFIED')
    stamps=data.get('timestamp') or []
    blocks=(data.get('indicators') or {}).get('quote') or []
    if len(blocks)!=1:raise ValueError('YAHOO_QUOTES_MALFORMED')
    values=blocks[0]
    if any(len(values.get(k) or [])!=len(stamps) for k in ('open','high','low','close','volume')):
        raise ValueError('YAHOO_ARRAY_LENGTH_MISMATCH')
    # Chart OHLC may be rescaled by a later split. Never compare such a price
    # to an unadjusted strike, and never silently reverse a provider adjustment.
    for event in ((data.get('events') or {}).get('splits') or {}).values():
        stamp=datetime.fromtimestamp(float(event['date']),UTC)
        if day<stamp.astimezone(ZoneInfo('America/New_York')).date()<=received.astimezone(ZoneInfo('America/New_York')).date():
            raise ValueError('YAHOO_POST_SESSION_SPLIT')
    found=[]
    for i,ts in enumerate(stamps):
        stamp=datetime.fromtimestamp(float(ts),UTC)
        if stamp>received:continue
        if stamp.astimezone(ZoneInfo('America/New_York')).date()!=day:continue
        row={k:values[k][i] for k in ('open','high','low','close','volume')}
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in row):
            raise ValueError('YAHOO_INVALID_NUMERIC_REFERENCE')
        op,hi,lo,cl=[float(row[k]) for k in ('open','high','low','close')]
        if not all(v>0 for v in (op,hi,lo,cl)) or not lo<=min(op,cl)<=max(op,cl)<=hi or row['volume']<=0:
            raise ValueError('YAHOO_INVALID_OHLCV_REFERENCE')
        found.append(dict(symbol=symbol,provider_symbol=provider_symbol,price=cl,session_date=str(day),
            provider=PROVIDER,currency='USD',source='yahoo_daily_close',price_timestamp=stamp.isoformat(),
            observed_at=received.isoformat(),available_at=received.isoformat(),usage='OPTION_DISCOVERY_ONLY'))
    if len(found)>1:raise ValueError('YAHOO_DUPLICATE_SESSION')
    return found[0] if found else None


class SqlReceipts:
    """Shared cache and cross-process spacing with a scoped MySQL advisory lock."""
    def __init__(self,engine,run_id,batch_name,*,dry=False):
        self.engine,self.run_id,self.batch_name,self.dry=engine,run_id,batch_name,dry

    @contextmanager
    def locked(self):
        if self.engine.dialect.name!='mysql' or self.engine.url.database!='alpha_trade':
            raise ValueError('Yahoo option references require alpha_trade MySQL')
        with self.engine.connect() as conn:
            name='alpha_trade:options:yahoo_reference'
            if conn.execute(text('SELECT GET_LOCK(:name,60)'),dict(name=name)).scalar()!=1:
                raise RuntimeError('Yahoo reference lock unavailable')
            try:
                yield conn
                conn.commit()  # Receipt must be visible before another runner acquires the lock.
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute(text('SELECT RELEASE_LOCK(:name)'),dict(name=name))
                conn.commit()

    def cached(self,conn,symbol,day):
        key=f'{PROTOCOL}:{symbol}:{day}'
        now=datetime.now(UTC)
        row=conn.execute(text('SELECT payload_json,payload_hash,observed_at FROM pit_raw_payloads '
            'WHERE provider=:provider AND endpoint=:endpoint AND entity_key=:entity '
            'AND available_at>=:earliest AND available_at<=:now '
            'ORDER BY observed_at DESC,id DESC LIMIT 1'),dict(provider=PROVIDER,endpoint=ENDPOINT,entity=key,
                earliest=(now-timedelta(hours=24)).replace(tzinfo=None),now=now.replace(tzinfo=None))).mappings().first()
        if not row:return None
        from service.forward_pit.batch import _hash
        payload=json.loads(row['payload_json'])
        if _hash(payload)!=row['payload_hash']:raise ValueError('Yahoo cached receipt hash mismatch')
        observed=row['observed_at'].replace(tzinfo=UTC)
        if payload.get('protocol')!=PROTOCOL or payload.get('symbol')!=symbol or payload.get('session_date')!=str(day):
            raise ValueError('Yahoo cached receipt scope mismatch')
        # Do not freeze an empty response permanently; published valid J closes
        # are reusable for 24h. All dates remain exact, never previous-session.
        ttl=86400 if payload.get('reference') else 1800
        if not 0<=(now-observed).total_seconds()<=ttl:return None
        return payload

    def last_received(self,conn):
        value=conn.execute(text('SELECT MAX(observed_at) FROM pit_raw_payloads WHERE provider=:provider '
            'AND endpoint=:endpoint AND entity_key LIKE :prefix AND available_at>=:earliest'),
            dict(provider=PROVIDER,endpoint=ENDPOINT,prefix=PROTOCOL+':%',
                earliest=(datetime.now(UTC)-timedelta(minutes=1)).replace(tzinfo=None))).scalar()
        return value.replace(tzinfo=UTC).timestamp() if value is not None else None

    def save(self,conn,envelope,http_status,received):
        if self.dry:return
        from service.forward_pit.batch import _raw
        key=f'{PROTOCOL}:{envelope["symbol"]}:{envelope["session_date"]}'
        _raw(conn,self.run_id,self.batch_name,PROVIDER,ENDPOINT,key,envelope,http_status,received.replace(tzinfo=None))


def recover_references(engine,cfg,*,prices,symbols,day,run_id,batch_name,outcome,session,dry=False,
                       store=None,now_fn=None,sleep_fn=None,uniform_fn=None,monotonic_fn=None):
    """Keep Alpaca first, attempt only missing tradable symbols, preserve receipts."""
    policy=RecoveryConfig(**(cfg.get('yahoo_reference_recovery') or {}))
    stats=dict(enabled=policy.enabled,status='DISABLED' if not policy.enabled else 'NOT_NEEDED',
        calls=0,recovered=0,cache_hits=0,not_found=0,invalid=0,technical_failures=0,
        eligible_symbols=0,remaining=0,elapsed_seconds=0.,http_seconds=0.,pause_seconds=0.,
        stop_http_status=None,stop_reason=None,recovered_symbols=[],remaining_symbols=[],
        reference_provider=PROVIDER,reference_usage='OPTION_DISCOVERY_ONLY',reference_session_date=str(day))
    references={}
    outcome.details['yahoo_reference_recovery']=stats
    output=dict(prices)
    missing=sorted(set(symbols)-set(prices))
    if not policy.enabled or not missing:return output
    path=Path(policy.symbols_file)
    if not path.is_absolute():path=ROOT/path
    tradable={s.upper() for s in re.split(r'[,;\s]+',path.read_text(encoding='utf-8-sig')) if s}
    eligible=sorted(set(missing)&tradable)
    stats.update(eligible_symbols=len(eligible),remaining=len(eligible),remaining_symbols=eligible.copy())
    if not eligible:return output
    now_fn=now_fn or (lambda:datetime.now(UTC));sleep_fn=sleep_fn or time.sleep
    uniform_fn=uniform_fn or random.uniform;monotonic_fn=monotonic_fn or time.monotonic
    now=now_fn()
    from common.market_calendar import get_market_calendar
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    if day not in cal.session_dates(day,day) or now<cal.session_bounds(day)[1]:
        stats['status']='WAITING_FOR_SESSION_CLOSE'
        outcome.warnings.append('⚠️ Yahoo références : séance non clôturée, aucun prix partiel utilisé')
        return output
    store=store or SqlReceipts(engine,run_id,batch_name,dry=dry)
    started=monotonic_fn();stats['status']='RUNNING'
    last_received=None
    start=datetime.combine(day,datetime.min.time(),ZoneInfo('America/New_York'))
    end=datetime.combine(now.astimezone(ZoneInfo('America/New_York')).date()+timedelta(days=1),
                         datetime.min.time(),ZoneInfo('America/New_York'))
    params=dict(period1=int(start.timestamp()),period2=int(end.timestamp()),interval='1d',events='div,splits')
    fresh_symbol=None
    try:
        for symbol in eligible:
            with store.locked() as conn:
                cached=store.cached(conn,symbol,day)
                if cached and cached.get('http_status') in (401,403,429):
                    stats.update(status='STOPPED_RATE_LIMIT' if cached['http_status']==429 else 'STOPPED_ACCESS_DENIED',
                        stop_http_status=cached['http_status'],stop_reason='Cached recent provider refusal')
                    break
                if cached is not None:
                    ref=cached.get('reference')
                    if ref:
                        # Revalidate original payload rather than trust normalized cache fields.
                        ref=normalize_daily_reference(cached['response'],symbol,day,datetime.fromisoformat(cached['received_at']))
                        if ref:
                            stats['cache_hits']+=1;output[symbol]=ref['price'];references[symbol]=ref
                    else:stats['not_found']+=1
                    continue
                previous=store.last_received(conn)
                previous=max(v for v in (previous,last_received) if v is not None) if previous is not None or last_received is not None else None
                if previous is not None:
                    gap=uniform_fn(policy.pause_min_seconds,policy.pause_max_seconds)
                    wait=max(0.,gap-(now_fn().timestamp()-previous))
                    if wait:sleep_fn(wait);stats['pause_seconds']+=wait
                stats['calls']+=1
                request_start=monotonic_fn()
                ref=None;payload={};status=None;error=None
                try:
                    response=session.get('https://query1.finance.yahoo.com'+ENDPOINT+'/'+quote(symbol.replace('.','-'),safe=''),
                        params=params,headers={'User-Agent':'AlphaTrade-OptionReference/1.0','Accept':'application/json'},
                        timeout=policy.timeout_seconds)
                    status=response.status_code
                    try:payload=response.json()
                    except ValueError:payload={'invalid_json':response.text[:500]}
                except Exception as exc:
                    error=type(exc).__name__;stats['technical_failures']+=1
                received=now_fn();last_received=received.timestamp()
                stats['http_seconds']+=monotonic_fn()-request_start
                if status==200:
                    try:ref=normalize_daily_reference(payload,symbol,day,received)
                    except (ValueError,TypeError,KeyError,OverflowError) as exc:
                        error=str(exc);stats['invalid']+=1
                    if not ref and not error:stats['not_found']+=1
                elif status==404:stats['not_found']+=1
                elif status not in (None,401,403,429):stats['technical_failures']+=1
                envelope=dict(protocol=PROTOCOL,symbol=symbol,session_date=str(day),request=params,
                    received_at=received.isoformat(),http_status=status,response=payload,reference=ref,error=error)
                fresh_symbol=symbol
                store.save(conn,envelope,status or 0,received)
                if status in (401,403,429):
                    stats.update(status='STOPPED_RATE_LIMIT' if status==429 else 'STOPPED_ACCESS_DENIED',
                        stop_http_status=status,stop_reason=f'HTTP {status}')
                    break
                if ref:output[symbol]=ref['price'];references[symbol]=ref
                if stats['technical_failures']>=3:
                    stats.update(status='STOPPED_TECHNICAL_ERRORS',stop_reason='Three technical failures')
                    break
            fresh_symbol=None
            LOGGER.info('Yahoo option references batch=%s calls=%d recovered=%d cache=%d',
                batch_name,stats['calls'],len(references),stats['cache_hits'])
        if stats['status']=='RUNNING':stats['status']='COMPLETED'
    except Exception as exc:
        if fresh_symbol is not None:
            output.pop(fresh_symbol,None)
            references.pop(fresh_symbol,None)
        stats.update(status='STOPPED_RECEIPT_ERROR',stop_reason=type(exc).__name__+': '+str(exc)[:200])
    finally:
        stats.update(elapsed_seconds=round(monotonic_fn()-started,3),http_seconds=round(stats['http_seconds'],3),
            pause_seconds=round(stats['pause_seconds'],3),recovered=len(references),
            recovered_symbols=sorted(references),remaining_symbols=sorted(set(eligible)-set(output)))
        stats['remaining']=len(stats['remaining_symbols'])
    if stats['status'].startswith('STOPPED'):
        icon='🚦' if stats['stop_http_status']==429 else '⛔' if stats['stop_http_status'] in (401,403) else '⚠️'
        outcome.warnings.append(f'{icon} Yahoo rattrapage arrêté : {stats["stop_reason"]} ; '
            f'{stats["calls"]} appels en {stats["elapsed_seconds"]:.1f}s ; {stats["remaining"]} titres sans référence')
    elif stats['technical_failures'] or stats['invalid']:
        outcome.warnings.append(f'⚠️ Yahoo références : {stats["technical_failures"]} erreurs techniques, '
                                f'{stats["invalid"]} réponses non qualifiées')
    LOGGER.info('Yahoo references final batch=%s status=%s calls=%d elapsed=%.1fs recovered=%d remaining=%d',
        batch_name,stats['status'],stats['calls'],stats['elapsed_seconds'],stats['recovered'],stats['remaining'])
    return output
