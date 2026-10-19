"""Offline audit of four-close TOP10 signals, J+3 entry and each scalar exit."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_four_session_confirmation as study
from scripts.research import us_top10_three_session_confirmation_audit as scalar_reference
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def audit(root):
    read=study.previous.prior.read
    p=read(root/'protocol.json'); ready=read(root/'data-ready.json'); report=read(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,ready['files']); verify_hashes(root,report['files'])
    assert report['protocol_sha256']==digest(root/'protocol.json')
    expected=pd.concat([pd.read_parquet(study.SOURCE/f'{year}-H10-scores.parquet') for year in p['years']],ignore_index=True)
    expected=expected[expected['rank'].le(10)]
    selected=pd.read_parquet(root/'selected-at-j.parquet'); key=['date','symbol']
    pd.testing.assert_frame_equal(expected.sort_values(key).reset_index(drop=True),selected.sort_values(key).reset_index(drop=True))
    old_selection=pd.read_parquet(study.THREE/'selected-at-j.parquet')
    pd.testing.assert_frame_equal(old_selection.sort_values(key).reset_index(drop=True),selected.sort_values(key).reset_index(drop=True))
    assert selected.groupby('date').size().eq(10).all()
    q=pd.read_parquet(root/'qualification.parquet'); e=pd.read_parquet(root/'evaluations.parquet')
    assert not q.duplicated(key).any() and len(q)==len(selected)==ready['selected']
    assert not e.duplicated(key+['side']).any()
    valid=q[q.quality_reason.eq('')]; assert len(e)==2*len(valid)
    pd.testing.assert_frame_equal(e[key].drop_duplicates().sort_values(key).reset_index(drop=True),valid[key].sort_values(key).reset_index(drop=True))
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',selected.symbol.unique().tolist())])
    groups={str(s):g for s,g in prices.groupby('symbol',observed=True)}; checked=0; same_pairs_controls=[]
    for symbol,g in q.groupby('symbol',observed=True):
        pos=days.get_indexer(g.date)
        grid,direction,reasons=study.qualify(groups[str(symbol)],days,pos,
            identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        np.testing.assert_array_equal(direction,g.direction.to_numpy()); np.testing.assert_array_equal(reasons,g.quality_reason.to_numpy())
        # Independent scalar confirmation, no future bar J+3 used for the signal.
        for offset,j in enumerate(pos):
            closes=grid.close.iloc[j-1:j+3].to_numpy(float)
            known=np.isfinite(closes).all() and (closes>0).all()
            actual='LONG' if known and all(a<b for a,b in zip(closes,closes[1:])) else (
                'SHORT' if known and all(a>b for a,b in zip(closes,closes[1:])) else 'NONE')
            assert direction[offset]==actual
        old_direction=study.previous.directions(grid.close.to_numpy(float),pos)
        assert ((direction=='NONE') | (direction==old_direction)).all()
        old_lookup=dict(zip(g.date,old_direction))
        for row in e[e.symbol.eq(symbol)].itertuples():
            j=days.get_loc(row.date)
            assert row.entry_date==days[j+3] and row.confirmation_date==days[j+2] and row.last_path_date==days[j+12]
            assert row.entry_date>row.confirmation_date>row.date
            result=scalar_reference.scalar(grid.iloc[j+3:j+13],row.side)
            for k,v in result.items():
                actual=getattr(row,k)
                if isinstance(v,float): assert abs(actual-v)<1e-12,(symbol,row.date,row.side,k)
                else: assert actual==v,(symbol,row.date,row.side,k)
            expected_net=row.path_return-p['costs_per_leg']*(1+row.exit_price/row.entry_price)
            if row.side=='SHORT': expected_net-=p['short_borrow_annual']*(row.exit_session-1)/252
            assert abs(row.net_outcome-expected_net)<1e-12
            checked+=1
            # Added control: three-close rule but ALSO wait to J+3. Same valid candidates/outcomes.
            same_pairs_controls.append(dict(date=row.date,symbol=row.symbol,year=row.year,side=row.side,
                direction_three=old_lookup[row.date],direction_four=row.direction,net_outcome=row.net_outcome))
    for result in report['results']:
        frame=study.previous.select_arm(e[e.year.eq(result['year'])],result['arm']); assert result['n']==len(frame)
        if len(frame):
            assert abs(result['mean_net']-frame.net_outcome.mean())<1e-12
            assert abs(result['win_rate']-frame.net_outcome.gt(0).mean())<1e-12
            independent=study.previous.execution.base.independent_fast(frame)
            assert len(independent)==result['independent_n']
            assert abs(independent.net_outcome.mean()-result['independent_mean_net'])<1e-12
    control=pd.DataFrame(same_pairs_controls); controls=[]
    for year,g in control.groupby('year'):
        for side in ('LONG','SHORT','COMBINED'):
            t=g[g.direction_three.eq(g.side)]; f=g[g.direction_four.eq(g.side)]
            if side!='COMBINED': t=t[t.side.eq(side)]; f=f[f.side.eq(side)]
            controls.append(dict(year=int(year),side=side,three_close_entry_j3_n=len(t),four_close_entry_j3_n=len(f),
                three_close_entry_j3_mean=float(t.net_outcome.mean()),four_close_entry_j3_mean=float(f.net_outcome.mean())))
    atomic_json(root/'same-entry-three-vs-four-control.json',dict(rows=controls,
        reserve='Descriptive extra-close control at identical J+3 timing; no rule selected for deployment'))
    result=dict(status='PASS_EXPLORATORY_ONLY',selected=len(selected),scalar_exits_verified=checked,
        scalar_confirmations_checked=len(q),confirmation_before_entry=True,same_original_top10_as_three_close=True,
        four_close_is_subset_of_three_close=True,fees_checked=True,protocol_sha256=digest(root/'protocol.json'),
        report_sha256=digest(root/'report.json'),audit_code_sha256=digest(Path(__file__)),
        scalar_reference_sha256=digest(Path(scalar_reference.__file__)),
        comparison_sha256=digest(root/'three-vs-four-closes.json'),same_entry_control_sha256=digest(root/'same-entry-three-vs-four-control.json'),
        new_fit=False,sql=False,production_changes=False,
        reserve='Rule and arithmetic audit, not independent fill/price or full feature PIT certification')
    atomic_json(root/'final-audit.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    print(audit(parser.parse_args().output))
