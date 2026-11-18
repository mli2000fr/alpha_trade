"""Read-only attribution of the observed late-2024/early-2025 SL10 drawdown.

No strategy changes, replay, SQL, model fitting or external data requests.
Daily close-to-close attribution is kept separate from the intraday maximum DD.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

SOURCE=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
FULL=Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')
ROOT=Path('artifacts/research/us_q051_b_sl10_drawdown_audit/20261117-v2')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def cutoff(day):return pd.Timestamp(day).tz_localize('America/New_York')+pd.Timedelta(hours=16)


def quantities(events,stamp):
    f=events[events.time.le(stamp)&events.event.isin(['BUY_FILL','SELL_FILL'])].copy()
    f['signed']=f.quantity*np.where(f.event.eq('BUY_FILL'),1.,-1.)
    q=f.groupby('symbol').signed.sum()
    if q.lt(-1e-9).any():raise ValueError('Negative reconstructed holdings')
    return q[q.gt(1e-9)]


def market_groups(day):
    from scripts.research.us_q051_feature_groups_cd_20261116 import ReferencePrices,EXT
    g=dict(ReferencePrices(EXT).day(day))
    extra=pd.read_parquet(SOURCE/'inputs/intraday'/(str(day)+'.parquet'))
    for symbol,frame in extra.groupby('symbol') if not extra.empty else []:
        if symbol in g:raise ValueError('Frozen supplementary tape collision')
        g[symbol]=frame
    return g


def marks_at(events,day,daily_close):
    q=quantities(events,cutoff(day));groups=market_groups(pd.Timestamp(day).date())
    fallback=set(events.loc[events.event.eq('DAILY_OHLC_FALLBACK')&events.time.eq(cutoff(day)),'symbol'])
    rows=[]
    for symbol,qty in q.items():
        if symbol in fallback:
            price=float(daily_close.loc[day,symbol]);kind='CANONICAL_DAILY_CLOSE_FALLBACK'
        else:
            frame=groups[symbol].sort_values('timestamp');price=float(frame.iloc[-1].close);kind='FROZEN_5M_LAST_CLOSE'
        if not np.isfinite(price) or price<=0:raise ValueError('Unqualified boundary mark')
        rows.append(dict(symbol=symbol,quantity=qty,price=price,value=qty*price,source=kind))
    return pd.DataFrame(rows,columns=['symbol','quantity','price','value','source']).set_index('symbol')


def main():
    ROOT.mkdir(parents=True,exist_ok=False)
    out=SOURCE/'cases/SL10/result'
    equity=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    m=pd.read_parquet(out/'equity-5m.parquet');m.timestamp=pd.to_datetime(m.timestamp,utc=True)
    dd=m.equity/m.equity.cummax()-1;it=dd.idxmin();ip=m.loc[:it].equity.idxmax()
    # Exact close-to-close counterpart of the visible drawdown. Intraday extrema
    # have different timestamps and must never share its realized-PnL attribution.
    search=equity.loc['2024-07-01':'2025-07-01'];daily_dd=search/search.cummax()-1
    end=daily_dd.idxmin();start=search.loc[:end].idxmax();a,b=cutoff(start),cutoff(end)
    trades=pd.read_csv(out/'trades.csv');trades['entry']=pd.to_datetime(trades.entry_date,utc=True)
    trades['exit']=pd.to_datetime(trades.exit_date,utc=True)
    events=pd.read_csv(out/'events.csv',low_memory=False);events.time=pd.to_datetime(events.time,utc=True)
    close=pd.read_parquet(FULL/'close.parquet');opening=pd.read_parquet(FULL/'open.parquet')
    actions=pd.read_parquet(FULL/'actions.parquet');actions['day']=pd.to_datetime(actions.ex_date)
    sectors=pd.read_parquet(FULL/'sectors.parquet').set_index('symbol').sector.to_dict()
    begin=marks_at(events,start,close);finish=marks_at(events,end,close)
    begin.to_csv(ROOT/'opening-holdings.csv');finish.to_csv(ROOT/'ending-holdings.csv')
    fills=events[events.time.gt(a)&events.time.le(b)&events.event.isin(['BUY_FILL','SELL_FILL'])].copy()
    fills['cashflow']=fills.quantity*fills.price*np.where(fills.event.eq('SELL_FILL'),1.,-1.)-fills.costs
    symbols=sorted(set(fills.symbol)|set(begin.index)|set(finish.index))
    attributed=pd.DataFrame(index=pd.Index(symbols,name='symbol'))
    attributed['cashflow']=fills.groupby('symbol').cashflow.sum().reindex(symbols,fill_value=0)
    attributed['starting_value']=begin.value.reindex(symbols,fill_value=0)
    attributed['ending_value']=finish.value.reindex(symbols,fill_value=0)
    attributed['dividends']=0.
    for row in actions[actions.day.gt(start)&actions.day.le(end)].itertuples():
        if row.ca_type not in ['cash_dividend','special_dividend']:raise ValueError('Unsupported corporate action in attribution')
        qty=quantities(events,pd.Timestamp(row.day).tz_localize('America/New_York')-pd.Timedelta(nanoseconds=1)).get(row.symbol,0.)
        if qty:
            if row.currency!='USD':raise ValueError('Unqualified dividend currency')
            attributed.loc[row.symbol,'dividends']+=qty*row.amount_per_share
    attributed['period_pnl']=attributed.cashflow+attributed.ending_value-attributed.starting_value+attributed.dividends
    attributed['sector']=[sectors.get(s,'UNKNOWN') for s in attributed.index]
    financing=float(events.loc[events.time.gt(a)&events.time.le(b)&events.event.eq('FINANCING'),'costs'].sum())
    delta=float(equity[end]-equity[start]);residual=delta-(attributed.period_pnl.sum()-financing)
    if abs(residual)>1e-6:raise ValueError('Capital attribution does not reconcile: '+str(residual))
    attributed.sort_values('period_pnl').to_csv(ROOT/'symbol-attribution.csv')
    attributed.groupby('sector').period_pnl.sum().sort_values().to_csv(ROOT/'sector-attribution.csv')
    window=trades[trades.exit.gt(a)&trades.exit.le(b)].copy()
    window['stop']=window.exit_reason.isin(['STOP','STOP_GAP'])
    window['same_session']=window.entry.dt.tz_convert('America/New_York').dt.date.eq(window.exit.dt.tz_convert('America/New_York').dt.date)
    window['month']=window.exit.dt.tz_convert('America/New_York').dt.strftime('%Y-%m')
    window.to_csv(ROOT/'closed-trades.csv',index=False)
    by_reason=window.groupby('exit_reason').agg(trades=('pnl','size'),pnl=('pnl','sum'),mean_pnl=('pnl','mean'),
        mean_return=('return_pct','mean'),win_pct=('pnl',lambda x:100*x.gt(0).mean()))
    by_reason.to_csv(ROOT/'exit-reasons.csv')
    monthly=[]
    for period,g in equity.loc[start:end].groupby(equity.loc[start:end].index.to_period('M')):
        prior=equity.loc[:g.index[0]].iloc[-2] if g.index[0]!=start else equity[start]
        u=window[window.month.eq(str(period))]
        monthly.append(dict(month=str(period),end_equity=float(g.iloc[-1]),return_pct=100*(float(g.iloc[-1])/prior-1),
            closed_trades=len(u),realized_pnl=float(u.pnl.sum()),win_pct=100*u.pnl.gt(0).mean(),
            stops=int(u.stop.sum()),stop_gaps=int(u.exit_reason.eq('STOP_GAP').sum())))
    pd.DataFrame(monthly).to_csv(ROOT/'monthly.csv',index=False)
    repeats=window.groupby('symbol').agg(exits=('pnl','size'),stops=('stop','sum'),pnl=('pnl','sum'))
    repeats.sort_values('pnl').to_csv(ROOT/'repeat-stops.csv')
    # Verify all gap exits against BOTH frozen daily open and available raw 5m
    # opening prints. Matching the same tape is an internal consistency check,
    # never independent verification by a second provider.
    gap_checks=[];cached={}
    for t in window[window.exit_reason.eq('STOP_GAP')].itertuples():
        day=t.exit.tz_convert('America/New_York').date()
        if day not in cached:cached[day]=market_groups(day)
        group=cached[day].get(t.symbol);raw=None
        if group is not None and not group.empty:
            matching=group[pd.to_datetime(group.timestamp,utc=True).eq(t.exit)]
            if len(matching)==1:raw=float(matching.iloc[0].open)
        daily=float(opening.loc[pd.Timestamp(day),t.symbol]);same=abs(daily-t.exit_price)<.011
        at_session_open=t.exit==pd.Timestamp(day).tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
        gap_checks.append(dict(symbol=t.symbol,entry_date=str(t.entry),exit_date=str(t.exit),quantity=t.quantity,
            entry_price=t.entry_price,exit_price=t.exit_price,pnl=t.pnl,return_pct=100*t.return_pct,
            daily_open=daily,daily_matches=same,at_session_open=at_session_open,raw_5m_open=raw,
            raw_5m_matches=None if raw is None else abs(raw-t.exit_price)<.011))
    pd.DataFrame(gap_checks).to_csv(ROOT/'gap-price-checks.csv',index=False)
    if not all((not g['at_session_open'] or g['daily_matches']) and g['raw_5m_matches'] is not False for g in gap_checks):
        raise ValueError('Gap-price discrepancy requires review')
    comparisons=[];curves=[]
    specs=[('B seul TOP10',SOURCE/'cases/CONTROL/result'),('B + anti-SL10 TOP10',out)]
    protected=Path('artifacts/research/us_q051_b_sl10_vol20_regime/20261117-v1')
    if read(protected/'progress.json').get('status')=='COMPLETED_EXPLORATORY':
        specs.append(('B + anti-SL10 + vol20/régime TOP10',protected/'cases/SL10_VOL20_REGIME/result'))
    for name,folder in specs:
        e=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity.loc[start:end]
        tt=pd.read_csv(folder/'trades.csv');xt=pd.to_datetime(tt.exit_date,utc=True)
        u=tt[xt.gt(a)&xt.le(b)]
        comparisons.append(dict(case=name,start_equity=float(e.iloc[0]),end_equity=float(e.iloc[-1]),
            window_return_pct=100*(e.iloc[-1]/e.iloc[0]-1),window_dd_pct=100*(e/e.cummax()-1).min(),
            closed_trades=len(u),win_pct=100*u.pnl.gt(0).mean()))
        curves.append((100*e/e.iloc[0]).rename(name))
    spy=close.loc[start:end,'SPY']
    comparisons.append(dict(case='SPY prix seuls',start_equity=float(spy.iloc[0]),end_equity=float(spy.iloc[-1]),
        window_return_pct=100*(spy.iloc[-1]/spy.iloc[0]-1),window_dd_pct=100*(spy/spy.cummax()-1).min()))
    curves.append((100*spy/spy.iloc[0]).rename('SPY prix seuls'))
    pd.DataFrame(comparisons).to_csv(ROOT/'same-window-comparison.csv',index=False)
    scores=pd.read_parquet(SOURCE/'variants/SL10/signals.parquet')
    buy=events[events.event.eq('BUY_FILL')][['time','symbol','signal_date']].copy()
    buy['trade_date']=pd.to_datetime(buy.signal_date)
    observed=window.merge(buy.rename(columns={'time':'entry'}),on=['entry','symbol'],validate='one_to_one')
    observed=observed.merge(scores[['trade_date','symbol','long_probability','SL10_risk','SL10_threshold','SL10_available']],
        on=['trade_date','symbol'],validate='many_to_one')
    if len(observed)!=len(window):raise ValueError('Missing actual-entry score lineage')
    if not (pd.to_datetime(observed.SL10_available).lt(observed.trade_date)).all():raise ValueError('Future SL10 model')
    observed.to_csv(ROOT/'actual-entry-scores.csv',index=False)
    span=m[m.timestamp.gt(a)&m.timestamp.le(b)]
    same=int((window.stop&window.same_session).sum());later=int((window.stop&~window.same_session).sum())
    summary=dict(status='ACCOUNTING_RECONCILED_RESEARCH_ONLY',daily_start=str(start.date()),daily_end=str(end.date()),
        daily_peak_equity=float(equity[start]),daily_trough_equity=float(equity[end]),capital_loss=delta,
        daily_drawdown_pct=100*delta/equity[start],intraday_peak_time=str(m.loc[ip,'timestamp']),
        intraday_trough_time=str(m.loc[it,'timestamp']),intraday_peak_equity=float(m.loc[ip,'equity']),
        intraday_trough_equity=float(m.loc[it,'equity']),intraday_max_drawdown_pct=100*float(dd[it]),
        closed_trades=len(window),win_pct=100*window.pnl.gt(0).mean(),realized_pnl=float(window.pnl.sum()),
        stop_count=int(window.stop.sum()),same_session_stops=same,later_session_stops=later,
        stop_gap_count=len(gap_checks),session_open_gap_count=sum(g['at_session_open'] for g in gap_checks),
        stop_gap_pnl=float(window.loc[window.exit_reason.eq('STOP_GAP'),'pnl'].sum()),
        average_gross_equity_pct=100*float((span.gross/span.equity).mean()),financing=financing,
        symbol_mark_to_market_pnl=float(attributed.period_pnl.sum()),accounting_residual=float(residual),
        top5_loss_symbols=attributed.nsmallest(5,'period_pnl').reset_index().to_dict('records'),
        gap_price_internal_consistency=True,independent_provider_price_check=False,
        strict_pit=False,full_live_parity=False,SQL_reads=0,provider_calls=0,production_changes=False)
    atomic_json(ROOT/'summary.json',summary)
    frozen=[out/n for n in ['configuration.json','report.json','trades.csv','events.csv','equity-daily.csv','equity-5m.parquet']]
    frozen += [FULL/(n+'.parquet') for n in ['open','close','actions','sectors']]
    frozen += [SOURCE/'variants/SL10/signals.parquet',Path(__file__)]
    atomic_json(ROOT/'sources.json',{str(p):digest(p) for p in frozen})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(13,9),gridspec_kw={'height_ratios':[2,1]})
    pd.concat(curves,axis=1).plot(ax=axes[0]);axes[0].set_ylabel('Base 100 au 6 novembre 2024')
    axes[0].set_title('B + anti-SL dix séances — audit de la baisse fin 2024 / début 2025')
    loss=attributed.nsmallest(10,'period_pnl').period_pnl.sort_values(ascending=False)
    loss.plot.barh(ax=axes[1],color='#cb4545');axes[1].set_xlabel('Contribution à la variation du capital ($)')
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'drawdown-audit.png',dpi=150);plt.close(fig)
    text=['# Audit de la baisse B + anti-SL10 TOP10 fin 2024 / début 2025','',
        f"Drawdown intraday : {summary['intraday_max_drawdown_pct']:.2f} %, de {summary['intraday_peak_time']} à {summary['intraday_trough_time']}.",
        f"Attribution distincte en clôture : {start.date()} → {end.date()}, {equity[start]:.2f} $ → {equity[end]:.2f} $, soit {delta:.2f} $ ({summary['daily_drawdown_pct']:.2f} %).",
        f"{len(window)} trades clôturés, {summary['win_pct']:.2f} % gagnants ; {summary['stop_count']} stops dont {same} pendant la séance d'entrée et {later} plus tard. "
        f"{len(gap_checks)} stops sur gap : {summary['stop_gap_pnl']:.2f} $ de PnL total de ces trades, pas une attribution indépendante des autres pertes.",
        f"Exposition brute/capital moyenne intraday de la fenêtre : {summary['average_gross_equity_pct']:.2f} %. Financement : {financing:.6f} $. "
        f"Résidu de rapprochement des flux, marques et dividendes : {residual:.10f} $.",
        '', 'Le modèle anti-SL prédit un SL5 pendant la première séance seulement. Dix séances décrit son historique de features, pas dix séances protégées contre les stops. '
        'Il ne garantit ni une absence de gap après la première séance, ni un rendement positif à H10. Les scores sont des estimations non garanties.',
        'La règle SL5 est un seuil de déclenchement ; une ouverture sous ce seuil est exécutée au cours disponible, donc une perte supérieure à 5 % est possible. '
        'Le portefeuille continue à prendre de nouvelles entrées : aucun B4/DD, régime ou budget de volatilité ne protège ce témoin.',
        '', 'Les PnL des trades clôturés ne sont pas la variation de capital : celle-ci inclut les positions détenues aux deux bornes. '
        'symbol-attribution.csv rapproche exactement les deux. Les secteurs sont ceux du référentiel contemporain, sans garantie historique PIT.',
        'Les gaps de début de séance sont comparés aux ouvertures journalières et aux impressions 5 minutes disponibles ; '
        'les gaps intraday aux seules ouvertures des bougies 5 minutes correspondantes. Cela contrôle la cohérence interne, '
        'pas une confirmation indépendante par un autre fournisseur. Couverture intraday partielle, repli OHLC, prix révisés, aucune certification live.',
        '', '## Comparaison sur la même fenêtre', '', '| Cas | Variation de capital | DD clôture dans la fenêtre | Taux gagnant des sorties |',
        '| --- | ---: | ---: | ---: |']
    for r in comparisons:
        text.append(f"| {r['case']} | {r['window_return_pct']:.2f} % | {r['window_dd_pct']:.2f} % | {r.get('win_pct',float('nan')):.2f} % |")
    message='\n'.join(text)+'\n';(ROOT/'audit.md').write_text(message,encoding='utf-8')
    Path('doc/ml/q051_b_sl10_drawdown_audit_20261117.md').write_text(message+'\nArchives : `'+str(ROOT)+'`.\n',encoding='utf-8')
    marker='<!-- Q051_B_SL10_DRAWDOWN_AUDIT_20261117 -->'
    doc=Path('doc/ml/experiences_done.md')
    if marker not in doc.read_text(encoding='utf-8'):
        with doc.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message+'\nArchives : `'+str(ROOT)+'`.\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
