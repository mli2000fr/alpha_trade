"""B+anti-SL reference versus one executed SL -> 100 NYSE sessions entry veto.

Same frozen candidate list, no refill, no model fitting or SQL/provider access.
All patches are confined to isolated research children, never production.
"""
import argparse
from copy import deepcopy
from datetime import date,datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch
import numpy as np
import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_b_one_sl_pause_policy_20261119 import StopPause

ROOT=Path('artifacts/research/us_b_one_sl_pause/20261119-v1')
MATCH=Path('artifacts/research/us_b_protection_partial/20261118-v1')
CASES=['REFERENCE','ONE_SL_PAUSE100']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare():
    if (ROOT/'protocol.json').exists():
        return
    ROOT.mkdir(parents=True,exist_ok=True)
    plan=deepcopy(read(MATCH/'protocol.json'))
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:
            raise ValueError('Changed reviewed source: '+file)
    for p in [Path(__file__),Path('scripts/research/us_b_one_sl_pause_policy_20261119.py'),
              Path('tests/test_b_one_sl_pause_20261119.py')]:
        plan['sources'][str(p)]=digest(p)
    inputs=ROOT/'inputs';inputs.mkdir();tape=inputs/'intraday';tape.mkdir()
    market=read(MATCH/'inputs/manifest.json');files=dict(market['files'])
    for file,h in files.items():
        if digest(Path(file))!=h:
            raise ValueError('Changed frozen market data: '+file)
    for p in (MATCH/'inputs/intraday').iterdir():
        if not p.is_file():continue
        target=tape/p.name
        try:os.link(p,target)
        except OSError:shutil.copyfile(p,target)
        files[str(target)]=digest(target)
    atomic_json(inputs/'manifest.json',dict(files=files,SQL_reads=0,provider_calls=0))
    for case in CASES:
        target=ROOT/'variants'/case/'signals.parquet';target.parent.mkdir(parents=True)
        shutil.copyfile(MATCH/'variants/SL10/signals.parquet',target)
        plan['sources'][str(target)]=digest(target)
    plan.update(study='One executed SL -> pause100, fixed B+anti-SL candidates',cases=CASES,
        date_start='2021-01-01',date_end='2026-10-01',initial_capital=4000,
        pause_convention='Trigger-session remainder plus100 following NYSE sessions; resume on session101',
        trigger='Every actually executed STOP/STOP_GAP, regardless of gross/net PnL; no horizon exits',
        availability='STOP at completed5m bar; STOP_GAP at observed opening; no future reference exits',
        selection='Same frozen OracleTOP179 -> B TOP10 -> antiSL candidates; entry veto only; no refill',
        exclusion_stage='After directional/meta selection and again at execution; not a before-Oracle universe rerank',
        reset='Actual variant exits only; no pause of other symbols; no account-wide halt',
        matched_control=str(MATCH/'cases/SL10/result'),
        prior_different_experiment='Two consecutive stops/30sessions ->100sessions, before-Oracle reranking, T0/B without antiSL',
        new_training=0,provider_calls=0,SQL_reads=0,SQL_writes=0,broker_orders=0,production_changes=False,
        independent_holdout=False,created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'progress.json',dict(status='PREPARED',total=2,completed=0))


