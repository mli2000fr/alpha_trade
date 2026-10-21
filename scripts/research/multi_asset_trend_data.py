"""Scoped immutable ETF source acquisition for a separately frozen research pilot."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_consensus_revenue_h10_evaluation import READ

CONFIG = Path('config/research/multi_asset_trend_pilot_20261020.json')
BASE = 'https://data.alpaca.markets'
PATHS = {'/v2/stocks/bars', '/v1/corporate-actions'}


def prepare(root):
    if (root / 'protocol.json').exists():
        p = READ(root / 'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists(): raise ValueError('Fresh directory required')
    cfg = READ(CONFIG)
    if cfg['symbols'] != ['SPY', 'TLT', 'GLD', 'DBC'] or cfg['feed'] != 'sip':
        raise ValueError('Frozen universe/source changed')
    root.mkdir(parents=True); (root / 'http').mkdir()
    paths = [Path(__file__), Path('tests/test_multi_asset_trend_data.py'), CONFIG]
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), config=cfg,
        sources={str(p): digest(p) for p in paths},
        acquisition='Alpaca historical SIP raw/split/all daily bars; full corporate-action types with pagination. No IEX fallback, no order endpoint.',
        limits=dict(requests=24, pages_per_kind=6, interval_seconds=.4, response_bytes=50*1024*1024),
        rules='One attempt per HTTP page; archive errors, never treat denial/partial as empty data. No paid upgrade, SQL writes or production changes.',
        primary='Predefined monthly 2-of-3 momentum signs 63/126/252 on reconstructed total-return signal; fixed25% slots, cash remainder, no fitting.',
        execution='Orders sized at prior close, next-open fills with fixed costs and pro-rata clipping if cash constrained. Dividends receivable ex-date, cash pay-date.',
        benchmarks='Same data, costs, initial4000USD: equal-weight initial buy/hold, equal-weight monthly.',
        confirmation='2016-2026Sep descriptive by calendar year, recent2024-2026 separately; not an untouched holdout or a professional return replication.',
        training=False, llm_calls=0, sql_writes=False, orders=False)
    atomic_json(root / 'protocol.json', p); return p


def fetch_kind(root, kind, path, params, session, headers, limits, budget):
    if path not in PATHS: raise ValueError('Endpoint outside read-only data scope')
    receipts = []; seen = set()
    for page in range(limits['pages_per_kind']):
        file = root / 'http' / f'{kind}-{page}.json'
        if file.exists():
            item = READ(file)
            if item['path'] != path or item['params'] != params: raise ValueError('Resume input mismatch')
        else:
            if budget[0] >= limits['requests']: raise ValueError('Request cap reached')
            time.sleep(limits['interval_seconds']); budget[0] += 1
            response = session.get(BASE + path, params=params, headers=headers, timeout=(10, 45))
            if len(response.content) > limits['response_bytes']: raise ValueError('Response too large')
            item = dict(path=path, params=dict(params), observed_at_utc=datetime.now(timezone.utc).isoformat(),
                status_code=response.status_code, status='OK' if response.status_code == 200 else 'HTTP_ERROR',
                payload=response.json() if response.status_code == 200 else None)
            atomic_json(file, item)
        receipts.append(dict(file=str(file.relative_to(root)), sha256=digest(file)))
        if item['status'] != 'OK': raise RuntimeError(f'Alpaca read-only source HTTP {item["status_code"]} for {kind}; no fallback')
        token = item['payload'].get('next_page_token')
        print(kind, 'page', page + 1, 'more_pages', bool(token), flush=True)
        if not token: return receipts
        if token in seen: raise ValueError('Repeated page token')
        seen.add(token); params = dict(params, page_token=token)
    raise ValueError('Pagination incomplete at bounded page cap')


def fetch(root):
    p = prepare(root)
    if (root / 'download.json').exists(): raise ValueError('Acquisition completed and immutable')
    from common.verified_http import verified_session
    from service.alpaca.clientAlpaca import _build_headers
    cfg = p['config']; budget = [0]; receipts = {}
    try:
        with verified_session() as session:
            headers = _build_headers('default')
            # Corporate actions first: do not silently omit distributions if denied.
            receipts['actions'] = fetch_kind(root, 'actions', '/v1/corporate-actions',
                dict(symbols=','.join(cfg['symbols']), start=cfg['history_start'], end=cfg['actions_end'],
                     limit=1000, sort='asc', data_quality='all'), session, headers, p['limits'], budget)
            for adjustment in ('raw', 'split', 'all'):
                receipts[adjustment] = fetch_kind(root, adjustment, '/v2/stocks/bars',
                    dict(symbols=','.join(cfg['symbols']), start=cfg['history_start']+'T00:00:00Z',
                        end=cfg['end']+'T23:59:59Z', timeframe='1Day', feed='sip', adjustment=adjustment,
                        asof='-', limit=10000, sort='asc'), session, headers, p['limits'], budget)
    except Exception as exc:
        atomic_json(root / 'download-error.json', dict(status='FAILED_OR_INCOMPLETE_SOURCE',
            error_type=type(exc).__name__, error=str(exc), actual_new_http_requests=budget[0],
            no_empty_data_inference=True, sql_writes=False, orders=False))
        raise
    value = dict(status='COMPLETE_HTTP_NOT_YET_QUALIFIED', actual_new_http_requests=budget[0],
        kinds=receipts, files={r['file']:r['sha256'] for rows in receipts.values() for r in rows})
    atomic_json(root / 'download.json', value); print(value['status'], 'requests', budget[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'fetch'], required=True)
    args = parser.parse_args(); globals()[args.phase](args.output)
