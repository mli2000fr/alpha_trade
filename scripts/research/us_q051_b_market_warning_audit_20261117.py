"""Read-only warning audit on the exact B/B+SL10 accounts, not a new replay.

Features are observable at signal close J, before entry J+1. Fixed univariate
rules and two declared conjunctions; no threshold search, fitting or PnL curve
manufactured by subtracting rejected trades. Historical periods already seen.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_b_market_warning_audit/20261117-v2')
SOURCE=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
SWITCH=Path('artifacts/research/us_q051_b_spy_switch/20261117-v1')
GROUPS=Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
FULL=Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')
DOC=Path('doc/ml/q051_b_market_warning_audit_20261117.md')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def market_features(close):
    if close.index.has_duplicates or not close.index.is_monotonic_increasing:raise ValueError('Ambiguous price dates')
    p=close.where(close.gt(0));spy=p.SPY
    valid=p.notna().rolling(51,min_periods=51).sum().eq(51)
    sma50=p.rolling(50,min_periods=50).mean();ret20=p/p.shift(20)-1
    ret20=ret20.where(p.notna().rolling(21,min_periods=21).sum().eq(21))
    names=[s for s in p if s!='SPY'];eligible=valid[names]
    f=pd.DataFrame(index=p.index)
    f['spy_close']=spy;f['spy_sma50']=spy.rolling(50,min_periods=50).mean()
    f['spy_sma200']=spy.rolling(200,min_periods=200).mean();f['spy_ret20']=ret20.SPY
    f['spy_vol20']=spy.pct_change(fill_method=None).rolling(20,min_periods=20).std()*np.sqrt(252)
    f['spy_vol20_median126']=f.spy_vol20.rolling(126,min_periods=126).median()
    f['universe_eligible']=eligible.sum(axis=1)
    f['universe_breadth50']=p[names].gt(sma50[names]).where(eligible).sum(axis=1).div(f.universe_eligible.replace(0,np.nan))
    f.loc[f.universe_eligible.lt(.8*len(names)),'universe_breadth50']=np.nan
    return f,ret20


def pool_features(pool,returns):
    pool=pool.copy();pool.date=pd.to_datetime(pool.date)
    if pool.duplicated(['date','symbol']).any():raise ValueError('Duplicate pool membership')
    if not pd.to_datetime(pool.model_available_date).lt(pool.date).all():raise ValueError('Future Oracle model')
    i=returns.index.get_indexer(pool.date);j=returns.columns.get_indexer(pool.symbol)
    if min(i.min(),j.min())<0:raise ValueError('Frozen pool price columns missing')
    pool['past_ret20']=returns.to_numpy()[i,j]
    rows=[]
    for day,g in pool.groupby('date'):
        known=g.past_ret20.notna();qualified=known.mean()>=.9
        rows.append(dict(date=day,pool_count=len(g),pool_known=int(known.sum()),
            oracle_positive20=float(g.loc[known,'past_ret20'].gt(0).mean()) if qualified else np.nan,
            oracle_median_ret20=float(g.past_ret20.median()) if qualified else np.nan))
    return pd.DataFrame(rows).set_index('date')


def health_features(trades,equity):
    t=trades.copy();t['exit']=pd.to_datetime(t.exit_date,utc=True);t=t.sort_values('exit',kind='stable')
    times=t.exit.astype('int64').to_numpy();pnls=t.pnl.to_numpy(float);rows=[]
    for day in equity.index:
        stamp=day.tz_localize('America/New_York')+pd.Timedelta(hours=16)
        n=np.searchsorted(times,stamp.value,side='right');past=pnls[max(0,n-20):n]
        losses=-past[past<0].sum();gains=past[past>0].sum()
        pf=(gains/losses if losses else (np.inf if gains else np.nan)) if len(past)==20 else np.nan
        rows.append(dict(date=day,pf20=pf,last_closed_count=len(past),
            last_exit_available=str(t.iloc[n-1].exit) if n else None))
    f=pd.DataFrame(rows).set_index('date');f['strategy_ret20']=equity/equity.shift(20)-1
    f['strategy_dd63']=equity/equity.rolling(63,min_periods=63).max()-1
    return f


def below(series,limit):return series.lt(limit).astype('boolean').where(series.notna())


def warnings(f):
    out=pd.DataFrame(index=f.index)
    out['SPY_SMA50']=below(f.spy_close/f.spy_sma50,1)
    out['SPY_SMA200']=below(f.spy_close/f.spy_sma200,1)
    out['SPY_RET20_NEGATIVE']=below(f.spy_ret20,0)
    out['SPY_VOL_ABOVE_MEDIAN']=below(f.spy_vol20_median126/f.spy_vol20,1)
    out['UNIVERSE_BREADTH50_LT40']=below(f.universe_breadth50,.4)
    out['ORACLE_BREADTH20_LT50']=below(f.oracle_positive20,.5)
    out['ORACLE_RELATIVE20_NEGATIVE']=below(f.oracle_median_ret20-f.spy_ret20,0)
    out['STRATEGY_PF20_LT1']=below(f.pf20,1)
    out['STRATEGY_RET20_LT_MINUS5']=below(f.strategy_ret20,-.05)
    out['STRATEGY_DD63_GT10']=below(f.strategy_dd63,-.1)
    out['SPY50_AND_PF20']=out.SPY_SMA50&out.STRATEGY_PF20_LT1
    out['ORACLE_WEAK_AND_STRATEGY_WEAK']=out.ORACLE_BREADTH20_LT50&out.STRATEGY_RET20_LT_MINUS5
    return out


def measure(frame,flag):
    known=frame[flag].notna();a=frame.loc[known];selected=a[flag].astype(bool);t=a.loc[selected];rest=a.loc[~selected]
    gross_gains=a.loc[a.pnl.gt(0),'pnl'].sum();gross_losses=-a.loc[a.pnl.lt(0),'pnl'].sum()
    return dict(known_trades=len(a),unknown_trades=len(frame)-len(a),flagged_trades=len(t),
        flagged_symbols=t.symbol.nunique(),flagged_entry_dates=t.entry_day.nunique(),
        flagged_share_pct=100*len(t)/len(a) if len(a) else np.nan,
        flagged_win_pct=100*t.pnl.gt(0).mean(),other_win_pct=100*rest.pnl.gt(0).mean(),
        flagged_mean_net_return_pct=100*t.return_pct.mean(),other_mean_net_return_pct=100*rest.return_pct.mean(),
        flagged_minus_other_return_pp=100*(t.return_pct.mean()-rest.return_pct.mean()),
        flagged_realized_pnl=float(t.pnl.sum()),flagged_winning_pnl=float(t.loc[t.pnl.gt(0),'pnl'].sum()),
        flagged_losing_pnl=float(t.loc[t.pnl.lt(0),'pnl'].sum()),
        captured_loss_mass_pct=100*-t.loc[t.pnl.lt(0),'pnl'].sum()/gross_losses if gross_losses else np.nan,
        sacrificed_gain_mass_pct=100*t.loc[t.pnl.gt(0),'pnl'].sum()/gross_gains if gross_gains else np.nan)


def main():
    ROOT.mkdir(parents=True,exist_ok=False)
    declared=dict(target_entry_window=['2024-11-01','2025-06-30'],rules=12,threshold_search=False,
        scopes=['target','outside_target','all','entry_year'],outcome='actual accepted LONG trades, net fees, common H10 maturity',
        no_portfolio_counterfactual=True,no_training=True,SQL_reads=0,provider_calls=0,production_changes=False)
    atomic_json(ROOT/'protocol.json',declared)
    close=pd.read_parquet(FULL/'close.parquet');market,ret20=market_features(close)
    pools=pd.concat([pd.read_parquet(GROUPS/'years'/str(y)/'pool.parquet') for y in range(2021,2027)],ignore_index=True)
    pool=pool_features(pools,ret20);market=market.join(pool)
    market.to_parquet(ROOT/'market-features.parquet')
    # Recompute on historical prefixes; future alterations/rows cannot affect J.
    for day in ['2022-12-30','2024-10-31','2025-03-31']:
        short,_=market_features(close.loc[:day]);pd.testing.assert_frame_equal(short,market.loc[:day,short.columns])
    annual=pd.read_csv(SWITCH/'annual-comparison.csv')
    annual.pivot(index='year',columns='case',values='return_pct').to_csv(ROOT/'annual-switch-returns.csv')
    records=[];blocked=[];extrema=[];episodes=[];frames=[];healths={};references={}
    all_inputs=[FULL/'close.parquet']+[GROUPS/'years'/str(y)/'pool.parquet' for y in range(2021,2027)]
    calendar=close.index[(close.index>='2021-01-01')&(close.index<='2026-10-01')]
    for family,case in [('B','CONTROL'),('SL10','SL10')]:
        folder=SOURCE/'cases'/case/'result';t=pd.read_csv(folder/'trades.csv');e=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        h=health_features(t,e);healths[family]=h;context=market.join(h)
        for day in ['2022-12-30','2024-10-31','2025-03-31']:
            bound=pd.Timestamp(day).tz_localize('America/New_York')+pd.Timedelta(hours=16)
            historical=t[pd.to_datetime(t.exit_date,utc=True).le(bound)]
            pd.testing.assert_frame_equal(health_features(historical,e.loc[:day]),h.loc[:day])
        flags=warnings(context);context.join(flags).to_parquet(ROOT/(family+'-features-and-warnings.parquet'))
        entries=pd.to_datetime(pd.to_datetime(t.entry_date,utc=True).dt.tz_convert('America/New_York').dt.date)
        positions=calendar.get_indexer(entries)
        if (positions<0).any():raise ValueError('Entry outside audited calendar')
        mature=positions+10<len(calendar)
        t['entry_day']=entries;t['signal_date']=calendar.take(np.maximum(positions-1,0))
        # First entry uses the preceding exchange session from the actual BUY
        # receipt, not the first replay session or an invented previous weekday.
        ev=pd.read_csv(folder/'events.csv',low_memory=False);buys=ev[ev.event.eq('BUY_FILL')][['symbol','time','signal_date']]
        buys=buys.rename(columns={'time':'entry_date','signal_date':'actual_signal'});buys.actual_signal=pd.to_datetime(buys.actual_signal)
        t=t.merge(buys,on=['symbol','entry_date'],validate='one_to_one')
        t['signal_date']=t.actual_signal
        if not t.signal_date.lt(t.entry_day).all():raise ValueError('Signal not before entry')
        t['mature']=mature;t['family']=family;t['entry_year']=t.entry_day.dt.year
        t=t.join(context.join(flags),on='signal_date',rsuffix='_feature')
        t.to_parquet(ROOT/(family+'-actual-trade-context.parquet'),index=False)
        usable=t[t.mature].copy();frames.append(usable)
        usable['target']=usable.entry_day.between('2024-11-01','2025-06-30')
        for label,g in [('target',usable[usable.target]),('outside_target',usable[~usable.target]),('all',usable)]:
            for flag in flags:records.append(dict(family=family,scope=label,rule=flag,**measure(g,flag)))
        for year,g in usable.groupby('entry_year'):
            for flag in flags:records.append(dict(family=family,scope=str(year),rule=flag,**measure(g,flag)))
        for name in ['trades.csv','events.csv','equity-daily.csv','equity-5m.parquet']:all_inputs.append(folder/name)
        references[family]=e
    for family in ['B','SL10']:
        for window in [20,50,100]:
            case=f'{family}_MA{window}';folder=SWITCH/'cases'/case/'result'
            m=pd.read_parquet(folder/'equity-5m.parquet');d=m.equity/m.equity.cummax()-1;j=d.idxmin();i=m.loc[:j].equity.idxmax()
            extrema.append(dict(case=case,peak=str(m.loc[i,'timestamp']),trough=str(m.loc[j,'timestamp']),max_dd_pct=100*d[j]))
            x=pd.read_csv(folder/'active-budget-decisions.csv');x['year']=pd.to_datetime(x.time,utc=True).dt.year
            for year,g in x.groupby('year'):
                blocked.append(dict(case=case,year=int(year),budget_decisions=len(g),zero_quantity=int(g.final_quantity.eq(0).sum()),
                    zero_quantity_pct=100*g.final_quantity.eq(0).mean(),
                    median_existing_forecast_vol_pct=100*g.current_vol.median(),
                    median_native_quantity=float(g.native_quantity.median()),median_final_quantity=float(g.final_quantity.median())))
            states=pd.read_parquet(SWITCH/'inputs'/f'spy-states-MA{window}.parquet').loc['2020-12-31':'2026-09-30']
            start=None
            for day,row in states.iterrows():
                if row.active and start is None:start=day
                if not row.active and start is not None:
                    episodes.append(dict(case=case,signal_start=str(start.date()),signal_end=str(day.date()),open_at_end=False));start=None
            if start is not None:episodes.append(dict(case=case,signal_start=str(start.date()),signal_end=str(states.index[-1].date()),open_at_end=True))
            all_inputs += [folder/'active-budget-decisions.csv',folder/'equity-5m.parquet']
    stats=pd.DataFrame(records);stats.to_csv(ROOT/'warning-diagnostics.csv',index=False)
    pd.DataFrame(extrema).to_csv(ROOT/'switch-max-dd-dates.csv',index=False)
    pd.DataFrame(blocked).to_csv(ROOT/'budget-impact-by-year.csv',index=False)
    pd.DataFrame(episodes).to_csv(ROOT/'switch-episodes.csv',index=False)
    # Signal-calendar occurrence, independent of which trades passed cash/sizing.
    occurrence=[]
    for family,h in healths.items():
        f=market.join(h);w=warnings(f).loc['2021-01-01':'2026-09-30']
        target=w.index.to_series().between('2024-11-01','2025-06-30')
        for label,mask in [('target',target),('outside_target',~target)]:
            for rule in w:
                g=w.loc[mask,rule];first=g[g.fillna(False)].index.min()
                occurrence.append(dict(family=family,scope=label,rule=rule,known_days=int(g.notna().sum()),
                    flagged_days=int(g.fillna(False).sum()),flagged_pct=100*g.mean() if g.notna().any() else None,
                    first_flag=str(first.date()) if pd.notna(first) else None))
    pd.DataFrame(occurrence).to_csv(ROOT/'warning-calendar.csv',index=False)
    atomic_json(ROOT/'sources.json',{str(p):digest(p) for p in [*all_inputs,Path(__file__)]})
    atomic_json(ROOT/'validation.json',dict(status='PASS',market_prefix_checks=3,health_prefix_checks=6,
        real_entry_signal_receipts=True,common_maturity=True,threshold_search=False,new_replays=0,
        economic_counterfactual_estimated=False,strict_pit=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(15,13),sharex=True)
    span=slice('2024-08-01','2025-07-01');days=market.loc[span].index
    for name,e in references.items():
        g=e.reindex(days);(100*g/g.iloc[0]).plot(ax=axes[0],label=name)
    s=close.SPY.loc[span];(100*s/s.iloc[0]).plot(ax=axes[0],label='SPY prix seuls');axes[0].legend()
    market.loc[span,['universe_breadth50','oracle_positive20']].mul(100).plot(ax=axes[1])
    axes[1].axhline(40,color='grey',linestyle=':');axes[1].axhline(50,color='grey',linestyle='--');axes[1].set_ylabel('Titres favorables (%)')
    for name,h in healths.items():h.strategy_ret20.loc[span].mul(100).plot(ax=axes[2],label=name+' rendement20 passé')
    axes[2].axhline(-5,color='grey',linestyle=':');axes[2].legend();axes[2].set_ylabel('Rendement20 (%)')
    for window in [20,50,100]:
        f=pd.read_parquet(SWITCH/'inputs'/f'spy-states-MA{window}.parquet');f.active.loc[span].astype(int).mul(window/20).plot(ax=axes[3],label='Bascule MA'+str(window),drawstyle='steps-post')
    axes[3].legend();axes[3].set_yticks([]);axes[3].set_ylabel('Protection active')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Diagnostic observé à J — marché, pool Oracle et santé des deux stratégies');fig.tight_layout()
    fig.savefig(ROOT/'warning-context.png',dpi=145);plt.close(fig)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDIT',new_replays=0,training=0,rules=12,
        families=['B','SL10'],production_changes=False))
    print(stats[stats.scope.eq('target')][['family','rule','flagged_trades','flagged_realized_pnl','flagged_minus_other_return_pp','captured_loss_mass_pct','sacrificed_gain_mass_pct']].to_string(index=False))


if __name__=='__main__':main()
