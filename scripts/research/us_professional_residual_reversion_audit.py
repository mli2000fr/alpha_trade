"""Second offline implementation checks OU estimates, exits and all leg costs."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_professional_residual_reversion import READ,PRICE,valid_grid


def independent_scalar(c,m,pos):
    stock=c[pos-59:pos+1]/c[pos-60:pos]-1
    market=m[pos-59:pos+1]/m[pos-60:pos]-1
    fit=np.linalg.lstsq(np.column_stack([np.ones(60),market]),stock,rcond=None)[0]
    residual=stock-fit[0]-fit[1]*market
    state=np.cumsum(residual)
    ar=np.linalg.lstsq(np.column_stack([np.ones(59),state[:-1]]),state[1:],rcond=None)[0]
    error=state[1:]-ar[0]-ar[1]*state[:-1]
    score=(state[-1]-ar[0]/(1-ar[1]))/np.sqrt((error@error)/57/(1-ar[1]**2))
    return fit[1],ar[1],score


def independent_exit(so,sc,mo,mc,z,valid,pos,side,beta):
    sign=1 if side=='LONG' else -1
    for age in range(1,11):
        k=pos+age
        value=sign*((sc[k]/so[pos+1]-1)-beta*(mc[k]/mo[pos+1]-1))/(1+beta)
        if value<=-.05+1e-12:return k+1,'DAILY_RISK_NEXT_OPEN',age
        if not valid[k] or not np.isfinite(z[k]):return k+1,'INVALID_MODEL_NEXT_OPEN',age
        if sign*z[k]>=-.5:return k+1,'REVERSION_NEXT_OPEN',age
    return pos+11,'TIMEOUT_NEXT_OPEN',10


def audit(root):
    p=READ(root/'protocol.json');report=READ(root/'report.json');ready=READ(root/'data-ready.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,ready['files']);verify_hashes(root,report['files'])
    days=pd.DatetimeIndex(pd.read_parquet(root/'sessions.parquet').date)
    candidates=pd.read_parquet(root/'candidates.parquet');trades=pd.read_parquet(root/'trades.parquet')
    keys=['symbol','date','scope']
    assert not candidates.duplicated(keys).any()
    assert not trades.duplicated(keys+['policy']).any()
    assert len(trades)==4*candidates.quality.eq('OK').sum()
    top=pd.read_parquet(root/'oracle-top10.parquet');topkeys=set(zip(top.symbol,pd.to_datetime(top.date)))
    assert all((r.symbol,r.date) in topkeys for r in candidates[candidates.scope.eq('ORACLE_H10_TOP10')].itertuples())
    # Membership is set before seeing quality or realised exit, including unknown candidates.
    for _,f in candidates.groupby(['scope','symbol']):
        blocked=pd.Timestamp.min
        for r in f.sort_values('date').itertuples():
            expected=r.date>blocked
            assert r.independent==expected
            if expected:blocked=r.last_path_date
    raw=pd.read_parquet(PRICE);by_symbol=dict(tuple(raw.groupby('symbol',sort=False)))
    spy=valid_grid(by_symbol['SPY'],days)
    scalar_count=0;prefix_count=0;trade_count=0
    from scripts.research.us_professional_residual_reversion import ou_signals
    for name in ready['files']:
        if not name.endswith('-features.parquet'):continue
        feat=pd.read_parquet(root/name)
        if not len(feat):continue
        for symbol,f in feat.groupby('symbol',sort=False):
            f=f.set_index('date').reindex(days)
            g=valid_grid(by_symbol[symbol],days,p['price_reserves'].get(symbol),p['identity_events'].get(symbol,[]))
            valid=f.model_valid.to_numpy(bool);z=f.s_score.to_numpy(float)
            goodpos=np.flatnonzero(valid)
            # Three scalar least-squares estimates per supported symbol; no selecting by returns.
            for pos in goodpos[::max(1,len(goodpos)//3)][:3]:
                beta,b,s=independent_scalar(g.close.to_numpy(float),spy.close.to_numpy(float),int(pos))
                assert np.isclose(beta,f.beta.iloc[pos],rtol=0,atol=1e-8)
                assert np.isclose(b,f.ar_b.iloc[pos],rtol=0,atol=1e-8)
                assert np.isclose(s,z[pos],rtol=0,atol=1e-7)
                scalar_count+=1
            # Prefix reconstruction of signal inputs on deterministic symbol subset, no future perturbation.
            if sum(map(ord,symbol))%31==0:
                cut=days.searchsorted(pd.Timestamp('2025-01-02'))+1
                good=g.history_point_good.to_numpy(bool)&spy.history_point_good.to_numpy(bool)
                prefix=ou_signals(g.close.iloc[:cut],spy.close.iloc[:cut],good[:cut])
                assert np.allclose(prefix.s_score,z[:cut],rtol=0,atol=1e-8,equal_nan=True)
                prefix_count+=1
            sub=trades[trades.symbol.eq(symbol)]
            so=g.open.to_numpy(float);sc=g.close.to_numpy(float);mo=spy.open.to_numpy(float);mc=spy.close.to_numpy(float)
            native=sub[sub.policy.eq('OU_DYNAMIC')]
            for r in native.itertuples():
                pos=days.get_loc(r.date)
                end,why,age=independent_exit(so,sc,mo,mc,z,valid,pos,r.side,r.beta)
                assert days[end]==r.exit_date and why==r.exit_reason and age==r.exit_session
                assert r.date<r.entry_date<=r.exit_date<=r.last_path_date
            for r in sub.itertuples():
                i=days.get_loc(r.entry_date);e=days.get_loc(r.exit_date)
                assert np.isclose(r.entry_stock,so[i]) and np.isclose(r.exit_stock,so[e])
                assert np.isclose(r.entry_market,mo[i]) and np.isclose(r.exit_market,mo[e])
                sign=1 if r.executed_side=='LONG' else -1
                b=r.beta if r.policy!='SAME_SIDE_UNHEDGED' else 0.
                ws=sign/(1+b);wm=-sign*b/(1+b)
                gross=ws*(so[e]/so[i]-1)+wm*(mo[e]/mo[i]-1)
                turnovers=abs(ws)*(1+so[e]/so[i])+abs(wm)*(1+mo[e]/mo[i])
                borrow=(abs(min(0,ws))+abs(min(0,wm)))*.003*max(1,(r.exit_date-r.entry_date).days)/365
                assert np.isclose(r.gross,gross,rtol=0,atol=1e-12)
                assert np.isclose(r.net,gross-.0008*turnovers-borrow,rtol=0,atol=1e-12)
                assert np.isclose(r.net_stress,gross-.002*turnovers-borrow,rtol=0,atol=1e-12)
                trade_count+=1
    assert trade_count==len(trades)
    out=dict(status='PASS_EXPLORATORY_ADAPTATION_ONLY',report_sha256=digest(root/'report.json'),
        candidates=len(candidates),checked_trade_rows=trade_count,scalar_ou_checks=scalar_count,
        prefix_checks=prefix_count,scope_gates=report['scope_gates'],
        note='Second implementation by same assistant, not independent human review; no full sector/PCA replication, portfolio or historical borrow/dividend certification')
    atomic_json(root/'final-audit.json',out);print(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
