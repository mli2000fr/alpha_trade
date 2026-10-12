"""Bounded 2026 comparison with real successor bars and audited CA reserves.

No SQL write, model fit or broker order. STRICT remains blocked on unknown CIL.
The separate UNVALUED_RECEIVABLE scenario cannot be called complete wealth.
Original reports/input hashes remain immutable; both models rerun with the
same AVB historical share-unit restoration, quantities, fees and CA policy.
"""
import argparse
from dataclasses import asdict
from functools import partial
import json
import logging
from pathlib import Path
import ssl

import numpy as np
import pandas as pd
import requests

from common.config_loader import load_config
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import SECTORS, freeze_candidates, read
from scripts.research.us_oracle_merger_ledger import EVENTS, MergerLedger
from service.alpaca.clientAlpaca import _build_headers
from service.market import parse_market_regimes

LOG = logging.getLogger(__name__)
RATIO = 2.793
SOURCES = {
    'merger': 'https://investors.avalonbay.com/sec-filings/all-sec-filings/content/0001104659-26-097833/tm2623381d1_8k.htm',
    'fractional_contract': 'https://www.sec.gov/Archives/edgar/data/915912/000110465926064781/tm2615292d1_ex2-1.htm',
    'broker_orders': 'https://docs.alpaca.markets/us/docs/mandatory-corporate-actions',
    'paper_limitations': 'https://forum.alpaca.markets/t/corporate-actions-handeling/19325',
}


def fetch_history(output):
    cache = output/'successor-evidence'
    cache.mkdir(parents=True, exist_ok=True)
    files = [cache/f'{s}-bars.json' for s in ('AVB', 'EQR', 'VMRK')]
    files.append(cache/'VMRK-asset.json')
    if (cache/'manifest.json').exists():
        manifest = read(cache/'manifest.json')
        verify_hashes(cache, manifest['files'])
        return cache, manifest
    trust = cache/'windows-trust.pem'
    trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in
        ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
    with requests.Session() as session:
        session.verify = str(trust.resolve())
        headers = _build_headers('default')
        for symbol in ('AVB', 'EQR', 'VMRK'):
            start = '2026-08-14' if symbol == 'VMRK' else '2024-01-01'
            response = session.get(f'https://data.alpaca.markets/v2/stocks/{symbol}/bars',
                params=dict(timeframe='1Day', feed='sip', adjustment='split', limit=1000,
                    start=start+'T00:00:00-04:00', end='2026-10-07T00:00:00-04:00'),
                headers=headers, timeout=40)
            response.raise_for_status()
            payload = response.json()
            if payload.get('next_page_token'):
                raise ValueError('Unexpected pagination: qualify rather than truncate')
            atomic_json(cache/f'{symbol}-bars.json', payload)
        response = session.get('https://paper-api.alpaca.markets/v2/assets/VMRK', headers=headers, timeout=30)
        response.raise_for_status()
        public = response.json()
        atomic_json(cache/'VMRK-asset.json', {k: public.get(k) for k in
            ('id', 'symbol', 'name', 'exchange', 'status', 'fractionable')})
    manifest = dict(files={p.name: digest(p) for p in files},
        feed='sip', adjustment='split', observed_now_not_historical_publication=True,
        provider_get_only=True, broker_orders=False, sources=SOURCES,
        actual_fraction_cash_price=None, actual_fraction_payment_date=None)
    atomic_json(cache/'manifest.json', manifest)
    return cache, manifest


