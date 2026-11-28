"""Complete, validate and publish the prespecified entry-ceiling comparison."""
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from scripts.research.us_q051_entry_ceiling_20261127 import ROOT,CASES,INPUT,previous,read,validate_reference
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def finalize():
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from ihm.services.backtesting_import import import_continuous_winner
    validate_reference();plan=read(ROOT/'protocol.json')
    for name,sha in plan['sources'].items():
        if digest(name)!=sha:raise ValueError('Frozen source changed: '+name)
    panel=pd.read_parquet(ROOT/'inputs/candidates.parquet')
    frames={k:pd.read_parquet(INPUT/(k+'.parquet')) for k in ('open','high','low','close')}
    # Scalar ATR check independent of the vectorized ceiling calculator.
    for row in panel.itertuples():
        i=frames['close'].index.get_loc(pd.Timestamp(row.origin_signal_date));trs=[]
        for j in range(i-19,i+1):
            h=frames['high'].iloc[j][row.symbol];lo=frames['low'].iloc[j][row.symbol]
            pc=frames['close'].iloc[j-1][row.symbol]
            trs.append(max(h-lo,abs(h-pc),abs(lo-pc)))
        expected=float(np.mean(trs))
        if not np.isclose(expected,row.atr20,rtol=1e-11,atol=1e-9):raise ValueError('Scalar ATR mismatch')
        if not np.isclose(row.signal_close+.5*expected,row.ceiling,atol=1e-9):raise ValueError('Ceiling mismatch')
    with replay_market_registry(previous.shared.restore_registry(previous.shared.ROOT)):
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in cal.sessions(pd.Timestamp('2019-01-01').date(),pd.Timestamp('2026-11-01').date()) if s.is_open]
    positions={s.session_date:i for i,s in enumerate(sessions)}
    openings={s.session_date:pd.Timestamp(s.open_at_utc) for s in sessions}
    origins=panel.set_index('origin_id');rows=[];annual=[];curves=[];configurations=[];checks=[]
    for case,label in CASES.items():
        folder=ROOT/'cases'/case;out=folder/'result'
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Case incomplete')
        isolation=read(folder/'isolation.json')
        if isolation['status']!='COMPLETED' or isolation.get('violations'):raise ValueError('Isolation failed')
        configurations.append(read(out/'configuration.json')['portfolio'])
        report=read(out/'report.json');trades=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        marks=pd.read_parquet(out/'equity-5m.parquet');equity=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        pnl=trades.quantity*(trades.exit_price-trades.entry_price)-trades.entry_fees-trades.exit_fees+trades.dividends
        if not np.allclose(pnl,trades.pnl,rtol=1e-10,atol=1e-7):raise ValueError('PnL mismatch')
        costs=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
        if not np.isclose(costs,report['costs'],atol=1e-7):raise ValueError('Fees mismatch')
        dd=100*(pd.concat([pd.Series([4000.]),marks.equity],ignore_index=True).pipe(lambda e:e/e.cummax()-1)).min()
        if not np.isclose(dd,report['max_drawdown_pct'],atol=1e-7):raise ValueError('DD mismatch')
        accounting=report['settled_cash']+report['unsettled_cash']+report['gross']+report.get('dividends_receivable',0)
        if not np.isclose(accounting,report['final_equity'],atol=1e-7):raise ValueError('Final accounting mismatch')
        buys=events.loc[events.event.eq('BUY_FILL')].copy()
        if case!='REFERENCE':
            if buys.origin_id.duplicated().any():raise ValueError('Signal attempted twice after fill')
            for fill in buys.itertuples():
                source=origins.loc[fill.origin_id];stamp=pd.Timestamp(fill.time)
                wait=positions[stamp.date()]-positions[pd.Timestamp(source.origin_signal_date).date()]
                if wait not in ((1,) if case=='CAP_OPEN' else (1,2)):raise ValueError('Entry beyond fixed waiting window')
                if fill.price>source.ceiling+1e-8:raise ValueError('Entry above ceiling')
                if not np.isclose(fill.entry_ceiling,source.ceiling,atol=1e-8):raise ValueError('Entry ceiling changed after J')
                if fill.execution_proxy=='DAILY_SESSION_OPEN':
                    if stamp!=openings[stamp.date()]:raise ValueError('Daily fill off opening')
                    expected=frames['open'].at[pd.Timestamp(stamp.date()),fill.symbol]
                    if not np.isclose(expected,fill.price,atol=1e-8):raise ValueError('Invented daily opening')
        for trade in trades.itertuples():
            en=pd.Timestamp(trade.entry_date);ex=pd.Timestamp(trade.exit_date)
            held=positions[ex.date()]-positions[en.date()]
            if not 0<=held<=10:raise ValueError('Held longer than H10')
            if trade.exit_reason=='HORIZON_OPEN' and (held!=10 or ex!=openings[ex.date()]):raise ValueError('Not open11')
        if not trades.side.eq('buy').all() or trades.exit_reason.str.startswith('TP').any():raise ValueError('Unexpected SHORT/TP')
        a=pd.read_csv(out/'annual-summary.csv')
        if not np.isclose(4000*np.prod(1+a.return_pct/100),report['final_equity'],atol=1e-6):raise ValueError('Annual reset or compounding mismatch')
        a['case']=case;annual.append(a);curves.append(equity.rename(case))
        wins=trades[trades.pnl.gt(0)];losses=trades[trades.pnl.lt(0)]
        metrics=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers',
                 'average_winning_pnl','average_losing_pnl','average_gross_capital','maximum_gross_capital',
                 'average_gross_equity_ratio','costs','margin_interest']
        row={k:report[k] for k in metrics}
        row.update(case=case,label=label,profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()),
            stop_exits=int(trades.exit_reason.str.contains('STOP',case=False).sum()),
            same_day_stops=int((trades.exit_reason.str.contains('STOP',case=False)&trades.is_day_trade).sum()),
            winner_mean_return_pct=float(100*wins.return_pct.mean()),loser_mean_return_pct=float(100*losses.return_pct.mean()),
            winning_mean_holding_calendar_days=float(wins.holding_days.mean()),losing_mean_holding_calendar_days=float(losses.holding_days.mean()),
            buys=len(buys),open_positions=len(report.get('open_positions',[])))
        if case!='REFERENCE':
            base_trades=pd.read_csv(ROOT/'cases/REFERENCE/result/trades.csv')
            base_buys=pd.read_csv(ROOT/'cases/REFERENCE/result/events.csv')
            base_buys=base_buys[base_buys.event.eq('BUY_FILL')].copy()
            # Original identity from its recorded daily signal date, never the
            # result of a future ranking or a same-date symbol approximation.
            base_buys['origin_id']=pd.to_datetime(base_buys.signal_date).dt.strftime('%Y-%m-%d')+'|'+base_buys.symbol
            base_buys['entry_date']=pd.to_datetime(base_buys.time,utc=True)
            base_trades['entry_date']=pd.to_datetime(base_trades.entry_date,utc=True)
            merged=base_trades.merge(base_buys[['origin_id','symbol','entry_date']],on=['symbol','entry_date'],validate='many_to_one')
            missed=merged[~merged.origin_id.isin(set(buys.origin_id))]
            missed.to_csv(out/'reference-trades-not-bought.csv',index=False)
            row.update(reference_trades_not_bought=len(missed),reference_winners_not_bought=int(missed.pnl.gt(0).sum()),
                       reference_losers_not_bought=int(missed.pnl.lt(0).sum()),
                       fixed_reference_pnl_of_missed_trades=float(missed.pnl.sum()))
        rows.append(row);checks.append(dict(case=case,status='PASS',trades=len(trades),fills=len(buys)))
        rec=import_continuous_winner(folder,run_id='20261127_q051_ceiling_'+case.lower(),
            label=label+' — 2021–2026 — recherche',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=rec['run_id']))
    if any(x!=configurations[0] for x in configurations):raise ValueError('Different economic configurations')
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    atomic_json(ROOT/'comparison.json',dict(cases=rows))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,dax)=plt.subplots(2,1,sharex=True,figsize=(13,8),gridspec_kw={'height_ratios':[2,1]})
    for row,curve,color in zip(rows,curves,['#2455cc','#e8851c','#138b6c']):
        ax.plot(curve.index,curve,color=color,label=row['label']+f" : {row['return_pct']:+.2f} %")
        dax.plot(curve.index,100*(curve/curve.cummax().clip(lower=4000.)-1),color=color)
    ax.set_title('Q051 TOP10 — prix maximal d’entrée : clôture J + 0,5 ATR20')
    ax.set_ylabel('Capital ($), départ 4 000');ax.legend(fontsize=9);ax.grid(alpha=.2)
    dax.set_ylabel('DD aux clôtures (%)');dax.grid(alpha=.2)
    fig.text(.07,.01,'2021–1 octobre 2026. Même sélection et risque ; SL5/open11, frais et financement inclus.\nExploratoire : univers rétrospectif, 5m partiel/repli daily. Entrées tardives : couverture 5m complète requise ex post.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    table=['| Variante | Capital final $ | Rendement | DD max intraday | Trades | Gagnants | Capital engagé moyen $ |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:table.append(f"| {r['label']} | {r['final_equity']:.2f} | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | {r['closed_lot_trades']} | {r['win_pct']:.2f} % | {r['average_gross_capital']:.2f} |")
    (ROOT/'results.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    atomic_json(ROOT/'validation.json',dict(status='PASS',baseline_exact=True,scalar_ATR_signals=len(panel),
        configurations_identical=True,checks=checks,review='same assistant, not independent human review'))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=3,total=3,validation='PASS',
        finished_at_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(rows,ensure_ascii=False),flush=True)


