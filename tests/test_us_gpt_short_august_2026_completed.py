"""Independent checks over sealed eight-account outputs; no rerun/network."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_gpt_short_august_2026 as study

ROOT=study.ROOT


@pytest.fixture(scope='module')
def report():
    if not (ROOT/'report.json').exists():
        pytest.skip('Local research outputs not present')
    r=study.base.read(ROOT/'report.json')
    assert r['status']=='COMPLETED_AUDITED_EXPLORATORY'
    study.base.verify(r['sources'])
    for arm in r['cases']:
        study.base.verify({str(ROOT/arm['arm']/name):sha for name,sha in arm['files'].items()})
    return r


@pytest.mark.parametrize('confirmed,archived_arm',[(False,'DIRECT_ONLY'),(True,'WINNER_ONLY')])
def test_long_controls_reproduce_all_entries_exits_and_curve(report,confirmed,archived_arm):
    ref=study.original.ROOT/archived_arm if confirmed else study.PARENT/archived_arm
    arm=next(r for r in report['cases'] if r['side']=='buy' and r['confirmation']==confirmed)
    new=ROOT/arm['arm']
    a=pd.read_parquet(ref/'equity-5m.parquet');b=pd.read_parquet(new/'equity-5m.parquet')
    pd.testing.assert_series_equal(a.timestamp,b.timestamp)
    np.testing.assert_allclose(a[['equity','gross']],b[['equity','gross']],rtol=1e-12,atol=1e-8)
    old_events=pd.read_parquet(ref/'events.parquet');old_events=old_events[old_events.event.eq('BUY_FILL')]
    new_events=pd.read_parquet(new/'events.parquet');new_events=new_events[new_events.event.eq('BUY')]
    cols=['time','symbol','price','quantity']
    pd.testing.assert_frame_equal(old_events[cols].reset_index(drop=True),new_events[cols].reset_index(drop=True),check_dtype=False)
    a=pd.read_parquet(ref/'trades.parquet');b=pd.read_parquet(new/'trades.parquet')
    cols=['symbol','entry_date','exit_date','entry_price','exit_price','quantity','pnl','exit_reason']
    # Multiple broker stops at the same5m boundary can have different report
    # insertion order; compare immutable trade keys, not row enumeration.
    keys=['exit_date','symbol','entry_date']
    pd.testing.assert_frame_equal(a[cols].sort_values(keys).reset_index(drop=True),
        b[cols].sort_values(keys).reset_index(drop=True),check_dtype=False,atol=1e-8,rtol=1e-12)


@pytest.mark.parametrize('case',range(6))
def test_short_portfolios_independent_accounting_gross_and_selected_signals(report,case):
    r=report['cases'][case];assert r['side']=='sell'
    folder=ROOT/r['arm'];events=pd.read_parquet(folder/'events.parquet');trades=pd.read_parquet(folder/'trades.parquet')
    curve=pd.read_parquet(folder/'equity-5m.parquet');cohort=pd.read_parquet(ROOT/'common-cohort.parquet')
    eligible=cohort.selected & ~study.veto_mask(cohort,r['veto_low'])
    approved=set(zip(cohort.loc[eligible,'date'].dt.date,cohort.loc[eligible,'symbol']))
    held={};collateral=4000.;marks={}
    paths={s:pd.read_parquet(ROOT/'inputs'/f'{s}.parquet').set_index('bar_timestamp') for s in events.symbol.dropna().unique()}
    for row in events.to_dict('records'):
        stamp=pd.Timestamp(row['time']);s=row['symbol']
        day=stamp.tz_convert('America/New_York').date()
        if row['event']=='SELL_SHORT':
            assert s not in held and (row['signal_date'],s) in approved
            assert len(held)<5
            # Exact simultaneous raw OPEN, no future close or inverse LONG gain.
            assert row['price']==pytest.approx(paths[s].at[stamp,'open'])
            marks={h:float(paths[h].at[stamp,'open']) for h in held}
            equity=collateral+sum(p['q']*(p['entry']-marks[h]) for h,p in held.items())
            gross=sum(p['q']*marks[h] for h,p in held.items())
            assert gross+row['quantity']*row['price'] <= equity+1e-7
            assert row['quantity']>=1 and float(row['quantity']).is_integer()
            held[s]=dict(q=row['quantity'],entry=row['price'])
            collateral-=row['fee']
        elif row['event']=='BUY_TO_COVER':
            p=held.pop(s)
            assert p['q']==row['quantity']
            collateral+=p['q']*(p['entry']-row['price'])-row['fee']-row['borrow']
        elif row['event']=='BORROW_ACCRUAL':
            assert s in held
            collateral-=row['borrow']
        else:raise AssertionError(row['event'])
    assert set(held)=={p['symbol'] for p in r['open_positions']}
    equity=collateral+sum(p['quantity']*(p['entry_price']-p['mark']) for p in r['open_positions'])
    assert equity==pytest.approx(r['final_equity'],abs=1e-7)
    assert trades.pnl.sum()==pytest.approx(r['net_closed_pnl'])
    assert sum(events.fee.fillna(0))==pytest.approx(r['costs'])
    assert sum(events.borrow.fillna(0))==pytest.approx(r['borrow_cost'])
    values=np.r_[4000.,curve.equity.to_numpy()]
    assert 100*np.min(values/np.maximum.accumulate(values)-1)==pytest.approx(r['max_drawdown_pct'])
