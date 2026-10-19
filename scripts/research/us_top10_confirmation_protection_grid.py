"""Bounded TP/SL sensitivity on frozen four-close H10 TOP10 entries at J+3.

Choose on 2024 only; inspect frozen choices in 2025/26. No fitting, SQL, API,
production changes or capital portfolio claim. Prior studies stay immutable.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import logging

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_four_session_confirmation as parent
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = Path('artifacts/research/us_top10_four_session_confirmation/20261019-v1')
REFERENCE = 'TP10_SL5'
READ = parent.previous.prior.read
EXEC = parent.previous.execution
ARMS = parent.previous.ARMS
MAIN_ARMS = ['CONFIRMED_LONG','CONFIRMED_SHORT','CONFIRMED_DIRECTION']
LOG = logging.getLogger(__name__)


def profiles():
    return {f'TP{tp}_SL{sl}':dict(tp=tp/100,sl=sl/100) for tp in (5,10,15,20) for sl in (3,5,7,10)}


def atr_profiles():
    return {f'ATR{k:g}_RR2':dict(mode='atr20',stop_atr_multiple=k,reward_risk=2.,min_sl=.03,max_sl=.10) for k in (1.,1.5,2.)}


def atr20_at_confirmation(grid, positions):
    """Simple mean true range20 at J+2, with 21 consecutive valid historical bars."""
    pos=np.asarray(positions,dtype=int); end=pos+2
    if (end<20).any(): raise ValueError('Insufficient ATR calendar history')
    values=grid[['open','high','low','close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    good=(np.isfinite(values[['open','high','low','close']]).all(axis=1)
        & values[['open','high','low','close']].gt(0).all(axis=1)
        & values.high.ge(values[['open','close','low']].max(axis=1))
        & values.low.le(values[['open','close','high']].min(axis=1))
        & values.volume.gt(0) & values.is_filled.eq(0))
    indexes=end[:,None]+np.arange(-20,1)
    valid=good.to_numpy()[indexes].all(axis=1)
    for field in ('instrument_id','data_source','data_adjustment'):
        codes=pd.factorize(grid[field])[0][indexes]
        known=codes[:,0]>=0
        if field!='instrument_id': known &= ~grid[field].iloc[end-20].astype(str).str.upper().isin(['UNKNOWN','']).to_numpy()
        valid &= (codes==codes[:,:1]).all(axis=1) & known
    with np.errstate(divide='ignore',invalid='ignore'):
        closes=values.close.to_numpy()[indexes]; ratios=closes[:,1:]/closes[:,:-1]
    valid &= ~((ratios>=20)|(ratios<=.05)).any(axis=1)
    tr=pd.concat([values.high-values.low,(values.high-values.close.shift()).abs(),(values.low-values.close.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(20,min_periods=20).mean().to_numpy()[end]
    valid &= np.isfinite(atr) & (atr>0)
    return np.where(valid,atr,np.nan),np.where(valid,'','INVALID_ATR20_HISTORY_AT_J_PLUS_2')


def atr_distances(atr,entry,protection):
    atr=np.asarray(atr,dtype=float); entry=np.asarray(entry,dtype=float)
    if not (np.isfinite(atr).all() and (atr>0).all() and np.isfinite(entry).all() and (entry>0).all()):
        raise ValueError('Invalid ATR or entry price')
    sl=np.clip(protection['stop_atr_multiple']*atr/entry,protection['min_sl'],protection['max_sl'])
    return sl*protection['reward_risk'],sl


def variable_paths(grid,positions,side,tp,sl):
    """Vector barrier counterpart for entry-specific distances; sealed helper unchanged."""
    from numpy.lib.stride_tricks import sliding_window_view
    pos=np.asarray(positions,dtype=int); n=len(pos); horizon=10
    tp=np.broadcast_to(np.asarray(tp,dtype=float),(n,)); sl=np.broadcast_to(np.asarray(sl,dtype=float),(n,))
    if not n or (pos<0).any() or (pos+12>=len(grid)).any(): raise ValueError('Invalid delayed path window')
    if side not in ('LONG','SHORT') or not (np.isfinite(tp).all() and np.isfinite(sl).all() and ((tp>0)&(tp<1)&(sl>0)&(sl<1)).all()):
        raise ValueError('Invalid barriers')
    a={k:sliding_window_view(grid[k].to_numpy(float),horizon)[pos+3] for k in ('open','high','low','close')}
    if any(not np.isfinite(v).all() or (v<=0).any() for v in a.values()): raise ValueError('Invalid path prices')
    entry=a['open'][:,0]; long=side=='LONG'; sign=1 if long else -1
    take=entry*(1+tp if long else 1-tp); stop=entry*(1-sl if long else 1+sl)
    tt=1e-12*np.abs(take); tol=1e-12*np.abs(stop)
    hit_tp=a['high']>=(take-tt)[:,None] if long else a['low']<=(take+tt)[:,None]
    hit_sl=a['low']<=(stop+tol)[:,None] if long else a['high']>=(stop-tol)[:,None]
    code=np.zeros(n,dtype=np.int8); price=a['close'][:,-1].copy(); age=np.full(n,horizon,dtype=np.int16)
    ambiguous=np.zeros(n,dtype=bool); gap=np.zeros(n,dtype=bool); at_open=np.zeros(n,dtype=bool)
    for k in range(horizon):
        active=code==0
        os=np.zeros(n,dtype=bool) if k==0 else active & (a['open'][:,k]<=stop+tol if long else a['open'][:,k]>=stop-tol)
        ot=np.zeros(n,dtype=bool) if k==0 else active & ~os & (a['open'][:,k]>=take-tt if long else a['open'][:,k]<=take+tt)
        st=active & ~os & ~ot & hit_sl[:,k]; target=active & ~os & ~ot & ~st & hit_tp[:,k]
        code[os|st]=2; code[ot|target]=1; price[os]=a['open'][os,k]; price[st]=stop[st]; price[ot|target]=take[ot|target]
        age[os|ot|st|target]=k+1; ambiguous[st & hit_tp[:,k]]=True; gap[os]=True; at_open[os|ot]=True
    adverse=1-a['low']/entry[:,None] if long else a['high']/entry[:,None]-1
    day=np.arange(horizon)[None,:]; prior=day<age[:,None]-1
    mae_before=np.maximum(0.,np.where(prior,adverse,0.).max(axis=1))
    mae_through=np.maximum(0.,np.where(day<age[:,None],adverse,0.).max(axis=1))
    mae_through[at_open]=np.maximum(mae_before[at_open],np.maximum(0.,-sign*(price/entry-1))[at_open])
    terminal=sign*(a['close'][:,-1]/entry-1)
    return dict(outcome=np.array(['TIMEOUT','TP','SL'])[code],tp_first=code==1,sl_first=code==2,
        ambiguity=ambiguous,gap_stop=gap,entry_price=entry,exit_price=price,exit_session=age,
        path_return=sign*(price/entry-1),terminal_direction_right=terminal>0,mae_before_exit_bar=mae_before,
        mae_through_exit_bar=mae_through,terminal_signed_return=terminal)


def execute(grid, positions, side, protection):
    return EXEC.paths(grid,np.asarray(positions)+2,side,horizon=10,**protection)


def select_2024(rows, grid):
    """Never read test-year metrics for selection, even if supplied by a caller."""
    result={}
    for arm in MAIN_ARMS:
        eligible=[r for r in rows if r['year']==2024 and r['arm']==arm and r['n']>0]
        if len(eligible)!=len(grid): raise ValueError('Incomplete 2024 grid')
        def tie(row):
            spec=grid[row['profile']]
            return (-row['mean_net'],spec.get('sl',spec.get('min_sl')),spec.get('tp',1.),row['profile'])
        winner=min(eligible,key=tie)
        result[arm]=dict(profile=winner['profile'],selection_year=2024,criterion='Maximum mean net per opportunity; ties smaller SL then TP',
            selection_n=winner['n'],selection_mean_net=winner['mean_net'])
    return result


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); return p
    prior=READ(SOURCE/'protocol.json'); audit=READ(SOURCE/'final-audit.json')
    if audit['status']!='PASS_EXPLORATORY_ONLY' or audit['protocol_sha256']!=digest(SOURCE/'protocol.json'):
        raise ValueError('Unqualified four-close reference')
    verify_hashes(Path('.'),prior['sources']); verify_hashes(SOURCE,READ(SOURCE/'data-ready.json')['files'])
    verify_hashes(SOURCE,READ(SOURCE/'report.json')['files'])
    if audit['report_sha256']!=digest(SOURCE/'report.json'): raise ValueError('Changed reference')
    source_files=[Path(__file__),Path('tests/test_us_top10_confirmation_protection_grid.py'),
        Path(parent.__file__),Path(parent.previous.__file__),Path(EXEC.__file__),Path(EXEC.gate.__file__),Path(EXEC.base.__file__),Path('common/oracle_atr.py'),
        SOURCE/'protocol.json',SOURCE/'final-audit.json',SOURCE/'report.json',SOURCE/'selected-at-j.parquet',
        SOURCE/'qualification.parquet',SOURCE/'evaluations.parquet',Path(prior['prices'])]
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in source_files},
        profiles={**profiles(),**atr_profiles()},reference=REFERENCE,years=[2024,2025,2026],selection_year=2024,validation_years=[2025,2026],
        policy='Original H10 TOP10 at J; same strict four closes J-1..J+2, no new rank or replacement',
        entry='J+3 open; ten sessions entry included, timeout J+12 close',holding_sessions=10,trailing=False,
        parameter_selection='Separately LONG, SHORT and one common combined profile: highest 2024 mean net among 19; ties smaller fixed SL/ATR min SL then fixed TP or name; no eligibility tuning',
        atr='Simple mean TR20 using adjusted bars through J+2; absolute ATR divided by actual entry open J+3; SL clip(k*ATR/entry,3%,10%), TP=2*SL; levels fixed after fill, no trailing',
        common_cohort='Require same qualified 21-bar ATR history for all 19 profiles, including fixed controls; original J TOP10 never replaced',
        test_use='2025/26 descriptive frozen validation, never used for selecting a profile; historically already examined years',
        combination='Also report 2024-selected LONG and SHORT profiles combined, without using test years to choose whether to trade a side',
        costs_per_leg=prior['costs_per_leg'],short_borrow_annual=prior['short_borrow_annual'],
        prices=prior['prices'],price_reserves=prior['price_reserves'],identity_events=prior['identity_events'],
        gaps=prior['gaps'],collision=prior['collision'],last_signal=prior['last_signal'],observation_end=prior['observation_end'],
        interpretation='Per-occasion outcomes at identical entries, not annual capital returns, DD, margin or position sizing',
        sql=False,new_fit=False,api_calls=0,orders=False,production_changes=False,reserves=prior['reserves'])
    root.mkdir(parents=True,exist_ok=False); (root/'parts').mkdir(); atomic_json(root/'protocol.json',p); return p


def build(root):
    p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources'])
    if (root/'data-ready.json').exists(): verify_hashes(root,READ(root/'data-ready.json')['files']); return
    q=pd.read_parquet(SOURCE/'qualification.parquet'); selected=pd.read_parquet(SOURCE/'selected-at-j.parquet')
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',q.symbol.unique().tolist())])
    groups={str(s):g for s,g in prices.groupby('symbol',observed=True)}; symbols=sorted(groups)
    original=pd.read_parquet(SOURCE/'evaluations.parquet').set_index(['date','symbol','side'])
    files={}; parity=0; cohort=[]
    for chunk,start in enumerate(range(0,len(symbols),50)):
        folder=root/'parts'/f'{chunk:04}'; folder.mkdir(exist_ok=True); marker=folder/'done.json'
        if marker.exists():
            done=READ(marker); verify_hashes(root,done['files']); files.update(done['files']); parity+=done['reference_parity_rows']; cohort.extend(done['cohort']); continue
        pieces={name:[] for name in p['profiles']}; checked=0; diagnostics=[]
        for symbol in symbols[start:start+50]:
            s=q[q.symbol.eq(symbol)].sort_values('date'); pos=days.get_indexer(s.date)
            grid,direction,reasons=parent.qualify(groups[symbol],days,pos,
                identity_events=p['identity_events'].get(symbol,[]),price_reserve=p['price_reserves'].get(symbol))
            np.testing.assert_array_equal(direction,s.direction); np.testing.assert_array_equal(reasons,s.quality_reason)
            atr,atr_reason=atr20_at_confirmation(grid,pos)
            reasons=np.where(reasons!='',reasons,atr_reason)
            for event in p['identity_events'].get(symbol,[]):
                cross=((days[pos-18]<=pd.Timestamp(event['last_predecessor_date'])) & (days[pos+2]>=pd.Timestamp(event['first_successor_date'])))
                reasons[(reasons=='') & cross]='IDENTITY_BREAK_IN_ATR_HISTORY'
            for i,row in enumerate(s.itertuples()): diagnostics.append(dict(date=row.date,symbol=symbol,year=row.year,direction=row.direction,quality_reason=reasons[i],atr20=float(atr[i]) if np.isfinite(atr[i]) else None))
            keep=reasons==''; admitted=s[keep]; indexes=pos[keep]; atr=atr[keep]
            if admitted.empty: continue
            for name,protection in p['profiles'].items():
                for side in ('LONG','SHORT'):
                    if protection.get('mode')=='atr20':
                        tp_pct,sl_pct=atr_distances(atr,grid.open.iloc[indexes+3].to_numpy(float),protection)
                        result=variable_paths(grid,indexes,side,tp_pct,sl_pct)
                    else:
                        tp_pct=np.full(len(indexes),protection['tp']); sl_pct=np.full(len(indexes),protection['sl'])
                        result=execute(grid,indexes,side,protection)
                    if name==p['reference']:
                        ref=original.reindex(pd.MultiIndex.from_arrays([admitted.date,np.full(len(admitted),symbol),np.full(len(admitted),side)],names=original.index.names))
                        for field,value in result.items(): np.testing.assert_array_equal(value,ref[field].to_numpy())
                        checked+=len(ref)
                    pieces[name].append(pd.DataFrame(dict(date=admitted.date.to_numpy(),symbol=symbol,year=admitted.year.to_numpy(),
                        side=side,direction=admitted.direction.to_numpy(),entry_date=days[indexes+3],
                        confirmation_date=days[indexes+2],last_path_date=days[indexes+12],atr20=atr,tp_pct=tp_pct,sl_pct=sl_pct,**result)))
        part_files={}
        for name,frames in pieces.items():
            path=folder/f'{name}.parquet'; frame=EXEC.gate.attach_costs(pd.concat(frames,ignore_index=True))
            frame.to_parquet(path,index=False); part_files[str(path.relative_to(root))]=digest(path)
        atomic_json(marker,dict(files=part_files,reference_parity_rows=checked,cohort=diagnostics)); files.update(part_files); parity+=checked; cohort.extend(diagnostics)
        atomic_json(root/'progress.json',dict(status='RUNNING',phase='TP_SL_GRID',completed=min(start+50,len(symbols)),total=len(symbols)))
        LOG.info('Protection grid %d/%d symbols, reference parity %d',min(start+50,len(symbols)),len(symbols),parity)
    cohort=pd.DataFrame(cohort); cohort.to_parquet(root/'cohort.parquet',index=False); files['cohort.parquet']=digest(root/'cohort.parquet')
    assert parity==2*int(cohort.quality_reason.eq('').sum()) and len(selected)==len(q)==len(cohort)
    verify_hashes(Path('.'),p['sources']); atomic_json(root/'data-ready.json',dict(files=files,reference_parity_rows=parity,selected=len(q),common_qualified=int(cohort.quality_reason.eq('').sum()),exclusions=cohort.quality_reason.value_counts().to_dict()))


def summarize_arm(f,arm,profile,year,reference,days):
    s=parent.previous.select_arm(f[f.year.eq(year)],arm)
    if s.empty: return dict(year=year,profile=profile,arm=arm,n=0)
    independent=EXEC.base.independent_fast(s); win=s.net_outcome.gt(0); gains=s.loc[win,'net_outcome']; losses=s.loc[~win,'net_outcome']
    row=dict(year=year,profile=profile,arm=arm,n=len(s),mean_net=float(s.net_outcome.mean()),median_net=float(s.net_outcome.median()),
        win_rate=float(win.mean()),tp_rate=float(s.tp_first.mean()),sl_rate=float(s.sl_first.mean()),timeout_rate=float(s.outcome.eq('TIMEOUT').mean()),
        mean_win=float(gains.mean()) if len(gains) else None,mean_loss=float(losses.mean()) if len(losses) else None,
        profit_factor=float(gains.sum()/-losses.sum()) if len(losses) and losses.sum()<0 else None,worst=float(s.net_outcome.min()),
        gap_stop_rate=float(s.gap_stop.mean()),ambiguity_rate=float(s.ambiguity.mean()),
        median_tp_pct=float(s.tp_pct.median()),median_sl_pct=float(s.sl_pct.median()),min_sl_pct=float(s.sl_pct.min()),max_sl_pct=float(s.sl_pct.max()),
        independent_n=len(independent),independent_mean_net=float(independent.net_outcome.mean()),independent_win_rate=float(independent.net_outcome.gt(0).mean()))
    ref=parent.previous.select_arm(reference[reference.year.eq(year)],arm)
    pairs=s.merge(ref[['date','symbol','side','net_outcome']],on=['date','symbol','side'],validate='one_to_one',suffixes=('','_reference'))
    assert len(pairs)==len(ref)==len(s)
    row['paired_gain_vs_tp10_sl5']=EXEC.gate.block_interval((pairs.net_outcome-pairs.net_outcome_reference).groupby(pairs.date).mean(),days)
    return row


def summarize(root):
    p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); ready=READ(root/'data-ready.json'); verify_hashes(root,ready['files'])
    frames={name:pd.concat([pd.read_parquet(root/n) for n in ready['files'] if Path(n).stem==name],ignore_index=True) for name in p['profiles']}
    reference=frames[p['reference']]; days=nyse_sessions('2024-01-01','2026-10-09')
    # Seal the choice on 2024 before computing any test-year summaries.
    rows=[summarize_arm(f,arm,name,2024,reference,days) for name,f in frames.items() for arm in ARMS]
    selection=select_2024(rows,p['profiles'])
    atomic_json(root/'selected-on-2024.json',dict(choices=selection,protocol_sha256=digest(root/'protocol.json'),
        training_rows=rows,claim='Only 2024 used for parameter selection; later years cannot change these profiles'))
    for year in p['validation_years']:
        rows.extend(summarize_arm(f,arm,name,year,reference,days) for name,f in frames.items() for arm in ARMS)
    validation=[]
    for arm,choice in selection.items():
        for year in p['years']:
            row=next(r for r in rows if (r['year'],r['profile'],r['arm'])==(year,choice['profile'],arm))
            validation.append(row)
    mixed=[]
    for year in p['years']:
        sides=[]
        for side in ('LONG','SHORT'):
            name=selection['CONFIRMED_'+side]['profile']; f=frames[name]
            sides.append(parent.previous.select_arm(f[f.year.eq(year)],'CONFIRMED_'+side))
        data=pd.concat(sides,ignore_index=True)
        mixed.append(summarize_arm(data,'CONFIRMED_DIRECTION','MIXED_2024_SIDE_CHOICES',year,reference,days))
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in rows]).to_csv(root/'grid-comparison.csv',index=False)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in validation+mixed]).to_csv(root/'frozen-validation.csv',index=False)
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(root/'protocol.json'),
        grid=rows,choices=selection,frozen_validation=validation,mixed_frozen_validation=mixed,
        coverage=dict(selected=ready['selected'],common_qualified=ready['common_qualified'],exclusions=ready['exclusions']),
        files={n:digest(root/n) for n in ['selected-on-2024.json','grid-comparison.csv','frozen-validation.csv']},
        claim='Bounded grid, selection on 2024 then frozen 2025/26; not a global optimum or annual capital performance'))
    verify_hashes(Path('.'),p['sources']); atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',phase='DONE'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','build','summarize','all'],default='all')
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for name,function in [('prepare',prepare),('build',build),('summarize',summarize)]:
        if args.phase in ('all',name): function(args.output)
