"""Run-local repair overlay and per-entry POST-HOC coverage gate.

Canonical SQL remains read-only. Native responses and their real retrieval time
are cached, never relabelled as SIP or historically available observations.
"""
from datetime import UTC, datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import random
import time
from urllib.parse import quote

import pandas as pd

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import regular_bounds

LOG = logging.getLogger(__name__)
FIELDS = ('open', 'high', 'low', 'close', 'volume')
PROVIDERS = ('alpaca_sip', 'yahoo', 'eodhd')
CACHE_VERSION = 1


def qualified_frame(frame, symbol, day):
    """Discard invalid candles, never interpolate; conflicting duplicates reject."""
    if frame.empty:
        return pd.DataFrame(columns=['symbol', 'timestamp', *FIELDS])
    frame = frame.copy()
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True, errors='coerce')
    for field in FIELDS:
        frame[field] = pd.to_numeric(frame[field], errors='coerce')
    opening, closing = regular_bounds(day)
    valid = (frame.symbol.eq(symbol) & frame.timestamp.ge(opening) & frame.timestamp.lt(closing)
        & (frame.timestamp-pd.Timestamp(opening)).dt.total_seconds().mod(300).eq(0)
        & frame[list(FIELDS)].gt(0).all(axis=1)
        & frame[list(FIELDS)].lt(float('inf')).all(axis=1)
        & frame.high.ge(frame[['open', 'close']].max(axis=1))
        & frame.low.le(frame[['open', 'close']].min(axis=1)))
    if 'bar_end_timestamp' in frame:
        valid &= (pd.to_datetime(frame.bar_end_timestamp, utc=True, errors='coerce')-frame.timestamp).eq(pd.Timedelta(minutes=5))
    if 'payload_hash' in frame:
        valid &= frame.payload_hash.notna() & frame.payload_hash.ne('')
    frame = frame.loc[valid]
    if frame.duplicated('timestamp').any():
        raise ValueError('Conflicting/duplicate recovery candles')
    return frame.sort_values('timestamp').reset_index(drop=True)


def complete(frame, day):
    opening, closing = regular_bounds(day)
    expected = pd.date_range(opening, closing, freq='5min', inclusive='left')
    return len(frame) == len(expected) and set(frame.timestamp) == set(expected)


def provider_payload(provider, symbol, day):
    """Explicit providers, no subscription upgrade, IEX or daily substitution."""
    opening, closing = regular_bounds(day)
    kwargs = dict(start_epoch=int(opening.timestamp()), end_epoch=int(closing.timestamp()), interval='5m')
    if provider == 'alpaca_sip':
        from service.alpaca.intraday_bars import fetch_intraday
        time.sleep(1.)
        return fetch_intraday(symbol, feed='sip', account_id='default', **kwargs)
    if provider == 'eodhd':
        from service.eodhd.clientEodhd import fetch_intraday
        from common.verified_http import verified_session
        with verified_session() as http:
            return fetch_intraday(symbol, session=http, **kwargs)
    if provider != 'yahoo':
        raise ValueError('Unknown repair provider')
    # Yahoo 5m is a rolling short history. Still try the requested date: an
    # explicit range error is recorded, not replaced with recent/daily data.
    from common.verified_http import verified_session
    from service._http_retry import request_with_retry, RetryPolicy
    time.sleep(random.uniform(1., 5.))
    with verified_session() as http:
        response = request_with_retry(http, 'GET',
            'https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol.replace('.', '-'), safe=''),
            params=dict(period1=kwargs['start_epoch'], period2=kwargs['end_epoch'], interval='5m',
                        includePrePost='false', events='splits'),
            headers={'User-Agent':'AlphaTrade-IntradayRepair/1.0', 'Accept':'application/json'},
            policy=RetryPolicy(max_attempts=2, timeout_seconds=20))
        response.raise_for_status()
        return response.json()


