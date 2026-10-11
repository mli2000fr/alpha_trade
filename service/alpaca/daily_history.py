"""Explicit-feed, split-only daily history; never falls back or remaps tickers."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import time
import requests
from common.verified_http import verified_session
from service._http_retry import request_with_retry,RetryPolicy
from service.alpaca.clientAlpaca import _build_headers


class DailyHistoryBlocked(RuntimeError):
    pass


def fetch_daily_history(symbol,*,start,end,feed='sip',account_id='default',session=None,now=None):
    if feed not in ('sip','iex'):raise ValueError('Invalid daily Alpaca feed')
    now=now or datetime.now(timezone.utc)
    boundary=datetime.fromisoformat(end).replace(tzinfo=ZoneInfo('America/New_York'))+timedelta(days=1)
    cutoff=min(boundary.astimezone(timezone.utc),now-timedelta(minutes=20))
    beginning=datetime.fromisoformat(start).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
    if cutoff<=beginning:raise ValueError('Daily history range is empty or too recent')
    params=dict(symbols=symbol,timeframe='1Day',feed=feed,adjustment='split',asof='-',
        start=beginning.isoformat(),end=cutoff.isoformat(),limit=10000,sort='asc')
    owned=session is None;http=session or verified_session();rows=[];seen=set()
    try:
        while True:
            try:
                response=request_with_retry(http,'GET','https://data.alpaca.markets/v2/stocks/bars',
                    params=params,headers=_build_headers(account_id),policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
            except requests.HTTPError as exc:
                status=getattr(exc.response,'status_code',None)
                if status in (401,403,429):raise DailyHistoryBlocked(f'Alpaca HTTP {status}; no feed fallback') from exc
                raise
            payload=response.json()
            if not isinstance(payload,dict) or not isinstance(payload.get('bars'),dict):raise ValueError('Invalid daily history payload')
            if set(payload['bars'])-{symbol}:raise ValueError('Unexpected daily history symbol')
            rows.extend(payload['bars'].get(symbol,[]))
            token=payload.get('next_page_token')
            if not token:return rows
            if token in seen:raise ValueError('Repeated daily pagination token')
            seen.add(token);params['page_token']=token;time.sleep(.4)
    finally:
        if owned:http.close()
