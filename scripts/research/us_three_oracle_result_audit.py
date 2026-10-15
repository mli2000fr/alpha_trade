"""Audit completed three-model comparison tapes; never run or train a model."""
import argparse
from pathlib import Path

import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics


def audit(root):
    root = Path(root)
    report, manifest = read(root/'report.json'), read(root/'manifest.json')
    if report['status'] != 'COMPLETED_EXPLORATORY' or report['completed'] != 9 or report['failed']:
        raise ValueError('Nine completed cases required')
    if report['manifest_sha256'] != digest(root/'manifest.json'):
        raise ValueError('Changed manifest')
    verify_hashes(Path('.'),manifest['source_hashes'])
    verify_hashes(Path('.'),manifest['code_hashes'])
    expected = {(y,a) for y in manifest['years'] for a in manifest['models']}
    if {(r['year'],r['arm']) for r in report['portfolios']} != expected or len(report['portfolios']) != 9:
        raise ValueError('Duplicate or missing case')
    common_hashes, keys = None, None
    for arm in manifest['models']:
        armroot = root/arm
        ready = read(armroot/'ready.json')['files']
        verify_hashes(armroot,ready)
        current = {n:ready[n] for n in ('prices.parquet','macro.parquet','lifecycle.json')}
        if common_hashes is not None and current != common_hashes:
            raise ValueError('Execution inputs differ between models')
        common_hashes = current
        current_keys = pd.read_parquet(armroot/'scores.parquet',columns=['date','symbol'])
        if keys is not None:
            pd.testing.assert_frame_equal(keys,current_keys)
        keys = current_keys
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp('2026-10-09').date())
    checks, paths = [], [root/'manifest.json',root/'report.json']
    for result in report['portfolios']:
        case = Path(result['output'])
        verify_hashes(case,result['files'])
        if result['baseline_model'] != manifest['models'][result['arm']]['batch_id']:
            raise ValueError('Wrong model attribution')
        trades, daily = [pd.read_parquet(case/n) for n in ('trades.parquet','daily.parquet')]
        if not trades.side.eq('buy').all() or not trades['rank'].between(1,50).all():
            raise ValueError('Unexpected side or entry rank')
        if daily.positions.iloc[-1] or abs(result['cash_reconciliation_error'])>1e-6:
            raise ValueError('Incomplete portfolio/cash')
        if not result['account_wealth_complete'] or result['unvalued_fractional_claims']:
            raise ValueError('Unvalued corporate action')
        cutoff = pd.Timestamp('2026-09-03' if result['year']==2026 else f"{result['year']}-12-31")
        if not pd.to_datetime(trades.signal_date).le(cutoff).all():
            raise ValueError('Signal past the annual decision cut')
        if annual_metrics(result,trades,daily,result['year']) != result['annual_metrics']:
            raise ValueError('Metrics do not reproduce trade tapes')
        checks.append(dict(year=result['year'],arm=result['arm'],
            **verify_trade_contract(trades,.2,.1,calendar),cash_error=result['cash_reconciliation_error'],
            final_positions=0,corporate_action_events=result['corporate_action_events']))
        paths.extend(case/n for n in ('case-report.json','trades.parquet','daily.parquet'))
    references = [r for r in report['portfolios'] if r['arm']=='TRAIN_TP20_SL10']
    if len(references)!=3 or not all(r.get('reference_reproduced_exactly') for r in references):
        raise ValueError('Reference baseline not reproduced')
    result = dict(status='NINE_CASES_COMMON_INPUTS_AND_TRADE_CONTRACTS_VERIFIED',checks=checks,
        source_hashes={str(p):digest(p) for p in paths},code_sha256=digest(__file__),
        common_keys=True,common_prices_macro_lifecycle=True,reference_three_years_reproduced=True,
        no_sql_writes=True,no_training=True,no_broker_orders=True,exploratory_not_live_certification=True)
    atomic_json(root/'completion-audit.json',result)
    print(result['status'],flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    audit(**vars(parser.parse_args()))
