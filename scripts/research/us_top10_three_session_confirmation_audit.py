"""Read-only source audit plus offline scalar verification of every TOP10 exit."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_three_session_confirmation as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def scalar(path, side):
    entry=float(path.open.iloc[0]); long=side=='LONG'; sign=1 if long else -1
    tp=entry*(1.10 if long else .90); sl=entry*(.95 if long else 1.05)
    st=abs(sl)*1e-12; tt=abs(tp)*1e-12
    result=dict(exit_price=float(path.close.iloc[-1]),outcome='TIMEOUT',exit_session=10,gap_stop=False)
    for age, row in enumerate(path.itertuples(),1):
        open_sl=age>1 and (row.open<=sl+st if long else row.open>=sl-st)
        open_tp=age>1 and (row.open>=tp-tt if long else row.open<=tp+tt)
        intrabar_sl=row.low<=sl+st if long else row.high>=sl-st
        intrabar_tp=row.high>=tp-tt if long else row.low<=tp+tt
        if open_sl: result.update(exit_price=float(row.open),outcome='SL',exit_session=age,gap_stop=True)
        elif open_tp: result.update(exit_price=tp,outcome='TP',exit_session=age)
        elif intrabar_sl: result.update(exit_price=sl,outcome='SL',exit_session=age)
        elif intrabar_tp: result.update(exit_price=tp,outcome='TP',exit_session=age)
        else: continue
        break
    result['entry_price']=entry; result['path_return']=sign*(result['exit_price']/entry-1)
    return result


def audit(root):
    p=study.prior.read(root/'protocol.json'); ready=study.prior.read(root/'data-ready.json'); report=study.prior.read(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,ready['files']); verify_hashes(root,report['files'])
    assert report['protocol_sha256']==digest(root/'protocol.json')
    expected=pd.concat([pd.read_parquet(study.SOURCE/f'{year}-H10-scores.parquet') for year in p['years']],ignore_index=True)
    expected=expected[expected['rank'].le(10)]
    selected=pd.read_parquet(root/'selected-at-j.parquet')
    key=['date','symbol']
    pd.testing.assert_frame_equal(expected.sort_values(key).reset_index(drop=True),selected.sort_values(key).reset_index(drop=True))
    assert selected.groupby('date').size().eq(10).all()
    q=pd.read_parquet(root/'qualification.parquet')
    assert not q.duplicated(key).any() and len(q)==len(selected)==ready['selected']
    e=pd.read_parquet(root/'evaluations.parquet')
    assert not e.duplicated(key+['side']).any()
    valid=q[q.quality_reason.eq('')]
    assert len(e)==2*len(valid)
    pd.testing.assert_frame_equal(e[key].drop_duplicates().sort_values(key).reset_index(drop=True),valid[key].sort_values(key).reset_index(drop=True))
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',selected.symbol.unique().tolist())])
    price_groups={str(s):g for s,g in prices.groupby('symbol',observed=True)}
    checked=0
    for symbol,g in q.groupby('symbol',observed=True):
        pos=days.get_indexer(g.date)
        grid,direction,reasons=study.qualify(price_groups[str(symbol)],days,pos,
            identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        np.testing.assert_array_equal(direction,g.direction.to_numpy()); np.testing.assert_array_equal(reasons,g.quality_reason.to_numpy())
        for row in e[e.symbol.eq(symbol)].itertuples():
            j=days.get_loc(row.date)
            assert row.entry_date==days[j+2] and row.confirmation_date==days[j+1] and row.last_path_date==days[j+11]
            assert row.entry_date>row.confirmation_date>row.date
            result=scalar(grid.iloc[j+2:j+12],row.side)
            for k,v in result.items():
                actual=getattr(row,k)
                if isinstance(v,float): assert abs(actual-v)<1e-12,(symbol,row.date,row.side,k,actual,v)
                else: assert actual==v,(symbol,row.date,row.side,k,actual,v)
            expected_net=row.path_return-p['costs_per_leg']*(1+row.exit_price/row.entry_price)
            if row.side=='SHORT': expected_net-=p['short_borrow_annual']*(row.exit_session-1)/252
            assert abs(row.net_outcome-expected_net)<1e-12
            checked+=1
    for result in report['results']:
        frame=study.select_arm(e[e.year.eq(result['year'])],result['arm'])
        assert result['n']==len(frame)
        if len(frame):
            assert abs(result['mean_net']-frame.net_outcome.mean())<1e-12
            assert abs(result['win_rate']-frame.net_outcome.gt(0).mean())<1e-12
            episodes=study.execution.base.independent_fast(frame)
            assert len(episodes)==result['independent_n']
            assert abs(episodes.net_outcome.mean()-result['independent_mean_net'])<1e-12
    result=dict(status='PASS_EXPLORATORY_ONLY',selected=len(selected),scalar_exits_verified=checked,
        confirmation_before_entry=True,original_top10_no_future_replacement=True,fees_checked=True,
        protocol_sha256=digest(root/'protocol.json'),report_sha256=digest(root/'report.json'),
        audit_code_sha256=digest(Path(__file__)),new_fit=False,sql=False,production_changes=False,
        reserve='Audits rule and execution arithmetic, not historical feature PIT or independently certified fills')
    atomic_json(root/'final-audit.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    print(audit(parser.parse_args().output))
