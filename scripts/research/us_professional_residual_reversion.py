"""Bounded, offline professional-method adaptation: SPY-residual OU reversion.

Not a replication of a fund or the full sector/PCA Avellaneda-Lee model.
Read existing archives only. No SQL/provider/LLM/order/production mutation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from numpy.lib.stride_tricks import sliding_window_view

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PRICE = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
SCORES = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
QUALITY = PRICE.parent
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
LOG = logging.getLogger(__name__)
WINDOW = 60
MAX_HOLD = 10
POLICIES = ['OU_DYNAMIC', 'SAME_SIDE_FIXED10', 'REVERSE_SAME_EXIT', 'SAME_SIDE_UNHEDGED']
REFERENCES = [
    dict(title='Avellaneda & Lee, Statistical Arbitrage in the U.S. Equities Market, June2009 working version',
         url='https://math.nyu.edu/~avellane/AvellanedaLeeStatArb20090616.pdf',
         use='60 trailing returns, residual OU, entry absolute s>1.25, fast relaxation tau<30 sessions; adaptation not full replication'),
    dict(title='AQR, Trading Costs of Asset Pricing Anomalies, 2012',
         url='https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies',
         use='Short reversal costs/capacity warning; prespecify conservative costs and stress'),
    dict(title='Robeco, Residual momentum, 2013',
         url='https://www.robeco.com/en-int/insights/2013/10/robecos-residual-momentum-less-risky-and-more-sustainable',
         use='Stock-specific vs systematic returns distinction; NOT the same as this mean-reversion rule'),
    dict(title='Man AHL investment approach', url='https://www.man.com/ahl',
         use='Diversification and costs/implementation, not a promise our narrow adaptation succeeds')]


def ou_signals(close, spy, history_good):
    """Each row at J only uses returns from J-59..J and prices J-60..J.

    OLS with intercept against SPY, cumulative residuals X[1:60], AR(1),
    equilibrium sigma, uncentered s. No cross-sectional/sector metadata.
    """
    c = np.asarray(close, dtype=float); m = np.asarray(spy, dtype=float)
    valid = np.asarray(history_good, dtype=bool)
    if c.ndim != 1 or c.shape != m.shape or c.shape != valid.shape or len(c) <= WINDOW:
        raise ValueError('Aligned price/history arrays with at least 61 sessions required')
    out = np.full((len(c), 7), np.nan)
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        y = sliding_window_view(c[1:]/c[:-1]-1, WINDOW)
        x = sliding_window_view(m[1:]/m[:-1]-1, WINDOW)
        xm = x.mean(axis=1); ym = y.mean(axis=1)
        xc = x-xm[:,None]; yc = y-ym[:,None]
        beta = (xc*yc).sum(axis=1)/(xc*xc).sum(axis=1)
        alpha = ym-beta*xm
        eps = y-alpha[:,None]-beta[:,None]*x
        cumulative = np.cumsum(eps, axis=1)
        prev = cumulative[:,:-1]; nxt = cumulative[:,1:]
        pmean = prev.mean(axis=1); nmean = nxt.mean(axis=1)
        centered = prev-pmean[:,None]
        b = (centered*(nxt-nmean[:,None])).sum(axis=1)/(centered*centered).sum(axis=1)
        a = nmean-b*pmean
        eta = nxt-a[:,None]-b[:,None]*prev
        variance = (eta*eta).sum(axis=1)/(WINDOW-3)  # 59 AR observations -2 fitted coefficients.
        mean = a/(1-b)
        equilibrium_sigma = np.sqrt(variance/(1-b*b))
        score = (cumulative[:,-1]-mean)/equilibrium_sigma
        tau = -1/np.log(b)
        out[WINDOW:] = np.column_stack([beta, alpha, b, mean, equilibrium_sigma, score, tau])
    f = pd.DataFrame(out, columns=['beta','alpha','ar_b','equilibrium_mean','equilibrium_sigma','s_score','tau_sessions'])
    supported = sliding_window_view(valid, WINDOW+1).all(axis=1)
    history = np.r_[np.zeros(WINDOW, dtype=bool), supported]
    finite = np.isfinite(out).all(axis=1)
    f['model_valid'] = (history & finite & f.beta.gt(0).to_numpy() & f.beta.le(3).to_numpy()
        & f.ar_b.gt(0).to_numpy() & f.ar_b.lt(np.exp(-1/30)).to_numpy()
        & f.equilibrium_sigma.gt(1e-8).to_numpy())
    f.loc[~history, ['beta','alpha','ar_b','equilibrium_mean','equilibrium_sigma','s_score','tau_sessions']] = np.nan
    return f


def valid_grid(bars, days, price_reserve=None, identity_events=()):
    if bars.duplicated('date').any():
        raise ValueError('Duplicate symbol/date prices')
    g = bars.set_index('date').reindex(days).copy()
    raw = g[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    adjusted = raw.adj_close.where(raw.adj_close.notna(), raw.close)
    factor = adjusted/raw.close
    good = (np.isfinite(raw[['open','high','low','close']]).all(axis=1)
        & raw[['open','high','low','close']].gt(0).all(axis=1)
        & raw.high.ge(raw[['open','close','low']].max(axis=1))
        & raw.low.le(raw[['open','close','high']].min(axis=1))
        & factor.gt(0) & np.isfinite(factor) & raw.volume.gt(0) & raw.is_filled.eq(0))
    for k in ['open','high','low','close']:
        g[k] = raw[k]*factor
    history_good = good.copy()
    stable_history = pd.Series(True,index=days)
    for field in ['instrument_id','data_source','data_adjustment']:
        known = g[field].notna()
        if field!='instrument_id':
            known &= ~g[field].astype(str).str.upper().isin(['UNKNOWN','','NAN','NONE'])
        history_good &= known
        codes = pd.Series(pd.factorize(g[field])[0],index=days,dtype=float)
        stable_history &= codes.rolling(61,min_periods=61).min().eq(codes.rolling(61,min_periods=61).max()) & codes.ge(0)
    ratio = adjusted/adjusted.shift(1)
    history_good &= ~(ratio.ge(20)|ratio.le(.05))
    if price_reserve:
        history_good &= days < pd.Timestamp(price_reserve['start'])
    for event in identity_events:
        last=pd.Timestamp(event['last_predecessor_date']); first=pd.Timestamp(event['first_successor_date'])
        # Prevent any 61-session history from crossing the known identity discontinuity.
        crossed=(days>=first)&(days.to_series(index=days).shift(60).le(last).to_numpy())
        stable_history &= ~crossed
    g['daily_good'] = good
    g['history_point_good'] = history_good
    g['stable_history'] = stable_history
    # Liquidity proxy from stored fields, not independently certified historical capitalisation.
    g['adv20_proxy'] = (raw.close*raw.volume).rolling(20,min_periods=20).mean()
    g['liquidity_pass'] = g.adv20_proxy.ge(5_000_000) & raw.close.ge(5)
    return g


def window_reason(g, pos, reserve=None, events=()):
    stop=pos+MAX_HOLD+1
    if stop>=len(g): return 'IMMATURE'
    w=g.iloc[pos:stop+1]
    if not w.daily_good.all(): return 'INVALID_OR_MISSING_FUTURE_PRICE'
    for field in ['instrument_id','data_source','data_adjustment']:
        if w[field].isna().any() or w[field].nunique()!=1:
            return 'CHANGED_OR_UNKNOWN_'+field.upper()
        if field!='instrument_id' and w[field].astype(str).str.upper().isin(['UNKNOWN','','NAN','NONE']).any():
            return 'CHANGED_OR_UNKNOWN_'+field.upper()
    ratios=w.close.to_numpy(float)[1:]/w.close.to_numpy(float)[:-1]
    if ((ratios>=20)|(ratios<=.05)).any(): return 'UNEXPLAINED_20X_BREAK'
    if reserve and w.index[-1]>=pd.Timestamp(reserve['start']): return 'RESERVED_PRICE_BASIS'
    for ev in events:
        if w.index[0]<=pd.Timestamp(ev['last_predecessor_date']) and w.index[-1]>=pd.Timestamp(ev['first_successor_date']):
            return 'IDENTITY_BREAK'
    return 'OK'


def pair_mark(stock, market, entry_stock, entry_market, beta, sign):
    return sign*((stock/entry_stock-1)-beta*(market/entry_market-1))/(1+beta)


def daily_exit(stock_open, stock_close, market_open, market_close, scores, model_valid,
               *, pos, side, beta):
    """Open J+1 entry. Close decisions only; execute paired legs next open.

    There is no invented intraday hedge fill or guaranteed -5% stop execution.
    """
    if side not in ('LONG','SHORT') or not 0<beta<=3:
        raise ValueError('Invalid side/beta')
    arrays=[np.asarray(a) for a in [stock_open,stock_close,market_open,market_close,scores,model_valid]]
    if len({len(a) for a in arrays})!=1 or pos<0 or pos+MAX_HOLD+1>=len(arrays[0]):
        raise ValueError('Incomplete pair path')
    so,sc,mo,mc,z,valid=arrays
    observed=np.r_[so[pos+1:pos+12],sc[pos+1:pos+11],mo[pos+1:pos+12],mc[pos+1:pos+11]].astype(float)
    if not np.isfinite(observed).all() or (observed<=0).any():
        raise ValueError('Invalid pair prices')
    sign=1 if side=='LONG' else -1
    entry=pos+1
    for age in range(1,MAX_HOLD+1):
        day=pos+age
        mark=pair_mark(sc[day],mc[day],so[entry],mo[entry],beta,sign)
        if mark<=-.05+1e-12:
            return day+1,'DAILY_RISK_NEXT_OPEN',age
        if not valid[day] or not np.isfinite(z[day]):
            return day+1,'INVALID_MODEL_NEXT_OPEN',age
        if (sign==1 and z[day]>=-.5) or (sign==-1 and z[day]<=.5):
            return day+1,'REVERSION_NEXT_OPEN',age
    return pos+MAX_HOLD+1,'TIMEOUT_NEXT_OPEN',MAX_HOLD


def returns_for(entry_stock,exit_stock,entry_market,exit_market,beta,side,calendar_days,policy,cost=.0008):
    if (not np.isfinite([entry_stock,exit_stock,entry_market,exit_market,beta,cost]).all()
        or min(entry_stock,exit_stock,entry_market,exit_market)<=0 or not 0<beta<=3
        or side not in ('LONG','SHORT') or policy not in POLICIES or cost<0):
        raise ValueError('Invalid prices/beta')
    sign=1 if side=='LONG' else -1
    if policy=='REVERSE_SAME_EXIT': sign=-sign
    hedged=policy!='SAME_SIDE_UNHEDGED'
    b=beta if hedged else 0.
    gross=sign*((exit_stock/entry_stock-1)-b*(exit_market/entry_market-1))/(1+b)
    fees=cost*((1+exit_stock/entry_stock)+b*(1+exit_market/entry_market))/(1+b)
    borrowed=(1. if sign<0 else b)/(1+b)
    borrow=.003*max(1,calendar_days)/365*borrowed
    return dict(gross=float(gross),costs=float(fees),borrow=float(borrow),net=float(gross-fees-borrow),
        net_stress=float(gross-fees*(.002/.0008)-borrow))


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); return p
    if root.exists(): raise ValueError('New output directory required')
    parent=READ(SCORES/'protocol.json')
    if READ(SCORES/'final-audit.json')['status']!='PASS_EXPLORATORY_ONLY':
        raise ValueError('Unqualified source model audit')
    if digest(PRICE)!=parent['sources'][str(PRICE)]: raise ValueError('Changed normalized prices')
    files=[Path(__file__),Path('scripts/research/us_professional_residual_reversion_audit.py'),
        Path('tests/test_us_professional_residual_reversion.py'),PRICE,UNIVERSE,
        SCORES/'protocol.json',SCORES/'final-audit.json',QUALITY/'report.json',QUALITY/'quality-reserves.json']
    for year in (2024,2025,2026):
        done=READ(SCORES/f'{year}-done.json'); name=f'{year}-H10-scores.parquet'
        if digest(SCORES/name)!=done['files'][name]: raise ValueError('Changed Oracle scores')
        files.extend([SCORES/name,SCORES/f'{year}-done.json'])
    symbols=sorted({s.strip() for s in UNIVERSE.read_text(encoding='utf-8-sig').replace('\n',',').split(',') if s.strip()}-{'SPY'})
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        references=REFERENCES,symbols=symbols,universe_count=len(symbols),years=[2024,2025,2026],
        signal_end='2026-09-01',observation_end='2026-09-30',
        method='Single SPY factor OLS+OU residual reversion adaptation; not sector/PCA model or claimed institutional returns',
        not_duplicate='E17 residual momentum H120 and E10 simple pullback differ: this is residual mean-reversion, explicit SPY hedge, daily state exits',
        window=60,ols='Simple close returns with intercept, cumulative 60 residuals, AR1 on X1..X59->X2..X60, noise variance SSE/57',
        score='s=(X60-a/(1-b))/sqrt(noise_variance/(1-b^2)); uncentered cross-section; no volume-clock variant',
        model_valid='61 qualified stable history sessions; 0<beta<=3, 0<b<exp(-1/30), equilibrium_sigma>1e-8',
        liquidity='Current stored close>=5 and trailing20 stored close*volume mean>=5M USD proxy; not verified historical market-cap filter',
        signal='At J close: s<-1.25 LONG stock/SHORT beta SPY; s>1.25 SHORT stock/LONG beta SPY; strict, no parameter search',
        exit='Observe J+k close; exit both legs next open if long s>=-.5 / short s<=.5, invalid model, or marked gross pair loss<=-5%; otherwise after10 sessions next open',
        risk='-5% daily observation threshold NOT intraday guaranteed stop. No TP, trailing, threshold optimization or retroactive favourable fill.',
        hedge='Fixed entry beta, fixed units; stock weight sign/(1+beta), SPY weight -sign*beta/(1+beta), gross at entry=1; no daily rehedge/netting',
        scopes=['FULL_TRADABLE','ORACLE_H10_TOP10'],oracle='Only original rank<=10 at J permits TOP10 entry; held position need not remain TOP10',
        independence='Earliest candidate per symbol before future-quality inspection, either side blocks through J+11 full window even if earlier exit; primary NON_OVERLAP; all signals secondary',
        paths='Require all stock/SPY daily bars J..J+11 valid/stable; no future replacement, invalid remains unknown and still blocks an independent episode',
        costs_per_leg=.0008,stress_cost_per_leg=.002,borrow_annual=.003,borrow_day_basis=365,
        financing='No short rebate, cash yield or leverage interest; price return proxy, no independently qualified dividend/corporate-action cashflows or locates',
        policies=POLICIES,controls='Fixed10 same side; reverse same exit and unhedged same exit are paired counterfactuals, not new tuned executable policies',
        bootstrap='20-signal-session blocks with2000 fixedseed ratio draws; dates shared by names, both per-trade and equal-date means',
        gate='For each scope primary OU_DYNAMIC NON_OVERLAP: >=100 trades, per-trade AND equal-date CI95 lower>0 in2025 AND2026; stress mean>0 both years; top20 winning trades <50% of positive contribution both years. Otherwise no robust promotion.',
        price_reserves=parent['price_reserves'],identity_events=parent['identity_events'],
        sql=False,api_calls=0,new_ml_training=False,production_changes=False,orders=False,portfolio_pnl=False,
        reserves=['Previously explored2024-26, not virgin OOS; current survivor universe, no historical capitalisation/sector reconstruction',
                  'Research normalized daily prices, not independent execution certification; split/reserve rules inherited',
                  'Market-only, fixed hedge, symmetric exits, ten-session cap and risk overlay are deviations from professional sector/PCA design',
                  'Per gross unit trade returns, no finite portfolio capacity, integer shares, actual margin/borrow/dividends or annual capital-return claim'])
    atomic_json(root/'protocol.json',p)
    dates=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date=p['observation_end']).index
    pd.DataFrame(dict(date=dates)).to_parquet(root/'sessions.parquet',index=False)
    top=pd.concat([pd.read_parquet(SCORES/f'{y}-H10-scores.parquet',columns=['date','symbol','rank']) for y in p['years']],ignore_index=True)
    top=top[top['rank'].le(10)].sort_values(['date','rank','symbol']).reset_index(drop=True)
    top.to_parquet(root/'oracle-top10.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={f:digest(root/f) for f in ['sessions.parquet','oracle-top10.parquet']}))
    return p


def build(root):
    p=prepare(root); verify_hashes(root,READ(root/'prepared.json')['files'])
    if (root/'data-ready.json').exists():
        verify_hashes(root,READ(root/'data-ready.json')['files']); return
    days=pd.DatetimeIndex(pd.read_parquet(root/'sessions.parquet').date)
    prices=pd.read_parquet(PRICE); groups=dict(tuple(prices.groupby('symbol',sort=False)))
    spy=valid_grid(groups['SPY'],days)
    spy_valid=spy.history_point_good.to_numpy(bool)
    top=pd.read_parquet(root/'oracle-top10.parquet'); top_keys=set(zip(top.symbol,pd.to_datetime(top.date)))
    root.joinpath('parts').mkdir(exist_ok=False)
    diagnostics=[]; candidate_parts=[]; feature_parts=[]; result_parts=[]; files={}
    for ix,symbol in enumerate(p['symbols']):
        if symbol not in groups:
            diagnostics.append(dict(symbol=symbol,status='NO_ARCHIVED_PRICES',feature_days=0,liquid_days=0,ou_days=0,signals=0))
            continue
        reserve=p['price_reserves'].get(symbol); events=p['identity_events'].get(symbol,[])
        g=valid_grid(groups[symbol],days,reserve,events)
        f=ou_signals(g.close,spy.close,g.history_point_good.to_numpy(bool)&spy_valid)
        f.index=days
        f['model_valid'] &= g.stable_history.to_numpy(bool)&spy.stable_history.to_numpy(bool)
        f['entry_eligible']=f.model_valid&g.liquidity_pass.to_numpy(bool)
        f['adv20_proxy']=g.adv20_proxy.to_numpy(float)
        f['date']=days; f['symbol']=symbol
        period=(days>='2024-01-01')&(days<=p['signal_end'])
        cand=f.entry_eligible.to_numpy(bool)&f.s_score.abs().gt(1.25).to_numpy()&period
        diagnostics.append(dict(symbol=symbol,status='OK',feature_days=int((period&g.stable_history).sum()),
            liquid_days=int((period&g.liquidity_pass).sum()),ou_days=int((period&f.model_valid).sum()),signals=int(cand.sum())))
        # Keep the original past-only feature series for exit audit and prefix checks.
        feature_parts.append(f.reset_index(drop=True))
        blocked={'FULL_TRADABLE':-1,'ORACLE_H10_TOP10':-1}
        for pos in np.flatnonzero(cand):
            side='LONG' if f.s_score.iloc[pos]<0 else 'SHORT'; beta=float(f.beta.iloc[pos])
            for scope in p['scopes']:
                if scope=='ORACLE_H10_TOP10' and (symbol,days[pos]) not in top_keys: continue
                independent=pos>blocked[scope]
                if independent: blocked[scope]=pos+MAX_HOLD+1
                reason=window_reason(g,pos,reserve,events)
                if reason=='OK': reason=window_reason(spy,pos)
                common=dict(symbol=symbol,date=days[pos],year=int(days[pos].year),scope=scope,side=side,
                    beta=beta,s_score=float(f.s_score.iloc[pos]),tau_sessions=float(f.tau_sessions.iloc[pos]),
                    independent=independent,entry_date=days[pos+1],last_path_date=days[pos+11],quality=reason)
                candidate_parts.append(common)
                if reason!='OK': continue
                end,why,age=daily_exit(g.open,g.close,spy.open,spy.close,f.s_score,f.model_valid,
                    pos=pos,side=side,beta=beta)
                for policy in POLICIES:
                    exit_pos=pos+11 if policy=='SAME_SIDE_FIXED10' else end
                    expiry=policy=='SAME_SIDE_FIXED10'
                    calendar_days=(days[exit_pos]-days[pos+1]).days
                    ret=returns_for(float(g.open.iloc[pos+1]),float(g.open.iloc[exit_pos]),
                        float(spy.open.iloc[pos+1]),float(spy.open.iloc[exit_pos]),beta,side,calendar_days,policy)
                    result_parts.append(dict(**common,policy=policy,exit_date=days[exit_pos],
                        executed_side=('SHORT' if side=='LONG' else 'LONG') if policy=='REVERSE_SAME_EXIT' else side,
                        exit_reason='FIXED10_NEXT_OPEN' if expiry else why,exit_session=MAX_HOLD if expiry else age,
                        entry_stock=float(g.open.iloc[pos+1]),exit_stock=float(g.open.iloc[exit_pos]),
                        entry_market=float(spy.open.iloc[pos+1]),exit_market=float(spy.open.iloc[exit_pos]),**ret))
        if (ix+1)%50==0 or ix+1==len(p['symbols']):
            chunk=ix//50
            outputs={f'parts/{chunk:04d}-features.parquet':pd.concat(feature_parts,ignore_index=True) if feature_parts else pd.DataFrame(),
                f'parts/{chunk:04d}-candidates.parquet':pd.DataFrame(candidate_parts),
                f'parts/{chunk:04d}-trades.parquet':pd.DataFrame(result_parts)}
            for name,frame in outputs.items():
                frame.to_parquet(root/name,index=False); files[name]=digest(root/name)
            feature_parts=[]; candidate_parts=[]; result_parts=[]
            atomic_json(root/'progress.json',dict(status='RUNNING',completed=ix+1,total=len(p['symbols']),phase='OU_SIGNALS_AND_REPLAY'))
            LOG.info('OU reversion %d/%d',ix+1,len(p['symbols']))
    # Last symbol may have no archive; flush remaining buffers regardless.
    if feature_parts or candidate_parts or result_parts:
        for suffix,frame in [('features',pd.concat(feature_parts,ignore_index=True) if feature_parts else pd.DataFrame()),
                             ('candidates',pd.DataFrame(candidate_parts)),('trades',pd.DataFrame(result_parts))]:
            name=f'parts/tail-{suffix}.parquet';frame.to_parquet(root/name,index=False);files[name]=digest(root/name)
    pd.DataFrame(diagnostics).to_csv(root/'coverage.csv',index=False);files['coverage.csv']=digest(root/'coverage.csv')
    verify_hashes(Path('.'),p['sources'])
    atomic_json(root/'data-ready.json',dict(files=files))


def block_interval(frame,days,column='net'):
    if not len(frame): return [None,None]
    blocks=days.get_indexer(pd.to_datetime(frame.date))//20
    totals=pd.DataFrame(dict(block=blocks,value=frame[column].to_numpy(),n=1)).groupby('block')[['value','n']].sum()
    if len(totals)<5: return [None,None]
    rng=np.random.default_rng(20261019); draws=rng.integers(0,len(totals),size=(2000,len(totals)))
    v=totals.to_numpy()[draws].sum(axis=1)
    return [float(x) for x in np.quantile(v[:,0]/v[:,1],[.025,.975])]


def metrics(frame,days):
    if not len(frame): return dict(n=0,mean_net=None,ci95=[None,None],gate=False)
    positive=frame.loc[frame.net.gt(0),'net'];negative=frame.loc[frame.net.lt(0),'net']
    bydate=frame.groupby('date',as_index=False)[['net','net_stress']].mean()
    concentration=float(positive.nlargest(20).sum()/positive.sum()) if len(positive) else None
    ci=block_interval(frame,days)
    dateci=block_interval(bydate,days)
    return dict(n=len(frame),symbols=int(frame.symbol.nunique()),dates=len(bydate),
        mean_net=float(frame.net.mean()),median_net=float(frame.net.median()),
        mean_stress=float(frame.net_stress.mean()),win_rate=float(frame.net.gt(0).mean()),
        mean_gain=float(positive.mean()) if len(positive) else None,mean_loss=float(negative.mean()) if len(negative) else None,
        profit_factor=float(positive.sum()/-negative.sum()) if len(negative) else None,
        worst=float(frame.net.min()),mean_hold=float(frame.exit_session.mean()),
        top20_positive_share=concentration,ci95=ci,mean_equal_date=float(bydate.net.mean()),equal_date_ci95=dateci,
        exits={str(k):int(v) for k,v in frame.exit_reason.value_counts().items()},
        gate=bool(len(frame)>=100 and ci[0] is not None and ci[0]>0 and dateci[0] is not None and dateci[0]>0
            and frame.net_stress.mean()>0 and concentration is not None and concentration<.5))


def summarize(root):
    p=prepare(root);ready=READ(root/'data-ready.json');verify_hashes(root,ready['files'])
    days=pd.DatetimeIndex(pd.read_parquet(root/'sessions.parquet').date)
    def load(suffix):
        pieces=[pd.read_parquet(root/n) for n in ready['files'] if n.endswith(suffix)]
        pieces=[x for x in pieces if len(x)]
        return pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()
    candidates=load('-candidates.parquet');trades=load('-trades.parquet')
    candidates.to_parquet(root/'candidates.parquet',index=False);trades.to_parquet(root/'trades.parquet',index=False)
    rows=[]
    if len(trades):
        for (scope,year,policy),f in trades.groupby(['scope','year','policy']):
            for side in ['ALL','LONG','SHORT']:
                g=f if side=='ALL' else f[f.side.eq(side)]
                for cohort,h in [('ALL',g),('NON_OVERLAP',g[g.independent])]:
                    rows.append(dict(scope=scope,year=int(year),policy=policy,side=side,cohort=cohort,**metrics(h,days)))
    pd.DataFrame(rows).to_csv(root/'summary.csv',index=False)
    primary=[r for r in rows if r['policy']=='OU_DYNAMIC' and r['cohort']=='NON_OVERLAP' and r['side']=='ALL']
    passes={scope:all(next((r.get('gate',False) for r in primary if r['scope']==scope and r['year']==y),False)
        for y in [2025,2026]) for scope in p['scopes']}
    cov=candidates.groupby(['scope','year','quality']).size().rename('n').reset_index() if len(candidates) else pd.DataFrame()
    cov.to_csv(root/'candidate-coverage.csv',index=False)
    report=dict(status='EXPLORATORY_SIGNAL_CANDIDATE_NOT_PRODUCTION' if any(passes.values()) else 'NO_ROBUST_RESIDUAL_REVERSION',
        scope_gates=passes,primary=primary,summaries=rows,
        signal_candidates=len(candidates),qualified_candidates=int(candidates.quality.eq('OK').sum()) if len(candidates) else 0,
        files={f:digest(root/f) for f in ['candidates.parquet','trades.parquet','summary.csv','candidate-coverage.csv']},
        conclusion='Bounded market-only adaptation. Per gross unit occasions, not annual capital PnL or a replication of professional fund returns.')
    atomic_json(root/'report.json',report)
    atomic_json(root/'progress.json',dict(status='COMPLETED',verdict=report['status'],scope_gates=passes))
    LOG.info('Finished: %s', {k:v for k,v in report.items() if k not in ['primary','summaries','files']})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','build','summarize'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'build':build,'summarize':summarize}[args.phase](args.output)


if __name__=='__main__':main()
