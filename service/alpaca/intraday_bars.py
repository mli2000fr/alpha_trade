"""Paginated raw historical Alpaca bars with an explicit, never-fallback feed."""
from datetime import datetime, timezone
import time
import requests
from service._http_retry import RetryPolicy, request_with_retry
from service.alpaca.clientAlpaca import _build_headers
from common.verified_http import verified_session


class AlpacaIntradayBlocked(RuntimeError):
    """Authentication, entitlement or exhausted rate limit: stop the backfill."""


def fetch_intraday(symbol, *, start_epoch, end_epoch, interval='5m', feed='iex',
                   account_id='default', session=None, sleep_seconds=1.):
    timeframes={'1m':'1Min','5m':'5Min','1h':'1Hour'}
    if interval not in timeframes or feed not in ('iex','sip') or end_epoch<=start_epoch:
        raise ValueError('Invalid Alpaca intraday interval/feed/range')
    if not account_id or sleep_seconds<.2:
        raise ValueError('Invalid Alpaca account/pause')
    params=dict(symbols=symbol,timeframe=timeframes[interval],feed=feed,adjustment='raw',
        asof='-',sort='asc',limit=10000,
        start=datetime.fromtimestamp(start_epoch,timezone.utc).isoformat(),
        end=datetime.fromtimestamp(end_epoch,timezone.utc).isoformat())
    try:
        headers=_build_headers(account_id)
    except (ValueError,RuntimeError,KeyError) as exc:
        raise AlpacaIntradayBlocked('Credentials Alpaca indisponibles pour le compte demandé') from exc
    owned=session is None
    http=session or verified_session()
    rows=[];seen=set()
    try:
        while True:
            try:
                response=request_with_retry(http,'GET','https://data.alpaca.markets/v2/stocks/bars',
                    headers=headers,params=params,
                    policy=RetryPolicy(max_attempts=4,timeout_seconds=30,base_delay_seconds=2))
            except requests.HTTPError as exc:
                code=exc.response.status_code if exc.response is not None else None
                if code in (401,403,429):
                    raise AlpacaIntradayBlocked(f'Alpaca HTTP {code} : compte/droits/quota ; flux {feed} inchangé') from exc
                raise
            if response.status_code in (401,403,429):
                raise AlpacaIntradayBlocked(f'Alpaca HTTP {response.status_code} : compte/droits/quota ; flux {feed} inchangé')
            response.raise_for_status()
            payload=response.json()
            if not isinstance(payload,dict) or not isinstance(payload.get('bars'),dict):
                raise RuntimeError('Réponse Alpaca bars invalide')
            if set(payload['bars'])-{symbol}:
                raise RuntimeError('Symbole inattendu dans la réponse Alpaca')
            bars=payload['bars'].get(symbol,[])
            if not isinstance(bars,list):raise RuntimeError('Liste de barres Alpaca invalide')
            for item in bars:
                stamp=datetime.fromisoformat(item['t'].replace('Z','+00:00'))
                if stamp.tzinfo is None:raise ValueError('Timestamp Alpaca sans timezone')
                # Original fields, including n/vw, remain available in the raw archive.
                rows.append(dict(item,timestamp=stamp.timestamp(),open=item.get('o'),
                    high=item.get('h'),low=item.get('l'),close=item.get('c'),volume=item.get('v')))
            token=payload.get('next_page_token')
            if not token:return rows
            if not isinstance(token,str) or token in seen:
                raise RuntimeError('Pagination Alpaca cyclique/invalide')
            seen.add(token);params['page_token']=token
            time.sleep(sleep_seconds)
    finally:
        if owned:http.close()
