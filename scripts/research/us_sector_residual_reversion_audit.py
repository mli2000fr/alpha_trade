"""Offline scalar checks, both factors and all pair legs. No new downloads."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research import us_sector_residual_reversion as study
from scripts.research import us_professional_residual_reversion as base
from scripts.research.us_professional_residual_reversion_audit import independent_scalar,independent_exit
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def audit(root):
    p=study.READ(root/'protocol.json');r=study.READ(root/'report.json');ready=study.READ(root/'data-ready.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,ready['files']);verify_hashes(root,r['files'])
    verify_hashes(root,study.READ(root/'prepared.json')['files']);verify_hashes(root,study.READ(root/'snapshot-ready.json')['files'])
    c=pd.read_parquet(root/'candidates.parquet');t=pd.read_parquet(root/'trades.parquet')
    keys=['symbol','date','scope','arm']
    assert not c.duplicated(keys).any() and not t.duplicated(keys+['policy']).any()
    assert len(t)==2*c.quality.eq('OK').sum()
    mapping=pd.read_parquet(root/'symbol-sector-map.parquet').set_index('symbol')
    assert c.symbol.isin(p['retained_symbols']).all()
    for _,f in c.groupby(['symbol','scope','arm']):
        blocked=pd.Timestamp.min
        for a in f.sort_values('date').itertuples():
            expected=a.date>blocked
            assert expected==a.independent
            if expected:blocked=a.last_path_date
    days=pd.DatetimeIndex(pd.read_parquet(study.PARENT/'sessions.parquet').date)
    groups=dict(tuple(pd.read_parquet(base.PRICE).groupby('symbol',sort=False)))
    refs={'SPY':base.valid_grid(groups['SPY'],days)}
    refs.update({str(s):study.etf_grid(f,days) for s,f in pd.read_parquet(root/'etf-bars.parquet').groupby('symbol',sort=False)})
    top=pd.read_parquet(study.PARENT/'oracle-top10.parquet');topkeys=set(zip(top.symbol,pd.to_datetime(top.date)))
    assert all((a.symbol,a.date) in topkeys for a in c[c.scope.eq('ORACLE_H10_TOP10')].itertuples())
    tradegroups=dict(tuple(t.groupby(['symbol','arm'],sort=False)))
    candidategroups=dict(tuple(c.groupby(['symbol','arm'],sort=False)))
    n=0;scalars=0;prefixes=0
    for name in ready['files']:
        if not name.endswith('-features.parquet'):continue
        feat=pd.read_parquet(root/name)
        for (symbol,arm),f in feat.groupby(['symbol','arm'],sort=False):
            f=f.set_index('date').reindex(days)
            hedge_name='SPY' if arm=='SPY' else str(mapping.loc[symbol,'hedge_etf'])
            assert f.hedge_symbol.eq(hedge_name).all()
            hedge=refs[hedge_name];sector=refs[str(mapping.loc[symbol,'hedge_etf'])]
            g=base.valid_grid(groups[symbol],days,p['rules']['price_reserves'].get(symbol),p['rules']['identity_events'].get(symbol,[]))
            so=g.open.to_numpy(float);sc=g.close.to_numpy(float);mo=hedge.open.to_numpy(float);mc=hedge.close.to_numpy(float)
            z=f.s_score.to_numpy(float);valid=f.model_valid.to_numpy(bool)
            common_support=(study.supported_history(g)&study.supported_history(refs['SPY'])&study.supported_history(sector)).to_numpy(bool)
            selected=np.flatnonzero(valid)
            for pos in selected[::max(1,len(selected)//2)][:2]:
                beta,b,s=independent_scalar(sc,mc,int(pos))
                assert np.isclose(beta,f.beta.iloc[pos],rtol=0,atol=1e-8)
                assert np.isclose(s,z[pos],rtol=0,atol=1e-7)
                scalars+=1
            if sum(map(ord,symbol))%37==0:
                cut=days.searchsorted(pd.Timestamp('2025-01-02'))+1
                support=g.history_point_good.to_numpy(bool)&hedge.history_point_good.to_numpy(bool)
                prefix=base.ou_signals(sc[:cut],mc[:cut],support[:cut])
                assert np.allclose(prefix.s_score,z[:cut],rtol=0,atol=1e-8,equal_nan=True)
                prefixes+=1
            for a in candidategroups.get((symbol,arm),pd.DataFrame()).itertuples():
                pos=days.get_loc(a.date)
                assert common_support[pos]
                assert a.hedge_symbol==hedge_name
                assert np.isclose(a.s_score,z[pos],rtol=0,atol=1e-10)
                assert a.quality==study.common_reason(g,refs['SPY'],sector,pos,
                    p['rules']['price_reserves'].get(symbol),p['rules']['identity_events'].get(symbol,[]))
            sub=tradegroups.get((symbol,arm),pd.DataFrame())
            for a in sub[sub.policy.eq('OU_DYNAMIC')].itertuples() if len(sub) else []:
                pos=days.get_loc(a.date);end,why,age=independent_exit(so,sc,mo,mc,z,valid,pos,a.side,a.beta)
                assert a.exit_date==days[end] and a.exit_reason==why and a.exit_session==age
            for a in sub.itertuples():
                i=days.get_loc(a.entry_date);j=days.get_loc(a.exit_date)
                assert a.date<a.entry_date<=a.exit_date<=a.last_path_date
                assert np.isclose(so[i],a.entry_stock) and np.isclose(so[j],a.exit_stock)
                assert np.isclose(mo[i],a.entry_market) and np.isclose(mo[j],a.exit_market)
                sign=1 if a.side=='LONG' else -1;ws=sign/(1+a.beta);wm=-sign*a.beta/(1+a.beta)
                gross=ws*(so[j]/so[i]-1)+wm*(mo[j]/mo[i]-1)
                turnover=abs(ws)*(1+so[j]/so[i])+abs(wm)*(1+mo[j]/mo[i])
                borrow=(abs(min(ws,0))+abs(min(wm,0)))*.003*max(1,(a.exit_date-a.entry_date).days)/365
                assert np.isclose(a.net,gross-.0008*turnover-borrow,rtol=0,atol=1e-12)
                assert np.isclose(a.net_stress,gross-.002*turnover-borrow,rtol=0,atol=1e-12)
                n+=1
    assert n==len(t)
    comparison=study.compare_dates(t,days)
    assert comparison==r['comparisons']
    result=dict(status='PASS_EXPLORATORY_SECTOR_PROXY_ONLY',report_sha256=digest(root/'report.json'),
        checked_trade_rows=n,checked_candidates=len(c),scalar_ou_checks=scalars,prefix_checks=prefixes,
        reproduced_parent_spy_series=ready['parent_spy_score_checks'],gates=r['gates'],
        note='Same assistant second implementation, not independent human review. Current industry proxy non-PIT, no PCA, no actual portfolio/borrow qualification.')
    atomic_json(root/'final-audit.json',result);print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
