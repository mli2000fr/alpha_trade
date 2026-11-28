"""Read-only checks of the completed matched ceiling overlay comparison."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_q051_ceiling_overlays_20261128 import ROOT,CASES,case_folder,read


def audit():
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from scripts.research.us_q051_entry_ceiling_20261127 import previous
    if read(ROOT/'validation.json')['status']!='PASS':raise ValueError('Comparison not completed/validated')
    plan=read(ROOT/'protocol.json')
    with replay_market_registry(previous.shared.restore_registry(previous.shared.ROOT)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in calendar.sessions(pd.Timestamp('2020-12-01').date(),pd.Timestamp('2026-11-01').date()) if s.is_open]
    index={s.session_date:i for i,s in enumerate(sessions)}
    opens={s.session_date:pd.Timestamp(s.open_at_utc) for s in sessions}
    candidates=pd.read_parquet(ROOT/'inputs/anti-sl-decisions.parquet').set_index('origin_id')
    # Preparation used a left join for missing cached scores. Check that no
    # such row was actually an absent eligible feature frame, which would
    # otherwise have become the head's entirely-imputed default prediction.
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict
    anti=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
    scores=pd.read_parquet(ROOT/'inputs/anti-sl-scores.parquet');new_scores=0
    for year in range(2021,2027):
        cache=pd.read_parquet(anti/'heads'/str(year)/'probabilities.parquet')[['date','symbol']]
        cache=cache.rename(columns={'date':'origin_signal_date'})
        pending=scores[scores.entry_year.eq(year)].merge(cache,on=['origin_signal_date','symbol'],how='left',indicator=True)
        pending=pending[pending._merge.eq('left_only')];new_scores+=len(pending)
        for rec in read(anti/'heads'/str(year)/'models.json')['models']:
            if rec['variant']!='SL10' or 'file' not in rec:continue
            group=pending[pending.origin_signal_date.dt.year.eq(rec['model_year'])]
            weights=joblib.load(rec['file'])
            default=float(predict(weights,pd.DataFrame(np.nan,index=[0],columns=weights['features']))[0])
            if np.isclose(group.SL10_risk,default,rtol=0,atol=1e-12).any():
                raise ValueError('Missing-score input eligibility needs detailed reinspection')
    checks=[];configurations=[]
    for case in CASES:
        folder=case_folder(case);out=folder/'result'
        configurations.append(read(out/'configuration.json')['portfolio'])
        report=read(out/'report.json');trades=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        marks=pd.read_parquet(out/'equity-5m.parquet');buys=events[events.event.eq('BUY_FILL')].copy()
        fees=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
        if not np.isclose(fees,report['costs'],atol=1e-7,rtol=1e-10):raise ValueError('Fees do not reconcile')
        equity=report['settled_cash']+report['unsettled_cash']+report['gross']+report.get('dividends_receivable',0)
        if not np.isclose(equity,report['final_equity'],atol=1e-7,rtol=1e-10):raise ValueError('Final cash/positions do not reconcile')
        if not np.isclose(report['return_pct'],100*(report['final_equity']/4000.-1),atol=1e-9):raise ValueError('Wrong return base')
        dd=pd.concat([pd.Series([4000.]),marks.equity],ignore_index=True)
        if not np.isclose(100*(dd/dd.cummax()-1).min(),report['max_drawdown_pct'],atol=1e-8):raise ValueError('DD does not reconcile')
        if buys.origin_id.duplicated().any():raise ValueError('Signal filled more than once')
        for fill in buys.itertuples():
            origin=candidates.loc[fill.origin_id];stamp=pd.Timestamp(fill.time)
            day=stamp.tz_convert('America/New_York').date()
            wait=index[day]-index[pd.Timestamp(origin.origin_signal_date).date()]
            if wait not in (1,2) or not np.isclose(fill.price,min(fill.price,origin.ceiling),atol=1e-8):
                raise ValueError('Entry off two-session window/above ceiling')
            if case=='ANTI_SL' and origin.anti_sl_excluded:raise ValueError('Excluded signal filled')
        for trade in trades.itertuples():
            en=pd.Timestamp(trade.entry_date).tz_convert('America/New_York')
            ex=pd.Timestamp(trade.exit_date).tz_convert('America/New_York')
            held=index[ex.date()]-index[en.date()]
            if not 0<=held<=10:raise ValueError('Held outside horizon')
            if trade.exit_reason=='HORIZON_OPEN' and (held!=10 or ex!=opens[ex.date()]):raise ValueError('Not open11')
        stopped=trades.exit_reason.str.contains('STOP')
        same_day=pd.to_datetime(trades.entry_date,utc=True).dt.tz_convert('America/New_York').dt.date.eq(
            pd.to_datetime(trades.exit_date,utc=True).dt.tz_convert('America/New_York').dt.date)
        extra=dict(stop_exits=int(stopped.sum()),first_session_stops=int((stopped&same_day).sum()),
            first_session_stops_per_entry_pct=100*float((stopped&same_day).sum())/len(buys))
        if case=='VOL20_REGIME':
            gate=pd.read_csv(out/'regime-decisions.csv');budget=pd.read_csv(out/'portfolio-risk-decisions.csv')
            # Include the observed opening source so a budget silently attached
            # only to daily entries cannot pass the validation.
            required={'CANONICAL_DAILY_OPEN','OBSERVED_5M_OPEN'}
            if not required<=set(budget.price_source):raise ValueError('Budget missing one entry path')
            keys={}
            for row in budget[budget.status.eq('QUALIFIED')].itertuples():
                key=(pd.Timestamp(row.time),row.symbol)
                if key in keys:raise ValueError('Duplicate sizing receipt')
                keys[key]=row
                prior=pd.Timestamp(row.history_end).date()
                if not prior<pd.Timestamp(row.time).tz_convert('America/New_York').date():raise ValueError('Future covariance')
                if row.final_quantity>row.native_quantity:raise ValueError('Budget increased quantity')
                if row.final_quantity>0 and row.approved_vol>.20+1e-9:raise ValueError('Volatility approval over target')
            allowed={pd.Timestamp(row.cutoff).tz_convert('America/New_York').date():row.entry_allowed for row in gate.itertuples()}
            for fill in buys.itertuples():
                stamp=pd.Timestamp(fill.time);receipt=keys.get((stamp,fill.symbol))
                if receipt is None or fill.quantity>receipt.final_quantity:raise ValueError('Buy missing sizing approval')
                if not allowed.get(stamp.tz_convert('America/New_York').date(),False):raise ValueError('Buy in blocked regime')
            extra.update(volatility_receipts=len(budget),scheduled_receipts=int(budget.price_source.eq('OBSERVED_5M_OPEN').sum()),
                daily_receipts=int(budget.price_source.eq('CANONICAL_DAILY_OPEN').sum()),regime_blocked_days=int((~gate.entry_allowed).sum()))
        isolation=read(folder/'isolation.json')
        if isolation['status']!='COMPLETED' or isolation.get('violations'):raise ValueError('Isolation not qualified')
        checks.append(dict(case=case,status='PASS',trades=len(trades),buys=len(buys),**extra))
    if any(cfg!=configurations[0] for cfg in configurations):raise ValueError('Native portfolio configuration changed')
    result=dict(status='PASS',checks=checks,baseline=read(ROOT/'baseline-reproduction.json')['kind'],
        native_portfolio_configuration_identical=True,
        newly_inferred_qualified_rows=new_scores,entirely_missing_input_defaults=0,
        reviewer='separate scalar audit in same assistant session',production_changes=False,
        sources={str(Path(__file__)):digest(Path(__file__))})
    atomic_json(ROOT/'supplementary-validation.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':audit()
