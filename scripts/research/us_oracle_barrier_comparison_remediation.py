"""Bounded replay of missing cash-tail macro cases; never drop an AVB trade.

Original complete portfolios remain immutable. A successor/cash-in-lieu event
not handled by the shared ledger remains blocked, not a fictitious sell.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import logging

import pandas as pd

from common.config_loader import load_config
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import FixedBarrierLedger, SECTORS, freeze_candidates, read
from service.market import parse_market_regimes


def verify_replay_sources(hashes):
    allowed = Path('scripts/research/us_concentrated_live_portfolio.py')
    for name, checksum in hashes.items():
        if Path(name) != allowed and digest(name) != checksum:
            raise ValueError(f'Original source changed beyond cash-tail driver: {name}')


def run(source, output):
    output.mkdir(parents=True, exist_ok=True)
    previous, original = read(source/'report.json'), read(source/'protocol.json')
    if previous['status'] != 'PARTIAL_FAILED' or len(previous['portfolios']) != 6:
        raise ValueError('Unexpected source state for bounded remediation')
    allowed = 'scripts/research/us_concentrated_live_portfolio.py'
    verify_replay_sources(original['source_hashes'])
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    risk = frozen_backtest_config('2025-01-01', original['as_of'])
    if json.loads(json.dumps(asdict(market), default=str)) != original['portfolio']['market']:
        raise ValueError('Market config changed')
    if json.loads(json.dumps(asdict(risk.risk_config), default=str)) != original['portfolio']['risk']:
        raise ValueError('Risk config changed')
    bars = []
    files = [source/'report.json', source/'protocol.json', source/'scores.parquet', source/'labels.parquet', source/'selected-outcomes.parquet', source/'macro.parquet']
    for path in sorted(source.glob('bars-*.parquet')):
        verify_hashes(source, {path.name: read(source/f'{path.name}.json')['sha256']})
        bars.append(pd.read_parquet(path))
        files.append(path)
    for name in ('scores.parquet', 'labels.parquet', 'macro.parquet'):
        verify_hashes(source, {name: read(source/f'{name}.json')['sha256']})
    source_hashes = {str(path): digest(path) for path in files}
    protocol = dict(original_protocol_sha256=digest(source/'protocol.json'), source=str(source),
        source_hashes=source_hashes, code_sha256=digest(__file__), driver_sha256=digest(allowed),
        scope='macro is unnecessary ONLY when no positions and no future decisions in expiry tail',
        unchanged_complete_2025_reused=True, avb_successor_not_implemented=True,
        price_substitution=False, sql_writes=False, training=False, broker_orders=False)
    if (output/'protocol.json').exists() and read(output/'protocol.json') != protocol:
        raise ValueError('Remediation resume source mismatch')
    atomic_json(output/'protocol.json', protocol)
    bars = pd.concat(bars, ignore_index=True)
    factor = bars.adj_close.where(bars.adj_close.notna(), bars.close)/bars.close
    adjusted = bars.copy()
    adjusted[['open', 'high', 'low', 'close']] = adjusted[['open', 'high', 'low', 'close']].mul(factor, axis=0)
    from modelFactory.oracle.build_labels import nyse_sessions
    calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(original['as_of']).date())
    scores = pd.read_parquet(source/'scores.parquet')
    macro = ArchivedMacro(pd.read_parquet(source/'macro.parquet'))
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    reports = list(previous['portfolios'])
    # These fail on the merger while the position is still owned. No future
    # symbol deletion, filled bar, liquidation or renamed series is invented.
    failures = [x for x in previous['failures'] if x['arm'] == 'NEW_BARRIER_LONG']
    for count in (10, 20, 50):
        atomic_json(output/'progress.json', dict(status='RUNNING', count=count,
            arm='OLD_TERMINAL_LONG', year=2026, completed_runs=len(reports), blocked_runs=len(failures), total_runs=12))
        destination = output/f'2026-TOP{count}-OLD_TERMINAL_LONG'
        if (destination/'report.json').exists():
            result = read(destination/'report.json')
        else:
            candidates = freeze_candidates(scores.loc[scores.date.dt.year.eq(2026)], count, 'OLD_TERMINAL_LONG')
            required = set(candidates.symbol) | {'SPY'}
            subset = adjusted.loc[adjusted.symbol.isin(required)]
            frames = {key: subset.pivot(index='date', columns='symbol', values=column).reindex(calendar)
                for key, column in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
            final = calendar[calendar <= pd.Timestamp('2026-09-03')][-1]
            end = calendar[calendar.get_loc(final)+21]
            try:
                result = run_portfolio(frames=frames, scores=candidates, sectors=sectors, macro=macro,
                    market_config=market, policy='selected', variant='CURRENT_NO_EXPIRY', output=destination,
                    start_date='2026-01-01', end_date=str(end.date()), decision_end_date=str(final.date()),
                    quality=bars.loc[bars.symbol.isin(required), ['date', 'symbol', 'is_filled', 'instrument_id']],
                    ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
                    protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
            except Exception as exc:
                failures.append(dict(year=2026, count=count, arm='OLD_TERMINAL_LONG', error=str(exc)))
                continue
        result.update(year=2026, count=count, arm='OLD_TERMINAL_LONG')
        trades = pd.read_parquet(destination/'trades.parquet')
        result['exit_reasons'] = trades.exit_reason.value_counts().to_dict()
        atomic_json(destination/'report.json', result)
        reports.append(result)
        atomic_json(output/'portfolio-results.partial.json', reports)
    for path, checksum in source_hashes.items():
        if digest(path) != checksum:
            raise ValueError(f'Input changed during remediation: {path}')
    verify_replay_sources(original['source_hashes'])
    if digest(allowed) != protocol['driver_sha256'] or digest(__file__) != protocol['code_sha256']:
        raise ValueError('Remediation code changed during execution')
    # Produce a consolidated summary with explicit original/remediated lineage.
    from scripts.research.us_oracle_barrier_comparison_summary import portfolio_periods
    summary = []
    for item in reports:
        folder = (source if item['year'] == 2025 else output)/f"{item['year']}-TOP{item['count']}-{item['arm']}"
        daily = pd.read_parquet(folder/'daily.parquet')
        cutoff = '2025-12-31' if item['year'] == 2025 else '2026-09-03'
        summary.append(dict(arm=item['arm'], count=item['count'], **portfolio_periods(daily, item['year'], cutoff),
            closed_positions=item['closed_positions'], exits=item['exit_reasons'],
            cash_reconciliation_error=item['cash_reconciliation_error'], directory=str(folder)))
    # Paired prefixes are diagnostics, NOT a new shorter-period confirmation.
    prefix = []
    for count in (10, 20, 50):
        for arm in ('OLD_TERMINAL_LONG', 'NEW_BARRIER_LONG'):
            folder = (output if arm == 'OLD_TERMINAL_LONG' else source)/f'2026-TOP{count}-{arm}'
            filename = 'daily.parquet' if arm == 'OLD_TERMINAL_LONG' else 'daily.partial.parquet'
            if (folder/filename).exists():
                daily = pd.read_parquet(folder/filename)
                prefix.append(dict(count=count, arm=arm,
                    **portfolio_periods(daily.loc[daily.date.le('2026-08-14')], 2026, '2026-08-14')))
    result = dict(status='PARTIAL_BLOCKED_CORPORATE_ACTION', portfolios=reports, summary=summary,
        failures=failures, complete_runs=len(reports), total_runs=12,
        paired_prefix_diagnostic_not_confirmation=prefix, candidates=previous['candidates'],
        original_source=str(source), avb_evidence='artifacts/research/us_oracle_barrier_comparison/avb-evidence-20261012-v1',
        promotion=False, limitations=original['limitations'])
    atomic_json(output/'report.json', result)
    atomic_json(output/'progress.json', dict(status=result['status'], completed_runs=len(reports), blocked_runs=len(failures), total_runs=12))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    run(args.source, args.output)
