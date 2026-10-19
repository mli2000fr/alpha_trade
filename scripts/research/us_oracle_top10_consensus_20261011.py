"""Read-only, preliminary comparison of archived TOP10 and 11 October consensus.

No provider/LLM, training, SQL writes, backtest engine or order. Selection and
two descriptive sign rules fixed before reading subsequent price outcomes.
"""
import argparse
from collections import Counter
from datetime import date,datetime,timedelta,timezone
import json
import math
from pathlib import Path

from sqlalchemy import bindparam,event,text

from service.llm_directional.repository import dumps,digest

RUN_ID='llm-bc155d0d71484217b0bdc98cd9e06c7d'
SNAPSHOT=date(2026,10,11)
FIELDS=('eps_avg','eps_current','eps_7d_ago','eps_30d_ago','eps_60d_ago','eps_90d_ago',
    'eps_analyst_count','revenue_avg','revenue_analyst_count','revisions_up_7d','revisions_down_7d',
    'revisions_up_30d','revisions_down_30d','units_qualified','fiscal_identity_qualified',
    'historical_pit_qualified','qualification_status','currency')


def number(value):
    if value is None:return None
    if isinstance(value,bool):raise ValueError('Boolean numeric input')
    result=float(value)
    if not math.isfinite(result):raise ValueError('Nonfinite numeric input')
    return result


def direction(value):
    return 'MISSING' if value is None else 'UP' if value>0 else 'DOWN' if value<0 else 'UNCHANGED'


def signals(consensus):
    current=number(consensus.get('eps_current'));prior=number(consensus.get('eps_7d_ago'))
    prior30=number(consensus.get('eps_30d_ago'))
    delta=None if current is None or prior is None else current-prior
    up=number(consensus.get('revisions_up_30d'));down=number(consensus.get('revisions_down_30d'))
    net=None if up is None or down is None else up-down
    return dict(eps_7d_direction=direction(delta),eps_7d_delta=delta,
        eps_7d_change_pct=100*delta/abs(prior) if delta is not None and prior!=0 else None,
        eps_30d_change_pct=100*(current-prior30)/abs(prior30) if current is not None and prior30 not in (None,0) else None,
        revisions_30d_direction=direction(net),revisions_30d_net=net)


def outcome(bars,prediction_day,entry_day,expected_days):
    by_day={str(b['date'])[:10]:b for b in bars}
    required=[str(prediction_day),*[str(d) for d in expected_days]]
    if not all(d in by_day for d in required):return dict(status='MISSING_BAR')
    selected=[by_day[d] for d in required]
    for row in selected:
        prices=[number(row[k]) for k in ('open','high','low','close')]
        if (row['is_filled'] or any(p is None or p<=0 for p in prices)
                or not prices[2]<=min(prices[0],prices[3])<=max(prices[0],prices[3])<=prices[1]):
            return dict(status='INVALID_OHLC')
    baseline=by_day[str(prediction_day)];entry=by_day[str(entry_day)];latest=selected[-1]
    future=[by_day[str(d)] for d in expected_days]
    entry_price=number(entry['open']);last=number(latest['close'])
    provenance={(b['data_source'],b['data_adjustment']) for b in selected}
    allowed={'eodhd','eodhd_eod','alpaca_sip'}
    qualified=len(provenance)==1 and all(p[0] in allowed for p in provenance)
    return dict(status='AVAILABLE' if qualified else 'UNQUALIFIED_PROVENANCE',
        baseline_close=number(baseline['close']),baseline_date=str(prediction_day),
        entry_open=entry_price,entry_date=str(entry_day),latest_close=last,latest_date=str(latest['date'])[:10],
        close_to_close_pct=100*(last/number(baseline['close'])-1),
        entry_to_latest_pct=100*(last/entry_price-1),
        max_up_from_entry_pct=100*(max(number(b['high']) for b in future)/entry_price-1),
        max_down_from_entry_pct=100*(min(number(b['low']) for b in future)/entry_price-1),
        observed_sessions=len(expected_days),provenance=[list(p) for p in sorted(provenance)],
        warning='Price-only description, not realized portfolio PnL; no dividends, costs, stops or leverage.')


