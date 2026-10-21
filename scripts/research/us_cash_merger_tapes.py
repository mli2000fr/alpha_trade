"""Offline pre-closing tapes and single-event payment-source reconciliation, no PnL."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_cash_merger_completion import READ,prepare,freeze_cohort,normalized
from scripts.research.us_cash_merger_readiness import validate_events,validate_bar_values
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def reconcile_action(records,event,initial_cover):
    matching=[r for r in records if r.get('acquiree_symbol')==event['symbol']]
    if not matching:raise ValueError('No independently corroborating provider action')
    cusips={r.get('acquiree_cusip') for r in matching}
    if len(cusips)!=1 or not next(iter(cusips)):raise ValueError('Missing/ambiguous provider CUSIP')
    cusip=next(iter(cusips));cover=re.sub(r'[^A-Z0-9]','',initial_cover.upper())
    if cusip not in cover:raise ValueError('Provider CUSIP not supported by original issuer cover')
    if not all(np.isclose(r.get('rate',float('nan')),event['cash_per_share_usd'],atol=1e-10,rtol=0) for r in matching):
        raise ValueError('Provider action amount conflicts with SEC contract')
    dates={r['payable_date'] for r in matching if r.get('payable_date')}
    if len(dates)>1:raise ValueError('Conflicting provider payment dates; never choose the favorable one')
    payment=next(iter(dates)) if dates else None
    if payment and payment<event['completed_on']:raise ValueError('Payment predates legal cash right')
    return dict(symbol=event['symbol'],target_cik=event['target_cik'],cusip=cusip,
        cash_per_share_usd=event['cash_per_share_usd'],sec_legal_closing=event['completed_on'],
        provider_payable_date=payment,payment_date_status='SUPPLIER_DECLARED_NOT_BROKER_VERIFIED' if payment else 'UNKNOWN',
        broker_spendable_date=None,broker_credit_qualified=False,
        economic_event_count=1,provider_record_count=len(matching),provider_records=matching,
        instruction='One cash right and at most one future payment per economic deal, never one payment per provider row. SEC legal closing and provider payable/process/effective dates are separate facts.')


def executable_tape(raw,event):
    calendar=mcal.get_calendar('NYSE')
    next_day=(pd.Timestamp(event['initial_filed'])+pd.Timedelta(days=1)).date()
    end=(pd.Timestamp(event['completed_on'])-pd.Timedelta(days=1)).date()
    expected=[str(d.date()) for d in calendar.valid_days(start_date=next_day,end_date=end)]
    day=lambda b:str(pd.Timestamp(b['t']).tz_convert('America/New_York').date())
    chosen=[r for r in raw if day(r) in set(expected)]
    if [day(r) for r in chosen]!=expected:raise ValueError('Missing, duplicate or unordered executable sessions')
    if validate_bar_values(chosen):raise ValueError('Invalid pre-closing OHLCV, do not remove issuer')
    excluded=[r for r in raw if day(r)>=event['completed_on']]
    if any(day(r)!=event['completed_on'] or r['v']!=0 or r.get('n')!=0 for r in excluded):
        raise ValueError('Unexpected post-closing trades need independent qualification')
    return chosen,[dict(symbol=event['symbol'],date=day(r),reason='ZERO_VOLUME_ZERO_TRADES_AT_LEGAL_CLOSING_NOT_EXECUTABLE',source_bar=r) for r in excluded]


def audit_build(root):
    prepare(root);cohort=freeze_cohort(root);events=validate_events(root)
    out=root/'tapes-v1'
    if out.exists():raise ValueError('Immutable audited tapes directory')
    ready=root/'readiness-v1';report=READ(ready/'report.json');verify_hashes(ready,report['files'])
    verify_hashes(Path('.'),READ(ready/'protocol.json')['sources'])
    initial=READ(root/'initials.json');verify_hashes(root,initial['files'])
    bysymbol={r['symbol']:r for r in cohort['rows'] if r['eligible']}
    life=READ(root/'lifecycle.json');parts=READ(root/'lifecycle-extract.json')
    index_acc={r['index']['accession'] for r in parts['documents']}
    if len(index_acc)!=23 or any(not r['bound_pass'] for r in life['cases']):raise ValueError('Lifecycle completeness changed')
    raw=READ(ready/'raw.json')['payload']['bars'];split=READ(ready/'split.json')['payload']['bars']
    actions=READ(ready/'actions.json')['payload']['corporate_actions']
    if any(rows for name,rows in actions.items() if name!='cash_mergers'):raise ValueError('Unsupported additional actions')
    tapes=[];quarantine=[];cash=[];summaries=[]
    for e in events:
        s=e['symbol'];original=READ(root/bysymbol[s]['initial_review_file'])
        cover=next(p['text'] for p in original['parts'] if p['type']=='SC TO-T')
        mapping=reconcile_action(actions.get('cash_mergers',[]),e,cover);cash.append(mapping)
        bars,excluded=executable_tape(raw.get(s,[]),e);quarantine+=excluded
        a={r['t']:[r[k] for k in ['o','h','l','c']] for r in bars}
        b={r['t']:[r[k] for k in ['o','h','l','c']] for r in split.get(s,[])}
        if not all(t in b and np.allclose(a[t],b[t],rtol=0,atol=1e-8) for t in a):raise ValueError('Execution adjustment mismatch')
        first=pd.Timestamp(bars[0]['t'])
        if pd.Timestamp(original['accepted_utc'])>=first+pd.Timedelta(hours=9):raise ValueError('Acceptance later than conservative entry proxy')
        # Bars remain unadjusted. No hypothetical purchase, return or comparison
        # to the offer price is performed here.
        for row in bars:tapes.append(dict(symbol=s,date=pd.Timestamp(row['t']).tz_convert('America/New_York').date(),**row))
        summaries.append(dict(symbol=s,eligible_pre_closing_sessions=len(bars),first_session=str(pd.Timestamp(bars[0]['t']).tz_convert('America/New_York').date()),
            last_session=str(pd.Timestamp(bars[-1]['t']).tz_convert('America/New_York').date()),quarantined_closing_rows=len(excluded),
            initial_and_terminal_amount_equal=True,provider_and_sec_cusip_match=True,provider_payable_date=mapping['provider_payable_date'],
            broker_spendable_date=None))
    out.mkdir()
    sources=[Path(__file__),Path('tests/test_us_cash_merger_tapes.py'),root/'protocol.json',root/'cohort.json',ready/'report.json']
    atomic_json(out/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in sources},
        cash_date_convention_not_authorized_for_real_portfolio=True,no_model_or_sql_or_order=True,no_performance=True,
        price_selection='Fixed original5cases; no symbol dropped for future return. Only legal-closing synthetic rows excluded from executions, retained in quarantine.'))
    pd.DataFrame(tapes).to_parquet(out/'pre-closing-bars.parquet',index=False)
    atomic_json(out/'closing-row-quarantine.json',quarantine);atomic_json(out/'cash-action-reconciliation.json',cash)
    result=dict(status='PASS_COHORT_LIFECYCLE_PRE_CLOSING_TAPES_WITH_PAYMENT_RESERVE',
        initial_filings=13,excluded_by_initial_terms=8,term_eligible=5,documented_legal_completions=5,
        terminated_in_eligible_subset=0,unresolved_in_eligible_subset=0,not_five_winning_trades=True,
        lifecycle_filings=23,complete_numbered_amendments=15,other_8k=8,
        pre_closing_bars=len(tapes),quarantined_closing_rows=len(quarantine),
        provider_cash_records=len(actions['cash_mergers']),economic_cash_rights=5,
        provider_payable_dates=5,broker_spendable_dates_qualified=0,rows=summaries,
        sec_new_http_requests=len(list((root/'http').glob('*.json'))),alpaca_requests=READ(ready/'download.json')['new_requests'],
        caveats=['13initialSC TO-T filings, not all cash acquisitions; sample5not failure-risk estimate',
            'NGM non-rollover PUBLIC shares only, not insider rollover contract',
            'Historical supplier versions today, not original local reception or vintage PIT',
            'First worldwide announcement not certified; conservative post-initial-filing entry proxy only',
            'Plaintext of amendments can retain strikethrough deletions, not generic semantic/legal diff certification',
            'Provider payable date not actual broker credited buying power, no live parity',
            'No return, profit, win rate, drawdown or strategy efficacy evaluated'],
        no_performance=True,no_sql_writes=True,no_orders=True,
        files={f.name:digest(f) for f in out.glob('*') if f.is_file()})
    atomic_json(out/'report.json',result);print(result['status'],len(tapes),'bars',len(quarantine),'quarantined',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    audit_build(p.parse_args().root)