def provider_frame(cache, symbol):
    data = read(cache/f'{symbol}-bars.json')['bars']
    frame = pd.DataFrame(data).rename(columns=dict(o='open', h='high', l='low', c='close', v='volume'))
    frame['date'] = pd.to_datetime(frame.t, utc=True).dt.tz_convert('America/New_York').dt.normalize().dt.tz_localize(None)
    if frame.date.duplicated().any() or frame.empty:
        raise ValueError(f'Duplicate/empty provider history {symbol}')
    if not np.isfinite(frame[['open', 'high', 'low', 'close', 'volume']]).all().all() \
            or frame[['open', 'high', 'low', 'close', 'volume']].le(0).any().any() \
            or frame.high.lt(frame[['open', 'close', 'low']].max(axis=1)).any() \
            or frame.low.gt(frame[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError(f'Invalid provider OHLCV {symbol}')
    return frame[['date', 'open', 'high', 'low', 'close', 'volume']]


def prepare_prices(bars, cache, calendar):
    factor = bars.adj_close.where(bars.adj_close.notna(), bars.close)/bars.close
    adjusted = bars.copy()
    adjusted[['open', 'high', 'low', 'close']] = adjusted[['open', 'high', 'low', 'close']].mul(factor, axis=0)
    raw = provider_frame(cache, 'AVB')
    original = adjusted.loc[adjusted.symbol.eq('AVB')]
    paired = raw.merge(original, on='date', suffixes=('_sip', '_sql'), validate='one_to_one')
    if len(paired) < 500:
        raise ValueError('Insufficient AVB historical basis evidence')
    errors = []
    row_ratios = pd.concat([paired[c+'_sip']/paired[c+'_sql']
                           for c in ('open', 'high', 'low', 'close')], axis=1).median(axis=1)
    multipliers = pd.Series(np.where((row_ratios/RATIO-1).abs() < (row_ratios-1).abs(),
                                    RATIO, 1.), index=paired.index)
    for column in ('open', 'high', 'low', 'close'):
        error = (paired[column+'_sip']/(paired[column+'_sql']*multipliers)-1).abs()
        errors.append(dict(field=column, within_01pct=float(error.le(.001).mean()),
                          maximum_relative_error=float(error.max())))
        # One retained EODHD low differs 0.335% from SIP on 03-Jun-2026.
        # The other three anchors agree: this is not evidence of a different
        # 179.3% share-unit basis. Retain the archived low, record the mismatch,
        # and do not pretend the independent OHLC feeds are identical.
        tolerance = .005 if column == 'low' else .001
        if not error.le(tolerance).all():
            raise ValueError(f'Historical AVB basis not qualified: {column}')
    # The archive is MIXED: older AVB bars are already raw, only recent
    # refreshed dates are successor-adjusted. Restore only independently
    # matched dates; never multiply the whole history by the merger ratio.
    restore_dates = paired.loc[multipliers.eq(RATIO), 'date']
    if len(paired) != len(original.loc[original.date.lt('2026-08-17')]):
        raise ValueError('AVB restoration requires every pre-merger input date')
    mask = adjusted.symbol.eq('AVB') & adjusted.date.isin(restore_dates)
    adjusted.loc[mask, ['open', 'high', 'low', 'close']] *= RATIO
    adjusted.loc[mask, 'volume'] /= RATIO
    successor = provider_frame(cache, 'VMRK')
    eqr = provider_frame(cache, 'EQR')
    overlap = successor.merge(eqr, on='date', suffixes=('_new', '_old'), validate='one_to_one')
    if len(overlap) < 2:
        raise ValueError('EQR/VMRK alias overlap unavailable')
    for column in ('open', 'high', 'low', 'close'):
        if not np.allclose(overlap[column+'_new'], overlap[column+'_old'], rtol=1e-6, atol=1e-6):
            raise ValueError('EQR/VMRK alias OHLC discrepancy')
    successor = pd.concat([eqr.loc[eqr.date.lt('2026-08-18')], successor.loc[successor.date.ge('2026-08-18')]])
    expected = calendar[(calendar >= '2026-08-17') & (calendar <= '2026-10-05')]
    if not expected.isin(successor.date).all():
        raise ValueError('Missing successor tail sessions')
    successor = successor.assign(symbol='VMRK', adj_close=lambda x: x.close,
        is_filled=0, instrument_id=read(cache/'VMRK-asset.json')['id'],
        data_source='alpaca_sip_research_successor', data_adjustment='split')
    # Original EQR and AVB are not fabricated after retirement; only VMRK is
    # added under its own identity. Its pre-18-Aug alias is explicitly EQR.
    if adjusted.symbol.eq('VMRK').any():
        raise ValueError('Unexpected VMRK in frozen input')
    combined = pd.concat([adjusted, successor], ignore_index=True)
    if combined.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate qualified input keys')
    return combined, dict(avb_ohlc_basis=errors, paired_avb_rows=len(paired),
        avb_raw_rows=int(multipliers.eq(1.).sum()), avb_successor_adjusted_rows=len(restore_dates),
        avb_restored_first_date=str(restore_dates.min().date()) if len(restore_dates) else None,
        avb_restored_last_date=str(restore_dates.max().date()) if len(restore_dates) else None,
        eqr_vmrk_overlap_rows=len(overlap), successor_tail_sessions=len(expected),
        raw_avb_units_restored=True, avb_postretirement_bars_created=False,
        successor_trading_symbol_before_20260818='EQR')


def run(source, output):
    output.mkdir(parents=True, exist_ok=True)
    original = read(source/'protocol.json')
    from scripts.research.us_oracle_barrier_comparison_remediation import verify_replay_sources
    verify_replay_sources(original['source_hashes'])
    paths = [source/'protocol.json', source/'scores.parquet', source/'macro.parquet', Path(SECTORS)]
    bars = []
    for path in sorted(source.glob('bars-*.parquet')):
        verify_hashes(source, {path.name: read(source/f'{path.name}.json')['sha256']})
        paths.append(path)
        bars.append(pd.read_parquet(path))
    for name in ('scores.parquet', 'macro.parquet'):
        verify_hashes(source, {name: read(source/f'{name}.json')['sha256']})
    hashes = {str(p): digest(p) for p in paths}
    code = [Path(__file__), Path('scripts/research/us_oracle_merger_ledger.py'),
            Path('scripts/research/us_concentrated_live_portfolio.py')]
    code_hashes = {str(p): digest(p) for p in code}
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    risk = frozen_backtest_config('2025-01-01', original['as_of'])
    if json.loads(json.dumps(asdict(market), default=str)) != original['portfolio']['market'] \
            or json.loads(json.dumps(asdict(risk.risk_config), default=str)) != original['portfolio']['risk']:
        raise ValueError('Frozen risk/market parameters changed')
    cache, manifest = fetch_history(output)
    calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(original['as_of']).date())
    prices, qualification = prepare_prices(pd.concat(bars, ignore_index=True), cache, calendar)
    protocol = dict(source=str(source), source_hashes=hashes, code_hashes=code_hashes,
        market=original['portfolio']['market'], risk=original['portfolio']['risk'], events=EVENTS,
        evidence=manifest, qualification=qualification, decision_end='2026-09-03',
        counts=[10, 20, 50], sql_writes=False, training=False, broker_orders=False,
        official_cil_unknown=True, strict_will_not_assume_cash=True,
        research_equity_excludes_unvalued_receivables=True,
        protection_replacement_atomic_simulation_not_broker_observation=True)
    if (output/'protocol.json').exists() and read(output/'protocol.json') != json.loads(json.dumps(protocol, default=str)):
        raise ValueError('Resume lineage changed: use a new output')
    atomic_json(output/'protocol.json', protocol)
    scores = pd.read_parquet(source/'scores.parquet')
    macro = ArchivedMacro(pd.read_parquet(source/'macro.parquet'))
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    if sectors.get('AVB') != sectors.get('EQR'):
        raise ValueError('Successor sector attribution ambiguous')
    sectors['VMRK'] = sectors['EQR']
    reports, failures = [], []
    cases = [('STRICT', 'NEW_BARRIER_LONG', n) for n in (10, 20, 50)]
    cases += [('UNVALUED_RECEIVABLE', arm, n) for arm in ('OLD_TERMINAL_LONG', 'NEW_BARRIER_LONG') for n in (10, 20, 50)]
    for policy, arm, count in cases:
        atomic_json(output/'progress.json', dict(status='RUNNING', policy=policy, arm=arm,
            count=count, attempted=len(reports)+len(failures), total=len(cases)))
        destination = output/f'2026-TOP{count}-{arm}-{policy}'
        candidates = freeze_candidates(scores.loc[scores.date.dt.year.eq(2026)], count, arm)
        required = set(candidates.symbol) | {'SPY', 'VMRK'}
        subset = prices.loc[prices.symbol.isin(required)]
        frames = {key: subset.pivot(index='date', columns='symbol', values=column).reindex(calendar)
            for key, column in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
        final = calendar[calendar <= '2026-09-03'][-1]
        end = calendar[calendar.get_loc(final)+21]
        try:
            if (destination/'report.json').exists():
                result = read(destination/'report.json')
            else:
                result = run_portfolio(frames=frames, scores=candidates, sectors=sectors, macro=macro,
                    market_config=market, policy='selected', variant='CURRENT_NO_EXPIRY', output=destination,
                    start_date='2026-01-01', end_date=str(end.date()), decision_end_date=str(final.date()),
                    quality=subset[['date', 'symbol', 'is_filled', 'instrument_id']],
                    ledger_factory=partial(MergerLedger, cash_policy=policy), expiry_open_sessions=20,
                    protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
        except Exception as exc:
            failures.append(dict(policy=policy, arm=arm, count=count, error=str(exc)))
            LOG.warning('Blocked %s %s TOP%d: %s', policy, arm, count, exc)
            continue
        from scripts.research.us_oracle_barrier_comparison_summary import portfolio_periods
        daily = pd.read_parquet(destination/'daily.parquet')
        periods = portfolio_periods(daily, 2026, '2026-09-03')
        result.update(policy=policy, arm=arm, count=count, year=2026, periods=periods,
            net_total_wealth_return=None if not result['account_wealth_complete'] else result['return_pct'],
            interpretation='RESEARCH_CASH_AND_WHOLE_SHARES_WITH_UNPRICED_CLAIM_NOT_CERTIFIED_BROKER_PARITY')
        atomic_json(destination/'report.json', result)
        reports.append(result)
        atomic_json(output/'results.partial.json', dict(portfolios=reports, failures=failures))
    for p, checksum in {**hashes, **code_hashes}.items():
        if digest(p) != checksum:
            raise ValueError(f'Inputs/code changed during replay: {p}')
    result = dict(status='RESEARCH_COMPLETED_WITH_RESERVES' if len(reports) == 6 else 'PARTIAL_BLOCKED',
        completed_scenarios=len(reports), strict_blocked=len([x for x in failures if x['policy']=='STRICT']),
        portfolios=reports, failures=failures, full_broker_parity=False, promotion=False,
        remaining='Actual fractional sale proceeds/payment timing and CA order replacement fills are not qualified.')
    atomic_json(output/'report.json', result)
    atomic_json(output/'progress.json', dict(status=result['status'], completed=len(reports),
        failed_or_blocked=len(failures), total=len(cases)))
    rows = ['# Rejeu 2026 avec conversion AVB', '',
        '**Scénario de recherche : cash + actions entières ; créances de fractions non valorisées.**',
        'Ce n’est pas un rendement complet du patrimoine ni une parité courtier certifiée.', '',
        '| TOP | Modèle | Au 03/09 | Après sorties | DD | Fractions non valorisées |',
        '| ---: | --- | ---: | ---: | ---: | ---: |']
    for r in reports:
        rows.append(f"| {r['count']} | {r['arm']} | {r['periods']['calendar_mark_to_market_return']:+.2%} | "
            f"{r['return_pct']:+.2%} | {r['max_drawdown']:.2%} | {len(r['unvalued_fractional_claims'])} |")
    rows += ['', '## Réserves strictes', *[f"- {x['policy']} TOP{x['count']} : {x['error']}" for x in failures]]
    (output/'report.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.source, args.output)
