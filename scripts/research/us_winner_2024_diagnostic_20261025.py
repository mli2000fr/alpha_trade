"""Read-only attribution and TOP20 path directions; no replay or provider calls."""
from pathlib import Path
import json
import hashlib

import numpy as np
import pandas as pd

ROOT=Path('artifacts/research/us_winner_2024_diagnostic/20261025-v1')
INPUTS=Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
CASES={
    'SL5':Path('artifacts/research/us_winner_min70_4000/20261025-v1/cases/FIXED_REFERENCE_MIN70'),
    'SL1':Path('artifacts/research/us_winner_sl1_min70/20261025-v1/cases/FIXED_SL1_H20_MIN70'),
}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def excursion(entry,highs,lows):
    if entry<=0 or not np.isfinite(entry):raise ValueError('Invalid entry')
    values=np.r_[highs,lows]
    if not np.isfinite(values).all() or (values<=0).any():raise ValueError('Unqualified window')
    up=max(0.,float(max(highs)/entry-1))
    down=min(0.,float(min(lows)/entry-1))
    direction='UP' if up>abs(down)+1e-12 else 'DOWN' if abs(down)>up+1e-12 else 'TIE'
    return dict(max_up_pct=up*100,max_down_pct=down*100,dominant_direction=direction)


def main():
    from scripts.research import us_winner_monthly_inputs_20261024 as inputs
    tape=inputs.Tape(INPUTS)  # verifies the existing input manifest; no SQL path
    data={};sources={}
    for label,folder in CASES.items():
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        for name,expected in report['files'].items():
            path=folder/name
            if digest(path)!=expected:raise ValueError('Changed case output: '+str(path))
            sources[str(path)]=expected
        sources[str(folder/'report.json')]=digest(folder/'report.json')
        trades=pd.read_parquet(folder/'trades.parquet')
        trades['exit_year']=pd.to_datetime(trades.exit_date,utc=True).dt.tz_convert('America/New_York').dt.year
        stats=[]
        for year,group in trades.groupby('exit_year'):
            wins=group[group.pnl>0];losses=group[group.pnl<0]
            stats.append(dict(year=int(year),closed=len(group),winning=len(wins),losing=len(losses),
                win_pct=100*len(wins)/len(group),gains=float(wins.pnl.sum()),losses=float(losses.pnl.sum()),
                net_closed=float(group.pnl.sum()),average_win=float(wins.pnl.mean()),average_loss=float(losses.pnl.mean()),
                average_win_return_pct=float(wins.return_pct.mean()*100),
                average_loss_return_pct=float(losses.return_pct.mean()*100),
                profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()),
                exit_reasons=group.exit_reason.value_counts().to_dict()))
        q=trades[trades.exit_year==2024]
        curve=pd.read_parquet(folder/'equity-daily.parquet').equity
        curve.index=pd.to_datetime(curve.index)
        monthly=(curve.resample('ME').last().pct_change()*100).loc['2024']
        data[label]=dict(closed_trades_by_exit_year=stats,portfolio_annual_mark_to_market=report['annual'],
            monthly2024={str(k.date()):float(v) for k,v in monthly.items()},
            worst_symbols_net_closed_2024=q.groupby('symbol').pnl.sum().sort_values().head(10).to_dict(),
            best_symbols_net_closed_2024=q.groupby('symbol').pnl.sum().sort_values(ascending=False).head(5).to_dict())
    days=sorted(d for d in tape.schedule if d<=inputs.END)
    positions={d:i for i,d in enumerate(days)}
    windows=[];excluded={}
    for row in tape.cohort.itertuples():
        day=pd.Timestamp(row.date).date()
        if day.year not in [2023,2024]:continue
        reason=None;i=positions.get(day)
        window=days[i+1:i+21] if i is not None else []
        if not row.selected:reason='ORIGINAL_COVERAGE_OR_ACTION_EXCLUSION'
        elif len(window)!=20:reason='TWENTY_FUTURE_SESSIONS_NOT_ARCHIVED'
        else:
            idx=pd.to_datetime(window)
            try:
                entry=float(tape.pivots['open'].reindex(idx)[row.symbol].iloc[0])
                highs=tape.pivots['high'].reindex(idx)[row.symbol].to_numpy(float)
                lows=tape.pivots['low'].reindex(idx)[row.symbol].to_numpy(float)
                path=excursion(entry,highs,lows)
                windows.append(dict(year=day.year,signal_date=str(day),symbol=row.symbol,rank=int(row.rank),
                    entry_day=str(window[0]),end_day=str(window[-1]),**path))
            except (ValueError,KeyError):reason='DAILY_WINDOW_UNQUALIFIED'
        if reason:excluded[f'{day.year}:{reason}']=excluded.get(f'{day.year}:{reason}',0)+1
    paths=pd.DataFrame(windows)
    direction=[]
    for year,g in paths.groupby('year'):
        counts=g.dominant_direction.value_counts().to_dict()
        direction.append(dict(year=int(year),symbol_date_pairs=len(g),unique_symbols=int(g.symbol.nunique()),
            counts=counts,down_pct=float(g.dominant_direction.eq('DOWN').mean()*100),
            mean_max_up_pct=float(g.max_up_pct.mean()),mean_max_down_pct=float(g.max_down_pct.mean())))
    ROOT.mkdir(parents=True,exist_ok=False)
    paths.to_parquet(ROOT/'top20-path-directions.parquet',index=False)
    result=dict(status='COMPLETED_READ_ONLY_DIAGNOSTIC',runs=data,TOP20_direction=direction,
        excluded_direction_pairs=excluded,
        direction_convention='J+1 daily open; highs/lows over next20 sessions; split-adjusted daily prices; signed greatest absolute excursion; not trade returns',
        overlapping_repeated_signals=True,future_coverage_selection_bias=True,
        exits_by_exit_year_not_signal_year=True,closed_pnl_not_same_as_annual_equity_change=True,
        no_macro_causal_identification=True,no_new_backtest=True,SQL_reads=0,SQL_writes=0,API_calls=0,
        sources=sources,outputs={'top20-path-directions.parquet':digest(ROOT/'top20-path-directions.parquet')})
    (ROOT/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(TOP20_direction=direction,excluded=excluded),indent=2))


if __name__=='__main__':main()