def rows_from_payload(provider, payload, symbol):
    if provider == 'yahoo':
        if not isinstance(payload,dict) or not isinstance(payload.get('chart'),dict):
            raise ValueError('Yahoo chart missing')
        chart = payload['chart']
        if chart.get('error'):
            raise ValueError('Yahoo chart range/data unavailable')
        result, = chart.get('result') or []
        meta = result.get('meta') or {}
        if meta.get('symbol') != symbol.replace('.', '-') or meta.get('currency') != 'USD' or meta.get('dataGranularity') != '5m':
            raise ValueError('Yahoo symbol/currency/interval unqualified')
        quote_data, = result['indicators']['quote']
        timestamps = result.get('timestamp') or []
        if any(len(quote_data.get(k, [])) != len(timestamps) for k in FIELDS):
            raise ValueError('Yahoo inconsistent arrays')
        payload = [dict(timestamp=stamp, **{k:quote_data[k][i] for k in FIELDS}) for i, stamp in enumerate(timestamps)]
    if not isinstance(payload, list):
        raise ValueError('Provider candles must be a list')
    rows = [dict(symbol=symbol, timestamp=pd.to_datetime(r['timestamp'], unit='s', utc=True),
                 **{k:r.get(k) for k in FIELDS}, data_source=provider) for r in payload]
    return pd.DataFrame(rows, columns=['symbol', 'timestamp', *FIELDS, 'data_source'])


