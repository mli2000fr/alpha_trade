"""Audit native SHORT scores and daily account for the selected current batch."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_b_short_current_batch_20261118 import ROOT,MODEL,BATCH,TAPE,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_b_short_report_20261118 import curve_metrics


def main():
    plan=read(ROOT/'protocol.json');report=read(ROOT/'report.json')
    amendment=read(ROOT/'replay-amendment.json')
    if (digest(ROOT/'coordinator-before-volume-recovery.py')!=plan['source_sha256']
        or amendment['source_before_sha256']!=plan['source_sha256']
        or digest(Path('scripts/research/us_b_short_current_batch_20261118.py'))!=amendment['source_after_sha256']
        or digest(ROOT/'volume-recovery.json')!=amendment['recovery_sha256']
        or digest(ROOT/'price-recovery.json')!=amendment['price_recovery_sha256']):
        raise ValueError('Changed volume-recovery amendment')
    for file,checksum in plan['sources'].items():
        if digest(Path(file)) != checksum:raise ValueError('Changed native model inputs')
    for name in ['oracle','pool']:
        if digest(ROOT/(name+'.parquet')) != plan[name+'_sha256']:raise ValueError('Changed Oracle scores')
    oracle=pd.read_parquet(ROOT/'oracle.parquet');chosen=pd.read_parquet(ROOT/'signals.parquet')
    if not pd.to_datetime(oracle.model_available_date).lt(oracle.date).all():raise ValueError('Future Oracle')
    if (not chosen.short_probability.gt(.5).all() or not chosen.short_auc.ge(.5).all()
        or not chosen.oracle_rank.le(179).all() or not chosen.short_rank.le(10).all()
        or not pd.to_datetime(chosen.short_available).lt(chosen.date).all()
        or chosen.groupby('date').size().gt(10).any() or chosen.duplicated(['date','symbol']).any()):
        raise ValueError('Invalid current SHORT selection')
    manifest=read(MODEL/'directional/manifest.json');probabilities=[];native=[];used=[]
    for key in plan['jobs']:
        folder=ROOT/'jobs'/key
        for name,checksum in read(folder/'done.json')['outputs'].items():
            if digest(folder/name) != checksum:raise ValueError('Changed completed inference')
        probabilities.append(pd.read_parquet(folder/'probabilities.parquet'))
        used.extend(read(folder/'models.json')['models'])
    probabilities=pd.concat([p for p in probabilities if not p.empty],ignore_index=True)
    for record in used:
        if (digest(MODEL/record['file']) != record['sha256'] or record['side']!='short'
            or not pd.Timestamp(record['fit_available_max'])<pd.Timestamp(record['year']-1,1,1)
            or not pd.Timestamp(record['available'])<pd.Timestamp(record['year'],1,1)):
            raise ValueError('Changed/noncausal native SHORT model')
    # OOS files are a diagnostic comparator only, never an eligibility source.
    for file in manifest['oos_files']:
        path=MODEL/file['path']
        if digest(path) != file['sha256']:raise ValueError('Changed native OOS evidence')
        f=pd.read_parquet(path);native.append(f[f.side.eq('short')])
    native=pd.concat(native,ignore_index=True)
    paired=probabilities.merge(native,on=['date','symbol'],validate='one_to_one')
    if (paired.empty or not np.allclose(paired.short_probability,paired.probability,atol=1e-8,rtol=0)
        or not paired.short_model_sha256.eq(paired.model_sha256).all()):
        raise ValueError('Reconstructed native SHORT predictions differ from batch evidence')
    paired['mature']=pd.to_datetime(paired.available).le('2026-10-01')
    from modelFactory.oracle_path.directional_metrics import classification_metrics
    metrics=[]
    for year,group in paired[paired.mature].groupby(paired.date.dt.year):
        metrics.append(dict(year=int(year),**classification_metrics(group.label,group.short_probability)))
    pd.DataFrame(metrics).to_csv(ROOT/'classification.csv',index=False)
    trades=pd.read_csv(ROOT/'trades.csv');entries=pd.read_csv(ROOT/'entries.csv')
    equity=pd.read_csv(ROOT/'equity-daily.csv',index_col='date',parse_dates=True).equity
    calendar=pd.read_parquet(TAPE/'open.parquet',columns=['SPY']).index
    position={day.date():i for i,day in enumerate(calendar)}
    keys=set(zip(chosen.date.dt.date,chosen.symbol))
    for entry in entries.itertuples():
        signal=pd.Timestamp(entry.signal_date).date();day=pd.Timestamp(entry.entry_date).date()
        if (signal,entry.symbol) not in keys or position[day]-position[signal]!=1:raise ValueError('Invalid J+1 entry')
        if (entry.quantity*entry.entry_price>entry.equity_before*.2+1e-7
            or entry.gross_before+entry.quantity*entry.entry_price>entry.equity_before+1e-7):
            raise ValueError('Entry exceeds fixed reference risk caps')
    for trade in trades.itertuples():
        expected=trade.quantity*(trade.entry_price-trade.exit_price)-trade.entry_fees-trade.exit_fees+trade.dividends-trade.borrow_fees
        if trade.side!='sell' or abs(expected-trade.pnl)>1e-7:raise ValueError('SHORT ledger/trade error')
        if trade.exit_reason=='HORIZON_OPEN' and position[pd.Timestamp(trade.exit_date).date()]-position[pd.Timestamp(trade.entry_date).date()]!=10:
            raise ValueError('Incorrect SHORT horizon')
    from scripts.research.us_h10_price_readiness import RESERVED
    reserves=[];closed=set(trades.campaign_id)
    windows=[dict(symbol=t.symbol,start=str(pd.Timestamp(t.entry_date).date()),end=str(pd.Timestamp(t.exit_date).date())) for t in trades.itertuples()]
    windows.extend(dict(symbol=e.symbol,start=str(pd.Timestamp(e.entry_date).date()),end=str(equity.index[-1].date())) for e in entries.itertuples() if e.campaign_id not in closed)
    for window in windows:
        reserve=RESERVED.get(window['symbol'])
        if reserve and pd.Timestamp(window['end'])>=pd.Timestamp(reserve['start']):reserves.append(dict(**window,reason=reserve['reason']))
    pd.DataFrame(reserves,columns=['symbol','start','end','reason']).to_csv(ROOT/'price-basis-reserves.csv',index=False)
    annual=[];opening=4000.
    for year,group in equity.groupby(equity.index.year):
        t=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)]
        annual.append(dict(year=int(year),initial_equity=opening,**curve_metrics(group,opening),closed_trades=len(t),win_pct=float(100*t.pnl.gt(0).mean())))
        opening=float(group.iloc[-1])
    pd.DataFrame(annual).to_csv(ROOT/'annual.csv',index=False)
    spy=pd.read_parquet(TAPE/'close.parquet',columns=['SPY']).SPY
    curves=pd.DataFrame({'SHORT — batch actuel':equity,'SPY — prix seuls':spy.reindex(equity.index)/spy.loc[:'2024-12-31'].iloc[-1]*4000})
    curves.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,dd)=plt.subplots(2,1,figsize=(11,6.5),sharex=True,gridspec_kw={'height_ratios':[2,1]},facecolor='#f7f9fc')
    for (name,values),color in zip(curves.items(),['#bc3546','#da8a25']):
        ax.plot(values.index,values,color=color,label=name,lw=1.6)
        dd.plot(values.index,100*(values/values.cummax().clip(lower=4000)-1),color=color,lw=1.2)
    ax.set_ylabel('Capital à la clôture ($)');dd.set_ylabel('DD de clôture (%)');ax.legend(frameon=False)
    ax.axhline(4000,color='#94a3b8',ls='--',lw=.8)
    for a in [ax,dd]:a.grid(alpha=.2);a.spines[['top','right']].set_visible(False)
    fig.suptitle('SHORT seul — batch 2f6a31 — 2025 au 1er octobre 2026',fontweight='bold',fontsize=14)
    fig.text(.09,.02,'4 000 $ continus ; TOP179 Oracle → TOP10 SHORT ; SL5 / open11 ; frais 8 bps/côté.\n'
        'Emprunt supposé 3 %/an, locates non certifiés ; OHLC journalier. SPY sans dividendes ni frais.',fontsize=9,color='#475569')
    fig.subplots_adjust(top=.90,bottom=.16,left=.10,right=.97,hspace=.12);fig.savefig(ROOT/'capital-comparison.png',dpi=160);plt.close(fig)
    audit=dict(status='COMPLETED_EXPLORATORY_WITH_PRICE_RESERVES' if reserves else 'COMPLETED_EXPLORATORY_AUDITED',
        batch_id=BATCH,trained_new_models=0,native_short_heads_used=len(used),OOF_matching_probabilities=len(paired),
        native_prediction_max_difference=float((paired.short_probability-paired.probability).abs().max()),
        causal_folds_and_heads=True,trade_accounting_and_caps=True,price_basis_reserves=len(reserves),
        corporate_actions_not_certified_complete=True,borrow_not_certified=True,independent_holdout=False,
        coverage_min_pct=plan['coverage_min_pct'],SQL_writes=0,provider_calls=0,broker_orders=0,production_changes=False)
    audit.update(SQL_reads_for_recovery=amendment['SQL_read_queries'],
        volume_only_recovery='GWRE2026-06-18,78 existing SIP bars, unchanged OHLC/model inputs',
        price_recovery='LBRDK2026-07-20/21,78 existing SIP bars/session; input models/scores unchanged')
    atomic_json(ROOT/'validation.json',audit);atomic_json(ROOT/'final-status.json',dict(**audit,result=report,annual=annual))
    atomic_json(ROOT/'progress.json',dict(status=audit['status'],result=report))
    print(json.dumps(dict(validation=audit,result=report,annual=annual),indent=2))


if __name__=='__main__':main()
