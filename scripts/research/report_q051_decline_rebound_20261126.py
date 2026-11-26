"""Publication repair only: native trade CSV uses quantity, not qty.

The driver, frozen protocol, simulation outputs and market inputs stay intact.
This replacement finalizer additionally reconciles receivable dividends.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_q051_decline_rebound_20261126 import ROOT,BASE,CASES,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def finalize():
    from ihm.services.backtesting_import import import_continuous_winner
    from scripts.research.report_q051_selection_variants_20261115 import fr
    original=read(BASE/'result/report.json');control=read(ROOT/'cases/REFERENCE/result/report.json')
    old_curve=pd.read_csv(BASE/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
    new_curve=pd.read_csv(ROOT/'cases/REFERENCE/result/equity-daily.csv',index_col=0,parse_dates=True).equity
    keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','average_gross_capital']
    differences={k:[original[k],control[k]] for k in keys if not np.isclose(original[k],control[k],rtol=1e-10,atol=1e-6)}
    match=old_curve.index.equals(new_curve.index) and np.allclose(old_curve,new_curve,rtol=1e-10,atol=1e-6)
    atomic_json(ROOT/'baseline-reproduction.json',dict(status='PASS' if not differences and match else 'DIFFERENT',
        differences=differences,every_daily_equity_equal=bool(match)))
    if differences or not match:raise ValueError('Témoin historique non reproduit')
    audit=pd.read_parquet(ROOT/'inputs/candidate-audit.parquet')
    rows=[];annual=[];curves=[]
    for case,label in CASES.items():
        folder=ROOT/'cases'/case;out=folder/'result';r=read(out/'report.json')
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Simulation non terminée')
        t=pd.read_csv(out/'trades.csv');m=pd.read_parquet(out/'equity-5m.parquet')
        e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        expected=t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
        if not np.allclose(expected,t.pnl,rtol=1e-10,atol=1e-7):raise ValueError('PnL non réconcilié')
        cash=r['settled_cash']+r['unsettled_cash']+r['gross']+r.get('dividends_receivable',0)
        if not np.isclose(cash,r['final_equity'],atol=1e-7):raise ValueError('Capital non réconcilié')
        dd=100*(pd.concat([pd.Series([4000.]),m.equity],ignore_index=True).pipe(lambda v:v/v.cummax()-1)).min()
        if not np.isclose(dd,r['max_drawdown_pct'],atol=1e-7):raise ValueError('DD non réconcilié')
        s=pd.read_parquet(ROOT/'inputs'/f'signals-{case}.parquet')
        expected_signals=audit.loc[audit[case],['trade_date','symbol','rank']].reset_index(drop=True)
        if not s[['trade_date','symbol','rank']].reset_index(drop=True).equals(expected_signals):
            raise ValueError('Sélection différente du filtre figé')
        wins=t[t.pnl.gt(0)];losses=t[t.pnl.lt(0)]
        row={k:r[k] for k in keys+['win_pct','average_winning_pnl','average_losing_pnl','average_gross_equity_ratio',
            'maximum_gross_capital','margin_interest','selected_signals']}
        row.update(case=case,label=label,profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()) if len(losses) else None,
            winning_holding_calendar_days=float(wins.holding_days.mean()),losing_holding_calendar_days=float(losses.holding_days.mean()),
            winning_return_pct=float(100*wins.return_pct.mean()),losing_return_pct=float(100*losses.return_pct.mean()),
            symbols=int(t.symbol.nunique()),stop_exits=int(t.exit_reason.str.contains('STOP',case=False).sum()),
            open_positions_final=len(r.get('open_positions',[])))
        rows.append(row);curves.append(e.rename(case))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
        run_id='20261126_q051_rebound_'+case.lower()
        display=label+' — '+('sans filtre' if case=='REFERENCE' else 'baisse20j/10%')+' — 2021–2026'
        record=import_continuous_winner(folder,run_id=run_id,label=display,result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    atomic_json(ROOT/'comparison.json',dict(cases=rows))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,ddax)=plt.subplots(2,1,sharex=True,figsize=(13,8),gridspec_kw={'height_ratios':[2,1]})
    for case,label,color in zip(CASES,CASES.values(),['#2455cc','#999999','#e8851c','#138b6c']):
        e=pd.read_csv(ROOT/'cases'/case/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        row=next(r for r in rows if r['case']==case)
        pct=f"{row['return_pct']:+.2f}".replace('.',',')
        ax.plot(e.index,e,color=color,label=label+f' : {pct} %')
        ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000.)-1),color=color)
    ax.set_title('Q051 TOP10 — baisse préalable puis début de reprise')
    ax.set_xlim(pd.Timestamp('2021-01-01'),pd.Timestamp('2026-10-01'))
    ax.set_ylabel('Capital ($), départ 4 000');ax.legend(fontsize=9);ax.grid(alpha=.2)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.07,.01,'2021–1 octobre 2026. SL5/open11, frais inclus, achat J+1. Aucun remplacement après filtre.\nRésultats exploratoires : univers rétrospectif, intraday partiel/repli OHLC ; DD du tableau mesuré en intraday.',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    table=['| Variante | Capital final | Rendement | DD max intraday | Trades | Gagnants | Exposition moyenne |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        table.append('| '+r['label']+' | '+fr(r['final_equity'])+' $ | '+fr(r['return_pct'],percent=True)+' | '+
            fr(r['max_drawdown_pct'],percent=True)+' | '+str(r['closed_lot_trades'])+' | '+fr(r['win_pct'],percent=True)+
            ' | '+fr(100*r['average_gross_equity_ratio'],percent=True)+' |')
    (ROOT/'results.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    atomic_json(ROOT/'reporting-repair.json',dict(status='PASS',reporter_sha256=digest(Path(__file__)),
        corrected='CSV field quantity and receivable dividends in accounting check only',
        simulation_inputs_unchanged=True,simulation_outputs_unchanged=True))
    return rows


if __name__=='__main__':print(json.dumps(finalize(),ensure_ascii=False))