def summarize(rows,key):
    valid=[r for r in rows if r.get('prices',{}).get('status')=='AVAILABLE']
    active=[r for r in valid if r['signals'][key] in ('UP','DOWN')]
    correct=sum((r['signals'][key]=='UP' and r['prices']['entry_to_latest_pct']>0)
        or (r['signals'][key]=='DOWN' and r['prices']['entry_to_latest_pct']<0) for r in active)
    groups={}
    for label in ('UP','DOWN','UNCHANGED','MISSING'):
        group=[r for r in valid if r['signals'][key]==label]
        returns=[r['prices']['entry_to_latest_pct'] for r in group]
        groups[label]=dict(n=len(group),price_up=sum(v>0 for v in returns),price_down=sum(v<0 for v in returns),
            mean_price_return_pct=sum(returns)/len(returns) if returns else None)
    return dict(rule=key,active_n=len(active),same_direction_n=correct,
        same_direction_pct=100*correct/len(active) if active else None,groups=groups,
        interpretation='DESCRIPTIVE_SHORT_WINDOW_ONLY_NOT_H20_VALIDATION')


def run(engine,output):
    from common.market_calendar import get_market_calendar
    if engine.url.database!='alpha_trade':raise ValueError('US only')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    now=datetime.now(timezone.utc)
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    prediction_day=max(calendar.session_dates(SNAPSHOT-timedelta(days=10),SNAPSHOT))
    entry_day=calendar.next_session(SNAPSHOT)
    entry_at,_=calendar.session_bounds(entry_day)
    closed=[s.session_date for s in calendar.sessions(entry_day,now.date()) if s.is_open and s.close_at_utc<=now]
    if not closed:raise ValueError('No closed forward session')
    latest=closed[-1]
    horizon=calendar.session_dates(entry_day,entry_day+timedelta(days=50))[:20]
    policy=dict(snapshot_date=str(SNAPSHOT),oracle_prediction_date=str(prediction_day),entry_date=str(entry_day),
        consensus_cutoff_exclusive_utc=entry_at.isoformat(),latest_closed_session=str(latest),
        rule_one='Sign of eps_current minus eps_7d_ago, raw horizon 0q, nearest fiscal period J-120..J+400.',
        rule_two='Sign of revisions_up_30d minus revisions_down_30d, same period/horizon.',
        missing_policy='NULL stays unknown; zero is neutral; no substitution between horizons or fields.',
        selection='First ten oracle_rank from exact archived run; never rerank using future price.',
        no_threshold_optimization=True,h20_last_session=str(horizon[-1]),
        read_only=True,no_llm=True,no_provider_download=True)
    (output/'protocol.json').write_text(dumps(policy),encoding='utf-8')

    def guard(c,cu,sql,p,ct,m):
        if not sql.lstrip().upper().startswith('SELECT'):raise ValueError('SELECT only')
    event.listen(engine,'before_cursor_execute',guard)
    try:
        with engine.connect() as conn:
            archived=conn.execute(text('SELECT * FROM llm_directional_runs WHERE run_id=:r'),dict(r=RUN_ID)).mappings().one()
            snapshot=json.loads(archived['input_json'])
            if digest(snapshot)!=archived['input_sha256']:raise ValueError('Archive hash mismatch')
            if archived['completed_at'].replace(tzinfo=timezone.utc)>=entry_at:raise ValueError('Selection saved after entry')
            selected=sorted(snapshot['candidates'],key=lambda c:c['oracle_rank'])[:10]
            if len(selected)!=10 or [c['oracle_rank'] for c in selected]!=list(range(1,11)):
                raise ValueError('Incomplete original TOP10')
            report=dict(protocol=policy,computed_at_utc=now.isoformat(),run_id=RUN_ID,
                batch_id=archived['batch_id'],archive_input_sha256=archived['input_sha256'],
                selection_available_at_utc=archived['completed_at'].isoformat()+'Z',
                ranking_archive_preserved_but_original_model_not_retrained=True,
                symbol_source=snapshot['symbol_source'],candidates=[])
            for candidate in selected:
                symbol=candidate['symbol']
                if candidate['trade_date']!=str(prediction_day):raise ValueError('Archive trade date mismatch')
                columns=','.join(FIELDS)
                sql=f'''SELECT id,provider,symbol,snapshot_date,fiscal_period_end,horizon_raw,
                    available_at,observed_at,raw_hash,raw_payload_json,{columns}
                    FROM stock_analyst_consensus_eodhd_history
                    WHERE provider='eodhd' AND symbol=:s AND snapshot_date=:d
                    AND observed_at<=available_at AND available_at<:cutoff
                    AND fiscal_period_end BETWEEN :since AND :until
                    ORDER BY horizon_raw,ABS(DATEDIFF(fiscal_period_end,:d)),fiscal_period_end'''
                values=conn.execute(text(sql),dict(s=symbol,d=SNAPSHOT,since=SNAPSHOT-timedelta(days=120),
                    until=SNAPSHOT+timedelta(days=400),cutoff=entry_at.replace(tzinfo=None))).mappings()
                periods={}
                for value in values:periods.setdefault(value['horizon_raw'],dict(value))
                primary=periods.get('0q',{})
                raw=primary.get('raw_payload_json','{}');raw=json.loads(raw) if isinstance(raw,str) else raw
                prices=[dict(r) for r in conn.execute(text('''SELECT symbol,date,open,high,low,close,volume,
                    data_source,data_adjustment,is_filled,ingested_at,last_updated FROM stock_bars_daily
                    WHERE symbol=:s AND date BETWEEN :d AND :last ORDER BY date'''),
                    dict(s=symbol,d=prediction_day,last=latest)).mappings()]
                price_result=outcome(prices,prediction_day,entry_day,closed)
                reference=[b for b in candidate.get('prices_through_decision_date',[]) if str(b['date'])[:10]==str(prediction_day)]
                reference_price=number(reference[0]['close']) if reference else None
                archived_price_matches=reference_price==price_result.get('baseline_close') if reference_price is not None else None
                row=dict(symbol=symbol,oracle_rank=candidate['oracle_rank'],oracle_score=candidate['oracle_score'],
                    company_name=candidate['issuer_reference'].get('company_name'),consensus_primary=primary,
                    consensus_other_periods=periods,signals=signals(primary),prices=price_result,
                    archived_baseline_close=reference_price,baseline_matches_archive=archived_price_matches,
                    down_7d_present_in_raw='epsRevisionsDownLast7days' in raw)
                report['candidates'].append(row)
                print(dumps(dict(symbol=symbol,rank=row['oracle_rank'],prices=price_result,signals=row['signals'])),flush=True)
            report['summary']=dict(rules=[summarize(report['candidates'],key) for key in ('eps_7d_direction','revisions_30d_direction')],
                price_statuses=dict(Counter(c['prices']['status'] for c in report['candidates'])),
                baseline_mismatches=[c['symbol'] for c in report['candidates'] if c['baseline_matches_archive'] is False],
                missing_down_7d_in_provider=[c['symbol'] for c in report['candidates'] if not c['down_7d_present_in_raw']],
                observed_sessions=len(closed),h20_mature=latest>=horizon[-1])
            market_bars=[dict(r) for r in conn.execute(text('''SELECT symbol,date,open,high,low,close,volume,
                data_source,data_adjustment,is_filled FROM stock_bars_daily WHERE symbol='SPY'
                AND date BETWEEN :d AND :last ORDER BY date'''),dict(d=prediction_day,last=latest)).mappings()]
            report['benchmark_spy']=outcome(market_bars,prediction_day,entry_day,closed)
            actions=text('''SELECT symbol,provider,action_type,effective_date,value_num,related_symbol,
                available_at FROM corporate_action_source_events WHERE symbol IN :symbols
                AND effective_date>:d AND effective_date<=:last AND available_at<:now
                ORDER BY symbol,effective_date''').bindparams(bindparam('symbols',expanding=True))
            report['known_corporate_actions']=[dict(r) for r in conn.execute(actions,
                dict(symbols=[c['symbol'] for c in selected],d=prediction_day,last=latest,now=now.replace(tzinfo=None))).mappings()]
            report['corporate_action_warning']='Known events only, not exhaustive independent price/identity verification; split-adjusted price returns exclude dividends.'
            (output/'report.json').write_text(dumps(report),encoding='utf-8')
            return report
    finally:
        event.remove(engine,'before_cursor_execute',guard)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    report=run(get_sqlalchemy_engine(),args.output)
    print('SUMMARY '+dumps(report['summary']))


if __name__=='__main__':main()
