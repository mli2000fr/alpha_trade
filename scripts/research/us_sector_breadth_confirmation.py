"""Fixed sector/breadth and archived LONG regime audit. Read-only SQL, no fit."""
import json
import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from scripts.research.us_intersection_sentiment_deciles import ROOT
from scripts.research.us_feature_combination_d10 import metrics

DEST = ROOT / 'sector-breadth-confirmation-20261004-v1'
PROTOCOL = Path('doc/ml/us_confirmation_secteur_breadth_protocole.md')


def sector_context(bars, sectors, sessions):
    """Past-only features with dense-session support and leave-one-out peers."""
    if bars.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate price keys')
    prices = bars.pivot(index='date', columns='symbol', values='adj_close').reindex(sessions)
    prices = prices.where(prices.gt(0))
    support = prices.notna().rolling(21, min_periods=21).sum().eq(21)
    ret = (prices / prices.shift(20) - 1).where(support)
    above = prices.gt(prices.rolling(20, min_periods=20).mean()).astype(float).where(support)
    rows=[]
    for sector, group in sectors.groupby('sector'):
        if str(sector).strip().upper() in {'', 'UNKNOWN', 'NAN', 'NONE'}:
            continue
        names = sorted(set(group.symbol) & set(prices.columns))
        if len(names)<21:
            continue
        r, a = ret[names], above[names]
        count = r.notna().sum(axis=1)
        other = r.notna().astype(int).rsub(count, axis=0)
        peer_ret = r.rsub(r.sum(axis=1), axis=0).div(other.replace(0,np.nan))
        peer_breadth = a.rsub(a.sum(axis=1), axis=0).div(other.replace(0,np.nan))
        eligible = r.notna() & other.ge(20)
        fields={'relative20':(r-peer_ret).where(eligible),
                'breadth20':peer_breadth.where(eligible),
                'sector_peers':other.where(eligible)}
        tidy = pd.concat({k:v.stack() for k,v in fields.items()},axis=1).reset_index()
        tidy['sector_context']=sector
        rows.append(tidy)
    if not rows:
        raise ValueError('No supported sectors')
    return pd.concat(rows,ignore_index=True)


def regime_mask(frame):
    known=frame['mode'].isin(['normal','capital_preservation','close_only','cash_only']) & frame.allow_new_entries.notna()
    allowed=known & frame['mode'].eq('normal') & frame.allow_new_entries.eq(1)
    return known, allowed


def evaluate(data, mask):
    base=metrics(data)
    kept=data[mask]
    result=metrics(kept)
    valid=data.target_quality_valid.eq(1)&data.future_return.notna()
    d10=valid&data.oracle_decile.eq(10)
    d1=valid&data.oracle_decile.eq(1)
    result.update(retention_pct=100*float(mask.mean()) if len(data) else None,
                  d10_retained_pct=100*float(mask[d10].mean()) if d10.any() else None,
                  d1_removed_pct=100*float((~mask[d1]).mean()) if d1.any() else None,
                  fixed_initial_budget_return_pct=100*float(data.loc[valid & mask,'future_return'].sum()/valid.sum()) if valid.any() else None,
                  baseline=base)
    return result


