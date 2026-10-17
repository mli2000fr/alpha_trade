"""Audit only: paired annual results, causal indicator and unchanged source data."""
import argparse
from pathlib import Path

import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read, freeze_candidates
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics
from scripts.research.us_oracle_exposure_guard import POLICY, build_policy_tape


def audit(root):
    root=Path(root)
    protocol=read(root/'exposure-protocol.json')
    report=read(root/'report.json')
    if report['status']!='COMPLETED_EXPLORATORY' or len(report['years'])!=3 \
            or {r['year'] for r in report['years']}!={2024,2025,2026}:
        raise ValueError('All three completed years required')
    if protocol['policy']!=POLICY or report['protocol_sha256']!=digest(root/'exposure-protocol.json'):
        raise ValueError('Changed frozen protocol')
    verify_hashes(Path('.'),protocol['code_hashes'])
    verify_hashes(Path('.'),protocol['source_hashes'])
    verify_hashes(root,read(root/'ready.json')['files'])
    verify_hashes(root,read(root/'policy-tape.json')['files'])
    scores,prices=[pd.read_parquet(root/n) for n in ('scores.parquet','prices.parquet')]
    calendar=nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp('2026-10-09').date())
    tape=pd.read_parquet(root/'exposure-policy.parquet')
    expected=build_policy_tape(scores,prices,calendar)
    pd.testing.assert_frame_equal(tape,expected,check_dtype=False)
    if not (pd.to_datetime(tape.membership_date)<tape.date).all():
        raise ValueError('Noncausal membership')
    # Withhold all later scores and prices; earlier indicator must be identical.
    cut=pd.Timestamp('2025-06-30')
    prefix=build_policy_tape(scores.loc[scores.date.le(cut)],prices.loc[prices.date.le(cut)],calendar)
    pd.testing.assert_frame_equal(tape.loc[tape.date.le(cut)].reset_index(drop=True),prefix,check_dtype=False)
    keys=set(map(tuple,freeze_candidates(scores,50,'NEW_BARRIER_LONG')[['date','symbol']].to_numpy()))
    checks=[]
    attribution=[]
    source=Path(protocol['source'])
    references={r['year']:r for r in read(source/'report.json')['portfolios'] if r['arm']=='TRAIN_TP20_SL10'}
    for annual in report['years']:
        year=annual['year']
        case=Path(annual['output'])
        result=read(case/'case-report.json')
        if annual['result_sha256']!=digest(case/'case-report.json') \
                or annual['decision_audit_sha256']!=digest(case/'exposure-decisions.json'):
            raise ValueError('Changed case output')
        verify_hashes(case,result['files'])
        trades,daily=[pd.read_parquet(case/n) for n in ('trades.parquet','daily.parquet')]
        if annual_metrics(result,trades,daily,year)!=annual['exposure_guard']:
            raise ValueError('Case metrics mismatch')
        if references[year]['annual_metrics']!=annual['baseline']:
            raise ValueError('Changed reference')
        if result['status']!='COMPLETED_EXPLORATORY' or not result['account_wealth_complete'] \
                or daily.positions.iloc[-1] or abs(result['cash_reconciliation_error'])>1e-6:
            raise ValueError('Incomplete economic result')
        end=pd.Timestamp('2026-09-03' if year==2026 else f'{year}-12-31')
        for t in trades.itertuples():
            symbol=getattr(t,'entry_symbol',None)
            if symbol is None or pd.isna(symbol):symbol=t.symbol
            if (pd.Timestamp(t.signal_date),symbol) not in keys or t.side!='buy' \
                    or not pd.Timestamp(f'{year}-01-01')<=pd.Timestamp(t.signal_date)<=end \
                    or pd.Timestamp(t.entry_date)<=pd.Timestamp(t.signal_date):
                raise ValueError('Changed candidate/side/chronology')
        trace=read(case/'exposure-decisions.json')
        for row in trace:
            day=pd.Timestamp(row['date'])
            if day in set(tape.date):
                if row['exposure_scale']!=float(tape.set_index('date').at[day,'exposure_scale']):
                    raise ValueError('Wrong entry multiplier')
            if row['accepted'] and not row['allow_long']:
                raise ValueError('Macro guard bypass')
        checks.append(dict(year=year,closed_legs=len(trades),cash_error=result['cash_reconciliation_error'],
            **verify_trade_contract(trades,.2,.1,calendar)))
        baseline_case=Path(references[year]['output'])
        month={}
        first_breaker={}
        for name,folder in [('baseline',baseline_case),('guard',case)]:
            legs=pd.read_parquet(folder/'trades.parquet')
            curve=pd.read_parquet(folder/'daily.parquet')
            pnl=legs.assign(month=pd.to_datetime(legs.signal_date).dt.strftime('%Y-%m')).groupby('month').pnl.sum()
            exposure=curve.assign(month=pd.to_datetime(curve.date).dt.strftime('%Y-%m'),
                gross_fraction=curve.gross_notional/curve.equity).groupby('month').gross_fraction.mean()
            month[name]=dict(net_pnl_by_signal_month=pnl.to_dict(),
                mean_exposure_by_calendar_month=exposure.to_dict())
            regimes=pd.DataFrame(read(folder/'regimes.json'))
            reduced=regimes.loc[regimes.breaker_scale.lt(1)]
            first_breaker[name]=str(reduced.date.iloc[0]) if len(reduced) else None
        attribution.append(dict(year=year,monthly=month,first_native_breaker_reduction=first_breaker))
    result=dict(status='THREE_YEARS_AND_CAUSAL_TAPE_VERIFIED',checks=checks,
        prefix_causality_verified=True,source_code_and_inputs_unchanged=True,
        no_live_promotion=True,report_sha256=digest(root/'report.json'),
        audit_code_sha256=digest(__file__),attribution=attribution)
    atomic_json(root/'completion-audit.json',result)
    print(result['status'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    audit(**vars(parser.parse_args()))
