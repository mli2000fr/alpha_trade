"""Read-only production consolidated quotes. Sandbox cannot qualify live entries."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
import os
import re

from common.verified_http import verified_session
from service._http_retry import RetryPolicy, request_with_retry

LOGGER = logging.getLogger(__name__)
ENDPOINT = 'https://api.tradier.com/v1/markets/quotes'


def _stamp(value):
    if isinstance(value, bool):
        raise ValueError('Invalid bid/ask timestamp')
    milliseconds = float(value)
    if not math.isfinite(milliseconds) or milliseconds <= 0:
        raise ValueError('Missing bid/ask timestamp')
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc)


def _normalize(row):
    # Never substitute last trade time or collection time for bid/ask times.
    if row.get('type') not in ('stock', 'etf'):
        raise ValueError('Not a US equity quote')
    if row.get('currency', 'USD') != 'USD':
        raise ValueError('Non-USD quote')
    bid_time, ask_time = _stamp(row.get('bid_date')), _stamp(row.get('ask_date'))
    bid, ask, bs, ass = [float(row[k]) for k in ('bid', 'ask', 'bidsize', 'asksize')]
    if (not all(math.isfinite(v) and v > 0 for v in (bid, ask, bs, ass)) or ask <= bid):
        raise ValueError('Missing, crossed, locked or invalid bid/ask/size')
    if row.get('realtime') is False or row.get('delayed') is True:
        raise ValueError('Delayed quote')
    return dict(bp=bid, ap=ask, bs=bs, **{'as': ass},
                t=min(bid_time, ask_time).isoformat(),
                bid_time=bid_time.isoformat(), ask_time=ask_time.isoformat(),
                provider='tradier', feed='consolidated', is_realtime=True,
                source='tradier_consolidated', raw_quote=dict(row))


def _quota_violation(response):
    return response.status_code == 400 and 'quota violation' in response.text[:4096].lower()


def fetch_latest_quotes(symbols, session=None, account_id=None, *, settings=None):
    """GET quotes with a production token independent of the Alpaca account/mode."""
    if settings is None:
        from common.config_loader import load_config
        settings = ((load_config().get('market_data') or {}).get('tradier') or {})
    if not isinstance(settings, dict) or settings.get('environment', 'production') != 'production':
        raise ValueError('Tradier quotes live : environment=production requis ; sandbox différé interdit')
    env_name = settings.get('token_env', 'TRADIER_API_TOKEN')
    if not isinstance(env_name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env_name):
        raise ValueError('Tradier token_env invalide')
    normalized = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not normalized:
        return {}
    token = os.getenv(env_name, '').strip()
    if not token or any(c.isspace() for c in token):
        raise RuntimeError(f'Jeton Tradier de production absent/invalide : variable {env_name}')
    batch_size = settings.get('batch_size', 100)
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise ValueError('Tradier batch_size doit être entier entre 1 et 100')
    # Share classes use slash at Tradier; never alter the internal symbol.
    wire_map = {}
    for symbol in normalized:
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9./^-]{0,31}', symbol):
            raise ValueError('Symbole Tradier invalide')
        wire = symbol.replace('.', '/')
        if wire in wire_map:
            raise ValueError('Alias de symbole Tradier ambigu')
        wire_map[wire] = symbol
    owned = session is None
    client = session if session is not None else verified_session()
    policy = RetryPolicy(max_attempts=3, timeout_seconds=10, base_delay_seconds=1, max_delay_seconds=30)
    result = {}
    try:
        wires = list(wire_map)
        for offset in range(0, len(wires), batch_size):
            batch = wires[offset:offset + batch_size]
            response = request_with_retry(
                client, 'GET', ENDPOINT, policy=policy, retry_response=_quota_violation,
                headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
                params={'symbols': ','.join(batch), 'greeks': 'false'},
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise RuntimeError(f'Tradier quotes : statut HTTP inattendu {response.status_code}')
            payload = response.json()
            if not isinstance(payload, dict) or payload.get('errors') or not isinstance(payload.get('quotes'), dict):
                raise RuntimeError('Réponse Tradier quotes invalide')
            rows = payload['quotes'].get('quote')
            if isinstance(rows, dict):
                rows = [rows]
            if rows is None:
                rows = []
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise RuntimeError('Liste de quotes Tradier invalide')
            seen = set()
            for row in rows:
                wire = str(row.get('symbol') or '').strip().upper()
                if wire not in batch or wire in seen:
                    raise RuntimeError('Identité de quote Tradier inattendue/dupliquée')
                seen.add(wire)
                symbol = wire_map[wire]
                try:
                    result[symbol] = _normalize(row)
                except (ValueError, TypeError, KeyError, OverflowError, OSError):
                    LOGGER.warning('Tradier quote non qualifiée pour %s : bid/ask, type, tailles ou dates invalides', symbol)
        return result
    finally:
        if owned:
            client.close()