def main():
    logging.basicConfig(level=logging.INFO)
    DEST.mkdir(parents=True,exist_ok=False)
    def progress(phase,**fields):
        payload={'phase':phase,**fields}
        (DEST/'progress.json').write_text(json.dumps(payload),encoding='utf-8')
        logging.info('%s',payload)
    progress('LOAD_SELECTION')
    paths=[ROOT/'combination-history-2019-2025-20261004-v1/mv_top10_all_years.parquet',
           ROOT/'combination-history-2026q1-20261004-v1/mv_top10_all_years.parquet']
    selected=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
    if selected.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate selections')
    universe=Path('config/univers/univers_filtred_tradable.txt')
    symbols=sorted(set(x.strip().upper() for x in universe.read_text().split(',') if x.strip()))
    engine=get_sqlalchemy_engine()
    bars=[]
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US database required')
        sectors=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata'),conn)
        if sectors.symbol.duplicated().any():
            raise ValueError('Duplicate sector keys')
        sectors=sectors[sectors.symbol.isin(symbols)].dropna(subset=['sector'])
        sessions=pd.read_sql(text("SELECT date FROM stock_bars_daily WHERE symbol='SPY' AND date BETWEEN '2018-10-01' AND '2026-03-31' ORDER BY date"),conn)
        macro=pd.read_sql(text("SELECT trade_date AS date,mode,allow_new_entries,vix,vxn,vix3m,move FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2019-01-01' AND '2026-03-31'"),conn)
        query=text("SELECT date,symbol,adj_close FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN '2018-10-01' AND '2026-03-31'").bindparams(bindparam('symbols',expanding=True))
        for offset in range(0,len(symbols),150):
            progress('LOAD_BARS',symbols_done=offset,symbols_total=len(symbols))
            bars.append(pd.read_sql(query,conn,params={'symbols':symbols[offset:offset+150]}))
    bars=pd.concat(bars,ignore_index=True)
    bars['date']=pd.to_datetime(bars.date)
    sessions=pd.DatetimeIndex(pd.to_datetime(sessions.date))
    if sessions.duplicated().any():
        raise ValueError('Duplicate calendar dates')
    macro['date']=pd.to_datetime(macro.date)
    progress('COMPUTE_SECTOR_CONTEXT',bars=len(bars))
    context=sector_context(bars,sectors,sessions)
    del bars
    selected=selected.merge(context,on=['date','symbol'],how='left',validate='one_to_one').merge(macro,on='date',how='left',validate='many_to_one')
    known, allowed=regime_mask(selected)
    complete=selected[['vix','vxn','vix3m','move']].notna().all(axis=1)
    rs=selected.relative20.gt(0)
    breadth=selected.breadth20.gt(.5)
    masks={'BASE':pd.Series(True,index=selected.index),'REGIME':allowed,
           'RS':rs,'BREADTH':breadth,'RS_BREADTH':rs&breadth,
           'REGIME_RS':allowed&rs,'REGIME_BREADTH':allowed&breadth,
           'REGIME_RS_BREADTH':allowed&rs&breadth}
    # The masks reference only present/past prices, metadata and archived mode.
    for name,mask in masks.items():
        selected['keep_'+name]=mask
    selected['regime_known']=known
    selected['macro_complete']=complete
    scopes={'2019_2022':selected.date.lt('2023-01-01'),
            '2023_2025':selected.date.ge('2023-01-01')&selected.date.lt('2026-01-01'),
            '2026Q1':selected.date.ge('2026-01-01')}
    def summarize(group):
        return {name:evaluate(group,group['keep_'+name]) for name in masks}
    result={'status':'COMPLETED_EXPLORATORY_NON_PIT_SECTORS','protocol_sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            'universe_sha256':hashlib.sha256(universe.read_bytes()).hexdigest(),
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'overall':summarize(selected),
            'windows':{key:summarize(selected[mask]) for key,mask in scopes.items()},
            'years':{str(k):summarize(g) for k,g in selected.groupby(selected.date.dt.year)},
            'months':{str(k):summarize(g) for k,g in selected.groupby(selected.date.dt.to_period('M'))},
            'coverage':{'sector_supported':int(selected.relative20.notna().sum()),'total':len(selected),
                        'regime_known':int(known.sum()),'macro_complete':int(complete.sum()),
                        'normal_missing_macro':int((allowed&~complete).sum())},
            'regime_groups':{str(k):metrics(g) for k,g in selected.groupby(selected['mode'].fillna('UNKNOWN'))},
            'blocked_known_regime':metrics(selected[known&~allowed]),
            'notes':['Current sector metadata non-PIT; static surviving universe',
                     'Archived mode at signal J; not full risk engine replay or entry J+1',
                     'No regime replacement for missing macros; normal incomplete marked',
                     'No fill, costs, portfolio, refit, reranking, tuning, or SQL write',
                     'Previously inspected years: no pristine prospective confirmation']}
    progress('WRITE_RESULTS')
    selected.to_parquet(DEST/'selection_masks.parquet',index=False)
    context.to_parquet(DEST/'sector_context.parquet',index=False)
    (DEST/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    progress('COMPLETED')
    print('COMPLETED',DEST)


if __name__=='__main__':
    main()
