"""Read-only audit of nine completed baseline cases; never launches challengers."""
import argparse
from pathlib import Path

import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics
from scripts.research.us_oracle_tp20_sl10_lifecycle import load_events


def audit(root, reference):
    root, reference = Path(root), Path(reference)
    if read(root/'progress.json') != {'status':'COMPLETED','phase':'baseline'}:
        raise ValueError('Baseline is not complete')
    report = read(root/'baseline-report.json')
    expected = {(year, count) for year in (2024,2025,2026) for count in (10,20,50)}
    if report['status'] != 'COMPLETED_EXPLORATORY' or report['failed'] or report['completed'] != 9:
        raise ValueError('Failed or incomplete case report')
    actual = {(r['year'],r['count']) for r in report['portfolios']}
    if actual != expected or len(report['portfolios']) != 9:
        raise ValueError('Missing or duplicate case')
    verify_hashes(root, read(root/'ready.json')['files'])
    verify_hashes(Path('.'), read(root/'baseline-source-manifest.json')['files'])
    protocol = read(root/'protocol.json')
    verify_hashes(Path('.'), protocol['model_files'])
    if (protocol['take_profit_pct'],protocol['stop_loss_pct'],protocol['side'],protocol['trailing']) != (.2,.1,'LONG',False):
        raise ValueError('Unexpected strategy contract')
    events = load_events(root)
    if not any(e.get('event_type') == 'NAME_CHANGE' for e in events):
        raise ValueError('Missing qualified lifecycle')
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp(protocol['as_of']).date())
    checks, paths = [], [root/'baseline-report.json',root/'ready.json',root/'baseline-source-manifest.json']
    all_trades = {}
    for result in report['portfolios']:
        year, count = result['year'], result['count']
        case = root/'BASELINE'/f'{year}-TOP{count}'
        verify_hashes(case,result['files'])
        if read(case/'case-report.json') != result or result['status'] != 'COMPLETED_EXPLORATORY':
            raise ValueError('Case/report discrepancy')
        trades, daily = [pd.read_parquet(case/name) for name in ('trades.parquet','daily.parquet')]
        metrics = annual_metrics(result,trades,daily,year)
        if metrics != result['annual_metrics']:
            raise ValueError('Summary counters disagree with trades')
        if daily.positions.iloc[-1] != 0 or abs(metrics['cash_reconciliation_error']) > 1e-6:
            raise ValueError('Unclosed or unreconciled portfolio')
        if not result['account_wealth_complete'] or result['unvalued_fractional_claims']:
            raise ValueError('Incomplete wealth')
        if not trades.side.eq('buy').all() or not trades['rank'].between(1,count).all():
            raise ValueError('Unexpected side or candidate rank')
        cut = pd.Timestamp(protocol['decision_end'] if year == 2026 else f'{year}-12-31')
        if not pd.to_datetime(trades.signal_date).le(cut).all():
            raise ValueError('Signal outside annual decision cohort')
        check = dict(year=year,count=count,**verify_trade_contract(trades,.2,.1,calendar),
            final_positions=0,complete_wealth=True,first_entry=str(trades.entry_date.min()),
            last_exit=str(trades.exit_date.max()),cash_error=metrics['cash_reconciliation_error'],
            corporate_action_events=result['corporate_action_events'])
        if year < 2026:
            oldcase = reference/'BASELINE'/f'{year}-TOP{count}'
            old = read(oldcase/'case-report.json')
            verify_hashes(oldcase,old['files'])
            if old['annual_metrics'] != metrics:
                raise ValueError('Unaffected baseline metrics changed')
            pd.testing.assert_frame_equal(trades,pd.read_parquet(oldcase/'trades.parquet'))
            check['unaffected_reference_reproduced'] = True
        all_trades[(year,count)] = trades
        checks.append(check)
        paths.extend([case/'case-report.json',case/'trades.parquet',case/'daily.parquet'])
    plateau = {str(year):all_trades[(year,20)].equals(all_trades[(year,50)])
               for year in (2024,2025,2026)}
    output = dict(status='ALL_NINE_BASELINE_CASES_VERIFIED',checks=checks,
        top20_top50_identical_trades_by_year=plateau,sql_writes=False,broker_orders=False,
        challengers_launched=False,retraining=False,
        source_hashes={str(p):digest(p) for p in paths},audit_code_sha256=digest(__file__),
        limitations=protocol['limitations']+read(root/'lifecycle.json')['reserves'])
    atomic_json(root/'completion-audit.json',output)
    print(output['status'], 'TOP20/TOP50 identical trades by year:', plateau, flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    audit(**vars(parser.parse_args()))