def run_case(case):
    from backtesting.simulator import BacktestEngine
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions=[d.date() for d in nyse_sessions(date(2020,1,1),date(2028,1,1))]
    ledger=StopPause(sessions,enabled=case!='REFERENCE')
    native=BacktestEngine.run
    def run(engine,*args,**kwargs):
        if kwargs.get('winner_selection_source') is not None:
            raise ValueError('Unexpected existing selection policy')
        with ledger.installed():
            result=native(engine,*args,**kwargs,winner_selection_source=ledger.select)
        ledger.blocked(pd.Timestamp('2026-10-02T00:00Z'))
        out=ROOT/'cases'/case/'result'
        atomic_json(out/'pause-triggers.json',ledger.triggers)
        atomic_json(out/'selection-decisions.json',ledger.decisions)
        atomic_json(out/'execution-vetoes.json',ledger.vetoes)
        return result
    with patch.object(source,'ROOT',ROOT),patch.object(BacktestEngine,'run',run):
        source.run_case(case)


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    control=ROOT/'cases/REFERENCE/result';original=MATCH/'cases/SL10/result'
    for name in ['equity-daily.csv','trades.csv']:
        pd.testing.assert_frame_equal(pd.read_csv(control/name),pd.read_csv(original/name),check_exact=False,rtol=0,atol=1e-8)
    pd.testing.assert_frame_equal(pd.read_parquet(control/'equity-5m.parquet'),pd.read_parquet(original/'equity-5m.parquet'),check_exact=False,rtol=0,atol=1e-8)
    rows=[];curves={};annual=[];checks=[]
    for case in CASES:
        out=ROOT/'cases'/case/'result';r=validate_case(ROOT/'cases'/case)
        t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        buys=events[events.event.eq('BUY_FILL')].copy()
        buys['stamp']=pd.to_datetime(buys.time,utc=True)
        triggers=read(out/'pause-triggers.json')
        if case!='REFERENCE':
            for e in triggers:
                a=pd.Timestamp(e['known_at']);b=pd.Timestamp(e['resume_session']).tz_localize('America/New_York')
                if ((buys.symbol.eq(e['symbol'])) & buys.stamp.ge(a) & buys.stamp.lt(b)).any():
                    raise ValueError('Purchase during known pause')
                matching=t[t.campaign_id.eq(e['campaign_id']) & t.exit_reason.isin(['STOP','STOP_GAP'])]
                if len(matching)!=1:raise ValueError('Pause not linked to an actual stop')
        unrealized=fees=0.
        for p in r['open_positions']:
            entry=buys[buys.symbol.eq(p['symbol'])].sort_values('stamp').iloc[-1]
            unrealized+=p['qty']*(p['mark']-entry.price)
            fees+=entry.costs*p['qty']/entry.quantity
        expected=4000+t.pnl.sum()+unrealized-fees+r['dividends_accrued']-t.dividends.sum()-r['margin_interest']
        if abs(expected-r['final_equity'])>1e-6:raise ValueError('Final equity/PnL mismatch')
        curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity;curves[case]=curve
        decisions=read(out/'selection-decisions.json')
        fields=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']
        rows.append(dict(case=case,**{k:r.get(k) for k in fields},pauses=len(triggers) if case!='REFERENCE' else 0,
            excluded_candidate_occurrences=sum(len(d['excluded']) for d in decisions)))
        checks.append(dict(case=case,accounting_error=float(expected-r['final_equity']),actual_pause_entries_checked=True))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.DataFrame(curves).to_csv(ROOT/'capital-curves.csv')
    labels=pd.read_parquet(source.ROOT/'test-labels-and-risks.parquet')
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',CASES):
        review=source.post_review(labels)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(13,6))
    for case,color in zip(CASES,['#2458c6','#d97706']):
        label='B + anti-SL témoin' if case=='REFERENCE' else 'Après1SL : pause100séances'
        ax.plot(curves[case],color=color,label=label,lw=1.5)
    ax.legend(frameon=False);ax.set_ylabel('Capital ($)');ax.grid(alpha=.2)
    ax.set_title('B + anti-SL TOP10 — un stop déclenche100séances sans achat du titre')
    fig.text(.08,.02,'4 000 $ continus ; 2021–1er octobre2026 ; frais inclus ; mêmes candidats, aucun remplacement.\nReplay exploratoire, intraday partiel/repli OHLC et réserves de prix/labels héritées.',fontsize=9)
    fig.subplots_adjust(bottom=.16);fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    atomic_json(ROOT/'final-status.json',dict(status='COMPLETED_EXPLORATORY_WITH_INHERITED_RESERVES',
        control_equity_daily_intraday_trades_exact=True,checks=checks,review=review,
        production_changes=False,new_holdout=False,provider_calls=0,SQL_writes=0,broker_orders=0))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=2,total=2,results=rows))
    print(json.dumps(rows,indent=2))


def run():
    prepare();active={};handles=[]
    try:
        logs=ROOT/'logs';logs.mkdir(exist_ok=True)
        for case in CASES:
            if (ROOT/'cases'/case/'validation.json').exists():continue
            out=(logs/(case+'.stdout.log')).open('ab');err=(logs/(case+'.stderr.log')).open('ab');handles.extend([out,err])
            active[case]=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase','case','--key',case],
                cwd=Path.cwd(),stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        while active:
            for case,child in list(active.items()):
                code=child.poll()
                if code is None:continue
                if code:raise RuntimeError(case+' failed; inspect its log')
                del active[case]
            atomic_json(ROOT/'progress.json',dict(status='REPLAYING',active=list(active),completed=2-len(active),total=2,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if active:time.sleep(2)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error=str(exc),type=type(exc).__name__))
        raise
    finally:
        for child in active.values():
            if child.poll() is None:child.terminate();child.wait()
        for handle in handles:handle.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],default='all');p.add_argument('--key');a=p.parse_args()
    if a.phase=='case':run_case(a.key)
    elif a.phase=='prepare':prepare()
    elif a.phase=='finish':finish()
    else:run()
