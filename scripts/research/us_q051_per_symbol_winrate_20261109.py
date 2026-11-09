"""Recount existing Q051 trades, no new replay, model, SQL or provider request."""
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

SOURCES={
    'avec_per_symbol':Path('artifacts/research/us_winner_continuous_q051_q088/20261108-v2/cases/Q051_050'),
    'sans_per_symbol':Path('artifacts/research/us_winner_vol20_extensions/20261109-v1/cases/Q051_NO_PER'),
}
ROOT=Path('artifacts/research/us_q051_per_symbol_winrate/20261109-v1')


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def stats(frame):
    n=len(frame);pnl=pd.to_numeric(frame.pnl,errors='raise')
    if not np.isfinite(pnl).all():raise ValueError('Non-finite trade PnL')
    wins=int(pnl.gt(0).sum());losses=int(pnl.lt(0).sum());flat=int(pnl.eq(0).sum())
    return dict(trades=n,winners=wins,losers=losses,flat=flat,
        win_rate_pct=100*wins/n if n else None,loss_rate_pct=100*losses/n if n else None,
        realized_pnl_USD=float(pnl.sum()),symbols=int(frame.symbol.nunique()))


def run(root=ROOT):
    root.mkdir(parents=True,exist_ok=False)
    configs={k:read(folder/'result/configuration.json')['portfolio'] for k,folder in SOURCES.items()}
    if configs['avec_per_symbol']!=configs['sans_per_symbol']:
        raise ValueError('Portfolio configurations differ; cannot call this matched Q051 settings')
    protocols={k:read(folder/'protocol.json') for k,folder in SOURCES.items()}
    models={k:{year:item['batch_id'] for year,item in p['annual_models'].items()} for k,p in protocols.items()}
    if models['avec_per_symbol']!=models['sans_per_symbol']:raise ValueError('Annual models differ')
    rows=[];symbol_year=[];symbol_total=[];totals={};hashes={}
    for variant,folder in SOURCES.items():
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Incomplete source run')
        trades=pd.read_csv(folder/'result/trades.csv');annual=pd.read_csv(folder/'result/annual-summary.csv')
        trades['entry_date']=pd.to_datetime(trades.entry_date,utc=True)
        trades['exit_date']=pd.to_datetime(trades.exit_date,utc=True)
        trades['year']=trades.exit_date.dt.tz_convert('America/New_York').dt.year
        if not trades.side.eq('buy').all():raise ValueError('Expected LONG-only source')
        report=read(folder/'result/report.json');total=stats(trades)
        for field,key in [('trades','closed_lot_trades'),('winners','winners'),('losers','losers'),('win_rate_pct','win_pct')]:
            if not np.isclose(total[field],report[key],rtol=0,atol=1e-10):raise ValueError('Global recount mismatch '+field)
        total.update(final_equity=report['final_equity'],return_pct=report['return_pct'],
            max_drawdown_pct=report['max_drawdown_pct'],
            trades_crossing_years=int(trades.entry_date.dt.year.ne(trades.exit_date.dt.year).sum()))
        totals[variant]=total
        for year,group in trades.groupby('year'):
            computed=stats(group);saved=annual[annual.year.eq(year)]
            if len(saved)!=1:raise ValueError('Missing annual source')
            saved=saved.iloc[0]
            for field,key in [('trades','closed_lot_trades'),('winners','winners'),('losers','losers'),('win_rate_pct','win_pct')]:
                if not np.isclose(computed[field],saved[key],rtol=0,atol=1e-10):raise ValueError('Annual recount mismatch')
            if saved.model!=models[variant][str(year)]:raise ValueError('Annual model mismatch')
            rows.append(dict(variant=variant,year=int(year),**computed,return_pct=saved.return_pct,
                annual_max_drawdown_pct=saved.max_drawdown_pct,model=saved.model))
        for (year,symbol),group in trades.groupby(['year','symbol']):
            s=stats(group);symbol_year.append(dict(variant=variant,year=int(year),symbol=symbol,**s,small_sample_lt10=s['trades']<10))
        for symbol,group in trades.groupby('symbol'):
            s=stats(group);symbol_total.append(dict(variant=variant,symbol=symbol,**s,small_sample_lt10=s['trades']<10))
        for name in ['protocol.json','result/configuration.json','result/trades.csv','result/annual-summary.csv','result/report.json']:
            hashes[str(folder/name)]=digest(folder/name)
    frame=pd.DataFrame(rows);frame.to_csv(root/'annual-by-variant.csv',index=False)
    paired=frame[frame.variant.eq('avec_per_symbol')].drop(columns='variant').merge(
        frame[frame.variant.eq('sans_per_symbol')].drop(columns='variant'),on='year',suffixes=('_with','_without'),validate='one_to_one')
    paired['win_rate_lift_pp']=paired.win_rate_pct_with-paired.win_rate_pct_without
    paired.to_csv(root/'annual-comparison.csv',index=False)
    pd.DataFrame(symbol_year).to_csv(root/'per-symbol-by-year.csv',index=False)
    pd.DataFrame(symbol_total).to_csv(root/'per-symbol-overall.csv',index=False)
    atomic_json(root/'report.json',dict(status='COMPLETED_EXISTING_TRADES_RECOUNT',
        start='2021-01-01',end='2026-10-01',initial_equity=4000.,annual_reset=False,
        portfolio_configurations_identical=True,annual_models_identical=True,
        annual_grouping='Year of actual exit, America/New_York; open holdings not counted as closed trades',
        winner_definition='Trade PnL > 0, including buy/sell fees and allocated dividends; portfolio financing not allocated per trade',
        with_selection='TOP10% Oracle (179) -> TOP5 LONG per-symbol -> score > .50 and calibration AUC >= .50 -> risk -> Winner',
        without_selection='TOP10% Oracle (179), original amplitude order -> risk -> Winner, no LONG probability/AUC/TOP5 selection',
        interpretation='Population/order/position occupancy/capital path also change; not an isolated classification accuracy test',
        totals=totals,annual=paired.to_dict('records'),sources=hashes,source_code_sha256=digest(Path(__file__)),
        limitations=['Both original runs have incomplete 5m coverage and daily OHLC fallback',
            'Small per-symbol samples and repeated trades; not independent evidence of predictability',
            'Continuous portfolio with positions, capital and risk carried between years, not annual standalone restarts'],
        new_replays=0,SQL_calls=0,provider_calls=0,orders=0,finished_at_utc=datetime.now(timezone.utc).isoformat()))
    print(paired[['year','win_rate_pct_with','winners_with','trades_with','win_rate_pct_without','winners_without','trades_without','win_rate_lift_pp']].to_string(index=False))
    print(json.dumps(totals,ensure_ascii=False))


if __name__=='__main__':run()
