"""Paired native LONG Winner replay, with/without archived GPT score 1..3 veto.

No new LLM/provider call, training, SQL write, production change or broker order.
Two fresh USD4000 accounts, same TOP20/data/risk/protections/costs; no replacement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam,text

from scripts.research import us_winner_bottom_rank_filter_20261022 as base
from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from backtesting.winner_campaign_replay import atomic_json,metrics
from common.daily_bar_sources import select_daily_bars
from modelFactory.oracle.security_continuity import load_security_discontinuities,path_crosses_known_discontinuity
from service.market.intraday_backfill import run_lock

GPT=Path('artifacts/research/us_gpt_august_2026_path_audit/20261025-v2')
REFERENCE=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2/protocol.json')
ROOT=Path('artifacts/research/us_winner_gpt_veto_august_2026/20261025-v1')
START,END=date(2026,8,3),date(2026,9,30)
ARMS=('WINNER_ONLY','WINNER_GPT_VETO_1_3')


def freeze_veto(candidates,answers):
    candidates=candidates[['date','symbol','oracle_rank','score']].copy()
    if len(candidates)!=420 or candidates.duplicated(['date','symbol']).any():raise ValueError('420 original TOP20 pairs required')
    if any(set(g.oracle_rank)!=set(range(1,21)) for _,g in candidates.groupby('date')):raise ValueError('Ranks changed')
    records=[]
    for row in answers:
        a=row.get('assessment') or {};score=a.get('direction_score') if row['status']=='VALID' else None
        if score is not None and (type(score) is not int or not 1<=score<=10):raise ValueError('Invalid archived score')
        records.append(dict(date=pd.Timestamp(row['date']),symbol=row['symbol'],gpt_status=row['status'],
            gpt_score=score,gpt_veto=bool(score is not None and score<=3)))
    answers=pd.DataFrame(records)
    if answers.duplicated(['date','symbol']).any() or set(zip(answers.date,answers.symbol))!=set(zip(candidates.date,candidates.symbol)):
        raise ValueError('Missing/duplicate archived answer')
    return candidates.merge(answers,on=['date','symbol'],validate='one_to_one').sort_values(['date','oracle_rank']).reset_index(drop=True)


def prepare(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    a=base.read(GPT/'analysis.json');p=base.read(GPT/'protocol.json')
    if a['status']!='SCORES_COMPLETED' or a['total']!=420:raise ValueError('All answers must be archived')
    base.verify({str(GPT/k):v for k,v in p['files'].items()})
    if base.digest(GPT/'scores.json')!=a['score_file_sha256']:raise ValueError('GPT scores altered')
    signals=freeze_veto(pd.read_parquet(GPT/'candidates.parquet'),base.read(GPT/'scores.json'))
    config=base.read(REFERENCE)
    # User amendment BEFORE any replay: disable trailing identically in both arms.
    config['winner_policy']=dict(config['winner_policy'],trailing_stop_pct=None)
    expected=dict(stop_loss_pct=.07,trailing_stop_pct=None,take_profit_pct=None,horizon_sessions=20,
        initial_position_fraction=.5,reinforcement_enabled=False,confirmation_bars=2,entry_valid_sessions=20)
    if any(config['winner_policy'][k]!=v for k,v in expected.items()):raise ValueError('Reference Winner policy changed')
    signal_path=root/'frozen-signals.parquet';signals.to_parquet(signal_path,index=False)
    source_files=[Path(__file__),Path('tests/test_us_winner_gpt_veto_august_2026.py'),REFERENCE,
        GPT/'analysis.json',GPT/'scores.json',GPT/'candidates.parquet',GPT/'protocol.json',
        Path(base.__file__),Path(grid.__file__),Path('scripts/research/us_winner_bottom_rank_filter_whole_shares_20261022.py'),
        Path('scripts/research/us_winner_sl3_tp7_tr3_open11_audit_20261023.py'),
        Path('scripts/research/us_winner_bottom_rank_filter_audit_20261022.py'),
        Path('backtesting/simulator.py'),Path('backtesting/winner_intraday.py'),
        Path('backtesting/winner_global_liquidation.py'),Path('backtesting/winner_campaign_replay.py')]
    for folder,pattern in [('common','winner*.py'),('execution_engine','winner*.py'),('risk_management','*.py')]:
        source_files.extend(Path(folder).glob(pattern))
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),arms=ARMS,initial_equity=4000,
        start=str(START),end=str(END),signal_period='2026-08-03..2026-08-31',signals=420,
        gpt_veto_signals=int(signals.gpt_veto.sum()),reference_config=config,
        winner_policy=expected,reference_amendment='User requested trailing OFF in both arms before replay',
        effective_gross_cap=1.,fee_bps_per_leg=8,
        rule='Exclude ONLY VALID score1..3 before plan staging; unknown/invalid kept. No TOP21 replacement.',
        existing_longs='No GPT exit; only new signal plans filtered. Previously staged plans keep their original validity.',
        terminal='Mark open positions to market at Sep30; no forced terminal sale, no invented maturity.',
        common_cohort='Same strict J..min(J+40,last replay session) full SIP session/sector/CA/identity coverage before both arms.',
        future_coverage_selection_bias=True,historical_gpt_non_PIT=True,full_live_parity=False,independent_holdout=False,
        global_risk='Frozen native B4/DD15 allocation; no addition of the separate experimental DD25/cooldown rules.',
        factor_overlays='Disabled identically as in frozen native reference; Pearson/sector/cash guards retained.',
        sql_writes=False,provider_calls=0,gpt_calls=0,training=False,production_changed=False,broker_orders=False,
        sources={str(f):base.digest(f) for f in source_files},files={'frozen-signals.parquet':base.digest(signal_path)})
    base.save_new(root/'protocol.json',protocol)
    atomic_json(root/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=2,veto_signals=int(signals.gpt_veto.sum())))
    return protocol


def snapshot(root):
    root=Path(root);p=base.read(root/'protocol.json');base.verify(p['sources'])
    base.verify({str(root/k):v for k,v in p['files'].items()})
    folder=root/'inputs';folder.mkdir(exist_ok=True)
    signals=pd.read_parquet(root/'frozen-signals.parquet');symbols=sorted(signals.symbol.unique())
    files={};receipts=[];daily=[]
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('US only')
            for i,symbol in enumerate(symbols):
                atomic_json(root/'progress.json',dict(status='SNAPSHOT_SQL_READ_ONLY',completed_symbols=i,total_symbols=len(symbols),symbol=symbol))
                file=folder/f'{symbol}.parquet'
                q=text('''SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash
                    FROM stock_bars_intraday FORCE INDEX(PRIMARY) WHERE symbol=:symbol
                    AND bar_timestamp>='2026-07-30' AND bar_timestamp<'2026-10-01'
                    AND provider='alpaca' AND data_source='alpaca_sip' AND market_code='US_EQ'
                    AND interval_code='5m' AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0
                    ORDER BY bar_timestamp''')
                f=pd.read_sql(q,conn,params={'symbol':symbol})
                for k in ('bar_timestamp','bar_end_timestamp'):f[k]=pd.to_datetime(f[k],utc=True)
                f['trade_date']=pd.to_datetime(f.trade_date);f.to_parquet(file,index=False)
                receipts.append(dict(symbol=symbol,file=file.name,rows=len(f)));files[file.name]=base.digest(file)
            for symbol in symbols+['SPY']:
                daily.append(pd.read_sql(text('''SELECT symbol,date,open,high,low,close,volume,data_source,data_adjustment,is_filled
                    FROM stock_bars_daily WHERE symbol=:symbol AND date BETWEEN '2024-08-01' AND '2026-09-30'
                    AND data_source IN ('eodhd_eod','alpaca_sip')'''),conn,params={'symbol':symbol}))
            for name,sql in [('sectors.parquet','SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols'),
                ('actions.parquet',"SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN '2026-07-30' AND '2026-09-30'")]:
                f=pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params={'symbols':symbols})
                f.to_parquet(folder/name,index=False);files[name]=base.digest(folder/name)
    finally:engine.dispose()
    d=select_daily_bars(pd.concat(daily,ignore_index=True),config={'market_data':{'daily_bars_preferred_source':'eodhd'}})
    d.to_parquet(folder/'daily.parquet',index=False);files['daily.parquet']=base.digest(folder/'daily.parquet')
    base.save_new(folder/'snapshot.json',dict(receipts=receipts,files=files,current_metadata_non_PIT=True,SQL_read_only=True))
    atomic_json(root/'progress.json',dict(status='INPUTS_READY',completed_runs=0,total_runs=2))


def load_inputs(root):
    root=Path(root);folder=root/'inputs';m=base.read(folder/'snapshot.json')
    base.verify({str(folder/k):v for k,v in m['files'].items()})
    calendar=[s for s in grid.calendar().sessions(START-timedelta(days=14),END+timedelta(days=100)) if s.is_open]
    schedule={s.session_date:s for s in calendar};groups={};raw={};quality=[]
    for receipt in m['receipts']:
        f=pd.read_parquet(folder/receipt['file'])
        f['session_close']=f.trade_date.map({pd.Timestamp(d):s.close_at_utc for d,s in schedule.items()})
        raw[receipt['symbol']]=f
        for stamp,g in f.groupby('trade_date'):
            day=pd.Timestamp(stamp).date();s=schedule.get(day)
            good=s is not None and base.qualify_session(g,s)
            quality.append(dict(symbol=receipt['symbol'],date=day,qualified=bool(good)))
            if good:groups[receipt['symbol'],day]=g.rename(columns={'bar_timestamp':'timestamp'}).copy()
    sectors={r.symbol:r.sector for r in pd.read_parquet(folder/'sectors.parquet').dropna().itertuples()}
    actions=pd.read_parquet(folder/'actions.parquet');actions['ex_date']=pd.to_datetime(actions.ex_date)
    actions['payable_date']=pd.to_datetime(actions.payable_date).dt.date
    signals=pd.read_parquet(root/'frozen-signals.parquet')
    days=[s.session_date for s in calendar if s.session_date<=END]
    cohort=grid.qualify_cohort(signals,groups,actions,sectors,days)
    registry=load_security_discontinuities()
    for i,row in cohort.iterrows():
        if row.selected and path_crosses_known_discontinuity(row.symbol,row.date,row.window_end,registry):
            cohort.loc[i,'selected']=False;cohort.loc[i,'coverage_reason']='IDENTITY_DISCONTINUITY'
    cohort.to_parquet(root/'common-cohort.parquet',index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet',index=False)
    d=pd.read_parquet(folder/'daily.parquet');d['date']=pd.to_datetime(d.date)
    values=d[['open','high','low','close','volume']].to_numpy(float)
    good=np.isfinite(values).all(axis=1)&(values>0).all(axis=1)&d.is_filled.eq(0)&d.data_adjustment.eq('split')
    d.loc[~good,['open','high','low','close','volume']]=np.nan
    pivots={k:d.pivot(index='date',columns='symbol',values=k).astype(float) for k in ('open','high','low','close','volume')}
    return cohort,groups,raw,actions,sectors,pivots,calendar


def arm_signals(cohort,arm):
    if arm not in ARMS:raise ValueError('Unknown arm')
    out=cohort[['date','symbol','oracle_rank']].rename(columns={'date':'trade_date','oracle_rank':'rank'}).copy()
    out['selected']=(cohort.selected & (~cohort.gpt_veto if arm==ARMS[1] else True)).to_numpy()
    out['side']='long'
    return out


def run(root):
    root=Path(root);p=base.read(root/'protocol.json');base.verify(p['sources'])
    base.verify({str(root/k):v for k,v in p['files'].items()})
    if (root/'report.json').exists():raise FileExistsError('Already completed; do not overwrite')
    cohort,groups,raw,actions,sectors,pivots,calendar=load_inputs(root)
    def bars(day,symbols):
        parts=[groups[s,day] for s in symbols if (s,day) in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    cfg=base.engine_config(p['reference_config'],2026)
    cfg=replace(cfg,start_date=START,end_date=END,cost_round_trip_bps=16.)
    profile=dict(stop_loss_pct=.07,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20)
    reports=[];results={}
    for arm in ARMS:
        folder=root/arm;folder.mkdir(exist_ok=False)
        selected=arm_signals(cohort,arm)
        def progress(done,total,day):
            atomic_json(root/'progress.json',dict(status='RUNNING',arm=arm,completed_runs=len(reports),total_runs=2,
                completed_sessions=done,total_sessions=total,last_date=day))
        with grid.runtime_adapter(2026,arm) as refusals:
            result=base.BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=selected,sector_map=sectors,intraday_source=bars,
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=actions.to_dict('records'))
            atomic_json(folder/'whole-share-refusals.json',refusals)
        summary=metrics(result,4000.)
        if summary['status']!='COMPLETED_EXPLORATORY':raise ValueError('Incomplete coverage: '+str(summary['coverage_gaps'][:5]))
        allowed=cohort.copy();allowed['selected']=selected.selected.to_numpy()
        audit=grid.audit_result(result,summary,profile,allowed,raw,calendar)
        result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
        result.trade_events_df.to_parquet(folder/'events.parquet',index=False)
        result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.drawdown_breaker_df.to_parquet(folder/'breaker.parquet',index=False)
        summary.update(arm=arm,audit=audit,**{k:audit[k] for k in ('average_winning_holding_sessions','average_losing_holding_sessions')},
            files={f.name:base.digest(f) for f in folder.iterdir() if f.is_file()})
        base.save_new(folder/'report.json',summary);reports.append(summary);results[arm]=result
    control,filtered=reports
    control_trades=results[ARMS[0]].closed_trades_df;filtered_trades=results[ARMS[1]].closed_trades_df
    def keys(frame):return {(r.symbol,str(r.entry_date)) for r in frame.itertuples()}
    ck,fk=keys(control_trades),keys(filtered_trades)
    removed=control_trades[[k not in fk for k in [(r.symbol,str(r.entry_date)) for r in control_trades.itertuples()]]]
    added=filtered_trades[[k not in ck for k in [(r.symbol,str(r.entry_date)) for r in filtered_trades.itertuples()]]]
    # Portfolio interactions mean "removed trades" are not a causal loss-only estimate.
    attribution=dict(control_only_closed_trades=len(removed),filtered_only_closed_trades=len(added),
        control_only_winners=int(removed.pnl.gt(0).sum()) if len(removed) else 0,
        control_only_losers=int(removed.pnl.lt(0).sum()) if len(removed) else 0,
        control_only_pnl=float(removed.pnl.sum()) if len(removed) else 0,
        filtered_only_pnl=float(added.pnl.sum()) if len(added) else 0,not_a_causal_per_trade_loss_estimate=True)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in reports]).to_csv(root/'comparison.csv',index=False)
    report=dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=reports,
        eligible_signals=int(cohort.selected.sum()),veto_original=int(cohort.gpt_veto.sum()),
        veto_eligible=int((cohort.selected&cohort.gpt_veto).sum()),coverage_reasons=cohort.coverage_reason.value_counts().to_dict(),
        net_capital_advantage_usd=filtered['final_equity']-control['final_equity'],
        return_advantage_points=filtered['return_pct']-control['return_pct'],attribution=attribution,
        historical_gpt_non_PIT=True,future_coverage_selection_bias=True,full_live_parity=False,independent_holdout=False,
        open_positions_marked_not_forced=True,gpt_calls=0,SQL_writes=False,broker_orders=False,
        sources=p['sources'],files={f.name:base.digest(f) for f in root.iterdir() if f.is_file() and f.name!='progress.json'})
    base.verify(p['sources']);base.save_new(root/'report.json',report)
    atomic_json(root/'progress.json',dict(status=report['status'],completed_runs=2,total_runs=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','snapshot','run','all'],default='all')
    parser.add_argument('--output',type=Path,default=ROOT);args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No API/provider/broker in this replay'))
    try:
        if args.phase in ('prepare','all'):prepare(args.output)
        with run_lock(args.output):
            if args.phase in ('snapshot','all'):snapshot(args.output)
            if args.phase in ('run','all'):
                r=run(args.output)
                print(base.json.dumps({k:v for k,v in r.items() if k not in ('sources','files','cases')}))
    except Exception as exc:
        if args.output.exists():atomic_json(args.output/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)[:500]))
        raise


if __name__=='__main__':main()
