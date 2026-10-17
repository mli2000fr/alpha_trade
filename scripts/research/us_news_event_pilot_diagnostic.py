"""One safe EODHD news request diagnostic; no credentials/URLs in output, no SQL."""
from datetime import datetime, timedelta, timezone
import json

import requests

from service._http_retry import request_with_retry, RetryPolicy
from service.eodhd.accounts import EodhdAccountRegistry


def run(adapter=None):
    registry = EodhdAccountRegistry.get()
    now = datetime.now(timezone.utc)
    params = dict(api_token=registry.get_token(), s='IRTC.US',
        **{'from':(now-timedelta(days=1)).date().isoformat(), 'to':now.date().isoformat()},
        limit=1, fmt='json')
    with requests.Session() as session:
        if adapter is not None:
            session.mount('https://eodhd.com/',adapter)
        try:
            response = request_with_retry(session,'GET','https://eodhd.com/api/news',params=params,
                policy=RetryPolicy(max_attempts=1,timeout_seconds=10))
            return dict(status=response.status_code, json_type=type(response.json()).__name__,
                max_attempts=1, sql_writes=False)
        except Exception as exc:
            chain, seen, current = [], set(), exc
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                chain.append(dict(type=type(current).__name__, errno=getattr(current,'errno',None),
                    winerror=getattr(current,'winerror',None)))
                current=current.__cause__ or current.__context__
            return dict(error_chain_types=chain,
                http_status=getattr(getattr(exc,'response',None),'status_code',None),
                is_ssl_error=isinstance(exc,requests.exceptions.SSLError),
                is_proxy_error=isinstance(exc,requests.exceptions.ProxyError),
                max_attempts=1, sql_writes=False)


if __name__=='__main__':
    print(json.dumps(run()))
