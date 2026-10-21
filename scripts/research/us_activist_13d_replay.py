"""Frozen post13D exploratory marks, no portfolio or first-announcement alpha."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_pilot import READ,parse,normalized
from scripts.research.us_activist_13d_review import freeze,check_clause,identity
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

PRICE=Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
SCORES=Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')


def price_path(rows,days,entry,horizon,reserve=None):
    if rows.duplicated('date').any():return None,'DUPLICATE_PRICE_DATES'
    if entry not in days:return None,'NON_SESSION_ENTRY'
    j=days.get_loc(entry)
    if j+horizon>len(days):return None,'IMMATURE'
    dates=days[j:j+horizon];g=rows.set_index('date').reindex(dates)
    raw=g[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    good=(np.isfinite(raw).all(axis=1)&raw[['open','high','low','close','adj_close','volume']].gt(0).all(axis=1)
        &raw.is_filled.eq(0)&raw.high.ge(raw[['open','close','low']].max(axis=1))&raw.low.le(raw[['open','close','high']].min(axis=1)))
    if not good.all():return None,'MISSING_OR_INVALID_PRICE'
    for field in ['instrument_id','data_source','data_adjustment']:
        if g[field].isna().any() or g[field].nunique()!=1 or g[field].astype(str).str.upper().isin(['','UNKNOWN','NAN','NONE']).any():
            return None,'PRICE_IDENTITY_PROVIDER_BASIS_CHANGED'
    if not g.data_source.str.lower().isin(['eodhd_eod','alpaca_sip','alpaca_sip_research_successor']).all():return None,'UNQUALIFIED_PROVIDER'
    factor=raw.adj_close/raw.close
    for col in ['open','high','low','close']:g[col]=raw[col]*factor
    ratio=g.close/g.close.shift(1)
    if ratio.ge(20).any() or ratio.le(.05).any():return None,'UNEXPLAINED_20X_BREAK'
    if reserve and dates[-1]>=pd.Timestamp(reserve['start']):return None,'INHERITED_PRICE_RESERVE'
    return g,'OK'


def marks(path,notional=1000.,commission=1.,bps=10.):
    if path is None or path.empty or notional<=0 or commission<0 or bps<0:raise ValueError('Qualified path/costs required')
    entry=float(path.open.iloc[0]);exit=float(path.close.iloc[-1]);gross=exit/entry-1
    if not np.isfinite([entry,exit]).all() or min(entry,exit)<=0:raise ValueError('Positive price marks required')
    shares=notional/entry;fixed=2*commission/notional
    friction=bps/10000*(1+exit/entry);net=gross-fixed-friction
    values=np.r_[entry,path.close.to_numpy(float)]
    dd=float(np.min(values/np.maximum.accumulate(values)-1))
    return dict(entry_adjusted_mark=entry,exit_adjusted_mark=exit,gross_return=gross,net_return=net,
        fixed_commissions_usd=2*commission,friction_usd=friction*notional,hypothetical_net_usd=notional*net,
        hypothetical_adjusted_units=shares,mfe=float(path.high.max()/entry-1),mae=float(path.low.min()/entry-1),
        max_close_drawdown=dd,last_session=str(path.index[-1].date()))


def prepare(root):
    reviewout,review=freeze(root);out=root/'replay-v1'
    if (out/'protocol.json').exists():
        p=READ(out/'protocol.json');verify_hashes(Path('.'),p['sources']);return out,p
    if out.exists():raise ValueError('Fresh replay output required')
    cap=READ(reviewout/'identity-capture.json');verify_hashes(root,cap['files'])
    identities={r['accession']:r for r in cap['rows']};events=[]
    for row in review['rows']:
        if not row['admitted']:continue
        known=bool(row.get('identity_contains'))
        proof=row.get('identity_contains')
        if not known and row['accession'] in identities:
            d=identities[row['accession']];proof=d
            if d.get('receipt',{}).get('status')=='OK':
                validated=identity((root/d['receipt']['file']).read_bytes(),row['cik'],row['symbol'])
                if validated!=d['identity']:raise ValueError('Historical cover no longer matches')
                known=bool(validated)
        events.append(dict(**row,historical_ticker_supported=known,identity_proof=proof,
            campaign_new_at_filing_certified=False,eligibility_fixed_before_returns=True))
    files=[Path(__file__),Path('tests/test_us_activist_13d_replay.py'),Path('scripts/research/us_activist_13d_replay_audit.py'),
        reviewout/'protocol.json',reviewout/'identity-capture.json',PRICE,PRICE.parent/'quality-reserves.json',
        SCORES/'protocol.json',SCORES/'final-audit.json',SCORES/'2024-done.json',SCORES/'2024-H20-scores.parquet']
    old=READ(SCORES/'protocol.json');expected=next(v for k,v in old['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected:raise ValueError('Research price tape changed')
    if digest(SCORES/'2024-H20-scores.parquet')!=READ(SCORES/'2024-done.json')['files']['2024-H20-scores.parquet']:
        raise ValueError('Oracle ranks changed')
    out.mkdir()
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},events=events,
        primary='3earliest issuer-level explicitCURRENT campaigns after13D, not worldwide first-announcement alpha. GIL/CRTO known earlierletters, separated in results. BJRI no earlierpublicdate certified does NOT prove firstpublicdate.',
        secondary='TPL governance-only proposal separately, never pooled to improve primary. SecondBJRIcurrentcampaign blocked before price checks by shared60sessionissuerpolicy.',
        freeze_before_price_outcomes=True,horizons=[20,60],observation_end='2024-06-30',
        sides='LONGonly, fractional adjusted-unit mark, no leverage/TP/SL/trailing, fixedendpoint. Not production execution, quote fill or actual broker lifecycle.',
        costs=dict(notional_usd=1000.,commission_per_order_usd=1.,spread_bps_per_leg=5.,slippage_bps_per_leg=5.,stress_total_bps_per_leg=25.),
        prices='Use existing same-date adj_close/close to scaleALL OHLC. Positive valid/stable rawbasis/provider/id/calendar across fullwindow; no missing=zero or replacement. Vendor adjusted return proxy, not independent corporateaction/dividend cashflow certification.',
        benchmark='SPY sameentry/exit, same1000notional, fixedcommission and friction. Excess is paired comparison, NOT betahedged portfolio or causal activism effect.',
        oracle='Rank from lastNYSEclose strictly beforeentry, exactsame4decisiondates, full scoredcount determinesceil20%; no later rank. Context only, not event selection.',
        caveats=['Current universe survivors only, selectiveindexroute correctedforfiler/subject, onequarter smallsample',
            'Originalfilings downloaded2026, not local2024receipts; knownpreannouncements explicit, no originalshock return capture',
            'No primaryfee/cash/margin/auctionfill/position constraint parity; noannualreturn/Sharpe/generalwinrate claim',
            'No hardstatisticalgate to avoid reporting smallsample, but no promotion even if allcases profitable'],
        no_training=True,no_sql=True,no_api_prices_or_llm=True,no_orders=True,no_production_changes=True)
    atomic_json(out/'protocol.json',p);return out,p


def run(root):
    out,p=prepare(root)
    if (out/'report.json').exists():raise ValueError('Immutable results')
    days=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date=p['observation_end']).index
    symbols=sorted({r['symbol'] for r in p['events']}|{'SPY'})
    prices=pd.read_parquet(PRICE,filters=[('symbol','in',symbols),('date','>=',pd.Timestamp('2024-01-01')),('date','<=',pd.Timestamp(p['observation_end']))])
    prices=prices.drop(columns=[c for c in ['daily_return','vwap'] if c in prices])
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    decision_dates=[days[days.get_loc(pd.Timestamp(r['entry']))-1] for r in p['events']]
    scores=pd.read_parquet(SCORES/'2024-H20-scores.parquet',columns=['date','symbol','rank','score'],filters=[('date','in',decision_dates)])
    if scores.duplicated(['date','symbol']).any():raise ValueError('Duplicate Oracle context')
    rows=[];bars=[]
    for event,decision in zip(p['events'],decision_dates):
        context=scores[(scores.date==decision)&scores.symbol.eq(event['symbol'])];n=int(scores.date.eq(decision).sum())
        if len(context)>1:raise ValueError('Multiple Oracle contextrows')
        rank=int(context.iloc[0]['rank']) if len(context) else None
        for horizon in p['horizons']:
            row=dict(symbol=event['symbol'],cik=event['cik'],accession=event['accession'],filed=event['filed'],entry=event['entry'],
                scope='PRIMARY_CURRENT_CAMPAIGN' if event['active'] else 'SECONDARY_GOVERNANCE_ONLY',horizon=horizon,
                known_earlier_public_date=event['earlier_public_action_date'],first_announcement_certified=False,
                oracle_decision_date=str(decision.date()),oracle_rank=rank,oracle_scored_count=n,
                in_top10=rank is not None and rank<=10,in_top20pct=rank is not None and rank<=int(np.ceil(.2*n)))
            if not event['historical_ticker_supported']:row.update(status='UNKNOWN',reason='HISTORICAL_TICKER_NOT_SUPPORTED');rows.append(row);continue
            pair={};problem=[]
            for s in [event['symbol'],'SPY']:
                path,why=price_path(groups.get(s,pd.DataFrame(columns=prices.columns)),days,pd.Timestamp(event['entry']),horizon,reserves.get(s))
                if path is None:problem.append(s+':'+why);continue
                pair[s]=path
            if problem:row.update(status='UNKNOWN',reason=';'.join(problem));rows.append(row);continue
            k=p['costs'];cost=k['spread_bps_per_leg']+k['slippage_bps_per_leg']
            stock=marks(pair[event['symbol']],k['notional_usd'],k['commission_per_order_usd'],cost)
            spy=marks(pair['SPY'],k['notional_usd'],k['commission_per_order_usd'],cost)
            stress=marks(pair[event['symbol']],k['notional_usd'],k['commission_per_order_usd'],k['stress_total_bps_per_leg'])
            row.update(status='EXPLORATORY_ADJUSTED_MARK',reason=None,**stock,
                benchmark_net_return=spy['net_return'],excess_vs_spy=stock['net_return']-spy['net_return'],stress_net_return=stress['net_return'])
            rows.append(row)
            for s,path in pair.items():
                tmp=path.reset_index(names='date');tmp['symbol']=s;tmp['accession']=event['accession'];tmp['horizon']=horizon;bars.append(tmp)
    f=pd.DataFrame(rows);f.to_csv(out/'event-results.csv',index=False);pd.concat(bars,ignore_index=True).to_parquet(out/'audited-mark-inputs.parquet',index=False) if bars else None
    prices.to_parquet(out/'source-price-snapshot.parquet',index=False);scores.to_parquet(out/'oracle-context.parquet',index=False)
    summaries=[]
    for scope in ['PRIMARY_CURRENT_CAMPAIGN','SECONDARY_GOVERNANCE_ONLY']:
        for h in p['horizons']:
            allrows=f[(f.scope==scope)&f.horizon.eq(h)];g=allrows[allrows.status=='EXPLORATORY_ADJUSTED_MARK']
            summaries.append(dict(scope=scope,horizon=h,admitted=len(allrows),qualified=len(g),unknown=len(allrows)-len(g),
                positive_net=int(g.net_return.gt(0).sum()) if len(g) else 0,negative_net=int(g.net_return.lt(0).sum()) if len(g) else 0,
                mean_net=float(g.net_return.mean()) if len(g) else None,mean_spy=float(g.benchmark_net_return.mean()) if len(g) else None,
                mean_excess=float(g.excess_vs_spy.mean()) if len(g) else None,
                mean_stress=float(g.stress_net_return.mean()) if len(g) else None,
                in_top10=int(g.in_top10.sum()) if len(g) else 0,in_top20pct=int(g.in_top20pct.sum()) if len(g) else 0,
                not_generalizable_win_rate=True))
    result=dict(status='EXPLORATORY_POST13D_CASES_COMPLETE_NOT_VALIDATED_SIGNAL',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        summaries=summaries,rows=len(f),hypothetical_notional_per_case=1000.,portfolio_pnl=False,
        source_rows=len(prices),capture=READ(root/'review-v1/identity-capture.json'),
        no_training_sql_llm_or_order=True,files={f.name:digest(f) for f in out.iterdir() if f.is_file()})
    verify_hashes(Path('.'),p['sources']);atomic_json(out/'report.json',result)
    print(result['status'],len(f),'event/horizon cases',flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','run'],required=True);args=a.parse_args();globals()[args.phase](args.output)
