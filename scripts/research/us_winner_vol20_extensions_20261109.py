"""Five prespecified extensions, continuous 2021–2026, no provider or broker.

Keep original archived prices unchanged. Additional symbols/dates are frozen
from existing SQL in a read-only transaction before the four wider replays.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime,timezone
from functools import lru_cache
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests
from sqlalchemy import bindparam,text

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_q051_risk_budget_20261109 import daily_metrics

BASE=shared.ROOT
ROOT=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')
CASES={
    'VOL20_REGIME_GROSS2':dict(profile='Q051',pool=.1,long_top_n=5,score=.5,auc=.5,controller=False,gross=2.,per_symbol=True,vol=.2,regime=True),
    'VOL20_REGIME_NO_PER':dict(profile='Q051',pool=.1,long_top_n=None,score=None,auc=None,controller=False,gross=1.,per_symbol=False,vol=.2,regime=True),
    'Q051_NO_PER':dict(profile='Q051',pool=.1,long_top_n=None,score=None,auc=None,controller=False,gross=1.,per_symbol=False,vol=None,regime=False),
    'Q088_NO_PER':dict(profile='Q088',pool=.2,long_top_n=None,score=None,auc=None,controller=True,gross=2.,per_symbol=False,vol=None,regime=False),
    'Q088_NO_PER_VOL20_REGIME':dict(profile='Q088',pool=.2,long_top_n=None,score=None,auc=None,controller=True,gross=2.,per_symbol=False,vol=.2,regime=True),
}
LABELS={
    'VOL20_REGIME_GROSS2':'Volatilité 20 % + régime — plafond 2×',
    'VOL20_REGIME_NO_PER':'Volatilité 20 % + régime — sans per-symbol',
    'Q051_NO_PER':'Q051 — sans per-symbol',
    'Q088_NO_PER':'Q088 — sans per-symbol',
    'Q088_NO_PER_VOL20_REGIME':'Q088 — sans per-symbol + volatilité 20 % + régime',
}


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def select_oracle_only(frame,count):
    """All Oracle candidates, no direction/score/AUC filter, no top-five cap."""
    frame=frame.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).copy()
    if frame.duplicated(['date','symbol']).any():raise ValueError('Duplicate Oracle scores')
    frame['rank']=frame.groupby('date').cumcount()+1
    frame=frame[frame['rank']<=count].copy()
    frame['side']='long';frame['selected']=True
    return frame.rename(columns={'date':'trade_date'})


def prepare(root):
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from backtesting.winner_campaign_replay import validate_scores,SqlIntradaySource
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    from modelFactory.oracle_path.predict import load_contract
    from database.connection import get_sqlalchemy_engine
    inputs=root/'inputs';inputs.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():
        for name,sha in read(inputs/'manifest.json')['files'].items():
            if digest(inputs/name)!=sha:raise ValueError('Prepared input modified: '+name)
        return
    plan=read(BASE/'protocol.json');manifest=read(BASE/'inputs/manifest.json')
    for name,sha in manifest['files'].items():
        if digest(BASE/'inputs'/name)!=sha:raise ValueError('Frozen input modified: '+name)
    (inputs/'market-registry.json').write_bytes((BASE/'inputs/market-registry.json').read_bytes())
    old_pivots,old_sectors,old_actions=shared.market_data(BASE)
    selections={179:[],358:[]}
    for year,model in plan['annual_models'].items():
        frame=pd.read_parquet(BASE/'inputs/rankings'/f'{year}.parquet')
        model_root,contract,_,folds=load_contract('artifacts/models',model['batch_id'])
        dates=sorted(pd.to_datetime(frame.date).dt.date.unique())
        if pd.Timestamp(contract['training_config']['data']['training_end_date'])>=pd.Timestamp(int(year),1,1):
            raise ValueError('Annual model would use future data')
        validate_scores(frame.rename(columns={'date':'trade_date'}),profile_hash=digest(model_root/'feature_profile.json'),
            folds=folds,expected_days=dates,top_n=358,horizon=10,universe_size=len(contract['universe']),min_coverage=.93)
        for count in selections:
            chosen=select_oracle_only(frame,count)
            chosen['oracle_batch_id']=model['batch_id'];chosen['entry_year']=int(year)
            selections[count].append(chosen)
    selections={k:pd.concat(v,ignore_index=True) for k,v in selections.items()}
    for count,frame in selections.items():frame.to_parquet(inputs/f'signals-oracle-{count}.parquet',index=False)
    names=sorted(set(selections[358].symbol)|{'SPY'})
    known=set(old_pivots['close']);new=sorted(set(names)-known)
    registry=shared.restore_registry(BASE)
    with replay_market_registry(registry):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s.session_date for s in calendar.sessions(date(2021,1,1),date(2026,10,1)) if s.is_open]
    windows=shared.supplemental_windows([selections[358]],sessions,set(),horizon=10)
    fully_known=set(manifest['known_symbols'])
    extra_known={d:set() for d in sessions}
    for row in read(BASE/'inputs/extra-price-receipts.json'):
        extra_known[date.fromisoformat(row['day'])].update(row['symbols'])
    source_receipts=[]
    with ReadOnlyReplay(root).install(),replay_market_registry(registry):
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        with engine.connect() as conn,conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            atomic_json(root/'preparation.json',dict(status='FREEZING_EXTRA_DAILY',symbols=len(new)))
            parts=[daily_bars(conn,new[i:i+100],old_pivots['close'].index.min().date(),date(2026,10,1)) for i in range(0,len(new),100)]
            extra=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
            extra.to_parquet(inputs/'daily.parquet',index=False)
            query=lambda sql:pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,
                params=dict(symbols=new)) if new else pd.DataFrame()
            sectors=query('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')
            actions=query("SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events "
                "WHERE symbol IN :symbols AND ex_date BETWEEN '2021-01-01' AND '2026-10-01'")
            sectors.to_parquet(inputs/'sectors.parquet',index=False);actions.to_parquet(inputs/'actions.parquet',index=False)
            source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
            tape=inputs/'intraday';tape.mkdir(exist_ok=True)
            for i,day in enumerate(sessions):
                missing=sorted(windows[day]-fully_known-extra_known[day])
                path=tape/f'{day}.parquet'
                if not path.exists():
                    pieces=[source(day,missing[j:j+100]) for j in range(0,len(missing),100)]
                    pieces=[p for p in pieces if not p.empty]
                    data=pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()
                    data.to_parquet(path,index=False)
                    atomic_json(tape/f'{day}.receipt.json',dict(day=str(day),queried=missing,receipts=source.receipts[-((len(missing)+99)//100):] if missing else []))
                atomic_json(root/'preparation.json',dict(status='FREEZING_EXTRA_5M_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day),symbols=len(missing)))
                if i%20==0:print('Additional prices',i+1,'/',len(sessions),day,flush=True)
    files={str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*') if p.is_file()}
    atomic_json(inputs/'manifest.json',dict(files=files,original_prices_unchanged=True,
        original_manifest_sha256=digest(BASE/'inputs/manifest.json'),supplement='ONLY_PREVIOUSLY_UNQUERIED_SYMBOL_DAY_PAIRS',
        strict_pit=False,provider_calls=0,SQL_writes=0,prepared_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(root/'preparation.json',dict(status='INPUTS_FROZEN',sessions=len(sessions),extra_symbols=len(new)))


class ExtendedPrices(shared.FrozenPrices):
    def __init__(self,root):super().__init__(BASE);self.extra=Path(root)
    @lru_cache(maxsize=6)
    def day(self,day):
        base=super().day(day)
        extra=pd.read_parquet(self.extra/'inputs/intraday'/f'{day}.parquet')
        groups=dict(base)
        for symbol,g in extra.groupby('symbol') if not extra.empty else []:
            if symbol in groups:raise ValueError('Supplement would overwrite original prices')
            groups[symbol]=g
        return groups


def run_case(root,name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    root=Path(root);folder=root/'cases'/name;out=folder/'result'
    if (folder/'progress.json').exists() and read(folder/'progress.json').get('status')=='COMPLETED_EXPLORATORY':
        return dict(case=name,folder=str(folder))
    folder.mkdir(parents=True,exist_ok=False);out.mkdir()
    try:
        plan=read(BASE/'protocol.json');case=deepcopy(CASES[name]);cfg=shared.configuration(plan['reference'],case)
        pivots,sectors,actions=shared.market_data(BASE)
        if not case['per_symbol']:
            for field in pivots:
                d=pd.read_parquet(root/'inputs/daily.parquet')
                if not d.empty:pivots[field]=pd.concat([pivots[field],d.pivot(index='date',columns='symbol',values=field)],axis=1).sort_index()
            sectors=pd.concat([sectors,pd.read_parquet(root/'inputs/sectors.parquet')],ignore_index=True)
            actions=pd.concat([actions,pd.read_parquet(root/'inputs/actions.parquet')],ignore_index=True)
        signals=pd.read_parquet(BASE/'inputs/signals-Q051_050.parquet') if case['per_symbol'] else pd.read_parquet(root/'inputs'/f'signals-oracle-{round(1790*case["pool"])}.parquet')
        reference=deepcopy(plan['reference']);reference['risk']=asdict(cfg.risk_config)
        reference['arguments'].update(top_n=round(1790*case['pool']),per_symbol_long=case['per_symbol'],
            per_symbol_top_long=case['long_top_n'],per_symbol_min_long_probability=case['score'],per_symbol_min_long_auc=case['auc'],
            drawdown_controller=case['controller'],portfolio_vol_target=case['vol'],entry_regime_filter=case['regime'])
        reference['per_symbol_selection']=shared.settings(case,1790).snapshot() if case['per_symbol'] else None
        reference['drawdown_controller']={'enabled':case['controller']}
        protocol={**plan,'reference':reference,'profile':case,'case':name,'start':'2021-01-01','end':'2026-10-01',
            'new_sources':read(root/'request.json')['sources'],'signals_sha256':digest(BASE/'inputs/signals-Q051_050.parquet') if case['per_symbol'] else digest(root/'inputs'/f'signals-oracle-{round(1790*case["pool"])}.parquet'),
            'replay_command':[sys.executable,'-m','scripts.research.us_winner_vol20_extensions_20261109','--output-dir',str(root),'--resume'],
            'entry_budget':dict(target=case['vol'],lookback=60),'regime':dict(enabled=case['regime'],sma=200,threshold=-.02)}
        atomic_json(folder/'protocol.json',protocol)
        atomic_json(out/'configuration.json',dict(profile=case,portfolio=asdict(cfg)))
        policy,gate=replay_protections(pivots['close'],daily_entry=True,target=case['vol'],regime=case['regime'])
        source=shared.FrozenPrices(BASE) if case['per_symbol'] else ExtendedPrices(root)
        def no_http(*a,**kw):raise ValueError('No HTTP in frozen replay')
        started=time.monotonic()
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
            def progress(done,total,day):
                state=dict(status='RUNNING',case=name,completed=done,total=total,last_date=str(day),elapsed_seconds=time.monotonic()-started)
                atomic_json(folder/'progress.json',state);atomic_json(out/'progress.json',state)
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],volume=pivots['volume'],
                signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),intraday_source=source,
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=actions.to_dict('records'),
                winner_selection_source=gate,winner_entry_risk_policy=policy)
            pd.DataFrame(policy.receipts if policy else []).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            pd.DataFrame(gate.receipts if gate else []).to_csv(out/'regime-decisions.csv',index=False)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            report=metrics(result,4000.);report.update(daily_metrics(result.equity_curve));annual=[];opening=4000.
            for year in sorted(result.equity_curve.index.year.unique()):
                curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=int(year),model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=name,profile=case,annual_models=plan['annual_models'],annual_reset=False,selected_signals=len(signals),
                provider_calls=0,broker_calls=0,SQL_writes=0,strict_pit=False,elapsed_seconds=time.monotonic()-started,
                portfolio_risk_audit=dict(decisions=len(policy.receipts) if policy else 0,missing_history=sum(r['status']=='UNQUALIFIED_HISTORY' for r in policy.receipts) if policy else 0),
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report)
            atomic_json(out/'progress.json',dict(status=report['status'],completed=len(result.equity_curve),total=len(result.equity_curve)))
            atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        return dict(case=name,folder=str(folder))
    except Exception as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def chart(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    curves={}
    for name in CASES:
        p=root/'cases'/name/'result/equity-daily.csv'
        if p.exists() and (p.parent/'report.json').exists():curves[LABELS[name]]=pd.read_csv(p,index_col=0,parse_dates=True).iloc[:,0]
    curves['Q051 témoin']=pd.read_csv(BASE/'cases/Q051_050/result/equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
    previous=Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result/equity-daily.csv')
    curves['Volatilité 20 % + régime — référence']=pd.read_csv(previous,index_col=0,parse_dates=True).iloc[:,0]
    prices=shared.market_data(BASE)[0]
    spy=prices['close']['SPY'].loc['2021-01-01':'2026-10-01'];opening=prices['open']['SPY'].loc[spy.index].iloc[0]
    curves['SPY (hors dividendes et frais)']=4000.*spy/opening
    frame=pd.DataFrame(curves).sort_index();frame.loc[pd.Timestamp('2021-01-01')]=4000.;frame=frame.sort_index()
    charts=root/'charts';charts.mkdir(exist_ok=True);frame.to_csv(charts/'capital-comparison.csv',index_label='date')
    fig,axes=plt.subplots(2,1,figsize=(16,11),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for column in frame:
        style='--' if column.startswith('SPY') else '-'
        axes[0].plot(frame.index,frame[column],style,label=column,linewidth=1.6)
        axes[1].plot(frame.index,100*(frame[column]/frame[column].cummax()-1),style,linewidth=1.)
    axes[0].set_title('Oracle H10 · cinq variantes · 2021–2026 · capital initial 4 000 $')
    axes[0].set_ylabel('Capital valorisé ($)');axes[1].set_ylabel('Drawdown journalier (%)')
    axes[0].legend(fontsize=9,loc='upper left');axes[0].grid(alpha=.2);axes[1].grid(alpha=.2)
    fig.text(.07,.015,'Stratégies : frais et financement inclus ; SPY hors dividendes/frais. Couverture 5m incomplète. Résultats exploratoires.',fontsize=10)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(charts/'capital-comparison.png',dpi=160);fig.savefig(charts/'capital-comparison.svg');plt.close(fig)


def run(root,resume=False):
    if not resume:root.mkdir(parents=True,exist_ok=False)
    plan=read(BASE/'protocol.json')
    sources={str(p):digest(p) for p in [Path(__file__),Path('backtesting/simulator.py'),*Path('backtesting').glob('winner*.py')]}
    if not (root/'request.json').exists():atomic_json(root/'request.json',dict(cases=CASES,start='2021-01-01',end='2026-10-01',initial_equity=4000.,
        annual_models=plan['annual_models'],sources=sources,annual_reset=False,provider_calls=0,SQL_writes=0,broker_calls=0))
    for name,sha in read(root/'request.json')['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Source changed after campaign launch: '+name)
    results=[];failures=[]
    def collect(future,name):
        try:
            value=future.result()
            from ihm.services.backtesting_import import import_continuous_winner
            record=import_continuous_winner(value['folder'],run_id=f'20261109_continu_{name}_ext_v1',label='Continu H10 2021–2026 — '+LABELS[name],result_subdir='result')
            value['ihm_run_id']=record['run_id'];results.append(value)
        except Exception as exc:failures.append(dict(case=name,error_type=type(exc).__name__,error=str(exc)))
        atomic_json(root/'progress.json',dict(status='RUNNING_FIVE_CASES',completed=len(results)+len(failures),total=5,results=results,failures=failures))
    with ProcessPoolExecutor(max_workers=3,mp_context=get_context('spawn')) as pool:
        first=pool.submit(run_case,str(root),'VOL20_REGIME_GROSS2')
        atomic_json(root/'progress.json',dict(status='RUNNING_FIRST_AND_PREPARING_OTHER_FOUR',completed=0,total=5))
        prepare(root)
        futures={pool.submit(run_case,str(root),name):name for name in CASES if name!='VOL20_REGIME_GROSS2'}
        futures[first]='VOL20_REGIME_GROSS2'
        for future in as_completed(futures):collect(future,futures[future])
    rows=[]
    for value in results:
        r=read(Path(value['folder'])/'result/report.json')
        rows.append(dict(case=value['case'],**{k:r.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','daily_max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital','maximum_gross_capital','costs','margin_interest']}))
    pd.DataFrame(rows).to_csv(root/'comparison.csv',index=False);chart(root)
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY' if not failures else 'INCOMPLETE_CASES',results=results,failures=failures,
        chart=str(root/'charts/capital-comparison.png'),provider_calls=0,SQL_writes=0,broker_calls=0))
    atomic_json(root/'progress.json',read(root/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    try:run(args.output_dir,args.resume)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
