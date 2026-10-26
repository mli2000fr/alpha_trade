"""Frozen bottom-rank veto before native Winner; read-only SQL, no provider/broker."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone, date, timedelta
import hashlib
import json
import logging
from pathlib import Path
import time

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import load_winner_pyramiding_config, WinnerPyramidingConfig
from execution_engine.config import ExecutionConfig, LeverageConfig, load_leverage_config_from_yaml
from risk_management.config import load_risk_config, RiskConfig
from backtesting.simulator import BacktestConfig, BacktestEngine
from backtesting.trading_constraints import TradingConstraintConfig
from backtesting.winner_campaign_replay import atomic_json, metrics

LOG=logging.getLogger(__name__)
ROOT=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v1')
TREND=Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v2')
DAILY=Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
DOC=Path('doc/ml/winner_filtre_bas_classement_protocole_20261022.md')
ARMS={'WINNER_ONLY':10,'DROP_BOTTOM3_KEEP7':7,'DROP_BOTTOM5_KEEP5':5}
ENDS={2025:date(2025,12,31),2026:date(2026,9,30)}
INITIAL=4000.


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def verify(items):
    for name,sha in items.items():
        if digest(name)!=sha:raise ValueError('Immutable input changed: '+str(name))


def save_new(path,value):
    if Path(path).exists():raise FileExistsError(str(path))
    atomic_json(Path(path),value)


def freeze_ranks(observable):
    cols=['date','symbol','score','oracle_rank','vol_ratio_20_60','J_qualified']
    a=observable[cols].copy()
    a['date']=pd.to_datetime(a.date).dt.normalize()
    if a.duplicated(['date','symbol']).any():raise ValueError('Duplicate observable candidate')
    if not a.groupby('date').oracle_rank.apply(lambda r:sorted(r)==list(range(1,11))).all():
        raise ValueError('Original TOP10 incomplete')
    a['aux_known']=a.J_qualified & np.isfinite(a.vol_ratio_20_60) & a.vol_ratio_20_60.gt(0)
    a['aux_priority']=a.vol_ratio_20_60.where(a.aux_known,np.inf)
    a=a.sort_values(['date','aux_priority','oracle_rank','symbol'])
    a['estimated_trend_rank']=a.groupby('date').cumcount()+1
    for arm,n in ARMS.items():a[arm]=a.aux_known & a.estimated_trend_rank.le(n)
    return a.sort_values(['date','oracle_rank','symbol']).reset_index(drop=True)


def annual_signals(frame,year):
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    seed=[s.session_date for s in cal.sessions(date(year-1,12,15),date(year,1,1)) if s.is_open][-1]
    return frame[frame.date.between(pd.Timestamp(seed),pd.Timestamp(ENDS[year]))].copy()


def prepare(root):
    if root.exists():raise FileExistsError('New immutable experiment directory required')
    report=read(TREND/'report.json');audit=read(TREND/'final-audit.json')
    if digest(TREND/'report.json')!=audit['report_sha256']:raise ValueError('Source result changed')
    verify({str(TREND/k):v for k,v in report['files'].items()})
    if report['best_discovery_diagnostic_only']!='vol_ratio_20_60':raise ValueError('Only previously chosen ratio permitted')
    chosen=next(x for x in report['features'] if x['feature']=='vol_ratio_20_60')
    if chosen['orientation_frozen_discovery']!=-1:raise ValueError('Frozen direction changed')
    policy=replace(load_winner_pyramiding_config(),enabled=True)
    expected=dict(initial_position_fraction=.5,reinforcement_enabled=False,confirmation_bars=2,
                  stop_loss_pct=.07,take_profit_pct=None,trailing_stop_pct=.15,horizon_sessions=20,entry_valid_sessions=20)
    if any(getattr(policy,k)!=v for k,v in expected.items()):raise ValueError('Winner settings differ from announced protocol')
    original=load_risk_config(equity=INITIAL,preset_key='capital_2001_5000',cli_overrides={'account_equity':INITIAL})
    risk=replace(original,enable_factor_model=False,use_factor_correlation_filter=False)
    leverage=load_leverage_config_from_yaml()
    allowed=min(2.,leverage.max_leverage if leverage.enabled else 1.)
    leverage=replace(leverage,audit_log=False,max_leverage=allowed,dry_run_simulated_leverage=allowed)
    sources={str(TREND/k):digest(TREND/k) for k in ['protocol.json','report.json','final-audit.json','observable-top10.parquet']}
    names=[Path(__file__),Path('tests/test_us_winner_bottom_rank_filter_20261022.py'),DOC,DAILY,Path('config.yaml'),
           Path('backtesting/winner_intraday.py'),Path('backtesting/simulator.py'),
           Path('backtesting/winner_campaign_replay.py'),Path('common/trading_costs.py'),
           Path('risk_management/config.py'),Path('risk_management/constraints.py'),
           Path('risk_management/risk_checker.py'),Path('risk_management/correlation_filter.py')]
    for folder,pattern in [('common','winner*.py'),('execution_engine','winner*.py')]:
        names.extend(Path(folder).glob(pattern))
    sources.update({str(x):digest(x) for x in names})
    # Bind the actual old daily bytes, never re-label them as SIP/raw.
    historic_sources=read('artifacts/research/us_winner_context_headroom/20261021-v1/protocol.json')['sources']
    daily_expected=next(v for k,v in historic_sources.items() if Path(k)==DAILY)
    if digest(DAILY)!=daily_expected:raise ValueError('Daily cache drift')
    ranked=freeze_ranks(pd.read_parquet(TREND/'observable-top10.parquet'))
    groups=[]
    for year in ENDS:
        a=annual_signals(ranked,year);a['year']=year;groups.append(a)
    signals=pd.concat(groups,ignore_index=True)
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        winner_policy=asdict(policy),risk=asdict(risk),original_risk=asdict(original),leverage=asdict(leverage),
        initial_equity=INITIAL,annual_reset=True,ends=ENDS,arms=ARMS,margin_interest_annual=.065,
        factor_overlay='Disabled identically in all research arms: qualified historical factor tapes unsupported by native Winner replay',
        effective_gross_cap=min(risk.max_gross_exposure,allowed),prior_negative_validation_disclosed=True,
        target_filter='Low vol20/vol60 first; veto estimated ranks8..10 or6..10; retained priority ORIGINAL Oracle',
        full_live_parity=False,training=False,SQL_writes=False,provider_calls=0,broker_calls=0,production_changed=False)
    save_new(root/'protocol.json',p);signals.to_parquet(root/'frozen-signals.parquet',index=False)
    save_new(root/'signals-ready.json',dict(files={'frozen-signals.parquet':digest(root/'frozen-signals.parquet')}))
    atomic_json(root/'progress.json',dict(status='PREPARED',signals=len(signals),unique_symbols=int(signals.symbol.nunique())))
    return p


def snapshot(root):
    from database.connection import get_sqlalchemy_engine
    p=read(root/'protocol.json');verify(p['sources'])
    verify({str(root/k):v for k,v in read(root/'signals-ready.json')['files'].items()})
    if (root/'snapshot.json').exists():raise FileExistsError('Snapshot already sealed')
    signals=pd.read_parquet(root/'frozen-signals.parquet')
    symbols=sorted(signals.symbol.unique());receipts=[];files={}
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn,conn.begin():
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US DB required')
            query=text('''SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,
                volume,payload_hash FROM stock_bars_intraday FORCE INDEX(PRIMARY)
                WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end
                AND provider='alpaca' AND data_source='alpaca_sip' AND market_code='US_EQ'
                AND interval_code='5m' AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0
                ORDER BY bar_timestamp''')
            for i,symbol in enumerate(symbols):
                file=root/f'sip-{i:03d}.parquet'
                marker=root/f'sip-{i:03d}.json'
                if marker.exists():
                    receipt=read(marker);verify({str(file):receipt['sha256']})
                    if receipt['symbol']!=symbol:raise ValueError('Snapshot symbol changed')
                else:
                    frame=pd.read_sql(query,conn,params=dict(symbol=symbol,start='2024-12-30 00:00:00',end='2026-10-01 00:00:00'))
                    for k in ['bar_timestamp','bar_end_timestamp']:frame[k]=pd.to_datetime(frame[k],utc=True)
                    frame['trade_date']=pd.to_datetime(frame.trade_date)
                    frame.to_parquet(file,index=False)
                    receipt=dict(symbol=symbol,rows=len(frame),file=file.name,sha256=digest(file),observed_at_utc=datetime.now(timezone.utc).isoformat())
                    save_new(marker,receipt)
                receipts.append(receipt);files[file.name]=receipt['sha256'];files[marker.name]=digest(marker)
                atomic_json(root/'progress.json',dict(status='SNAPSHOT_READ_ONLY',completed=i+1,total=len(symbols),last=symbol,rows=sum(x['rows'] for x in receipts)))
                LOG.info('SIP %s/%s %s: %s rows',i+1,len(symbols),symbol,receipt['rows'])
            for name,query2 in [
                ('sectors.parquet','SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols'),
                ('actions.parquet',"SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN '2024-12-30' AND '2026-09-30'")]:
                q=text(query2).bindparams(bindparam('symbols',expanding=True))
                frame=pd.read_sql(q,conn,params={'symbols':symbols});frame.to_parquet(root/name,index=False);files[name]=digest(root/name)
    finally:engine.dispose()
    save_new(root/'snapshot.json',dict(files=files,receipts=receipts,SQL_reads_only=True,provider_calls=0,
        same_transaction_on_first_pass=True,resumed_symbol_receipts_possible=True,metadata_current_non_PIT=True))
    return receipts


def qualify_session(frame,session):
    stamps=pd.to_datetime(frame.bar_timestamp,utc=True)
    expected=pd.date_range(session.open_at_utc,session.close_at_utc,freq='5min',inclusive='left')
    if len(frame)!=len(expected) or not pd.DatetimeIndex(stamps).equals(expected):return False
    n=frame[['open','high','low','close','volume']].to_numpy(float)
    if not np.isfinite(n).all() or (n<=0).any():return False
    o,h,l,c,v=n.T
    return bool((h>=np.maximum(o,c)).all() and (l<=np.minimum(o,c)).all() and (h>=l).all()
        and frame.payload_hash.notna().all() and (pd.to_datetime(frame.bar_end_timestamp,utc=True)-stamps).eq(pd.Timedelta(minutes=5)).all())


def common_cohort(signals,groups,actions,sectors):
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    result=[]
    for year,g in signals.groupby('year'):
        schedule=[s for s in cal.sessions(date(int(year)-1,12,15),ENDS[int(year)]) if s.is_open]
        days=[s.session_date for s in schedule];indices={d:i for i,d in enumerate(days)}
        for row in g.itertuples(index=False):
            reason=''
            i=indices[row.date.date()];end=min(i+40,len(days)-1)
            window=days[i:end+1]
            if row.symbol not in sectors or not sectors[row.symbol]:reason='CURRENT_SECTOR_MISSING'
            elif not row.aux_known:reason='UNKNOWN_J_FEATURES'
            elif any((row.symbol,d) not in groups for d in window):reason='COMMON_MAX_WAIT_AND_HOLD_SIP_WINDOW_MISSING'
            elif not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(pd.Timestamp(window[0]),pd.Timestamp(window[-1]))).any():reason='CORPORATE_ACTION_LIFECYCLE_RESERVED'
            result.append(dict(year=int(year),date=row.date,symbol=row.symbol,common_eligible=not reason,
                               coverage_reason=reason,common_window_end=window[-1]))
    return signals.merge(pd.DataFrame(result),on=['year','date','symbol'],validate='one_to_one')


def load_inputs(root):
    snap=read(root/'snapshot.json');verify({str(root/k):v for k,v in snap['files'].items()})
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    schedule={s.session_date:s for s in cal.sessions(date(2024,12,30),date(2026,9,30)) if s.is_open}
    groups={};quality=[]
    for item in snap['receipts']:
        frame=pd.read_parquet(root/item['file'])
        for day,g in frame.groupby('trade_date',sort=True):
            d=pd.Timestamp(day).date();s=schedule.get(d)
            good=s is not None and qualify_session(g,s)
            quality.append(dict(symbol=item['symbol'],date=d,qualified=bool(good),rows=len(g)))
            if good:groups[item['symbol'],d]=g.rename(columns={'bar_timestamp':'timestamp'}).copy()
    sectors_frame=pd.read_parquet(root/'sectors.parquet')
    if sectors_frame.symbol.duplicated().any():raise ValueError('Duplicate sector')
    sectors={str(r.symbol):str(r.sector) for r in sectors_frame.dropna().itertuples()}
    actions=pd.read_parquet(root/'actions.parquet');actions['ex_date']=pd.to_datetime(actions.ex_date)
    for k in ['payable_date']:
        actions[k]=pd.to_datetime(actions[k]).dt.date
    signals=common_cohort(pd.read_parquet(root/'frozen-signals.parquet'),groups,actions,sectors)
    signals.to_parquet(root/'qualified-signals.parquet',index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet',index=False)
    symbols=set(signals.symbol)|{'SPY'}
    daily=pd.read_parquet(DAILY,filters=[('symbol','in',list(symbols))])
    if daily.duplicated(['symbol','date']).any():raise ValueError('Ambiguous daily')
    numeric=daily[['open','high','low','close','volume']]
    valid=np.isfinite(numeric).all(axis=1)&numeric.gt(0).all(axis=1)&daily.is_filled.eq(0)&daily.data_adjustment.eq('split')
    daily=daily.copy();daily.loc[~valid,['open','high','low','close','volume']]=np.nan
    pivots={k:daily.pivot(index='date',columns='symbol',values=k).astype(float) for k in ('open','high','low','close','volume')}
    return signals,groups,actions,sectors,pivots


def engine_config(protocol,year):
    risk=RiskConfig(**{k:v for k,v in protocol['risk'].items() if not k.startswith('_')})
    lev=dict(protocol['leverage']);lev['buying_power_field_priority']=tuple(lev['buying_power_field_priority'])
    leverage=LeverageConfig(**lev)
    execution=ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(**protocol['winner_policy']),
        account_type='margin',dry_run=True,simulated_account_equity=INITIAL,leverage=leverage,
        simulated_margin_buying_power_multiplier=leverage.max_leverage if leverage.enabled else 1.)
    return BacktestConfig(start_date=date(year,1,1),end_date=ENDS[year],initial_equity=INITIAL,
        risk_config=risk,exec_config=execution,use_canonical_costs=True,
        margin_interest_rate_annual=protocol['margin_interest_annual'],
        trading_constraints=TradingConstraintConfig(account_type='margin',swing_only=False))


def run(root):
    p=read(root/'protocol.json');verify(p['sources'])
    if (root/'report.json').exists():raise FileExistsError('Results already sealed')
    signals,groups,actions,sectors,pivots=load_inputs(root)
    reports=[];started=time.monotonic()
    def source(day,symbols):
        parts=[groups[s,day] for s in symbols if (s,day) in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    for year in ENDS:
        annual=signals[signals.year.eq(year)]
        for arm in ARMS:
            folder=root/f'{year}-{arm}';folder.mkdir(exist_ok=False)
            selected=annual[['date','symbol','oracle_rank']].rename(columns={'date':'trade_date','oracle_rank':'rank'}).copy()
            selected['selected']=annual.common_eligible.to_numpy() & annual[arm].to_numpy()
            selected['side']='long'
            def progress(done,total,day):
                atomic_json(root/'progress.json',dict(status='RUNNING',year=year,arm=arm,completed_runs=len(reports),
                    total_runs=6,completed_sessions=done,total_sessions=total,last_date=day,elapsed_seconds=time.monotonic()-started))
            try:
                result=BacktestEngine(engine_config(p,year)).run(open_df=pivots['open'],close=pivots['close'],
                    high=pivots['high'],low=pivots['low'],volume=pivots['volume'],signals_df=selected,
                    sector_map=sectors,intraday_source=source,winner_research_assumptions=True,
                    winner_progress=progress,winner_corporate_actions=actions.to_dict('records'))
                summary=metrics(result,INITIAL)
                result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
                # Runtime event rows are heterogeneous (nested diagnostics and
                # aware timestamps); CSV preserves them without Arrow coercion.
                result.trade_events_df.to_csv(folder/'events.csv',index=False)
                result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
                result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
                result.drawdown_breaker_df.to_parquet(folder/'breaker.parquet',index=False)
                summary.update(year=year,arm=arm,original_signals=len(annual),common_eligible=int(annual.common_eligible.sum()),
                    selected_signals=int(selected.selected.sum()),rank_filter_excluded=int((annual.common_eligible & ~annual[arm]).sum()),
                    files={x.name:digest(x) for x in folder.iterdir() if x.suffix in ('.parquet','.csv')})
            except Exception as exc:
                LOG.exception('Annual account failed')
                summary=dict(year=year,arm=arm,status='FAILED',error_type=type(exc).__name__,error=str(exc))
            save_new(folder/'report.json',summary);reports.append(summary)
            LOG.info('%s %s %s',year,arm,summary.get('return_pct',summary['status']))
            pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in reports]).to_csv(root/'annual-summary.partial.csv',index=False)
    verify(p['sources'])
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in reports]).to_csv(root/'annual-summary.csv',index=False)
    coverage=signals.groupby(['year','coverage_reason'],dropna=False).size().rename('signals').reset_index().to_dict('records')
    report=dict(status='COMPLETED_EXPLORATORY' if all(x['status']=='COMPLETED_EXPLORATORY' for x in reports) else 'PARTIAL_OR_FAILED',
        cases=reports,coverage=coverage,elapsed_seconds=time.monotonic()-started,primary_filter_already_examined=True,
        full_live_parity=False,model_fits=0,SQL_writes=False,provider_calls=0,production_changed=False,
        files={x.name:digest(x) for x in root.iterdir() if x.is_file() and x.suffix in ('.parquet','.csv')})
    save_new(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed_runs=6,total_runs=6))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','snapshot','run'],required=True)
    parser.add_argument('--output',type=Path,default=ROOT);args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Provider/broker/LLM HTTP forbidden')
    requests.Session.request=forbidden
    {'prepare':prepare,'snapshot':snapshot,'run':run}[args.phase](args.output)
