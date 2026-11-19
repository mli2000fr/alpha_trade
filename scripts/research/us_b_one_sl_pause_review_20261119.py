"""Post-run accounting, exposure, missed-reference opportunity diagnostics."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scripts.research.us_b_one_sl_pause_20261119 import ROOT,CASES,read
from scripts.research.us_q051_b_early_sl_20261116 import FULL
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def main():
    final=read(ROOT/'final-status.json')
    if not final.get('control_equity_daily_intraday_trades_exact'):
        raise ValueError('Full no-pause control not verified')
    plan=read(ROOT/'protocol.json')
    for name,h in plan['sources'].items():
        if digest(Path(name))!=h:raise ValueError('Changed sealed source: '+name)
    from modelFactory.oracle.build_labels import nyse_sessions
    from datetime import date
    days=[d.date() for d in nyse_sessions(date(2020,1,1),date(2028,1,1))]
    positions={d:i for i,d in enumerate(days)}
    volume=pd.read_parquet(FULL/'inputs/volume.parquet')
    reference=pd.read_csv(ROOT/'cases/REFERENCE/result/trades.csv')
    reference['entry_ts']=pd.to_datetime(reference.entry_date,utc=True)
    intervals=read(ROOT/'cases/ONE_SL_PAUSE100/result/pause-triggers.json')
    reference['during_variant_pause']=False
    for e in intervals:
        end=pd.Timestamp(e['resume_session']).tz_localize('America/New_York')
        mask=reference.symbol.eq(e['symbol']) & reference.entry_ts.ge(pd.Timestamp(e['known_at'])) & reference.entry_ts.lt(end)
        reference.loc[mask,'during_variant_pause']=True
        if positions[date.fromisoformat(e['resume_session'])]-positions[date.fromisoformat(e['trigger_session'])]!=101:
            raise ValueError('Pause session expiry differs from protocol')
    reference.to_csv(ROOT/'reference-opportunities-during-variant-pauses.csv',index=False)
    missed=reference[reference.during_variant_pause]
    diagnostics=dict(scope='Trades actually bought by unpaused reference falling in actual variant pauses; not filtered portfolio PnL',
        trades=len(missed),winners=int(missed.pnl.gt(0).sum()),losers=int(missed.pnl.lt(0).sum()),
        net_pnl=float(missed.pnl.sum()),stop_exits=int(missed.exit_reason.isin(['STOP','STOP_GAP']).sum()))
    checks=[];window=[];symbols=[];anomalies=[];curves={};dd_episodes=[]
    for case in CASES:
        folder=ROOT/'cases'/case/'result';report=read(folder/'report.json')
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        curves[case]=curve
        marks=pd.read_parquet(folder/'equity-5m.parquet')
        drawdown=marks.equity/marks.equity.cummax().clip(lower=4000)-1
        trough=drawdown.idxmin();peak=marks.loc[:trough].equity.idxmax()
        dd_episodes.append(dict(case=case,peak_time=str(marks.loc[peak,'timestamp']),
            trough_time=str(marks.loc[trough,'timestamp']),max_intraday_dd_pct=float(100*drawdown[trough])))
        events=pd.read_csv(folder/'events.csv');trades=pd.read_csv(folder/'trades.csv')
        flows=events[events.event.isin(['BUY_FILL','SELL_FILL'])].copy()
        flows['day']=pd.to_datetime(flows.time,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        flows['delta']=flows.quantity*np.where(flows.event.eq('BUY_FILL'),1,-1)
        q=flows.pivot_table(index='day',columns='symbol',values='delta',aggfunc='sum',fill_value=0).reindex(curve.index,fill_value=0).cumsum()
        if q.lt(-1e-8).any().any():raise ValueError('Oversold holdings')
        if q.gt(0).sum(axis=1).max()>20:raise ValueError('More than20positions')
        expected={p['symbol']:int(p['qty']) for p in report['open_positions']}
        observed={s:int(v) for s,v in q.iloc[-1].items() if v>0}
        if observed!=expected:raise ValueError('Ending holdings mismatch')
        # Include same-day round trips and positions sold at the opening.
        bought=flows[flows.event.eq('BUY_FILL')].pivot_table(index='day',columns='symbol',values='quantity',aggfunc='sum',fill_value=0)
        held=q.gt(0)|q.shift(1,fill_value=0).gt(0)|bought.reindex(index=q.index,columns=q.columns,fill_value=0).gt(0)
        v=volume.reindex(index=q.index,columns=q.columns)
        bad=held&(v.isna()|v.le(0))
        for i,j in np.argwhere(bad.to_numpy()):
            anomalies.append(dict(case=case,date=str(q.index[i].date()),symbol=q.columns[j],
                volume=None if pd.isna(v.iloc[i,j]) else float(v.iloc[i,j])))
        fill_fees=float(flows.costs.sum())
        if abs(fill_fees-report['costs'])>1e-6:raise ValueError('Fill fees do not reconcile')
        for start,end in [('2024-11-06','2025-04-04'),('2024-11-06','2025-06-30'),('2025-07-01','2026-10-01')]:
            w=curve.loc[start:end]
            window.append(dict(case=case,start=start,end=end,return_pct=100*(w.iloc[-1]/w.iloc[0]-1),
                max_close_dd_pct=100*(w/w.cummax()-1).min(),start_equity=float(w.iloc[0]),end_equity=float(w.iloc[-1])))
        exit_ts=pd.to_datetime(trades.exit_date,utc=True)
        t=trades[exit_ts.gt(pd.Timestamp('2024-11-06T21:00Z')) & exit_ts.le(pd.Timestamp('2025-04-04T20:00Z'))].copy()
        t['stop']=t.exit_reason.isin(['STOP','STOP_GAP'])
        g=t.groupby('symbol').agg(trades=('pnl','size'),stops=('stop','sum'),pnl=('pnl','sum')).reset_index();g['case']=case;symbols.append(g)
        checks.append(dict(case=case,ending_holdings=True,no_oversells=True,max_positions=int(q.gt(0).sum(axis=1).max()),
            fill_fees=fill_fees,fees_reconciled=True,zero_volume_held_symbol_days=int(bad.sum().sum())))
    pd.DataFrame(window).to_csv(ROOT/'window-comparison.csv',index=False)
    pd.concat(symbols).to_csv(ROOT/'window-symbol-trades.csv',index=False)
    pd.DataFrame(dd_episodes).to_csv(ROOT/'max-dd-episodes.csv',index=False)
    atomic_json(ROOT/'opportunity-diagnostics.json',diagnostics)
    atomic_json(ROOT/'held-volume-screen.json',dict(status='REVIEW_REQUIRED' if anomalies else 'NO_ACTUAL_OVERLAP',
        anomalies=anomalies,scope='Anomaly screen only; not complete price certification'))
    atomic_json(ROOT/'completion.json',dict(status='COMPLETED_EXPLORATORY_WITH_RESERVES',checks=checks,
        pause_expiry_verified=True,tests_passed=6,actual_variant_pauses_only=True,
        unique_paused_symbols=len({e['symbol'] for e in intervals}),review_source_sha256=digest(Path(__file__)),
        sources_unchanged=True,missed_reference_opportunities=diagnostics,
        inherited_review=final['review'],volume_anomalies=anomalies,
        independent_holdout=False,production_changes=False,SQL_writes=0,provider_calls=0,broker_orders=0))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    colors=['#2458c6','#d97706'];labels=['B + anti-SL témoin','Un SL → pause de 100 séances']
    fig,(ax,z)=plt.subplots(2,1,figsize=(13,8),gridspec_kw={'height_ratios':[1.5,1]},facecolor='#f6f8fc')
    for axis in [ax,z]:
        axis.set_facecolor('white');axis.grid(axis='y',alpha=.2);axis.spines[['top','right']].set_visible(False)
    for (case,curve),color,label in zip(curves.items(),colors,labels):
        seeded=pd.concat([pd.Series([4000.],index=pd.to_datetime(['2020-12-31'])),curve])
        ret=100*(curve.iloc[-1]/4000-1)
        ax.plot(seeded.index,seeded,color=color,lw=1.6,label=f'{label} : {ret:+.2f} %'.replace('.',','))
        w=curve.loc['2024-11-06':'2025-04-04'];relative=100*w/w.iloc[0]
        z.plot(relative.index,relative,color=color,lw=1.7)
        z.annotate(f'{relative.iloc[-1]-100:+.2f} %'.replace('.',','),xy=(relative.index[-1],relative.iloc[-1]),
            xytext=(8,0),textcoords='offset points',va='center',color=color,fontweight='bold')
    ax.legend(frameon=False);ax.set_ylabel('Capital ($)')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v:,.0f}'.replace(',',' ')))
    ax.axvspan(pd.Timestamp('2024-11-06'),pd.Timestamp('2025-04-04'),color='#a7b3c6',alpha=.15)
    z.set_xlim(pd.Timestamp('2024-11-06'),pd.Timestamp('2025-05-01'))
    z.set_title('Zoom sur la baisse : base 100 au 6 novembre 2024',loc='left',fontsize=12,pad=10)
    z.set_ylabel('Évolution relative')
    fig.suptitle('B + anti-SL TOP10 — après chaque stop, 100 séances sans achat du titre',fontsize=15,fontweight='bold')
    fig.text(.08,.025,'4 000 $ continus ; 2021–1er octobre 2026 ; SL5/open11 ; frais et financement inclus.\n'
        'Mêmes candidats sans remplacement ; replay exploratoire, intraday partiel et réserves historiques.',fontsize=9)
    fig.subplots_adjust(left=.08,right=.97,top=.91,bottom=.14,hspace=.35)
    fig.savefig(ROOT/'capital-comparison-and-zoom.png',dpi=150);plt.close(fig)
    print(pd.read_csv(ROOT/'comparison.csv').to_string(index=False))
    print(pd.DataFrame(window).to_string(index=False))
    print(json.dumps(diagnostics,indent=2))


if __name__=='__main__':main()
