"""Research-only path qualification; never updates prices, labels or models.

Uses the archived capture audit. Optional bounded EODHD re-fetch is evidence
from the SAME vendor, not independent validation. No database connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_extreme50_capture import metrics


def save(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               default=str, allow_nan=False), encoding='utf-8')


def crosses(start, end, boundary):
    """Close-to-close return includes a rupture only AFTER its start close."""
    return pd.Timestamp(start) < pd.Timestamp(boundary) <= pd.Timestamp(end)


def qualify_path(path):
    bars = path['bars']
    prices = np.array([float(b['adj_close']) for b in bars])
    changes = prices[1:] / prices[:-1] - 1
    jumps = [dict(date=bars[i+1]['date'], previous=prices[i], current=prices[i+1],
                  return_pct=float(value*100)) for i, value in enumerate(changes)
             if abs(value) >= .5]
    flags = []
    if any(float(b.get('volume') or 0) <= 0 for b in bars):
        flags.append('ZERO_VOLUME_PATH')
    if any(bool(b.get('is_filled')) for b in bars):
        flags.append('FILLED_PATH')
    if len({b['instrument_id'] for b in bars if b.get('instrument_id') is not None}) > 1:
        flags.append('LOCAL_IDENTITY_CHANGE')
    symbol = path['symbol']
    if symbol == 'INDV' and bars[0]['date'] < '2023-06-12':
        flags.append('PRE_NASDAQ_ADR_MAPPING_UNRESOLVED')
    if symbol == 'INDV' and crosses(bars[0]['date'], bars[-1]['date'], '2022-10-11'):
        flags.append('FIVEFOLD_JUMP_NEAR_OFFICIAL_CONSOLIDATION')
    if symbol == 'GRND' and crosses(bars[0]['date'], bars[-1]['date'], '2022-11-18'):
        flags.append('BUSINESS_COMBINATION_IDENTITY_BOUNDARY')
    points = []
    for b in bars:
        if symbol == 'CLDX' and b['date'] == '2020-06-10':
            points.append(dict(date=b['date'], official_close=4.8, local_close=b['close'],
                               matches=abs(float(b['close'])-4.8) < 1e-6))
    return dict(symbol=symbol, start=bars[0]['date'], end=bars[-1]['date'],
                return_pct=path['future_return_pct'], flags=flags, jumps=jumps,
                independent_price_points=points,
                economic_path_certified=False,
                status='RESERVED' if flags else 'NO_LOCAL_BLOCKER_IN_SAMPLE_NOT_CERTIFIED')


def reservations(frame):
    """Ex-post sensitivity ONLY: never reselect or replace excluded candidates."""
    starts = pd.to_datetime(frame.date)
    ends = pd.to_datetime(frame.oracle_exit_date)
    indv = frame.symbol.eq('INDV') & starts.lt(pd.Timestamp('2023-06-12'))
    grnd = (frame.symbol.eq('GRND') & starts.lt(pd.Timestamp('2022-11-18'))
            & ends.ge(pd.Timestamp('2022-11-18')))
    return indv | grnd


def compare_vendor_paths(paths, output):
    """Vendor adjusted_close includes dividends: compare, do not overwrite.

    Absolute raw price scales can differ due to later splits while ratios
    remain identical. Such a scale difference alone is not a bad return.
    """
    rows = []
    for path in paths:
        file = output / f"{path['symbol']}_eod.json"
        if not file.exists():
            continue
        vendor = {b['date']: b for b in json.loads(file.read_text(encoding='utf-8'))}
        first, last = path['bars'][0], path['bars'][-1]
        if first['date'] not in vendor or last['date'] not in vendor:
            continue
        a, b = vendor[first['date']], vendor[last['date']]
        raw = 100*(float(b['close']) / float(a['close']) - 1)
        adjusted = 100*(float(b['adjusted_close']) / float(a['adjusted_close']) - 1)
        rows.append(dict(symbol=path['symbol'], start=first['date'], end=last['date'],
                         local_return_pct=path['future_return_pct'], fresh_vendor_raw_return_pct=raw,
                         fresh_vendor_total_adjusted_return_pct=adjusted,
                         independent_source=False))
    return rows


def run(source, output, refresh_provider=False):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths_file = source / 'largest_paths.json'
    paths = json.loads(paths_file.read_text(encoding='utf-8'))
    cases = [qualify_path(p) for p in paths]
    save(output / 'path_qualification.json', cases)
    rows = []
    counts = []
    for panel_path in sorted(source.glob('20*/panel.parquet')):
        frame = pd.read_parquet(panel_path)
        reserved = reservations(frame)
        counts.append(dict(year=int(panel_path.parent.name), reserved_rows=int(reserved.sum()),
                           reserved_extreme50=int((reserved & frame.future_return.abs().ge(.5)
                                                  & frame.target_quality_valid.eq(1)).sum())))
        # Original selections stay fixed, including their denominators. Removing
        # evidence sets labels unknown, not a retroactive trading veto.
        for view in ('ORIGINAL', 'RESERVATIONS_UNKNOWN'):
            data = frame.copy()
            if view != 'ORIGINAL':
                data.loc[reserved, 'target_quality_valid'] = 0
            for row in metrics(data, as_of='2026-10-06'):
                rows.append(dict(year=int(panel_path.parent.name), view=view, **row))
    metric_frame = pd.DataFrame(rows)
    metric_frame.to_parquet(output / 'sensitivity.parquet', index=False)
    aggregate = []
    subset = metric_frame[(metric_frame.scope == 'LABEL_VALID') & (metric_frame.side == 'ABS')]
    for (view, threshold, policy), group in subset.groupby(['view', 'threshold_pct', 'policy']):
        n, hits, total = (int(group[c].sum()) for c in ('evaluated', 'target_hits', 'reference_targets'))
        aggregate.append(dict(view=view, threshold_pct=int(threshold), policy=policy,
                              evaluated=n, hits=hits, reference_targets=total,
                              precision_pct=100*hits/n if n else None,
                              capture_pct=100*hits/total if total else None))
    save(output / 'sensitivity_summary.json', aggregate)
    provider_results = []
    if refresh_provider:
        from service.eodhd.clientEodhd import fetch_eod, fetch_splits
        from service.eodhd.quota import EodhdQuotaTracker
        import requests
        import ssl
        # Use system-trusted roots without disabling TLS verification or
        # changing application settings. Keep this diagnostic's quota local.
        certificate_path = output / 'system_trusted_ca.pem'
        certificate_path.write_text(''.join(ssl.DER_cert_to_PEM_cert(c)
            for c in ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
        session = requests.Session()
        session.verify = str(certificate_path.resolve())
        tracker = EodhdQuotaTracker(cache_dir=output / 'provider_quota')
        for symbol, start, end in [('INDV', '2022-09-26', '2022-12-30'),
                                   ('KNTK', '2020-10-01', '2020-12-10'),
                                   ('REPX', '2021-01-01', '2021-03-05')]:
            for kind, fetch in [('eod', fetch_eod), ('splits', fetch_splits)]:
                try:
                    payload = fetch(symbol, start=start, end=end, session=session, tracker=tracker,
                                    feature='extreme50_price_qualification')
                    save(output / f'{symbol}_{kind}.json', payload)
                    provider_results.append(dict(symbol=symbol, kind=kind, rows=len(payload), status='RECEIVED'))
                except Exception as exc:
                    # Exception strings can contain authenticated URLs: omit them.
                    provider_results.append(dict(symbol=symbol, kind=kind, status='FAILED',
                                                 error_type=type(exc).__name__))
        session.close()
    else:
        for symbol in ('INDV', 'KNTK', 'REPX'):
            for kind in ('eod', 'splits'):
                file = output / f'{symbol}_{kind}.json'
                if file.exists():
                    provider_results.append(dict(symbol=symbol, kind=kind, status='CACHED',
                        rows=len(json.loads(file.read_text(encoding='utf-8'))),
                        sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    save(output / 'vendor_path_comparison.json', compare_vendor_paths(paths, output))
    report = dict(source=str(source), paths_sha256=hashlib.sha256(paths_file.read_bytes()).hexdigest(),
                  inspected_paths=len(cases), symbols=len({c['symbol'] for c in cases}),
                  reserved_paths=sum(c['status'] == 'RESERVED' for c in cases),
                  independently_certified_paths=0, reserved_counts=counts,
                  provider_results=provider_results,
                  economic_replay='NOT_LAUNCHED', database_writes=False,
                  warning='Sensitivity is retrospective evidence qualification, NOT a PIT trading policy.')
    save(output / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='artifacts/research/us_extreme50_capture/audit-20261006-v1')
    parser.add_argument('--output', default='artifacts/research/us_extreme50_capture/price-qualification-20261006-v1')
    parser.add_argument('--refresh-provider', action='store_true')
    run(**vars(parser.parse_args()))
