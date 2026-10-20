"""Validate manual terms then audit date coverage only: no prices/returns evaluated."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata

import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_cash_merger_feasibility import READ, prepare
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

REVIEW=Path('doc/ml/sources/cash_merger_review_20261020.json')


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',value).replace('\u200b','').split()).casefold()


def validate_review(root):
    protocol=prepare(root);report=READ(root/'report.json');verify_hashes(root,report['files'])
    review=READ(REVIEW);rows=review['rows'];selected={r['accession']:r for r in report['rows']}
    if len(rows)!=protocol['sample_size'] or {r['accession'] for r in rows}!=set(selected):
        raise ValueError('Review must account for original complete sample, no replacements')
    result=[];calendar=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2024-04-10')
    for row in rows:
        original=selected[row['accession']];document=READ(root/original['review_file'])
        subject=re.search(r'SUBJECT COMPANY:(.*?)(?=FILED BY:|</SEC-HEADER>)',document['header'],re.S)
        if not subject:raise ValueError('Missing target identity')
        cik=re.search(r'CENTRAL INDEX KEY:\s*(\d+)',subject.group(1))
        name=re.search(r'COMPANY CONFORMED NAME:\s*([^\r\n]+)',subject.group(1))
        if not cik or not name or cik.group(1).zfill(10)!=row['target_cik'] or normalized(name.group(1))!=normalized(row['target']):
            raise ValueError('Target identity mismatch; never use indexed bidder as issuer')
        clauses=[]
        for evidence in row['evidence']:
            part=next((p for p in document['parts'] if p['filename']==evidence['filename']),None)
            if not part or normalized(evidence['contains']) not in normalized(part['text']):
                raise ValueError(f"Unsupported source clause {row['accession']} / {evidence['contains']}")
            clauses.append(dict(**evidence,source_review_file=original['review_file'],
                source_sha256=digest(root/original['review_file'])))
        if row['eligible'] and (not row['symbol'] or not row['offer_cash_usd'] or row['offer_cash_usd']<=0):
            raise ValueError('Eligible fixed cash terms incomplete')
        # Filed-day-only archive cannot prove morning public availability. Do NOT
        # promote the extraction's next-open-after-acceptance proxy to a safe fill.
        accepted=pd.Timestamp(document['accepted_utc']) if document['accepted_utc'] else None
        day_end=pd.Timestamp(original['filed']+' 23:59:59',tz='America/New_York').tz_convert('UTC')
        floor=max(accepted,day_end) if accepted is not None else None
        available=calendar[calendar.market_open.gt(floor)] if floor is not None else calendar.iloc[:0]
        first=str(available.index[0].date()) if len(available) else None
        window=[str(x.date()) for x in available.index[:5]]
        result.append(dict(**{k:v for k,v in row.items() if k!='evidence'},source_clauses=clauses,
            accepted_utc=document['accepted_utc'],filed=original['filed'],
            acceptance_only_open_proxy=document['first_full_session'],conservative_coverage_start=first,
            five_expected_sessions=window,actual_public_dissemination_proven=False,
            historical_target_cik_supported=True,contract_terms_supported=True,
            price_identity_chain_qualified=False,deal_outcome_known=False,
            expected_expiry_is_not_actual_closing_or_cash_credit=True))
    return result


def prepare_coverage(root):
    out=root/'coverage-v1';rows=validate_review(root)
    if (out/'protocol.json').exists():
        p=READ(out/'protocol.json');verify_hashes(Path('.'),p['sources']);return out,p
    if out.exists():raise ValueError('Fresh immutable coverage directory required')
    out.mkdir()
    paths=[Path(__file__),Path('tests/test_us_cash_merger_review.py'),REVIEW,root/'report.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(p):digest(p) for p in paths},rows=rows,
        question='Availability of dates only, no OHLC price/return/PnL analysis. Two fixed term-eligible cases, not positive outcomes.',
        local_sql='US READ ONLY UTC REPEATABLE READ, SELECT symbol/date/provenance/filled only 2023-2024 for two candidates, rollback; no writes.',
        supplier='At most2Alpaca GET /v2/stocks/bars, SIP raw/asof=-, five conservative initial sessions per symbol. No order, IEX fallback or retries, no paid upgrade. Archive source body but read dates/counts only.',
        coverage='Local2024 coverage beyond first5sessions not a required post-delist price; do not infer deal outcome from missing bars. Entire lifecycle and failed-deal sample still required.',
        budgets=dict(provider_requests=2,response_bytes=5*1024*1024,timeout_seconds=30),
        no_training=True,no_llm=True,no_order=True,no_sql_writes=True,no_performance=True)
    atomic_json(out/'protocol.json',p);return out,p


def local(root):
    from sqlalchemy import bindparam,create_engine,text
    from database.connection import get_sqlalchemy_engine
    out,p=prepare_coverage(root)
    if (out/'local.json').exists():raise ValueError('Immutable local coverage')
    symbols=[r['symbol'] for r in p['rows'] if r['eligible']]
    base=get_sqlalchemy_engine(db_name='alpha_trade')
    engine=create_engine(base.url,pool_size=1,max_overflow=0,connect_args={'connect_timeout':10,'read_timeout':25},echo=False)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'));conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('US only')
            query=text('''SELECT symbol,date,data_source,data_adjustment,is_filled FROM stock_bars_daily
                WHERE symbol IN :symbols AND date>='2023-01-01' AND date<='2024-12-31'
                ORDER BY symbol,date''').bindparams(bindparam('symbols',expanding=True))
            rows=[dict(r) for r in conn.execute(query,dict(symbols=symbols)).mappings()];conn.rollback()
    finally:engine.dispose()
    atomic_json(out/'local.json',dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),rows=rows,
        requested_symbols=symbols,no_price_values_read=True,no_sql_writes=True))
    print('Local dated bars',dict(Counter(r['symbol'] for r in rows)),flush=True)


def supplier(root):
    from common.public_data_http import verified_session
    from service.alpaca.clientAlpaca import _build_headers
    out,p=prepare_coverage(root);count=0
    if (out/'provider-report.json').exists():raise ValueError('Immutable supplier probe')
    with verified_session() as session:
        for row in [r for r in p['rows'] if r['eligible']]:
            symbol=row['symbol'];target=out/f'{symbol}-alpaca.json'
            if target.exists():continue
            if count>=p['budgets']['provider_requests']:raise ValueError('Probe budget')
            dates=row['five_expected_sessions'];params=dict(symbols=symbol,start=dates[0]+'T00:00:00Z',
                end=dates[-1]+'T23:59:59Z',timeframe='1Day',feed='sip',adjustment='raw',asof='-',sort='asc',limit=1000)
            count+=1
            response=session.get('https://data.alpaca.markets/v2/stocks/bars',params=params,
                headers=_build_headers('default'),timeout=(10,p['budgets']['timeout_seconds']))
            if len(response.content)>p['budgets']['response_bytes']:raise ValueError('Response cap')
            receipt=dict(endpoint='/v2/stocks/bars',params=params,observed_at_utc=datetime.now(timezone.utc).isoformat(),
                status_code=response.status_code,payload=response.json() if response.status_code==200 else None)
            atomic_json(target,receipt);print(symbol,'HTTP',response.status_code,flush=True)
            if response.status_code in (403,429):break
    atomic_json(out/'provider-report.json',dict(actual_new_requests=count,
        files={f.name:digest(f) for f in out.glob('*-alpaca.json')},no_price_values_evaluated=True))


def dates_from_receipt(r,symbol):
    if r['status_code']!=200:return dict(status='HTTP_UNAVAILABLE',dates=[])
    payload=r['payload']
    if payload.get('next_page_token'):return dict(status='UNEXPECTED_TRUNCATION',dates=[])
    other=set(payload.get('bars',{}))-{symbol}
    if other:raise ValueError('Provider returned wrong symbol')
    dates=[str(pd.Timestamp(b['t']).tz_convert('America/New_York').date()) for b in payload.get('bars',{}).get(symbol,[])]
    if len(dates)!=len(set(dates)):raise ValueError('Duplicate provider dates')
    return dict(status='DATES_RETURNED' if dates else 'EMPTY_NOT_AN_ERROR_NOT_PROOF_OF_NO_LISTING',dates=dates)


def build(root):
    out,p=prepare_coverage(root)
    if (out/'report.json').exists():raise ValueError('Immutable coverage result')
    verify_hashes(out,READ(out/'provider-report.json')['files']);local=READ(out/'local.json');results=[]
    for row in p['rows']:
        item=dict(**row)
        if row['eligible']:
            symbol=row['symbol'];expected=set(row['five_expected_sessions'])
            rows=[r for r in local['rows'] if r['symbol']==symbol]
            valid=[r for r in rows if not r['is_filled']]
            dates={str(r['date']) for r in valid};file=out/f'{symbol}-alpaca.json'
            provider=dates_from_receipt(READ(file),symbol) if file.exists() else dict(status='NOT_REQUESTED',dates=[])
            if not set(provider['dates']).issubset(expected):raise ValueError('Supplier probe outside fixed window')
            item.update(local_rows=len(rows),local_unfilled_rows=len(valid),
                local_min_date=min(dates) if dates else None,local_max_date=max(dates) if dates else None,
                local_first_five_present=len(dates&expected),local_first_five_missing=sorted(expected-dates),
                local_provenance=sorted({(r['data_source'],r['data_adjustment']) for r in rows}),
                alpaca_status=provider['status'],alpaca_first_five_present=len(set(provider['dates'])&expected),
                alpaca_first_five_missing=sorted(expected-set(provider['dates'])),
                price_values_quality_qualified=False,full_lifecycle_price_coverage_qualified=False)
        results.append(item)
    report=dict(status='FEASIBILITY_AUDIT_COMPLETE_NOT_READY_FOR_BACKTEST',filings=len(results),
        fixed_cash_term_candidates=sum(r['eligible'] for r in results),exclusion_reasons=dict(Counter(r['reason'] for r in results if not r['eligible'])),
        candidates_are_winners=False,rows=results,
        blockers=['Initial8of13tender filings, not full cash-merger population',
            'No complete outcome/amendment history yet: failure and termination coverage NOT certified',
            'No actual cash payment dates or broker treatment qualified',
            'Current ticker-price identity chain and corporate actions not qualified',
            'Dates-only initial-window probe is not full OHLCV/lifecycle certification',
            'No publicly demonstrable original local reception/vintage PIT'],
        no_pnl=True,no_sql_writes=True,no_orders=True,
        files={str(f.relative_to(out)):digest(f) for f in out.rglob('*') if f.is_file()})
    atomic_json(out/'report.json',report)
    print(report['status'],'cash term candidates',report['fixed_cash_term_candidates'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','local','supplier','build'],required=True);a=p.parse_args()
    if a.phase=='prepare':prepare_coverage(a.root)
    else:globals()[a.phase](a.root)
