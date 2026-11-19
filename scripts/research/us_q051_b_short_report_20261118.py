"""Independent audit and comparable close-to-close results for SHORT B29."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_q051_b_short_20261118 import ROOT, read
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def curve_metrics(curve, opening=4000.):
    value = pd.Series(curve, dtype=float)
    full = pd.concat([pd.Series([opening]), value.reset_index(drop=True)], ignore_index=True)
    return dict(final_equity=float(value.iloc[-1]), return_pct=float(100*(value.iloc[-1]/opening-1)),
        daily_close_dd_pct=float(100*(full/full.cummax()-1).min()))


def main():
    plan = read(ROOT/'protocol.json');short = read(ROOT/'report.json')
    chosen = pd.read_parquet(ROOT/'signals.parquet')
    if (not chosen.short_probability.gt(.5).all() or not chosen.short_auc.ge(.5).all()
            or not pd.to_datetime(chosen.short_available).lt(chosen.date).all()
            or not chosen.oracle_rank.le(179).all() or not chosen.short_rank.le(10).all()
            or chosen.groupby('date').size().gt(10).any() or not chosen.side.eq('short').all()
            or chosen.duplicated(['date','symbol']).any()):
        raise ValueError('Invalid annual SHORT selection')
    models = [];skips = []
    for task in plan['tasks']:
        folder = ROOT/'jobs'/task['key'];done = read(folder/'done.json')
        for name, expected in done['outputs'].items():
            if digest(folder/name) != expected:
                raise ValueError('Changed completed training record')
        records = read(folder/'models.json');skips.extend(records['skipped'])
        for record in records['models']:
            year = record['model_year']
            if (digest(Path(record['file'])) != record['sha256'] or record['features'] != plan['features']
                    or not pd.Timestamp(record['fit_available_max']) < pd.Timestamp(year-1,1,1)
                    or not pd.Timestamp(record['available']) < pd.Timestamp(year,1,1)):
                raise ValueError('Invalid model/future availability')
            models.append(dict(entry_year=task['year'], **record))
    for year in range(2021,2027):
        oracle = pd.read_parquet(Path('artifacts/research/us_q051_feature_groups/20261116-lot1/years')/str(year)/'oracle.parquet')
        if not pd.to_datetime(oracle.model_available_date).lt(pd.to_datetime(oracle.date)).all():
            raise ValueError('Noncausal frozen annual Oracle')
    atomic_json(ROOT/'short-models.json', dict(models=models, skipped=skips))

    equity = pd.read_csv(ROOT/'equity-daily.csv', index_col='date', parse_dates=True).equity
    trades = pd.read_csv(ROOT/'trades.csv');entries = pd.read_csv(ROOT/'entries.csv')
    if not trades.side.eq('sell').all():
        raise ValueError('LONG trade in SHORT-only campaign')
    if (entries.quantity*entries.entry_price > entries.equity_before*.2+1e-7).any():
        raise ValueError('Opening per-stock cap exceeded')
    if (entries.gross_before+entries.quantity*entries.entry_price > entries.equity_before+1e-7).any():
        raise ValueError('Opening gross1x cap exceeded')
    selected_keys = set(zip(pd.to_datetime(chosen.date).dt.date, chosen.symbol))
    calendar = pd.read_parquet('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs/open.parquet').index
    position = {d.date(): i for i,d in enumerate(calendar)}
    for row in entries.itertuples():
        signal, entry = pd.Timestamp(row.signal_date).date(),pd.Timestamp(row.entry_date).date()
        if (signal,row.symbol) not in selected_keys or position[entry] != position[signal]+1:
            raise ValueError('Entry outside selected signal or J+1')
    for trade in trades.itertuples():
        start = pd.Timestamp(trade.entry_date).date();end = pd.Timestamp(trade.exit_date).date()
        expected = trade.quantity*(trade.entry_price-trade.exit_price)-trade.entry_fees-trade.exit_fees+trade.dividends-trade.borrow_fees
        if abs(expected-trade.pnl) > 1e-7:
            raise ValueError('Independent SHORT trade accounting failed')
        if trade.exit_reason == 'HORIZON_OPEN' and position[end]-position[start] != 10:
            raise ValueError('SHORT horizon is not open11')
        if trade.exit_reason == 'STOP' and abs(trade.exit_price-round(trade.entry_price*1.05,2)) > 1e-7:
            raise ValueError('Incorrect initial SHORT stop')

    # Price reserves are inherited from the reviewed reference market tape.
    reserves = []
    from scripts.research.us_h10_price_readiness import RESERVED
    windows = []
    for trade in trades.itertuples():
        windows.append(dict(symbol=trade.symbol, start=pd.Timestamp(trade.entry_date).date(), end=pd.Timestamp(trade.exit_date).date()))
    closed_campaigns = set(trades.campaign_id)
    for entry in entries.itertuples():
        if entry.campaign_id not in closed_campaigns:
            windows.append(dict(symbol=entry.symbol, start=pd.Timestamp(entry.entry_date).date(), end=equity.index[-1].date()))
    for window in windows:
        reserve = RESERVED.get(window['symbol'])
        if reserve and window['end'] >= pd.Timestamp(reserve['start']).date():
            reserves.append(dict(**window, reason=reserve['reason']))
    pd.DataFrame(reserves, columns=['symbol','start','end','reason']).to_csv(ROOT/'price-basis-reserves.csv', index=False)

    parent = Path('artifacts/research/us_q051_b_early_sl/20261116-v1/cases')
    curves = pd.DataFrame({'B SHORT seul': equity})
    comparisons = [];annual = []
    for name,folder in [('B LONG témoin','CONTROL'),('B LONG + anti-SL témoin','SL10')]:
        nav = pd.read_csv(parent/folder/'result/equity-daily.csv', index_col=0, parse_dates=True).equity.reindex(equity.index)
        curves[name] = nav
        t = pd.read_csv(parent/folder/'result/trades.csv')
        comparisons.append(dict(case=name, **curve_metrics(nav), closed_trades=len(t), win_pct=100*t.pnl.gt(0).mean()))
    comparison = dict(case='B SHORT seul', **curve_metrics(equity), closed_trades=len(trades), win_pct=100*trades.pnl.gt(0).mean(),
        winning_trades=int(trades.pnl.gt(0).sum()), losing_trades=int(trades.pnl.lt(0).sum()),
        winning_pnl=float(trades.loc[trades.pnl.gt(0),'pnl'].sum()),
        losing_pnl=float(trades.loc[trades.pnl.lt(0),'pnl'].sum()),
        average_winner_holding_days=float(trades.loc[trades.pnl.gt(0),'holding_days'].mean()),
        average_loser_holding_days=float(trades.loc[trades.pnl.lt(0),'holding_days'].mean()),
        average_win=float(trades.loc[trades.pnl.gt(0),'pnl'].mean()), average_loss=float(trades.loc[trades.pnl.lt(0),'pnl'].mean()),
        average_win_return_pct=float(100*trades.loc[trades.pnl.gt(0),'return_pct'].mean()),
        average_loss_return_pct=float(100*trades.loc[trades.pnl.lt(0),'return_pct'].mean()),
        profit_factor=float(trades.loc[trades.pnl.gt(0),'pnl'].sum()/-trades.loc[trades.pnl.lt(0),'pnl'].sum()))
    comparisons.append(comparison)
    spy = pd.read_parquet('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs/close.parquet', columns=['SPY']).SPY
    seed = spy.loc[:'2020-12-31'].iloc[-1]
    curves['SPY prix seuls'] = spy.reindex(curves.index)/seed*4000.
    for name in curves:
        opening = 4000.
        for year,group in curves[name].groupby(curves.index.year):
            annual.append(dict(case=name, year=year, initial_equity=opening, **curve_metrics(group,opening)))
            opening = float(group.iloc[-1])
    pd.DataFrame(comparisons).to_csv(ROOT/'comparison.csv', index=False)
    pd.DataFrame(annual).to_csv(ROOT/'annual-comparison.csv', index=False)
    annual_trades = trades.groupby(pd.to_datetime(trades.exit_date, utc=True).dt.year).agg(
        closed_trades=('pnl','size'), winning_trades=('pnl',lambda v: int(v.gt(0).sum())),
        win_pct=('pnl',lambda v: float(100*v.gt(0).mean())), realized_pnl=('pnl','sum'))
    annual_trades.to_csv(ROOT/'annual-short-trades.csv', index_label='exit_year')
    curves.to_csv(ROOT/'capital-curves.csv')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10})
    colors = {'B SHORT seul':'#bd3948','B LONG témoin':'#2356c8','B LONG + anti-SL témoin':'#19886f','SPY prix seuls':'#de8b22'}
    fig,(ax,dd) = plt.subplots(2,1,figsize=(12,7.2),sharex=True,gridspec_kw={'height_ratios':[2,1]},facecolor='#f7f9fc')
    for name in curves:
        a = curves[name]
        ax.plot(a.index,a,color=colors[name],label=name,linewidth=1.5)
        peak = a.cummax().clip(lower=4000.)
        dd.plot(a.index,100*(a/peak-1),color=colors[name],linewidth=1.)
    ax.axhline(4000,color='#94a3b8',linestyle='--',linewidth=.8)
    ax.set_ylabel('Capital à la clôture ($)');dd.set_ylabel('DD de clôture (%)')
    for plot in [ax,dd]:plot.grid(alpha=.18);plot.spines[['top','right']].set_visible(False)
    ax.legend(loc='upper left',ncol=2,frameon=False)
    fig.suptitle('B SHORT seul face aux témoins LONG — 2021 au 1er octobre 2026',fontweight='bold',fontsize=15)
    fig.text(.08,.025,'4 000 $ continus ; SL5/open11 ; SHORT OHLC journalier, emprunt supposé 3 %/an.\n'
        'DD de clôture pour toutes les courbes ; pas de locates historiques certifiés. SPY sans dividendes/frais.',fontsize=9,color='#475569')
    fig.subplots_adjust(left=.09,right=.97,top=.90,bottom=.14,hspace=.10)
    fig.savefig(ROOT/'capital-comparison.png',dpi=160);plt.close(fig)

    verdict = 'COMPLETED_EXPLORATORY_WITH_PRICE_RESERVES' if reserves else 'COMPLETED_EXPLORATORY_AUDITED'
    audit = dict(status=verdict, models=len(models), skipped_models=len(skips), chosen_signals=len(chosen),
        short_only=True, future_models_rejected=True, no_refill=True, opening_caps_validated=True,
        actual_entry_keys_and_Jplus1_validated=True, trade_accounting_validated=True,
        price_basis_reserves=len(reserves), dividend_inventory='Only frozen known events, not certified complete for every underlying',
        historical_borrow='Assumed availability and3%rate, not certified',
        tests='Focused SHORT ranking, account, clock and accounting tests', independent_holdout=False,
        production_changes=False, SQL_writes=0, provider_calls=0, broker_orders=0)
    atomic_json(ROOT/'validation.json',audit)
    atomic_json(ROOT/'final-status.json',dict(**audit,result=short,comparison=comparisons))
    print(json.dumps(dict(validation=audit,result=comparison),indent=2))


if __name__ == '__main__':
    main()
