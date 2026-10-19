"""Offline scalar audit of all fixed/ATR protection exits and frozen selection."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_confirmation_protection_grid as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def scalar_exit(path,side,tp,sl):
    entry=float(path[0,0]); long=side=='LONG'; sign=1 if long else -1
    target=entry*(1+tp if long else 1-tp); stop=entry*(1-sl if long else 1+sl)
    tt=abs(target)*1e-12; st=abs(stop)*1e-12
    price=float(path[-1,3]); outcome='TIMEOUT'; age=10; gap=False
    for age0,(op,high,low,close) in enumerate(path,1):
        if age0>1 and (op<=stop+st if long else op>=stop-st): price=float(op); outcome='SL'; gap=True
        elif age0>1 and (op>=target-tt if long else op<=target+tt): price=target; outcome='TP'
        elif low<=stop+st if long else high>=stop-st: price=stop; outcome='SL'
        elif high>=target-tt if long else low<=target+tt: price=target; outcome='TP'
        else: continue
        age=age0; break
    return dict(entry_price=entry,exit_price=price,outcome=outcome,exit_session=age,gap_stop=gap,path_return=sign*(price/entry-1))


def audit(root):
    p=study.READ(root/'protocol.json'); ready=study.READ(root/'data-ready.json'); report=study.READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,ready['files']); verify_hashes(root,report['files'])
    assert report['protocol_sha256']==digest(root/'protocol.json')
    cohort=pd.read_parquet(root/'cohort.parquet'); source=pd.read_parquet(study.SOURCE/'qualification.parquet')
    pd.testing.assert_frame_equal(cohort[['date','symbol','year','direction']].sort_values(['date','symbol']).reset_index(drop=True),
        source[['date','symbol','year','direction']].sort_values(['date','symbol']).reset_index(drop=True))
    admitted=cohort[cohort.quality_reason.eq('')]; assert len(cohort)==ready['selected'] and len(admitted)==ready['common_qualified']
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',cohort.symbol.unique().tolist())])
    grids={}; atr_lookup={}
    for symbol,g in prices.groupby('symbol',observed=True):
        rows=admitted[admitted.symbol.eq(symbol)]; pos=days.get_indexer(rows.date)
        if not len(rows): continue
        grid,_,reason=study.parent.qualify(g,days,pos,identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        assert (reason=='').all(); a=grid[['open','high','low','close']].to_numpy(float); grids[str(symbol)]=a
        for row,j in zip(rows.itertuples(),pos):
            true_ranges=[max(a[k,1]-a[k,2],abs(a[k,1]-a[k-1,3]),abs(a[k,2]-a[k-1,3])) for k in range(j-17,j+3)]
            assert len(true_ranges)==20
            atr=float(np.mean(true_ranges)); assert abs(atr-row.atr20)<1e-10
            atr_lookup[(row.date,str(symbol))]=atr
    original=pd.read_parquet(study.SOURCE/'evaluations.parquet').set_index(['date','symbol','side'])
    keys=None; checked=0; parity=0; frames={}; limits=[]
    for name,protection in p['profiles'].items():
        frame=pd.concat([pd.read_parquet(root/n) for n in ready['files'] if Path(n).stem==name],ignore_index=True)
        frames[name]=frame; current=frame[['date','symbol','side']].sort_values(['date','symbol','side']).reset_index(drop=True)
        assert not current.duplicated().any() and len(frame)==2*len(admitted)
        if keys is not None: pd.testing.assert_frame_equal(keys,current)
        keys=current
        for row in frame.itertuples():
            j=days.get_loc(row.date); grid=grids[str(row.symbol)]; entry=grid[j+3,0]
            assert row.entry_date==days[j+3] and row.confirmation_date==days[j+2] and row.last_path_date==days[j+12]
            if protection.get('mode')=='atr20':
                atr=atr_lookup[(row.date,str(row.symbol))]
                sl=min(protection['max_sl'],max(protection['min_sl'],protection['stop_atr_multiple']*atr/entry)); tp=sl*protection['reward_risk']
            else: tp=protection['tp']; sl=protection['sl']
            assert abs(row.tp_pct-tp)<1e-12 and abs(row.sl_pct-sl)<1e-12
            out=scalar_exit(grid[j+3:j+13],row.side,tp,sl)
            for field,value in out.items():
                actual=getattr(row,field)
                if isinstance(value,float): assert abs(value-actual)<1e-12,(name,row.symbol,row.date,field)
                else: assert value==actual,(name,row.symbol,row.date,field)
            net=row.path_return-p['costs_per_leg']*(1+row.exit_price/row.entry_price)
            if row.side=='SHORT': net-=p['short_borrow_annual']*(row.exit_session-1)/252
            assert abs(net-row.net_outcome)<1e-12
            if name==p['reference']:
                old=original.loc[(row.date,row.symbol,row.side)]
                for field in ['entry_price','exit_price','net_outcome']: assert getattr(row,field)==old[field]
                parity+=1
            checked+=1
        if protection.get('mode')=='atr20':
            assert frame.sl_pct.between(.03,.10).all() and frame.tp_pct.between(.06,.20).all()
            np.testing.assert_allclose(frame.tp_pct,frame.sl_pct*2,rtol=0,atol=1e-14)
            limits.append(dict(profile=name,n=len(frame),median_sl=float(frame.sl_pct.median()),median_tp=float(frame.tp_pct.median()),
                min_cap_rate=float(frame.sl_pct.eq(.03).mean()),max_cap_rate=float(frame.sl_pct.eq(.10).mean())))
    selected=study.select_2024(report['grid'],p['profiles']); assert selected==report['choices']
    assert study.READ(root/'selected-on-2024.json')['choices']==selected
    for row in report['grid']:
        annual=frames[row['profile']]; annual=annual[annual.year.eq(row['year'])]
        values=study.parent.previous.select_arm(annual,row['arm']); assert len(values)==row['n']
        if len(values):
            assert abs(values.net_outcome.mean()-row['mean_net'])<1e-12
            assert abs(values.net_outcome.gt(0).mean()-row['win_rate'])<1e-12
            independent=study.EXEC.base.independent_fast(values)
            assert len(independent)==row['independent_n']
            assert abs(independent.net_outcome.mean()-row['independent_mean_net'])<1e-12
    atomic_json(root/'atr-distance-audit.json',dict(profiles=limits,availability='TR20 through J+2 only, scaled by fill open J+3; never recomputed after entry'))
    result=dict(status='PASS_EXPLORATORY_ONLY',profiles=len(p['profiles']),scalar_exits_verified=checked,
        reference_parity_rows=parity,selected_at_j=len(cohort),common_qualified=len(admitted),
        same_pairs_across_profiles=True,atr_scalar_checked=True,selection_year_only=2024,
        protocol_sha256=digest(root/'protocol.json'),report_sha256=digest(root/'report.json'),
        atr_audit_sha256=digest(root/'atr-distance-audit.json'),audit_code_sha256=digest(Path(__file__)),
        production_changes=False,sql=False,new_fit=False,api_calls=0,
        reserve='Bounded exploratory parameter sensitivity; no claim of global optimum, virgin holdout or capital portfolio return')
    atomic_json(root/'final-audit.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    print(audit(parser.parse_args().output))
