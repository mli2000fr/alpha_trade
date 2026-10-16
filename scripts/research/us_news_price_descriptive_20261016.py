"""Frozen small news-tone/5m-price description. No PnL, training or API calls.

Prepare BEFORE price extraction; use existing subject-reviewed texts only.
Retrospective human-like tone is not FinBERT, a calibrated score or a PIT signal.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, create_engine, text
from scripts.research import us_news_event_qualification as evidence
from scripts.research.us_news_financing_feasibility import windows, assess, FIVE
from scripts.research.us_news_financing_closure_20261016 import checked_reading

EXCLUDED_RIGHTS_SYMBOLS={'MSCI'}
TONES={'POSITIVE','NEGATIVE','MIXED_OR_NEUTRAL'}
NY=ZoneInfo('America/New_York')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def select_cohort(items,reviews,labels,now):
    by_key={r['evidence_key']:r for r in reviews}
    selected=[]
    exclusions=[]
    seen=set()
    for row in sorted(items,key=lambda r:r['evidence_key']):
        review=by_key[row['evidence_key']]
        reason=('SUBJECT_NOT_MATCHED' if not review['identity_verified'] else
                'EXISTING_RIGHTS_RESERVATION' if row['symbol'] in EXCLUDED_RIGHTS_SYMBOLS else
                'TEMPORAL_RESERVATION' if row['temporal_reservations'] else None)
        if reason:
            exclusions.append(dict(evidence_key=row['evidence_key'],symbol=row['symbol'],reason=reason))
            continue
        key=row['symbol'],row['text_hash']
        if key in seen:
            raise ValueError('Duplicate symbol/text; explicit deduplication required')
        seen.add(key)
        tone,field,quote,note=labels[row['article_id']]
        start=row['fields'].get(field,'').find(quote)
        if tone not in TONES or start<0 or len(quote.strip())<10:
            raise ValueError('Exact tone quotation required before prices')
        selected.append(dict(row,tone=tone,tone_rationale=note,
            tone_quote=dict(field=field,start=start,end=start+len(quote),text=quote),
            tone_available_at=now,tone_method='RETROSPECTIVE_CODEX_TECHNICAL_READING_NOT_FINBERT',
            independent_review=False,historical_instrument_identity_certified=False,
            legacy_keyword_control=not row['screened']))
    if {r['article_id'] for r in selected}!=set(labels):
        raise ValueError('Labels must cover exactly the selected articles, no silent exclusions')
    return selected,exclusions


def prepare(pack,labels_path,output):
    _,items,reviews=checked_reading(pack)
    if output.exists():
        raise FileExistsError('Fresh immutable experiment required')
    now=datetime.now(timezone.utc)
    selected,excluded=select_cohort(items,reviews,read(labels_path),now)
    source_protocol=read(pack/'protocol.json')
    protocol=dict(version='NEWS_PRICE_DESCRIPTIVE_V1',created_at_utc=now,
        source_news_cutoff_utc=source_protocol['cutoff_utc'],price_observation_cutoff_utc=now,
        source_scope='previously selected financing-review bodies and controls, NOT representative of all news',
        selection='All subject-matched pairs in completed frozen pack, excluding MSCI rights reservation; no price selection',
        tone_definition='Subject-specific favourable/adverse/mixed-neutral prose, not future realised direction or probability',
        tone_labels_fixed_before_price_queries=True,tone_labels_sha256=evidence.sha(labels_path),
        source_hashes={str(pack/p):evidence.sha(pack/p) for p in
            ('protocol.json','report.json','evidence.json','technical_review_filled.json','technical_review_result.json')},
        source_publication_window_not_shifted=True,
        price_clock='New explicitly frozen observation cutoff; not a replacement of old news cutoff',
        anchors=['publication','receipt'],receipt_anchor='max(text_available_at,mapping_available_at)',
        actual_label_available_at=now,receipt_panel_is_not_tradable_signal=True,
        window='6 regular 5m bars before and 6 after; containing off-grid bar excluded; outside RTH previous close to next open',
        return_definitions=dict(before_30m='last before close / first before open - 1',
            after_30m='last after close / first after open - 1',
            gap='first after open / last before close - 1',
            bridge='last after close / last before close - 1'),
        provider='alpaca',data_source='alpaca_sip',adjustment='raw',fallback=False,
        no_price_filling=True,no_p_values=True,no_independence_claim=True,no_multiple_threshold_search=True,
        no_causal_inference=True,no_macro_or_sector_control=True,no_split_dividend_qualification=True,
        receipts_are_real_not_backfilled=True,api_calls=0,llm_calls=0,sql_writes=False,
        training=False,economic_test=False,orders=False,code_sha256=evidence.sha(Path(__file__)))
    output.mkdir(parents=True)
    evidence.save(output/'protocol.json',protocol)
    evidence.save(output/'cohort.json',selected)
    evidence.save(output/'exclusions.json',excluded)
    manifest=dict(status='FROZEN_BEFORE_PRICE_EXTRACTION',cohort_pairs=len(selected),
        tone_counts=dict(Counter(r['tone'] for r in selected)),
        excluded_counts=dict(Counter(r['reason'] for r in excluded)),
        files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'preparation_report.json',manifest)
    return manifest


def reaction(plan,rows,cutoff):
    # One fixed provider/feed only, never stitch a 12-bar window across sources.
    usable=[r for r in rows if r['provider']=='alpaca' and r['data_source']=='alpaca_sip'
        and r.get('observed_at') is not None and evidence.utc(r['observed_at'],database=True)<=cutoff]
    coverage=assess(plan,usable,cutoff)
    if coverage['status']!='COMPLETE_SINGLE_SOURCE_WINDOW':
        return dict(coverage=coverage,metrics=None)
    before=[next(r for r in usable if evidence.utc(r['bar_timestamp'],database=True)==plan['before_start']+i*FIVE) for i in range(6)]
    after=[next(r for r in usable if evidence.utc(r['bar_timestamp'],database=True)==plan['after_start']+i*FIVE) for i in range(6)]
    metrics=dict(before_30m_pct=100*(float(before[-1]['close'])/float(before[0]['open'])-1),
        after_30m_pct=100*(float(after[-1]['close'])/float(after[0]['open'])-1),
        gap_pct=100*(float(after[0]['open'])/float(before[-1]['close'])-1),
        bridge_pct=100*(float(after[-1]['close'])/float(before[-1]['close'])-1),
        before_first_open=float(before[0]['open']),before_last_close=float(before[-1]['close']),
        after_first_open=float(after[0]['open']),after_last_close=float(after[-1]['close']),
        calculation_not_profit=True,historical_bar_availability_certified=False)
    return dict(coverage=coverage,metrics=metrics)


def summary(rows,anchor):
    panel=[r for r in rows if r['anchor']==anchor]
    complete=[r for r in panel if r['metrics'] is not None]
    groups={}
    for tone in sorted(TONES):
        group=[r for r in complete if r['tone']==tone]
        direction={'POSITIVE':1,'NEGATIVE':-1}.get(tone)
        def count(field):
            return sum(direction*r['metrics'][field]>0 for r in group) if direction else None
        groups[tone]=dict(n=len(group),
            means_pct={f:mean(r['metrics'][f] for r in group) if group else None for f in
                ('before_30m_pct','after_30m_pct','gap_pct','bridge_pct')},
            medians_pct={f:median(r['metrics'][f] for r in group) if group else None for f in
                ('before_30m_pct','after_30m_pct','gap_pct','bridge_pct')},
            aligned_before=count('before_30m_pct'),aligned_after=count('after_30m_pct'),
            aligned_bridge=count('bridge_pct'),
            alignment_is_not_directional_accuracy=True)
    return dict(total_pairs=len(panel),complete_pairs=len(complete),
        coverage=dict(Counter(r['coverage']['status'] for r in panel)),groups=groups,
        distinct_publication_ny_dates=len({r['publication_ny_date'] for r in complete}),
        distinct_symbols=len({r['symbol'] for r in complete}),
        symbol_publication_date_clusters=len({(r['symbol'],r['publication_ny_date']) for r in complete}),
        no_independence_or_significance_claim=True)


def run(experiment):
    manifest=read(experiment/'preparation_report.json')
    for name,digest in manifest['files'].items():
        if Path(name).name!=name or evidence.sha(experiment/name)!=digest:
            raise ValueError('Frozen protocol/cohort changed')
    output=experiment/'results'
    if output.exists():
        raise FileExistsError('Immutable results already exist')
    protocol=read(experiment/'protocol.json')
    cohort=read(experiment/'cohort.json')
    cutoff=evidence.utc(protocol['price_observation_cutoff_utc'])
    from common.market_calendar import get_market_calendar
    from database.connection import get_sqlalchemy_engine
    anchors=[evidence.utc(r[k]) for r in cohort for k in ('publication_utc','text_available_at','mapping_available_at')]
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    sessions=calendar.sessions((min(anchors)-timedelta(days=10)).date(),(max(anchors)+timedelta(days=10)).date())
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    cache={}
    results=[]
    sentiment=[]
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US alpha_trade required')
            ids=sorted({r['article_id'] for r in cohort})
            q=text('''SELECT article_id,symbol,model_name,model_version,text_hash,sentiment_label,
                positive_score,neutral_score,negative_score,inference_status,created_at,updated_at
                FROM news_ticker_sentiment WHERE article_id IN :ids''').bindparams(bindparam('ids',expanding=True))
            keys={(r['article_id'],r['symbol']) for r in cohort}
            sentiment=[dict(r) for r in conn.execute(q,{'ids':ids}).mappings() if (r['article_id'],r['symbol']) in keys]
            for item in cohort:
                receipt=max(evidence.utc(item['text_available_at']),evidence.utc(item['mapping_available_at']))
                for anchor,when in (('publication',evidence.utc(item['publication_utc'])),('receipt',receipt)):
                    plan=windows(when,sessions)
                    bars=[]
                    if plan['status']=='PLANNED' and plan['after_end']<=cutoff:
                        key=(item['symbol'],plan['before_start'],plan['after_start'])
                        if key not in cache:
                            params={'symbol':item['symbol'],**{k:plan[k].replace(tzinfo=None) for k in
                                ('before_start','before_end','after_start','after_end')}}
                            fetched=[dict(r) for r in conn.execute(text('''SELECT symbol,bar_timestamp,
                                bar_end_timestamp,interval_code,market_code,provider,data_source,open,high,
                                low,close,volume,is_filled,data_adjustment,session_tag,observed_at,payload_hash
                                FROM stock_bars_intraday WHERE symbol=:symbol AND interval_code='5m'
                                AND provider='alpaca' AND data_source='alpaca_sip'
                                AND ((bar_timestamp>=:before_start AND bar_timestamp<:before_end)
                                  OR (bar_timestamp>=:after_start AND bar_timestamp<:after_end))
                                ORDER BY bar_timestamp LIMIT 241'''),params).mappings()]
                            if len(fetched)>240:
                                raise ValueError('Bounded query truncated')
                            for r in fetched:
                                for field in ('open','high','low','close'):
                                    r[field]=float(r[field])
                            cache[key]=fetched
                        bars=cache[key]
                    checked=reaction(plan,bars,cutoff)
                    results.append(dict(evidence_key=item['evidence_key'],article_id=item['article_id'],symbol=item['symbol'],
                        headline=item['fields']['headline'],tone=item['tone'],legacy_keyword_control=item['legacy_keyword_control'],
                        publication_ny_date=str(evidence.utc(item['publication_utc']).astimezone(NY).date()),
                        anchor=anchor,anchor_at=when,publication_utc=item['publication_utc'],
                        receipt_available_at=receipt,tone_available_at=item['tone_available_at'],plan=plan,**checked,
                        publication_window_ended_before_receipt=(plan.get('after_end') is not None and plan['after_end']<receipt)
                            if anchor=='publication' else None,
                        prospective_score_binding_proven=False,tradable_signal=False))
            conn.rollback()
    finally:
        engine.dispose()
    # Freeze the extracted inputs before saving any interpreted aggregate.
    output.mkdir()
    evidence.save(output/'intraday_rows.json',[dict(symbol=k[0],before_start=k[1],after_start=k[2],rows=v) for k,v in cache.items()])
    evidence.save(output/'current_contextual_sentiment.json',dict(rows=sentiment,
        score_snapshot_available_at=datetime.now(timezone.utc),used_for_tone_or_returns=False,
        text_version_binding_proven=False,historical_available_at_proven=False))
    evidence.save(output/'cases.json',results)
    report=dict(status='EXPLORATORY_DESCRIPTION_ONLY_NOT_A_SIGNAL',created_at_utc=datetime.now(timezone.utc),
        cohort_pairs=len(cohort),cohort_tone_counts=dict(Counter(r['tone'] for r in cohort)),
        publication=summary(results,'publication'),receipt=summary(results,'receipt'),
        current_contextual_score_rows=len(sentiment),contextual_scores_used=False,
        polarity_source='Frozen retrospective qualitative reading, NOT stored FinBERT scores or calibrated probabilities',
        comments=['Not a causal test: price movement may precede commentary; simultaneous news and market moves uncontrolled.',
            'Neutral/mixed prose and legacy unscreened controls are not a matched no-news control group.',
            'Raw overnight gaps may contain dividends/actions; no economic or action-adjusted interpretation.',
            'Receipt panel uses retrospective tone unavailable then; no execution advantage claimed.',
            'No extension of this small, finance-keyword-enriched sample to all news, Oracle TOP20 or D1/D10.'],
        inference='INSUFFICIENT_FOR_PREDICTIVE_OR_PROFITABILITY_CONCLUSION',
        api_calls=0,llm_calls=0,sql_writes=False,training=False,economic_test=False,orders=False,
        source_protocol_sha256=evidence.sha(experiment/'protocol.json'),cohort_sha256=evidence.sha(experiment/'cohort.json'),
        code_sha256=evidence.sha(Path(__file__)),files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--pack',type=Path)
    parser.add_argument('--labels',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.phase=='prepare':
        if not args.pack or not args.labels:
            parser.error('prepare requires pack/labels')
        result=prepare(args.pack,args.labels,args.output)
    else:
        result=run(args.output)
    print(json.dumps(evidence.archive.json_value(result),ensure_ascii=False))
