"""Final frozen-case replay, using pre-price qualified identity supplements.

Same admission/timing/costs as confirmation_replay; original UNKNOWN capture is
preserved, not overwritten. No SQL, training, provider-price call or order.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.research.us_activist_13d_confirmation_replay import freeze,full_calendar,maturity,PRICE,SCORES,price_path,marks
from scripts.research.us_activist_13d_confirmation_identity import qualified_identities
from scripts.research.us_activist_13d_pilot import READ
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def json_records(frame):
    """Unknown/immature outcomes stay null, never NaN or zero in sealed JSON."""
    return frame.astype(object).where(pd.notna(frame),None).to_dict('records')


def run(root):
    reviewout,review=freeze(root);out=root/'replay-confirmation-final-v1'
    if out.exists():
        raise ValueError('Fresh immutable replay directory required')
    ids=qualified_identities(root);verify_hashes(root,ids['files'])
    known={r['accession']:r for r in ids['rows']};events=[r for r in review['rows'] if r['admitted']]
    files=[Path(__file__),Path('tests/test_us_activist_13d_confirmation_final.py'),Path('tests/test_us_activist_13d_confirmation_replay.py'),reviewout/'protocol.json',reviewout/'identity-capture.json',
           reviewout/'identity-qualified-v1.json',Path('scripts/research/us_activist_13d_confirmation_identity.py'),Path('tests/test_us_activist_13d_confirmation_identity.py'),PRICE,PRICE.parent/'quality-reserves.json',SCORES/'protocol.json',SCORES/'final-audit.json']
    expected=next(v for k,v in READ(SCORES/'protocol.json')['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected:
        raise ValueError('Frozen research price tape changed')
    for y in [2025,2026]:
        done=SCORES/f'{y}-done.json';score=SCORES/f'{y}-H20-scores.parquet'
        if digest(score)!=READ(done)['files'][score.name]:
            raise ValueError('Frozen scores changed')
        files.extend([done,score])
    out.mkdir()
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},events=events,
                  economic=review['economic'],price_end=review['price_end'],admissions_before_price_quality=True,
                  missing_or_immature_retained=True,not_portfolio_or_live_parity=True)
    atomic_json(out/'protocol.json',protocol)
    calendar=full_calendar();symbols=sorted({r['symbol'] for r in events}|{'SPY'})
    prices=pd.read_parquet(PRICE,filters=[('symbol','in',symbols),('date','>=',pd.Timestamp('2025-01-01')),('date','<=',pd.Timestamp(review['price_end']))])
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    decisions=[calendar.index[calendar.index.get_loc(pd.Timestamp(e['entry']))-1] for e in events]
    scores=pd.concat([pd.read_parquet(SCORES/f'{y}-H20-scores.parquet',columns=['date','symbol','rank','score'],
                     filters=[('date','in',[d for d in decisions if d.year==y])]) for y in [2025,2026]],ignore_index=True)
    if scores.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate Oracle context')
    rows=[];bars=[]
    for event,decision in zip(events,decisions):
        context=scores[(scores.date==decision)&scores.symbol.eq(event['symbol'])];n=int(scores.date.eq(decision).sum())
        rank=int(context.iloc[0]['rank']) if len(context)==1 else None
        for h in protocol['economic']['horizons']:
            mature,last,why=maturity(event['entry'],h,calendar.index,protocol['price_end'])
            row=dict(accession=event['accession'],symbol=event['symbol'],cik=event['cik'],event_year=event['event_year'],
                     quarter=event['quarter'],cohort=event['cohort'],filed=event['filed'],entry=event['entry'],
                     scope='PRIMARY' if event['active'] else 'SECONDARY_GOVERNANCE',horizon=h,mature=mature,required_exit_session=last,
                     case_kind=event.get('case_kind','UNSPECIFIED'),instrument_kind=event.get('instrument_kind','COMMON_EQUITY'),
                     earlier_public_action_date=event.get('earlier_public_action_date'),new_announcement_certified=False,
                     oracle_date=str(decision.date()),oracle_rank=rank,oracle_count=n,oracle_context_status='KNOWN' if rank is not None else 'UNKNOWN',
                     in_top10=rank<=10 if rank is not None else None,in_top20pct=rank<=int(np.ceil(.2*n)) if rank is not None else None)
            if not mature:
                row.update(status='IMMATURE',reason=why);rows.append(row);continue
            if not known.get(event['accession'],{}).get('identity'):
                row.update(status='UNKNOWN',reason='HISTORICAL_TICKER_NOT_SUPPORTED');rows.append(row);continue
            paths={};problems=[]
            for s in [event['symbol'],'SPY']:
                path,reason=price_path(groups.get(s,pd.DataFrame(columns=prices.columns)),calendar.index,pd.Timestamp(event['entry']),h,reserves.get(s))
                if path is None:
                    problems.append(s+':'+reason)
                else:
                    paths[s]=path
            if problems:
                row.update(status='UNKNOWN',reason=';'.join(problems));rows.append(row);continue
            c=protocol['economic'];bps=c['spread_bps_per_leg']+c['slippage_bps_per_leg']
            stock=marks(paths[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],bps)
            spy=marks(paths['SPY'],c['notional_usd'],c['commission_per_order_usd'],bps)
            stress=marks(paths[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],c['stress_total_bps_per_leg'])
            row.update(status='EXPLORATORY_ADJUSTED_MARK',reason=None,**stock,benchmark_net_return=spy['net_return'],
                       excess_vs_spy=stock['net_return']-spy['net_return'],stress_net_return=stress['net_return'])
            rows.append(row)
            for s,path in paths.items():
                frame=path.reset_index(names='date');frame['symbol']=s;frame['accession']=event['accession'];frame['horizon']=h;bars.append(frame)
    frame=pd.DataFrame(rows);frame.to_csv(out/'event-results.csv',index=False)
    prices.to_parquet(out/'source-price-snapshot.parquet',index=False);scores.to_parquet(out/'oracle-context.parquet',index=False)
    if bars:
        pd.concat(bars,ignore_index=True).to_parquet(out/'audited-mark-inputs.parquet',index=False)
    summaries=[]
    for y in [2025,2026]:
        for scope in ['PRIMARY','SECONDARY_GOVERNANCE']:
            for h in [20,60]:
                selected=frame[(frame.event_year==y)&frame.scope.eq(scope)&frame.horizon.eq(h)]
                good=selected[selected.status=='EXPLORATORY_ADJUSTED_MARK']
                summaries.append(dict(year=y,scope=scope,horizon=h,admitted=len(selected),unique_issuers=selected.cik.nunique(),
                     mature=int(selected.mature.sum()),qualified=len(good),immature=int(selected.status.eq('IMMATURE').sum()),unknown=int(selected.status.eq('UNKNOWN').sum()),
                     positive_net=int(good.net_return.gt(0).sum()) if len(good) else 0,negative_net=int(good.net_return.lt(0).sum()) if len(good) else 0,
                     mean_net=float(good.net_return.mean()) if len(good) else None,median_net=float(good.net_return.median()) if len(good) else None,
                     mean_spy=float(good.benchmark_net_return.mean()) if len(good) else None,mean_excess=float(good.excess_vs_spy.mean()) if len(good) else None,
                     mean_stress=float(good.stress_net_return.mean()) if len(good) else None,
                     oracle_known=int(good.oracle_context_status.eq('KNOWN').sum()) if len(good) else 0,
                     top10=int(good.in_top10.fillna(False).sum()) if len(good) else 0,top20pct=int(good.in_top20pct.fillna(False).sum()) if len(good) else 0))
    verify_hashes(Path('.'),protocol['sources'])
    result=dict(status='EXPLORATORY_2025_2026_NOT_VALIDATED_SIGNAL',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                price_end=protocol['price_end'],summaries=summaries,unknown_or_immature_cases=json_records(frame[frame.status.ne('EXPLORATORY_ADJUSTED_MARK')]),
                portfolio_pnl=False,files={f.name:digest(f) for f in out.iterdir() if f.is_file()})
    atomic_json(out/'report.json',result);print(result['status'],summaries,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
