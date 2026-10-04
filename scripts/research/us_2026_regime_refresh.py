"""Refresh frozen Q1 selections using new macro and pure sequential regime replay."""
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import event, text

from common.config_loader import load_config, resolve_config_path
from database.connection import get_sqlalchemy_engine
from service.market.config import parse_market_regimes
from service.market.macro_providers import TableFirstMacroProvider, _snapshot_to_next_state
from service.market.regime_manager import build_snapshot
from service.market.sentiment_provider import DbSentimentScoreProvider
from scripts.research.us_sector_breadth_confirmation import evaluate, regime_mask
from scripts.research.us_feature_combination_d10 import metrics
from scripts.research.us_intersection_sentiment_deciles import ROOT

SOURCE=ROOT/'sector-breadth-confirmation-20261004-v1/selection_masks.parquet'
DEST=ROOT/'regime-refresh-2026q1-20261004-v1'


def forbid_writes(conn,cursor,statement,parameters,context,executemany):
    if statement.lstrip().split()[0].upper() not in {'SELECT','SHOW','DESCRIBE','EXPLAIN'}:
        raise RuntimeError('Read-only research guard rejected SQL')


def main():
    logging.basicConfig(level=logging.INFO)
    DEST.mkdir(parents=True,exist_ok=False)
    def progress(phase,**fields):
        (DEST/'progress.json').write_text(json.dumps({'phase':phase,**fields}),encoding='utf-8')
        logging.info('%s %s',phase,fields)
    progress('LOAD')
    data=pd.read_parquet(SOURCE)
    data=data[data.date.ge('2026-01-01')].copy().reset_index(drop=True)
    config_path=resolve_config_path()
    root_cfg=load_config(config_path)
    config=parse_market_regimes(root_cfg.get('market_regimes') or {})
    engine=get_sqlalchemy_engine()
    event.listen(engine,'before_cursor_execute',forbid_writes)
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US database required')
        macro=pd.read_sql(text("SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2025-11-01' AND '2026-06-30' ORDER BY trade_date"),conn)
        sessions=pd.read_sql(text("SELECT date FROM stock_bars_daily WHERE symbol='SPY' AND date BETWEEN '2025-11-01' AND '2026-03-31' ORDER BY date"),conn)
    macro['date']=pd.to_datetime(macro.trade_date)
    if macro.date.duplicated().any():
        raise ValueError('Duplicate macro dates')
    macro.to_parquet(DEST/'macro_read_snapshot.parquet',index=False)
    fresh=macro[['date','mode','allow_new_entries','vix','vxn','vix3m','move']]
    joined=data.drop(columns=['mode','allow_new_entries','vix','vxn','vix3m','move']).merge(fresh,on='date',how='left',validate='many_to_one')
    known,archived=regime_mask(joined)
    complete=joined[['vix','vxn','vix3m','move']].notna().all(axis=1)
    if not complete.all():
        raise ValueError('Updated macro incomplete on frozen candidate dates')
    provider=TableFirstMacroProvider(None,engine=engine,strict_before=False,persist_fallback_hits=False)
    previous=None
    snapshots=[]
    candidate_allow={}
    for index,value in enumerate(pd.to_datetime(sessions.date)):
        day=value.date()
        progress('SEQUENTIAL_REPLAY',date=day.isoformat(),session=index+1,total=len(sessions))
        exact=macro[macro.date.eq(value)]
        if exact.empty:
            raise ValueError(f'Missing exact macro warmup {day}')
        snapshot=build_snapshot(day,config=config,equity=4000,execution_context='backtest',
                                macro_provider=provider,sentiment_score_provider=DbSentimentScoreProvider(day,engine=engine),
                                previous_state=previous,use_cache=False)
        previous=_snapshot_to_next_state(snapshot)
        payload=snapshot.to_summary_dict()
        payload['date']=day.isoformat()
        payload['allowed_long_entries']=snapshot.allowed_long_entries
        snapshots.append(payload)
        rows=joined[joined.date.eq(value)]
        for row in rows.itertuples():
            candidate_allow[(value,row.symbol)]=not snapshot.blocks_entry_for(row.symbol,row.sector if pd.notna(row.sector) else None,side='buy')[0]
    lookup=pd.DataFrame([{'date':pd.Timestamp(p['date']),'replayed_mode':p['mode'],
                          'replayed_allow_long':p['allowed_long_entries']} for p in snapshots])
    joined=joined.merge(lookup,on='date',how='left',validate='many_to_one')
    if joined.replayed_allow_long.isna().any():
        raise ValueError('Missing reconstructed regime')
    replayed=joined.replayed_allow_long.astype(bool)
    candidate=pd.Series([candidate_allow[(row.date,row.symbol)] for row in joined.itertuples()],index=joined.index)
    rs=joined.relative20.gt(0)
    breadth=joined.breadth20.gt(.5)
    masks={'BASE':pd.Series(True,index=joined.index),'ARCHIVED_REGIME':archived,
           'REPLAYED_LONG':replayed,'REPLAYED_LONG_SECTOR_BLOCKS':candidate,
           'RS_BREADTH':rs&breadth,'ARCHIVED_RS_BREADTH':archived&rs&breadth,
           'REPLAYED_RS_BREADTH':replayed&rs&breadth}
    for key,mask in masks.items():
        joined['refresh_keep_'+key]=mask
    def summarize(group):
        return {k:evaluate(group,group['refresh_keep_'+k]) for k in masks}
    summary={'status':'COMPLETED_READONLY_REFRESH','period':'2026-01-01/2026-03-31',
             'overall':summarize(joined),
             'months':{str(k):summarize(g) for k,g in joined.groupby(joined.date.dt.to_period('M'))},
             'archived_modes':joined.groupby('mode').size().to_dict(),
             'replayed_modes':joined.groupby('replayed_mode').size().to_dict(),
             'blocked_archived':metrics(joined[known&~archived]),
             'blocked_replayed':metrics(joined[~replayed]),
             'coverage':{'candidate_dates':joined.date.nunique(),'observations':len(joined),
                         'complete_macro_observations':int(complete.sum()),
                         'by_month':{str(m):{c:int(g[c].notna().sum()) for c in ['vix','vxn','vix3m','move']} for m,g in macro[macro.date.ge('2026-01-01')].groupby(macro.date.dt.to_period('M'))}},
             'blocked_dates_archived':sorted(joined.loc[~archived,'date'].dt.strftime('%Y-%m-%d').unique().tolist()),
             'blocked_dates_replayed':sorted(joined.loc[~replayed,'date'].dt.strftime('%Y-%m-%d').unique().tolist()),
             'config_path':str(config_path),'config_sha256':hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
             'selection_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
             'old_archived_regime_result':evaluate(data,data.keep_REGIME),
             'notes':['Candidates, relative features and labels frozen; no reranking or refit',
                      'New macro snapshot read only; SQL write guard active',
                      'Sequential build_snapshot with current config, equity4000, November2025 warmup',
                      'Exact signal-day regime, not entryJ+1 or portfolio/lifecycle',
                      'Sector blocks use current non-PIT tags; earnings lookup not injected',
                      'Db sentiment current history not newly certified PIT; no network fallback',
                      'Current adjusted prices and retrospective macro revisions not certified original vintages',
                      'Q1 only: no April-June selection generated by this refresh']}
    (DEST/'snapshots.json').write_text(json.dumps(snapshots,default=str,indent=2),encoding='utf-8')
    joined.to_parquet(DEST/'selection_refreshed.parquet',index=False)
    (DEST/'report.json').write_text(json.dumps(summary,default=str,indent=2,allow_nan=False),encoding='utf-8')
    progress('COMPLETED')
    print(DEST)


if __name__=='__main__':
    main()
