"""Research-only GPT sizing: FAVORABLE x5, neutral/no-news x1, UNFAVORABLE excluded."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import sqlite3

import pandas as pd

from scripts.research import us_gpt_winner_ab as source
from scripts.research.us_gpt_winner_favorable_only import classify,ROOT as PREVIOUS
from scripts.research.us_gpt_winner_invalid_excluded import METRICS
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_gpt_winner_boost_favorable/20261108-v1')


def scaled_risk(risk,multiplier):
    if multiplier not in (1,5):raise ValueError('Multiplicateur non autorisé')
    return replace(risk,risk_per_trade_pct=risk.risk_per_trade_pct*multiplier,
        max_position_weight=min(1.,risk.max_position_weight*multiplier))


@contextmanager
def entry_sizing(multipliers):
    """Keep the native entry and recheck path; change only the candidate budget/cap.

    Both points must use the same multiplier. No shared source file is edited.
    Applies only within this dedicated replay process; no live/broker imports.
    """
    from backtesting import winner_daily_entry as entry
    original_enter,original_approve=entry.enter_daily_candidates,entry.approve_daily_open
    def multiplier(day,symbol):
        key=(str(day)[:10],symbol)
        if key not in multipliers:raise ValueError('Multiplicateur de candidature absent')
        return multipliers[key]
    def enter(rows,**kwargs):
        order='rank' if 'rank' in rows else 'symbol'
        for _,row in rows.sort_values(order).iterrows():
            m=multiplier(kwargs['signal_day'],row['symbol'])
            original_enter(row.to_frame().T,**{**kwargs,'risk_config':scaled_risk(kwargs['risk_config'],m)})
    def approve(state,version,proposed,snapshot,now,*,context):
        m=multiplier(state['signal_date'],state['symbol'])
        return original_approve(state,version,proposed,snapshot,now,
            context={**context,'risk_config':scaled_risk(context['risk_config'],m)})
    with patch.object(entry,'enter_daily_candidates',enter),patch.object(entry,'approve_daily_open',approve):
        yield


def run(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid
    root.mkdir(parents=True,exist_ok=False)
    try:
        _,packets=source.verify(source.ROOT)
        db=sqlite3.connect((source.ROOT/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        try:
            records={key:dict(validation=json.loads(v),response=json.loads(raw) if raw else None)
                for key,v,raw in db.execute('SELECT a.request_key,a.validation_json,a.response_json '
                    'FROM attempts a WHERE a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.request_key=a.request_key)')}
        finally:db.close()
        rows=classify(packets,records)
        for row in rows:
            row['retained']=row['original_valid'] and row['assessment']!='UNFAVORABLE'
            row['size_multiplier']=5 if row['retained'] and row['assessment']=='FAVORABLE' else 1
        ledger=pd.DataFrame(rows)
        counts=dict(retained=int(ledger.retained.sum()),boosted=int((ledger.retained&ledger.size_multiplier.eq(5)).sum()),
            unfavorable=int(ledger.assessment.eq('UNFAVORABLE').sum()),invalid=int((~ledger.original_valid).sum()))
        if counts!=dict(retained=134,boosted=17,unfavorable=59,invalid=11):raise ValueError('Cohorte différente')
        base=pd.read_parquet(source.ROOT/'signals.parquet')
        if len(base)!=len(rows) or {(str(r.trade_date)[:10],r.symbol) for r in base.itertuples()}!={(r['signal_date'],r['symbol']) for r in rows}:
            raise ValueError('Signaux et décisions incompatibles')
        retained={(r['signal_date'],r['symbol']) for r in rows if r['retained']}
        selected=base.loc[[(str(r.trade_date)[:10],r.symbol) in retained for r in base.itertuples()]]
        ledger.to_csv(root/'decisions.csv',index=False)
        prior=source.read(PREVIOUS/'report.json')
        if prior['status']!='COMPLETED_EXPLORATORY':raise ValueError('Comparaisons précédentes absentes')
        atomic_json(root/'protocol.json',dict(policy='FAVORABLE_5_NEUTRAL_AND_NO_NEWS_1',year=2025,
            invalid='EXCLUDE',unfavorable='EXCLUDE_ALL_VALID_UNFAVORABLE_NOT_ONLY_PRIOR_34_VETOES',counts=counts,
            risk_per_trade_base=.0125,risk_per_trade_favorable=.0625,weight_base=.2,weight_favorable=1.,
            account_max_leverage=2.,risk_max_gross=2.,refill=False,
            amount_sizing='Native per-entry budget and per-position cap scaled; rounding and available buying power still apply',
            runtime_adapter='Native daily entry and its native recheck, research process only',
            script_sha256=digest(Path(__file__)),source_hashes={n:digest(source.ROOT/n) for n in ('protocol.json','requests.json','signals.parquet','analyses.sqlite3')},
            previous_report_sha256=digest(PREVIOUS/'report.json'),started_at_utc=datetime.now(timezone.utc).isoformat(),
            api_calls=0,broker_calls=0,shared_sql_writes=0,strict_pit=False,independent_holdout=False))
        grid.verify_inputs(grid.ROOT);grid.initialize_worker(grid.ROOT)
        reports=list(prior['arms'])
        for arm,boost in [('GPT_MIXED_NORMAL',False),('GPT_MIXED_BOOST5',True)]:
            out=root/arm;out.mkdir()
            multipliers={(r['signal_date'],r['symbol']):r['size_multiplier'] if boost else 1 for r in rows if r['retained']}
            selected.to_csv(out/'signals.csv',index=False)
            with ReadOnlyReplay(root).install(),entry_sizing(multipliers):
                def progress(done,total,day):
                    atomic_json(root/'progress.json',dict(status='REPLAYING',arm=arm,completed=done,total=total,last_date=str(day)))
                cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
                result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                    high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                    signals_df=selected,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                    winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
                report=metrics(result,4000.);report.update(arm=arm,selected_signals=len(selected),excluded_signals=len(base)-len(selected))
                atomic_json(out/'report.json',report)
                result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
                result.closed_trades_df.to_csv(out/'trades.csv',index=False)
                result.trade_events_df.to_csv(out/'events.csv',index=False)
                reports.append(report)
        table=pd.DataFrame([{k:r.get(k) for k in ('arm',)+METRICS+('selected_signals','excluded_signals')} for r in reports])
        table.to_csv(root/'comparison.csv',index=False)
        atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY',arms=reports,api_calls=0,broker_calls=0,strict_pit=False))
        atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY',new_arms=2))
        return table.to_dict('records')
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args();print(json.dumps(run(args.output_dir),ensure_ascii=False))


if __name__=='__main__':main()
