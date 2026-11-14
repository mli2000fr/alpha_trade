"""Run prespecified A2 comparisons, then two cost stresses, validate and plot."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
from multiprocessing import get_context
from pathlib import Path
import json

import pandas as pd

from scripts.research import us_q051_range_support_a2_20261109 as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def finalize(root,imports):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    results=[];annual=[];validation=[]
    fig,axes=plt.subplots(2,1,figsize=(14,10),sharex=True)
    labels={'BASELINE_ALL':'Témoin complet open J+1','BASELINE_COMMON':'Témoin contexte commun open J+1',
        'WAIT_COMMON':'Attente fixe10h30 NY','A2_COMMON':'A2 rebond support M15'}
    for item in imports:
        folder=Path(item['folder'])/'result';report=pilot.read(folder/'report.json');name=item['profile']
        trades=pd.read_csv(folder/'trades.csv');events=pd.read_csv(folder/'events.csv');risk=pd.read_csv(folder/'portfolio-risk-decisions.csv')
        assert len(trades)==report['closed_lot_trades']
        assert int(trades.pnl.gt(0).sum())==report['winners'] and int(trades.pnl.lt(0).sum())==report['losers']
        scheduled=events[events.get('execution_proxy',pd.Series(index=events.index,dtype=str)).eq('SCHEDULED_5M_OPEN')]
        for row in scheduled.to_dict('records'):
            if pd.Timestamp(row['available_at'])>pd.Timestamp(row['time']):raise ValueError('Future scheduled fill')
            expected=(pd.Timestamp(row['confirmed_at'])+pd.Timedelta(seconds=930)).ceil('5min')
            if row.get('setup')=='A2_RANGE_SUPPORT_LONG' and expected!=pd.Timestamp(row['time']):raise ValueError('Wrong delayed A2 execution clock')
        fallback=events[events.get('event',pd.Series(index=events.index,dtype=str)).eq('DAILY_OHLC_FALLBACK')]
        keys={(str(pd.Timestamp(row['time']).date()),row['symbol']) for row in fallback.to_dict('records')}
        fallback_entries=sum((str(pd.Timestamp(row['time']).date()),row['symbol']) in keys for row in scheduled.to_dict('records'))
        reduced=risk[risk.status.eq('QUALIFIED')] if len(risk) else risk
        if len(reduced) and (reduced.approved_vol.gt(.2+1e-10)&reduced.final_quantity.gt(0)).any():raise ValueError('New quantity above volatility budget')
        validation.append(dict(profile=name,trade_counts='PASS',availability='PASS',vol_budget='PASS',
            late_entries_with_daily_protection_bound=int(fallback_entries)))
        row={k:report.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers',
            'win_pct','average_winning_pnl','average_losing_pnl','average_gross_capital','maximum_gross_capital']}
        row.update(profile=name,late_entries_with_daily_protection_bound=int(fallback_entries));results.append(row)
        a=pd.read_csv(folder/'annual-summary.csv');a['profile']=name;annual.append(a)
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
        assert abs(float(curve.iloc[-1])-report['final_equity'])<1e-6
        for record in a.to_dict('records'):
            selected=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(record['year'])]
            assert len(selected)==record['closed_lot_trades'] and int(selected.pnl.gt(0).sum())==record['winners']
        ax=axes[1 if name.endswith('_COST25') else 0]
        curve.loc[pd.Timestamp('2021-01-01')]=4000.;curve=curve.sort_index()
        ax.plot(curve.index,curve,label=labels[name.replace('_COST25','')],linewidth=1.4)
    for ax,cost in zip(axes,[8,25]):
        ax.set_title(f'Coût simulé {cost} pb par opération');ax.set_ylabel('Capital valorisé USD');ax.legend();ax.grid(alpha=.2)
    fig.suptitle('Q051 volatilité20 % + régime — A2 support M15 — 2021–01/10/2026')
    fig.text(.07,.015,'Exploratoire. Couverture5m partielle ; secours quotidien conservateur, y compris après entrée tardive.',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.97));charts=root/'charts';charts.mkdir()
    fig.savefig(charts/'capital-comparison.png',dpi=140);fig.savefig(charts/'capital-comparison.svg');plt.close(fig)
    pd.DataFrame(results).to_csv(root/'comparison.csv',index=False);pd.concat(annual,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    atomic_json(root/'validation.json',dict(status='PASS',cases=validation,reference_reproduced=True,
        limitation='Daily high/low fallback after intraday entry is a conservative adverse bound; strict timing not certified'))
    report=dict(status='COMPLETED_EXPLORATORY',results=results,imports=imports,frequency=pilot.read(root/'frequency.json'),
        validation='PASS',source_sha256=digest(Path(__file__)),chart=str(charts/'capital-comparison.png'),
        provider_calls=0,SQL_writes=0,orders=0,production_changes=False,finished_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)


def run(root=pilot.ROOT):
    root=Path(root);pilot.run(root)
    report=pilot.read(root/'report.json')
    if report['status']=='INSUFFICIENT_FREQUENCY_NO_BACKTEST':return
    imports=list(report['imports'])
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(pilot.replay,str(root),case,True):case for case in ['BASELINE_COMMON','A2_COMMON']}
        for task in as_completed(tasks):
            imports.append(task.result())
            atomic_json(root/'progress.json',dict(status='RUNNING_COST25_STRESS',completed=len(imports),total=6,imports=imports))
    finalize(root,imports)


if __name__=='__main__':
    try:run()
    except Exception as exc:
        if pilot.ROOT.exists():atomic_json(pilot.ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