class RecoveringIntradaySource:
    """Complete SQL SIP first; overlay only missing timestamps in provider order."""
    def __init__(self, base, end, policy, *, cache_dir=None,
                 fetcher=None, now=None, progress=None,daily_entry=False):
        self.base, self.end, self.policy = base, end, policy
        self.daily_entry=daily_entry
        if cache_dir is None:
            from backtesting.isolation import active,local_path
            cache_dir=local_path('intraday-recovery-cache') if active() else Path('artifacts/winner_intraday_recovery')
        self.cache_dir, self.fetcher = Path(cache_dir), fetcher or provider_payload
        self.now = now or (lambda:datetime.now(UTC))
        self.progress = progress
        self.overlay, self.attempts, self.remaining, self.exclusions = {}, [], {}, {}
        self.stopped = {}
        self.yahoo_floor = None
        self._entry_cache = {}
        self._session_days = []
        self._remaining_dates = None
        self.calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)

    @property
    def receipts(self):
        return self.base.receipts

    def fetch(self, provider, symbol, day):
        if provider=='yahoo' and self.yahoo_floor is not None and day < self.yahoo_floor:
            self.attempts.append(dict(provider=provider,symbol=symbol,date=str(day),status='OUTSIDE_PROVIDER_HISTORY',
                                      reason='Yahoo 5m rolling history limit observed in provider response',cache_hit=False))
            return pd.DataFrame()
        key = hashlib.sha256(f'{CACHE_VERSION}/{provider}/{symbol}/{day}/5m'.encode()).hexdigest()
        path = self.cache_dir/(key+'.json')
        cached = False
        envelope = None
        if path.exists():
            wrapper = json.loads(path.read_text(encoding='utf-8'))
            envelope = wrapper['envelope']
            raw = json.dumps(envelope, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if hashlib.sha256(raw.encode()).hexdigest() != wrapper['sha256']:
                raise ValueError('Corrupt repair cache')
            if (envelope['provider'], envelope['symbol'], envelope['date']) != (provider, symbol, str(day)):
                raise ValueError('Repair cache identity mismatch')
            # Errors and empty responses are retried in a later run after 24h.
            if timedelta(0)<=self.now()-datetime.fromisoformat(envelope['observed_at']) < timedelta(hours=24):
                cached = True
            else:
                envelope = None
        if envelope is None:
            if provider in self.stopped:
                self.attempts.append(dict(provider=provider, symbol=symbol, date=str(day), status='PROVIDER_STOPPED',
                                          reason=self.stopped[provider], cache_hit=False))
                return pd.DataFrame()
            try:
                payload = self.fetcher(provider, symbol, day)
                envelope = dict(provider=provider, symbol=symbol, date=str(day), observed_at=self.now().isoformat(),
                                status='RECEIVED', payload=payload)
            except Exception as exc:
                response = getattr(exc, 'response', None)
                status = getattr(response, 'status_code', None)
                # Store no URL/token-bearing exception text. The type/status suffice.
                reason = type(exc).__name__+(f' HTTP {status}' if status else '')
                envelope = dict(provider=provider, symbol=symbol, date=str(day), observed_at=self.now().isoformat(),
                                status='ERROR', error=reason, http_status=status)
                if provider=='yahoo' and response is not None:
                    try:
                        from service._http_retry import _redact_sensitive_text
                        detail=(response.json().get('chart',{}).get('error') or {}).get('description','')
                        envelope['error_detail']=_redact_sensitive_text(str(detail))[:500]
                    except (ValueError,TypeError,AttributeError):
                        pass
                if status in (401, 403, 429) or type(exc).__name__ in (
                        'AlpacaIntradayBlocked', 'EodhdPermissionError', 'EodhdQuotaExceeded', 'EodhdCircuitOpen',
                        'EodhdTemporarilyUnavailable', 'CircuitOpenError'):
                    self.stopped[provider] = reason
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            from backtesting.winner_campaign_replay import atomic_json
            raw = json.dumps(envelope, sort_keys=True, separators=(',', ':'), allow_nan=False)
            atomic_json(path, dict(envelope=envelope, sha256=hashlib.sha256(raw.encode()).hexdigest()))
        attempt = dict(provider=provider, symbol=symbol, date=str(day), observed_at=envelope['observed_at'],
                       status=envelope['status'], cache_hit=cached, cache_path=str(path))
        raw=json.dumps(envelope,sort_keys=True,separators=(',', ':'),allow_nan=False)
        content_hash=hashlib.sha256(raw.encode()).hexdigest()
        immutable=self.cache_dir/'objects'/(content_hash+'.json')
        immutable.parent.mkdir(parents=True,exist_ok=True)
        if not immutable.exists():
            from backtesting.winner_campaign_replay import atomic_json
            atomic_json(immutable,dict(envelope=envelope,sha256=content_hash))
        attempt.update(cache_path=str(immutable),sha256=content_hash)
        self.attempts.append(attempt)
        if provider=='yahoo' and '60 days' in envelope.get('error_detail','').lower():
            self.yahoo_floor=self.now().date()-timedelta(days=60)
        if envelope['status'] != 'RECEIVED':
            attempt['reason'] = envelope['error']
            LOG.warning('Rattrapage %s %s %s : %s ; essai du fournisseur suivant',provider,symbol,day,envelope['error'])
            if envelope.get('http_status') in (401, 403, 429) or envelope['error'].split()[0] in (
                    'AlpacaIntradayBlocked','EodhdPermissionError','EodhdQuotaExceeded','EodhdCircuitOpen',
                    'EodhdTemporarilyUnavailable','CircuitOpenError'):
                self.stopped[provider] = envelope['error']
            return pd.DataFrame()
        try:
            if provider=='yahoo' and isinstance(envelope['payload'],dict):
                description=str((envelope['payload'].get('chart',{}).get('error') or {}).get('description',''))
                if '60 days' in description.lower():
                    self.yahoo_floor=self.now().date()-timedelta(days=60)
            frame = qualified_frame(rows_from_payload(provider, envelope['payload'], symbol), symbol, day)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            attempt.update(status='INVALID', reason=type(exc).__name__)
            LOG.warning('Rattrapage %s %s %s : réponse non qualifiée (%s)',provider,symbol,day,type(exc).__name__)
            return pd.DataFrame()
        attempt['qualified_bars'] = len(frame)
        return frame

    def prepare(self, audit):
        original = audit['gaps']
        for i, gap in enumerate(original):
            symbol, day = gap['symbol'], pd.Timestamp(gap['date']).date()
            original_sip = qualified_frame(self.base(day, [symbol]), symbol, day)
            combined = original_sip.copy()
            if 'data_source' not in combined:
                combined['data_source'] = 'alpaca_sip'
            added = False
            for provider in PROVIDERS:
                if complete(combined, day):
                    break
                candidate = self.fetch(provider, symbol, day)
                if candidate.empty:
                    continue
                if provider != 'alpaca_sip':
                    # Yahoo prices can be split adjusted. Never mix incompatible
                    # bases or trust a provider with no same-day raw SIP anchors.
                    anchor = combined.loc[combined.data_source.eq('alpaca_sip')]
                    overlap = anchor.merge(candidate, on='timestamp', suffixes=('_sip', '_fallback'))
                    price_fields = FIELDS[:4]
                    if len(overlap) < 3 or any(
                        ((overlap[k+'_fallback']/overlap[k+'_sip']-1).abs() > .01).any() for k in price_fields):
                        self.attempts[-1].update(status='INCOMPATIBLE_PRICE_BASIS',
                                                reason='Need >=3 same-day SIP anchors; all OHLC within 1%')
                        continue
                new = candidate.loc[~candidate.timestamp.isin(combined.timestamp)]
                if not new.empty:
                    combined = pd.concat([combined, new], ignore_index=True).sort_values('timestamp')
                    added = True
                    self.attempts[-1]['used_bars'] = len(new)
            if added:
                self.overlay[symbol, day] = combined
            if not complete(combined, day):
                self.remaining[symbol, day] = dict(gap, qualified_bars=len(combined),
                    missing_bars=max(0, gap['expected_bars']-len(combined)))
            LOG.info('Rattrapage intraday %d/%d : %s %s, %d/%d bougies',
                     i+1, len(original), symbol, day, len(combined), gap['expected_bars'])
            if self.progress:
                self.progress(i+1, len(original))
        audit.update(original_missing_sessions=len(original), missing_sessions=len(self.remaining),
            gaps=list(self.remaining.values()), affected_symbols=sorted({s for s, _ in self.remaining}),
            excluded_symbols=[], repaired_sessions=len(original)-len(self.remaining), removed_signals=0,
            exclusion_policy='PER_ENTRY_DAY_HOLDING_WINDOW_NO_ORACLE_REFILL',
            recovery=dict(providers=list(PROVIDERS), attempts=len(self.attempts),
                stopped_providers=dict(self.stopped), sql_modified=False,
                fallback_basis='>=3 same-day SIP anchors; each OHLC within 1%; missing timestamps only'))
        return audit

    def __call__(self, day, symbols):
        frame = self.base(day, symbols)
        chunks = []
        for symbol in symbols:
            if (symbol, day) in self.overlay:
                chunks.append(self.overlay[symbol, day])
            else:
                part = frame.loc[frame.symbol.eq(symbol)] if not frame.empty else pd.DataFrame()
                chunks.append(qualified_frame(part, symbol, day))
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    def entry_allowed(self, symbol, day):
        if self.daily_entry:return True  # Daily protection fallback, never a future coverage entry filter.
        if self._remaining_dates is None:
            self._remaining_dates={}
            for s,d in self.remaining:
                self._remaining_dates.setdefault(s,set()).add(d)
        if symbol not in self._remaining_dates:
            return True
        key = (symbol, day)
        if key not in self._entry_cache:
            # Include the exit session: a horizon-open sale needs an actual bar.
            if not self._session_days or day<self._session_days[0]:
                self._session_days=self.calendar.session_dates(day-timedelta(days=14),self.end)
            index=self._session_days.index(day)
            days=self._session_days[index:]
            days = days[:self.policy.horizon_sessions+1] if self.policy.horizon_sessions is not None else days
            prior = self._session_days[index-1]
            bad = [d.isoformat() for d in (days if self.daily_entry else [prior,*days]) if d in self._remaining_dates[symbol]]
            self._entry_cache[key] = bad
            if bad:
                self.exclusions[key] = dict(symbol=symbol, entry_date=day.isoformat(),
                    missing_dates=', '.join(bad), reason='UNRESOLVED_INTRADAY_IN_ENTRY_HOLDING_WINDOW')
                LOG.warning('Entrée exclue : %s | %s | séances manquantes : %s', symbol, day, ', '.join(bad))
        return not self._entry_cache[key]

    def export(self, output):
        from backtesting.winner_campaign_replay import atomic_json
        atomic_json(Path(output)/'intraday-recovery.json', dict(attempts=self.attempts,
            residual_gaps=list(self.remaining.values()), stopped_providers=self.stopped))
        columns = ['symbol', 'entry_date', 'missing_dates', 'reason']
        table = pd.DataFrame(list(self.exclusions.values()), columns=columns).sort_values(['entry_date', 'symbol'])
        table.to_csv(Path(output)/'entry-exclusions.csv', index=False)
        LOG.warning('Tableau des entrées exclues pour données intraday (%d couples titre/date) :\n%s',
                    len(table), table.to_string(index=False) if len(table) else 'Aucune')