def continue_after_reference():
    # A local coordinator, not a scheduled task or a second copy of a run.
    while True:
        path=ROOT/'cases/REFERENCE/progress.json'
        state=read(path) if path.exists() else {}
        if state.get('status')=='FAILED':raise ValueError('Reference failed: '+str(state))
        if state.get('status')=='COMPLETED_EXPLORATORY':break
        atomic_json(ROOT/'progress.json',dict(status='REPRODUCING_REFERENCE',completed=0,total=3,
            reference_completed=state.get('completed',0),reference_total=state.get('total',1443),
            last_date=state.get('last_date'),updated_at_utc=datetime.now(timezone.utc).isoformat()))
        time.sleep(5)
    validate_reference()
    atomic_json(ROOT/'progress.json',dict(status='REPLAYING',completed=1,total=3,
        baseline='PASS_VALIDATED_ARCHIVE_REUSE' if (ROOT/'baseline-reuse.json').exists() else 'PASS_REPRODUCED',
        running=['CAP_OPEN','CAP_WAIT2'],updated_at_utc=datetime.now(timezone.utc).isoformat()))
    subprocess.run([sys.executable,'-X','utf8','-m','scripts.research.us_q051_entry_ceiling_20261127','--phase','variants'],check=True)
    finalize()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--continue',dest='resume',action='store_true');args=p.parse_args()
    try:
        if args.resume:continue_after_reference()
        else:finalize()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
