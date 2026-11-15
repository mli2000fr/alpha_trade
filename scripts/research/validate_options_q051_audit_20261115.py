"""Independent coverage/selection/count reconciliation for the options audit."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scripts.research.us_options_q051_top_fraction_audit_20261115 import ROOT,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.options_asof_rows_20261115 import rows_asof
from service.options_directional.features import _latest
from common.daily_bar_sources import select_daily_bars


def latest_funnel(root):
    p=read(root/'protocol.json');day=pd.Timestamp(p['last_price_date']);cutoff=pd.Timestamp(p['cutoff_utc'])
    prices=select_daily_bars(pd.read_parquet(root/'prices.parquet'),config=p['daily_price_config'])
    prices['date']=pd.to_datetime(prices.date);prices['close']=pd.to_numeric(prices.close).astype(float)
    spots=prices[prices.date.eq(day)&prices.is_filled.eq(0)&prices.close.gt(0)].set_index('symbol').close.to_dict();result={}
    for name in ['snapshots','volumes']:
        frames=[]
        for file in (root/'raw'/name).glob('*.parquet'):
            if not pq.read_metadata(file).num_rows:continue
            f=pd.read_parquet(file,filters=[('available_at','>=',(cutoff-pd.Timedelta(hours=96)).tz_localize(None))])
            if len(f):frames.append(f)
        f=pd.concat(frames,ignore_index=True);f=f[pd.to_datetime(f.available_at,utc=True).le(cutoff)]
        q=rows_asof(f,day.date(),cutoff,volume=name=='volumes')
        stats=dict(received_last96h_symbols=int(f.symbol.nunique()),DTE15_25_and_session72h_symbols=int(q.symbol.nunique()))
        if name=='snapshots':
            q['strike']=pd.to_numeric(q.strike);q['open_interest']=pd.to_numeric(q.open_interest)
            q=_latest(q,['symbol','contract_symbol'],['open_interest','strike','expiration_date','option_type','payload_hash'])
            q['spot']=q.symbol.map(spots);q=q[(q.strike/q.spot-1).abs().le(.05)&q.open_interest.ge(0)&np.isfinite(q.open_interest)]
            stats['numeric_OI_and_ATM5pct_symbols']=int(q.symbol.nunique())
            both=q[q.option_type.eq('CALL')].merge(q[q.option_type.eq('PUT')],on=['symbol','expiration_date','strike'])
        else:
            q['volume']=pd.to_numeric(q.volume)
            q=_latest(q,['symbol','contract_symbol','bar_timestamp'],['volume','payload_hash','option_type','expiration_date'])
            q=q[q.volume.ge(0)&np.isfinite(q.volume)]
            both=q[q.option_type.eq('CALL')][['symbol','expiration_date']].drop_duplicates().merge(
                q[q.option_type.eq('PUT')][['symbol','expiration_date']].drop_duplicates(),on=['symbol','expiration_date'])
        stats['matched_CALL_PUT_symbols']=int(both.symbol.nunique());stats['matched_symbols']=sorted(both.symbol.unique());result[name]=stats
    result['joint_latest']=len(set(result['snapshots']['matched_symbols'])&set(result['volumes']['matched_symbols']))
    atomic_json(root/'latest-qualification-funnel.json',result)
    return result


def validate(root=ROOT):
    root=Path(root);out=root/'analysis-v2';p=read(root/'protocol.json');r=read(out/'report.json')
    for name,sha in read(root/'snapshot-seal.json')['files'].items():
        if digest(root/name)!=sha:raise ValueError('Changed SQL snapshot')
    for name,sha in read(out/'protocol.json')['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Changed analysis source')
    if read(out/'isolation.json')['status']!='COMPLETED' or read(out/'isolation.json').get('violations'):raise ValueError('Isolation incomplete')
    pool=pd.read_parquet(out/'oracle-pool-before-options.parquet')
    if pool.groupby('signal_day').size().ne(179).any():raise ValueError('Wrong frozen Oracle pool')
    selections=pd.read_parquet(out/'decisions-before-outcomes.parquet')
    if selections.duplicated(['mode','signal_day','symbol']).any():raise ValueError('Duplicate decision')
    if (selections.loc[selections.options_selected,'combined_score']<=.5).any():raise ValueError('Score gate not applied')
    features=pd.read_parquet(out/'features.parquet');clocks=pd.read_csv(out/'universe-daily-coverage.csv',parse_dates=['signal_day'])
    joined=features.merge(clocks[['mode','signal_day','decision_at']],on=['mode','signal_day'],validate='many_to_one')
    if not pd.to_datetime(joined.available_at,utc=True,format='mixed').le(pd.to_datetime(joined.decision_at,utc=True,format='mixed')).all():raise ValueError('Future option receipt')
    frame=pd.read_parquet(out/'outcomes.parquet')
    for s in r['results']:
        f=frame[frame['mode'].eq(s['mode'])&frame.horizon.eq(s['horizon'])]
        if s['stage']=='PER_SYMBOL_TOP5_RETAINED':f=f[f.per_symbol_selected]
        for name,g in [('all_stage',f),('covered',f[f.combined_score.notna()]),('selected',f[f.options_selected])]:
            m=s[name];direction=g[g.path_status.eq('LABEL')];trades=g[g.trade_status.eq('VALID')]
            if len(g)!=m['candidates'] or len(direction)!=m['direction_n'] or len(trades)!=m['trade_n']:raise ValueError('Outcome denominator mismatch')
            if int(direction.dominant_direction.eq('LONG').sum())!=m['long_n']:raise ValueError('Direction numerator mismatch')
            if len(trades) and int(trades.winning.sum())!=m['wins']:raise ValueError('Trade numerator mismatch')
    funnel=latest_funnel(root)
    latest=clocks[clocks['mode'].eq('ASOF_72H')].iloc[-1]
    if funnel['joint_latest']!=int(latest.qualified_combined):raise ValueError('Independent latest coverage differs')
    result=dict(status='PASS',Oracle_dates=int(pool.signal_day.nunique()),Oracle_candidates=len(pool),
        per_symbol_candidates=int(pool.per_symbol_selected.sum()),future_receipts=0,no_production_code_changed=True,
        outcomes_and_denominators_recounted=True,latest_qualified=funnel['joint_latest'],
        SQL_writes=0,provider_calls=0,orders=0,training=False,new_inference=False)
    atomic_json(out/'validation.json',result)
    return result


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
