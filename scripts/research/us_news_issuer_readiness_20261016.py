"""Research-only issuer anchors and intraday readiness; no collection or signals.

Explicit venue collisions can reserve a pair. A positive name/ticker anchor
only routes to review: it never proves the issuer of a financing clause.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from scripts.research import us_news_event_qualification as evidence
from scripts.research.us_news_financing_feasibility import read_pack

US_VENUES={'NASDAQ','NYSE','NYSEAMERICAN','AMEX','OTC','OTCQB','OTCQX'}
FOREIGN_VENUES={'CSE','TSXV','TSX','LSE','AIM','ASX','XETRA','XTRA','HKEX'}
MENTION=re.compile(r'\b(NASDAQ|NYSE\s*AMERICAN|NYSE|AMEX|OTCQB|OTCQX|OTC|CSE|TSXV|TSX|LSE|AIM|ASX|XETRA|XTRA|HKEX)\s*:\s*([A-Z0-9][A-Z0-9.\-]{0,19})\b',re.I)
LEGAL_WORDS={'inc','incorporated','corporation','company','limited','ltd','co','plc',
    'common','stock','ordinary','shares','adr','ads','class','unsponsored','netherlands','lp'}
GENERIC_WORDS={'financial','group','holding','holdings','services','systems','international',
    'global','first','the','and','trust','fund','class'}


def issuer_anchor(item,reference):
    body=' '.join(item['fields'].get(k) or '' for k in ('headline','summary','content'))
    mentions=[dict(venue=re.sub(r'\s+','',m[1].upper()),symbol=m[2].upper().rstrip('.'))
              for m in MENTION.finditer(body)]
    symbol=item['symbol'].upper()
    local_venue=str((reference or {}).get('exchange') or '').upper().replace(' ','')
    domestic=[r for r in mentions if r['symbol']==symbol and r['venue'] in US_VENUES]
    foreign=[r for r in mentions if r['symbol']==symbol and r['venue'] in FOREIGN_VENUES]
    words={w for w in re.findall(r'[a-z0-9]+',str((reference or {}).get('company_name') or '').lower())
           if len(w)>2 and w not in LEGAL_WORDS|GENERIC_WORDS}
    body_words=set(re.findall(r'[a-z0-9]+',body.lower()))
    name_hint=bool(words) and words<=body_words
    if reference is None:
        status='RESERVED_CURRENT_REFERENCE_MISSING'
    elif local_venue in US_VENUES and foreign and not domestic:
        status='RESERVED_EXPLICIT_CROSS_MARKET_COLLISION'
    elif domestic:
        status='REVIEW_REQUIRED_EXPLICIT_US_TICKER'
    elif name_hint:
        status='REVIEW_REQUIRED_NAME_HINT_ONLY'
    else:
        status='RESERVED_NO_EXPLICIT_LOCAL_ISSUER_ANCHOR'
    return dict(evidence_key=item['evidence_key'],symbol=symbol,status=status,
        current_reference_name=(reference or {}).get('company_name'),
        current_reference_exchange=local_venue,explicit_mentions=mentions,
        lexical_name_hint=name_hint,name_hint_is_identity_proof=False,
        issuer_of_financing_clause_verified=False,metadata_is_historical_pit=False,
        identity_qualified=False,event_qualified=False,tradable_signal=False)


def planned_request(items,reviews,diagnostics,now):
    """Plan by reviewed identity, never by price or direction. No API is called."""
    known={r['evidence_key']:r for r in items}
    gates={r['evidence_key']:r for r in diagnostics}
    # A textual subject match is still not event approval. Prefer only these
    # names for a bounded technical data-coverage test, including controls.
    selected=sorted({known[r['evidence_key']]['symbol'] for r in reviews
        if r.get('identity_verified') is True
        and gates[r['evidence_key']]['status'].startswith('REVIEW_REQUIRED_')})
    last_closed_day=now.astimezone(ZoneInfo('America/New_York')).date()-timedelta(days=1)
    return dict(status='PREPARED_NOT_EXECUTED',symbols=selected,symbol_count=len(selected),
        selection='Previously reviewed issuer/subject match plus no explicit venue collision; not an investment selection',
        technical_coverage_only=True,provider='alpaca',alpaca_feed='sip',account_id='default',
        interval='5m',start_date='2026-10-13',end_date=str(min(last_closed_day,datetime(2026,10,15).date())),
        deferred_dates=['2026-10-16'],
        deferred_reason='Existing backfill CLI only accepts end dates strictly before current New York date; do not bypass current-session guard',
        expected_symbol_slices=len(selected),
        proposed_universe_file='config/univers/research_news_issuer_20261016.txt',
        universe_file_created=False,requires_explicit_collection_go=True,
        creates_historical_news_availability=False,
        historical_bars_download_would_not_prove_historical_bar_availability=True,
        no_cost_or_access_guarantee=True,api_calls=0,sql_writes=False)


def run(pack,output):
    if output.exists():
        raise FileExistsError('Fresh output required')
    protocol,source,items,checked=read_pack(pack)
    references_path=pack/'technical_reference_snapshot.json'
    references=json.loads(references_path.read_text(encoding='utf-8'))
    reviews=json.loads((pack/'technical_review_filled.json').read_text(encoding='utf-8'))
    if any(r['current_reference_sha256']!=evidence.sha(references_path) for r in reviews):
        raise ValueError('Changed reference snapshot')
    by_symbol={r['symbol']:r for r in references['rows']}
    diagnostics=[issuer_anchor(item,by_symbol.get(item['symbol'])) for item in items]
    now=datetime.now(timezone.utc)
    latest=[]
    from database.connection import get_sqlalchemy_engine
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US schema required')
            for symbol in sorted({r['symbol'] for r in items}):
                row=conn.execute(text('''SELECT bar_timestamp,bar_end_timestamp,provider,data_source,
                    observed_at FROM stock_bars_intraday WHERE symbol=:symbol AND interval_code='5m'
                    AND bar_timestamp<:cutoff ORDER BY bar_timestamp DESC LIMIT 1'''),
                    {'symbol':symbol,'cutoff':now.replace(tzinfo=None)}).mappings().first()
                latest.append(dict(symbol=symbol,latest_row=dict(row) if row else None,
                    single_latest_row_not_full_history_audit=True))
            conn.rollback()
    finally:
        engine.dispose()
    # A limited inventory of the three existing plans is enough to establish
    # their requested end date; no raw payload, token, stdout or command dump.
    plans=[]
    root=Path('artifacts/intraday_backfill')
    for file in sorted(root.glob('*/plan.json')):
        plan=json.loads(file.read_text(encoding='utf-8'))
        if plan.get('market_code')=='US_EQ' and plan.get('interval')=='5m':
            plans.append(dict(path=str(file),sha256=evidence.sha(file),
                **{key:plan.get(key) for key in ('plan_id','start_date','end_date','provider','alpaca_feed')},
                symbols=len(plan.get('symbols',[]))))
    request=planned_request(items,reviews,diagnostics,now)
    output.mkdir(parents=True)
    evidence.save(output/'issuer_anchor_diagnostics.json',diagnostics)
    evidence.save(output/'latest_intraday_rows.json',latest)
    evidence.save(output/'backfill_request.json',request)
    # Command is intentionally not issued; proposed subset file does not exist yet.
    command=['python','-u','-m','service.market.intraday_backfill','--provider','alpaca',
        '--alpaca-feed','sip','--account-id','default','--interval','5m','--chunk-days','7',
        '--start-date',request['start_date'],'--end-date',request['end_date'],
        '--symbol-source','universe-file:'+request['proposed_universe_file'],'--plan-only']
    result=dict(status='RESEARCH_IDENTITY_GUARD_AND_TARGETED_REQUEST_PREPARED',created_at_utc=now,
        source_publication_cutoff_unchanged=protocol['cutoff_utc'],selected_pairs=len(items),
        anchor_counts=dict(Counter(r['status'] for r in diagnostics)),
        explicit_collision_symbols=sorted({r['symbol'] for r in diagnostics if r['status']=='RESERVED_EXPLICIT_CROSS_MARKET_COLLISION'}),
        latest_intraday_row_count=sum(r['latest_row'] is not None for r in latest),
        symbols_without_any_intraday_row=[r['symbol'] for r in latest if r['latest_row'] is None],
        latest_intraday_dates=dict(Counter(str(r['latest_row']['bar_timestamp'].date()) for r in latest if r['latest_row'])),
        existing_plan_inventory=plans,backfill_request=request,preview_command_not_executed=command,
        previously_read_sample_not_out_of_sample_validation=True,
        guard_is_production_integrated=False,guard_can_approve_identity=False,
        independent_review_certified=False,sql_writes=False,api_calls=0,llm_calls=0,
        models_changed=False,config_changed=False,returns_computed=False,economic_test=False,
        source_hashes={str(pack/name):evidence.sha(pack/name) for name in
            ('protocol.json','report.json','evidence.json','technical_review_filled.json',
             'technical_review_result.json','technical_reference_snapshot.json')},
        code_sha256=evidence.sha(Path(__file__)))
    result['files']={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()}
    evidence.save(output/'report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.pack,args.output)
    print(json.dumps({k:result[k] for k in ('status','anchor_counts','explicit_collision_symbols',
        'latest_intraday_dates','symbols_without_any_intraday_row','backfill_request')},ensure_ascii=False))
