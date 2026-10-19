"""Frozen sector-ETF versus SPY OU reversion, research only.

SELECT-only ETF snapshot, then offline calculations. Current industry proxy is
not a historical GICS constituent database. No PCA or production changes here.
"""
import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from modelFactory.cross_sectional import _map_to_gics_sector
from scripts.research import us_professional_residual_reversion as base
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

PARENT=Path('artifacts/research/us_professional_residual_reversion/20261019-v1')
MAPPING=Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
ETF={'Energy':'XLE','Materials':'XLB','Industrials':'XLI','Consumer Discretionary':'XLY',
     'Consumer Staples':'XLP','Health Care':'XLV','Financials':'XLF','Real Estate':'XLRE',
     'Information Technology':'XLK','Communication Services':'XLC','Utilities':'XLU'}
AMBIGUOUS={'retail','consumer products','communications','building','construction','distributors','packaging'}
DIRECT={'industrial conglomerates':'Industrials','transportation infrastructure':'Industrials'}
READ=base.READ
LOG=logging.getLogger(__name__)
POLICIES=['OU_DYNAMIC','SAME_SIDE_FIXED10']


def assign_etf(industry):
    if pd.isna(industry) or not str(industry).strip():return None,'MISSING_CLASSIFICATION'
    key=str(industry).strip().lower()
    if key in AMBIGUOUS:return None,'AMBIGUOUS_INDUSTRY'
    sector=DIRECT.get(key,_map_to_gics_sector(str(industry)))
    if sector not in ETF:return None,'UNMAPPED_INDUSTRY'
    return ETF[sector],'CURRENT_PROXY_NOT_PIT'


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh output directory required')
    old=READ(PARENT/'protocol.json');audit=READ(PARENT/'final-audit.json')
    if audit['status']!='PASS_EXPLORATORY_ADAPTATION_ONLY' or audit['report_sha256']!=digest(PARENT/'report.json'):
        raise ValueError('Parent replay not audited')
    verify_hashes(Path('.'),old['sources'])
    files=[Path(__file__),Path('scripts/research/us_sector_residual_reversion_audit.py'),
        Path('tests/test_us_sector_residual_reversion.py'),Path(base.__file__),
        Path('scripts/research/us_professional_residual_reversion_audit.py'),
        Path('modelFactory/cross_sectional.py'),MAPPING,PARENT/'protocol.json',PARENT/'report.json',
        PARENT/'final-audit.json',PARENT/'sessions.parquet',PARENT/'oracle-top10.parquet',base.PRICE]
    mapping=pd.read_parquet(MAPPING)
    if mapping.symbol.duplicated().any():raise ValueError('Ambiguous duplicate symbol mapping')
    m=pd.DataFrame(dict(symbol=old['symbols'])).merge(mapping,on='symbol',how='left',validate='one_to_one')
    mapped=[assign_etf(x) for x in m.sector]
    m['hedge_etf']=[x[0] for x in mapped];m['classification_status']=[x[1] for x in mapped]
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        parent=str(PARENT),etfs=ETF,ambiguous_industries=sorted(AMBIGUOUS),direct_industry_groups=DIRECT,
        original_symbols=old['symbols'],retained_symbols=m.loc[m.hedge_etf.notna(),'symbol'].tolist(),
        rules=old,arms=['SPY','SECTOR_ETF'],policies=POLICIES,
        sector_pit=False,mapping='Oct7 current industry proxy, no historical sectors. Exclude ambiguous/missing, no individual symbol patches or production mapping edits.',
        snapshot='Only SELECT existing ETF daily prices Jan2023-Sep2026, repeatable read/read only/rollback; no provider call',
        etf_identity='instrument_id is a research label ETF_SYMBOL:<ticker>, not an invented canonical SQL instrument id',
        factor_prices='Use existing adj_close/close scaling; reject IEX/Yahoo/unknown/invalid sources; no patched split',
        shocks='ETF adjusted close-close or overnight open/previous-close moves >=20% require review; affected row blocked in both arms until qualified, not assigned a fabricated correction',
        shared_entry_support='Same mapped symbols and stock/SPY/ETF past61 valid stable history, before separate OU estimates/trigger; no observed future input to selection',
        shared_future_quality='Same stock+SPY+assignedETF full J..J+11 price window for both arms; invalid unknown, no replacement',
        comparison='Each arm own frozen signal and exit. Separate independent memberships before future quality. Equal-date difference on common entry dates is descriptive, not paired identical trades.',
        unchanged='Same 60 returns, +/-1.25 entry, +/-0.5 symmetric exit, fixed entry beta, ten-session cap, daily -5% risk observed at close/exited next open, 8bps leg cost/20bps stress and .3% borrow',
        gates='Same positive per-trade AND equal-date CI, stress, n>=100 and concentration limits in both2025+2026. Additionally sector-minus-SPY equal-date CI lower>0 both years before claiming improvement.',
        sql_writes=False,provider_calls=0,ml_training=False,orders=False,production_changes=False,
        reserves=['Static survivor universe, current non-PIT industry approximation, not certified historical GICS',
                  'Sector SPDRs represent US large caps, not all ADR/small-cap industries; proxy basis risk remains',
                  'One factor per stock, no PCA, multi-factor hedge or daily rehedging; ETF/stock dividend cashflows not independently certified',
                  'Already explored years; per gross pair unit returns not finite-capital portfolio, live margin/borrow or guaranteed daily stop'])
    atomic_json(root/'protocol.json',p)
    m.to_parquet(root/'symbol-sector-map.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={'symbol-sector-map.parquet':digest(root/'symbol-sector-map.parquet')}))
    return p


def snapshot(root):
    from sqlalchemy import text,bindparam
    from database.connection import get_sqlalchemy_engine
    p=prepare(root)
    if (root/'snapshot-ready.json').exists():verify_hashes(root,READ(root/'snapshot-ready.json')['files']);return
    q=text('''SELECT symbol,date,open,high,low,close,adj_close,volume,is_filled,data_source,data_adjustment,
        ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols
        AND date BETWEEN :start AND :end ORDER BY symbol,date''').bindparams(bindparam('symbols',expanding=True))
    engine=get_sqlalchemy_engine()
    start=datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        rows=pd.read_sql_query(q,conn,params=dict(symbols=sorted(set(p['etfs'].values())),start='2023-01-01',end='2026-09-30'))
        conn.rollback()
    engine.dispose()
    rows['date']=pd.to_datetime(rows.date)
    rows['instrument_id']='ETF_SYMBOL:'+rows.symbol  # explicitly research-only key.
    rows.to_parquet(root/'etf-bars.parquet',index=False)
    atomic_json(root/'snapshot-ready.json',dict(started_at_utc=start,finished_at_utc=datetime.now(timezone.utc).isoformat(),
        transaction='REPEATABLE READ / READ ONLY / ROLLBACK',rows=len(rows),
        files={'etf-bars.parquet':digest(root/'etf-bars.parquet')}))
    LOG.info('ETF snapshot %d rows, %d symbols',len(rows),rows.symbol.nunique())


def etf_grid(rows,days):
    g=base.valid_grid(rows,days)
    allowed=g.data_source.astype(str).str.lower().isin(['eodhd_eod','alpaca_sip'])
    g['daily_good'] &= allowed
    g['history_point_good'] &= allowed
    # Quality flag only, not an economic veto chosen on profitable/losing trades.
    shock=(g.close/g.close.shift(1)-1).abs().ge(.20)|(g.open/g.close.shift(1)-1).abs().ge(.20)
    g['unqualified_etf_shock']=shock
    g['daily_good'] &= ~shock
    g['history_point_good'] &= ~shock
    return g


def supported_history(g):
    return g.history_point_good.astype(int).rolling(61,min_periods=61).sum().eq(61)&g.stable_history


def common_reason(g,spy,sector,pos,reserve=None,events=()):
    for name,grid,r,ev in [('STOCK',g,reserve,events),('SPY',spy,None,()),('SECTOR',sector,None,())]:
        reason=base.window_reason(grid,pos,r,ev)
        if reason!='OK':return name+':'+reason
    return 'OK'


def build(root):
    p=prepare(root);verify_hashes(root,READ(root/'prepared.json')['files'])
    snap=READ(root/'snapshot-ready.json');verify_hashes(root,snap['files'])
    if (root/'data-ready.json').exists():verify_hashes(root,READ(root/'data-ready.json')['files']);return
    old=p['rules'];days=pd.DatetimeIndex(pd.read_parquet(PARENT/'sessions.parquet').date)
    raw=pd.read_parquet(base.PRICE);stocks=dict(tuple(raw.groupby('symbol',sort=False)))
    spy=base.valid_grid(stocks['SPY'],days)
    etfraw=pd.read_parquet(root/'etf-bars.parquet')
    etfs={str(s):etf_grid(f,days) for s,f in etfraw.groupby('symbol',sort=False)}
    if set(etfs)!=set(ETF.values()):raise ValueError('Missing entire sector ETF, no fallback')
    diagnostics=[];shock_rows=[]
    for symbol,g in etfs.items():
        diagnostics.append(dict(symbol=symbol,expected_sessions=len(days),observed=int(g.close.notna().sum()),
            qualified=int(g.daily_good.sum()),sources=g.data_source.value_counts().to_dict(),
            adjustments=g.data_adjustment.value_counts().to_dict(),shocks=int(g.unqualified_etf_shock.sum())))
        z=g[g.unqualified_etf_shock].reset_index().rename(columns={'index':'date'})
        if len(z):shock_rows.extend(z.assign(symbol=symbol)[['date','symbol','open','close','data_source','data_adjustment']].to_dict('records'))
    atomic_json(root/'etf-quality.json',dict(etfs=diagnostics,shocks=shock_rows))
    mapping=pd.read_parquet(root/'symbol-sector-map.parquet').set_index('symbol')
    top=pd.read_parquet(PARENT/'oracle-top10.parquet');topkeys=set(zip(top.symbol,pd.to_datetime(top.date)))
    root.joinpath('parts').mkdir(exist_ok=False)
    features=[];candidates=[];trades=[];support=[];files={};parent_spy_checks=0
    old_features={}
    # Only score columns are compared, not reusing old future outcomes.
    for name in READ(PARENT/'data-ready.json')['files']:
        if name.endswith('-features.parquet'):
            chunk=pd.read_parquet(PARENT/name,columns=['symbol','date','beta','s_score','model_valid'])
            old_features.update({str(s):f.set_index('date') for s,f in chunk.groupby('symbol',sort=False)})
    for ix,symbol in enumerate(p['retained_symbols']):
        sector_symbol=str(mapping.loc[symbol,'hedge_etf']);sector=etfs[sector_symbol]
        if symbol not in stocks:raise ValueError('Missing cached stock '+symbol)
        reserve=old['price_reserves'].get(symbol);events=old['identity_events'].get(symbol,[])
        g=base.valid_grid(stocks[symbol],days,reserve,events)
        shared=supported_history(g)&supported_history(spy)&supported_history(sector)
        period=(days>='2024-01-01')&(days<=old['signal_end'])
        shared_entry=shared&g.liquidity_pass&period
        support.append(dict(symbol=symbol,hedge_etf=sector_symbol,dates=int(shared_entry.sum()),
            **{str(y):int((shared_entry&(days.year==y)).sum()) for y in old['years']}))
        for arm,hedge in [('SPY',spy),('SECTOR_ETF',sector)]:
            f=base.ou_signals(g.close,hedge.close,g.history_point_good.to_numpy(bool)&hedge.history_point_good.to_numpy(bool));f.index=days
            f['model_valid'] &= g.stable_history.to_numpy(bool)&hedge.stable_history.to_numpy(bool)
            f['entry_eligible']=f.model_valid&shared_entry
            if arm=='SPY':
                archived=old_features[symbol].reindex(days)
                assert np.allclose(f.s_score,archived.s_score,rtol=0,atol=1e-9,equal_nan=True)
                assert np.allclose(f.beta,archived.beta,rtol=0,atol=1e-9,equal_nan=True)
                assert np.array_equal(f.model_valid,archived.model_valid)
                parent_spy_checks+=1
            f['date']=days;f['symbol']=symbol;f['arm']=arm;f['hedge_symbol']='SPY' if arm=='SPY' else sector_symbol
            features.append(f.reset_index(drop=True))
            blocked={s:-1 for s in old['scopes']}
            positions=np.flatnonzero(f.entry_eligible.to_numpy(bool)&f.s_score.abs().gt(1.25).to_numpy())
            for pos in positions:
                for scope in old['scopes']:
                    if scope=='ORACLE_H10_TOP10' and (symbol,days[pos]) not in topkeys:continue
                    independent=pos>blocked[scope]
                    if independent:blocked[scope]=pos+11
                    reason=common_reason(g,spy,sector,pos,reserve,events)
                    side='LONG' if f.s_score.iloc[pos]<0 else 'SHORT';beta=float(f.beta.iloc[pos])
                    common=dict(symbol=symbol,date=days[pos],year=int(days[pos].year),scope=scope,arm=arm,
                        side=side,beta=beta,s_score=float(f.s_score.iloc[pos]),tau_sessions=float(f.tau_sessions.iloc[pos]),
                        hedge_symbol='SPY' if arm=='SPY' else sector_symbol,independent=independent,
                        entry_date=days[pos+1],last_path_date=days[pos+11],quality=reason)
                    candidates.append(common)
                    if reason!='OK':continue
                    end,why,age=base.daily_exit(g.open,g.close,hedge.open,hedge.close,f.s_score,f.model_valid,
                        pos=pos,side=side,beta=beta)
                    for policy in POLICIES:
                        j=pos+11 if policy=='SAME_SIDE_FIXED10' else end
                        ret=base.returns_for(float(g.open.iloc[pos+1]),float(g.open.iloc[j]),float(hedge.open.iloc[pos+1]),
                            float(hedge.open.iloc[j]),beta,side,(days[j]-days[pos+1]).days,policy)
                        trades.append(dict(**common,policy=policy,exit_date=days[j],executed_side=side,
                            exit_reason='FIXED10_NEXT_OPEN' if policy=='SAME_SIDE_FIXED10' else why,
                            exit_session=10 if policy=='SAME_SIDE_FIXED10' else age,
                            entry_stock=float(g.open.iloc[pos+1]),exit_stock=float(g.open.iloc[j]),
                            entry_market=float(hedge.open.iloc[pos+1]),exit_market=float(hedge.open.iloc[j]),**ret))
        if (ix+1)%50==0 or ix+1==len(p['retained_symbols']):
            chunk=ix//50
            for suffix,frame in [('features',pd.concat(features,ignore_index=True)),('candidates',pd.DataFrame(candidates)),('trades',pd.DataFrame(trades))]:
                name=f'parts/{chunk:04d}-{suffix}.parquet';frame.to_parquet(root/name,index=False);files[name]=digest(root/name)
            features=[];candidates=[];trades=[]
            atomic_json(root/'progress.json',dict(status='RUNNING',completed=ix+1,total=len(p['retained_symbols']),phase='SECTOR_AND_SPY'))
            LOG.info('Sector/SPY %d/%d',ix+1,len(p['retained_symbols']))
    pd.DataFrame(support).to_csv(root/'common-support.csv',index=False)
    for name in ['common-support.csv','etf-quality.json']:files[name]=digest(root/name)
    atomic_json(root/'data-ready.json',dict(files=files,parent_spy_score_checks=parent_spy_checks))


def compare_dates(trades,days):
    """Equal-date means, only common dates. Different signals, NOT causal A/B."""
    rows=[]
    primary=trades[trades.policy.eq('OU_DYNAMIC')&trades.independent]
    for (scope,year),f in primary.groupby(['scope','year']):
        a=f.groupby(['date','arm']).net.mean().unstack('arm')
        a=a.dropna(subset=['SPY','SECTOR_ETF'])
        if not len(a):continue
        delta=(a.SECTOR_ETF-a.SPY).rename('net').reset_index()
        ci=base.block_interval(delta,days)
        rows.append(dict(scope=scope,year=int(year),common_dates=len(a),
            sector_mean=float(a.SECTOR_ETF.mean()),spy_mean=float(a.SPY.mean()),
            delta=float(delta.net.mean()),ci95=ci,positive_ci=ci[0] is not None and ci[0]>0))
    return rows


def summarize(root):
    p=prepare(root);ready=READ(root/'data-ready.json');verify_hashes(root,ready['files'])
    if (root/'report.json').exists():raise ValueError('Immutable completed replay')
    def load(suffix):
        a=[pd.read_parquet(root/n) for n in ready['files'] if n.endswith(suffix)]
        return pd.concat([x for x in a if len(x)],ignore_index=True)
    cand=load('-candidates.parquet');trades=load('-trades.parquet')
    cand.to_parquet(root/'candidates.parquet',index=False);trades.to_parquet(root/'trades.parquet',index=False)
    days=pd.DatetimeIndex(pd.read_parquet(PARENT/'sessions.parquet').date)
    summaries=[]
    for (arm,scope,year,policy),f in trades.groupby(['arm','scope','year','policy']):
        for side in ['ALL','LONG','SHORT']:
            g=f if side=='ALL' else f[f.side.eq(side)]
            for cohort,h in [('ALL',g),('NON_OVERLAP',g[g.independent])]:
                summaries.append(dict(arm=arm,scope=scope,year=int(year),policy=policy,side=side,cohort=cohort,**base.metrics(h,days)))
    pd.DataFrame(summaries).to_csv(root/'summary.csv',index=False)
    comparisons=compare_dates(trades,days);pd.DataFrame(comparisons).to_csv(root/'comparisons.csv',index=False)
    primary=[r for r in summaries if r['policy']=='OU_DYNAMIC' and r['side']=='ALL' and r['cohort']=='NON_OVERLAP']
    gates={}
    for scope in p['rules']['scopes']:
        annual=all(next((r.get('gate',False) for r in primary if r['arm']=='SECTOR_ETF' and r['scope']==scope and r['year']==y),False) for y in [2025,2026])
        improved=all(next((r['positive_ci'] for r in comparisons if r['scope']==scope and r['year']==y),False) for y in [2025,2026])
        gates[scope]=dict(absolute_robust=annual,improvement_robust=improved,pass_both=annual and improved)
    report=dict(status='EXPLORATORY_ONLY' if any(g['pass_both'] for g in gates.values()) else 'NO_ROBUST_SECTOR_IMPROVEMENT',
        classifications_non_pit=True,symbols_requested=len(p['original_symbols']),mapped_symbols=len(p['retained_symbols']),
        candidates=len(cand),qualified=int(cand.quality.eq('OK').sum()),gates=gates,primary=primary,
        comparisons=comparisons,summaries=summaries,
        coverage=cand.groupby(['arm','scope','year','quality']).size().rename('n').reset_index().to_dict('records'),
        files={f:digest(root/f) for f in ['candidates.parquet','trades.parquet','summary.csv','comparisons.csv']},
        note='Current sector proxy, already explored years, illustrative costs/borrow, no dividend qualification or finite-capital/live execution claim. No PCA in this run.')
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status='COMPLETED',verdict=report['status']))
    LOG.info('Finished %s: mapped=%d candidates=%d',report['status'],report['mapped_symbols'],len(cand))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','snapshot','build','summarize'],required=True);args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'snapshot':snapshot,'build':build,'summarize':summarize}[args.phase](args.output)


if __name__=='__main__':main()
