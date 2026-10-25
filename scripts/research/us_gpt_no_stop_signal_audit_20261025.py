"""No-SL diagnostic per signal, not a portfolio or optimal hindsight sale.

Same frozen237 AugustTOP20 pairs, no provider/SQL/GPT/order. DirectJ+1 and
first Winner confirmation, fixed20 sessions/open21, fees8bps/leg. All open
or unqualified cases explicitly reserved, never labelled losing by default.
"""
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_winner_gpt_veto_signal_outcomes_august_2026 as prior

base,grid=prior.base,prior.grid
PARENT=Path('artifacts/research/us_winner_gpt_veto_august_2026/20261025-short-v1')
ROOT=PARENT.parent/'20261025-no-stop-signal-audit-v2'


def outcome(path,entry,sessions):
    days=[s.session_date for s in sessions]
    stamp=pd.Timestamp(entry.bar_timestamp);day=stamp.tz_convert('America/New_York').date()
    start=days.index(day);due=pd.Timestamp(sessions[start+20].open_at_utc)
    p=float(entry.open)
    window=path[path.bar_timestamp.ge(stamp)&path.bar_timestamp.lt(due)]
    if window.empty:raise ValueError('Missing observed path')
    last=path.iloc[-1].bar_end_timestamp
    result=dict(entry_time=stamp,entry_price=p,due_open=due,
        max_up_pct=100*(float(window.high.max())/p-1),max_down_pct=100*(float(window.low.min())/p-1),
        extrema_complete=False)
    due_row=path[path.bar_timestamp.eq(due)]
    expected=pd.DatetimeIndex(np.concatenate([pd.date_range(s.open_at_utc,s.close_at_utc,freq='5min',inclusive='left').to_numpy()
        for s in sessions[start:start+20]]))
    # Normalize tz explicitly: pandas/numpy representations differ by version.
    expected=pd.DatetimeIndex(pd.to_datetime(expected,utc=True))
    # Confirmed entry can occur inside its first holding session. Bars before
    # actual entry do not belong to its path and must not make it incomplete.
    expected=expected[expected>=stamp]
    full=pd.DatetimeIndex(pd.to_datetime(window.bar_timestamp,utc=True)).equals(expected)
    if not full or len(due_row)!=1:
        return dict(result,status='CENSORED_OR_INCOMPLETE',last_observed=last,
            observed_mark_return_pct=100*(float(window.close.iloc[-1])/p-1))
    price=float(due_row.iloc[0].open)
    net=price-p-prior.FEE*(price+p)
    gross=100*(price/p-1)
    # Reverse accounting identity independently of the entry-price ratio.
    grid.near(100*net/p,gross-100*prior.FEE*(1+price/p))
    return dict(result,status='WIN' if net>0 else 'LOSS' if net<0 else 'FLAT',
        extrema_complete=True,exit_price=price,gross_return_pct=gross,net_return_pct=100*net/p,
        h20_close_return_pct=100*(float(window.close.iloc[-1])/p-1))


def statistics(frame):
    done=frame[frame.status.isin(['WIN','LOSS','FLAT'])]
    return dict(signals=len(frame),symbols=int(frame.symbol.nunique()),
        counts=frame.status.value_counts().to_dict(),winners=int(done.status.eq('WIN').sum()),
        losers=int(done.status.eq('LOSS').sum()),mature=len(done),
        win_pct=100*done.status.eq('WIN').mean() if len(done) else None,
        loss_pct=100*done.status.eq('LOSS').mean() if len(done) else None,
        mean_net_return_pct=float(done.net_return_pct.mean()) if len(done) else None,
        median_net_return_pct=float(done.net_return_pct.median()) if len(done) else None,
        mean_positive_excursion_pct=float(done.max_up_pct.mean()) if len(done) else None,
        mean_negative_excursion_pct=float(done.max_down_pct.mean()) if len(done) else None)


def run():
    protocol=base.read(PARENT/'protocol.json');base.verify(protocol['sources'])
    manifest=base.read(PARENT/'inputs/snapshot.json')
    sources={str(PARENT/'inputs'/n):h for n,h in manifest['files'].items()}
    names=[Path(__file__),Path('tests/test_us_gpt_no_stop_signal_audit_20261025.py'),Path(prior.__file__),
        PARENT/'protocol.json',PARENT/'report.json',PARENT/'common-cohort.parquet']
    sources.update({str(p):base.digest(p) for p in names});base.verify(sources)
    cohort=pd.read_parquet(PARENT/'common-cohort.parquet');chosen=cohort[cohort.selected].copy()
    if len(chosen)!=237:raise ValueError('Original cohort changed')
    sessions=[s for s in grid.calendar().sessions(pd.Timestamp('2026-07-20').date(),pd.Timestamp('2026-11-30').date()) if s.is_open]
    days=[s.session_date for s in sessions]
    ROOT.mkdir(parents=True,exist_ok=False)
    base.save_new(ROOT/'protocol.json',dict(sources=sources,created_at_utc=datetime.now(timezone.utc).isoformat(),
        exit='Open21, noSL/noTP/noTR; do NOT sell at future optimum',economic_portfolio=False,
        mean_returns='Equal-weight per signal, overlapping, NOT capital compounded',
        invalid_gpt='No veto',historical_gpt_non_PIT=True,future_coverage_bias=True,
        gpt_calls=0,provider_calls=0,SQL_reads=0,SQL_writes=False,orders=False))
    paths={s:pd.read_parquet(PARENT/'inputs'/f'{s}.parquet').sort_values('bar_timestamp') for s in chosen.symbol.unique()}
    rows=[]
    for r in chosen.itertuples():
        day=pd.Timestamp(r.date).date();path=paths[r.symbol]
        direct=path[path.trade_date.eq(pd.Timestamp(days[days.index(day)+1]))].iloc[0]
        confirmed=prior.first_confirmation(path,day,days)
        for mode,entry in [('DIRECT_J1',direct),('WINNER_FIRST_CONFIRMATION',confirmed)]:
            result=dict(status='NO_ENTRY') if entry is None else outcome(path,entry,sessions)
            rows.append(dict(date=r.date,symbol=r.symbol,rank=int(r.oracle_rank),gpt_status=r.gpt_status,
                gpt_score=r.gpt_score,mode=mode,**result))
    frame=pd.DataFrame(rows);frame.to_parquet(ROOT/'outcomes.parquet',index=False)
    summaries=[]
    for mode,f in frame.groupby('mode'):
        for cut in [None,3,4,5]:
            veto=pd.Series(False,index=f.index) if cut is None else (f.gpt_status.eq('VALID')&f.gpt_score.between(1,cut)).fillna(False)
            summaries.append(dict(mode=mode,cutoff=cut,retained=statistics(f[~veto]),excluded=statistics(f[veto])))
    by_score=[dict(mode=mode,score=None if pd.isna(score) else float(score),**statistics(g))
        for (mode,score),g in frame.groupby(['mode','gpt_score'],dropna=False)]
    base.verify(sources)
    base.save_new(ROOT/'report.json',dict(status='COMPLETED_READ_ONLY_SIGNAL_AUDIT',cases=summaries,by_score=by_score,
        sources=sources,files={'outcomes.parquet':base.digest(ROOT/'outcomes.parquet')},economic_portfolio=False,
        overlapping_signals=True,historical_gpt_non_PIT=True,gpt_calls=0,SQL_writes=False))
    print(base.json.dumps(summaries))


if __name__=='__main__':
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No network'))
    run()
