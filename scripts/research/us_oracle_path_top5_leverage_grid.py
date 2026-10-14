"""Annual supplied path models, real chronological research ledger, TOP5 LONG.

144 frozen exit profiles, no training/SQL writes/broker calls. Native shared
risk/execution/accounting, explicit 2x leverage, financed cash and open MTM.
Not historical broker certification: marginability/dividends are unqualified.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, fields, replace
from functools import partial
import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from backtesting.risk_overlay import SectoralCapConfig
from execution_engine.config import ExecutionConfig, LeverageConfig
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.predict import load_contract, select_fold
from modelFactory.oracle_path.train import model_probabilities, restore_ranks
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_concentrated_fixed_stop import fixed_stop_protections
from scripts.research.us_oracle_barrier_comparison import SECTORS
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_trailing_grid import trailing_protections
from scripts.research.us_oracle_path_economic_replay import qualify_entries
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
from service.market import parse_market_regimes

LOG=logging.getLogger(__name__)
MODELS={2024:'model-factory-20261014052407-a4bd20',2025:'model-factory-20261014052414-155d09',
        2026:'model-factory-20261014052423-4df571'}
ARCHIVE=Path('artifacts/research/oracle_path_confirmation/20261013-v1')
BASE=Path('artifacts/research/us_oracle_path_economic/20261013-v1')
SLS=(.05,.07,.10)
TRAILS=(None,.10,.15,.20)
TPS=(None,.10,.20,.30)
ENDS={2024:'2024-12-31',2025:'2025-12-31',2026:'2026-09-30'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def key(case):
    y,sl,trail,tp=case
    return f'{y}-SL{sl*100:g}-TRAIL'+('OFF' if trail is None else f'{trail*100:g}')+'-TP'+('OFF' if tp is None else f'{tp*100:g}')


def planned_cases():
    return [(year,sl,trail,tp) for year in MODELS for sl in SLS for trail in TRAILS for tp in TPS]


@dataclass(frozen=True,slots=True)
class ResearchMarginExecutionConfig(ExecutionConfig):
    """Isolated 2x cap extension; production's legacy validation stops at 1x.

    All other native config validations run unchanged. This does NOT remove
    regime caps below one, nor the native execution buying-power constraints.
    Dataclass replace retains the subtype through the chronological loop.
    """
    def __post_init__(self):
        cap=self.regime_max_gross_exposure
        if cap is not None and (not np.isfinite(cap) or not 0<float(cap)<=2):
            raise ValueError('Research execution cap must remain in (0,2]')
        object.__setattr__(self,'regime_max_gross_exposure',min(cap,1.) if cap is not None else None)
        try:
            ExecutionConfig.__post_init__(self)
        finally:
            object.__setattr__(self,'regime_max_gross_exposure',cap)


def configure_leverage(cfg, sl):
    # Aggressive research allocation: <=40% equity per position, <=200% total.
    # SL-adjusted risk budget makes this independent of different SL distances.
    # Native market/circuit/diversification constraints may reduce it further.
    cfg.risk_config=replace(cfg.risk_config, fixed_stop_pct=sl, risk_per_trade_pct=.4*sl,
        max_position_weight=.4,max_gross_exposure=2.,max_long_exposure=2.,max_sector_weight=1.,sizing_mode='atr')
    original={f.name:getattr(cfg.exec_config,f.name) for f in fields(ExecutionConfig) if f.init}
    cfg.exec_config=replace(ResearchMarginExecutionConfig(**original),leverage=LeverageConfig(enabled=True,mode='regt_swing',
        max_leverage=2.,dry_run_simulated_leverage=2.,only_in_entry_mode='normal',
        disable_in_capital_preservation=True,min_equity_usd=2000.),
        simulated_margin_buying_power_multiplier=2.,regime_max_gross_exposure=2.)
    cfg.risk_overlay=replace(cfg.risk_overlay,sectoral_cap=SectoralCapConfig(enabled=True,max_sector_exposure_pct=1.))
    cfg.margin_interest_rate_annual=.065
    return cfg


def maintenance_requirement(positions, prices):
    total=0.
    for symbol,pos in positions.items():
        p=float(prices[symbol])
        if not np.isfinite(p) or p<=0:
            raise ValueError('Unknown maintenance mark')
        fraction=1. if p<2.5 else .5 if p<=6. else .3
        total+=float(pos.quantity)*p*fraction
    return total


class UnlimitedLedger(GridLedger):
    """Research subclass only; native core and other studies stay unchanged."""
    def __init__(self,cfg,*args,sl,trail,tp,study_end,**kwargs):
        self.sl,self.trail,self.tp=sl,trail,tp
        self.study_end=pd.Timestamp(study_end)
        self.terminal_exits_suppressed=0
        self.margin_audits=[]
        self.margin_breached=False
        configure_leverage(cfg,sl)
        super().__init__(cfg,*args,tp_pct=tp or .2,sl_pct=sl,**kwargs)

    def _build_entry_protections(self,phase3,*,execution_config):
        if self.tp is None:
            protection=OraclePortfolioLedger._build_entry_protections(self,phase3,execution_config=execution_config)
            protection=fixed_stop_protections(protection,self.sl)
        else:
            protection=super()._build_entry_protections(phase3,execution_config=execution_config)
        return trailing_protections(protection,self.trail)

    def close_resolved(self,exits,*,phase):
        actual=[e for e in exits if e['exit_reason']!='terminal_close']
        self.terminal_exits_suppressed+=len(exits)-len(actual)
        return super().close_resolved(actual,phase=phase)

    def _accrue_margin_interest(self,state,*,annual_rate,sessions_per_year=252):
        # Calendar days, including weekends, ACT/360; current fixed-rate assumption.
        index=self.days.get_loc(self.current_day)
        next_day=self.days[index+1] if index+1<len(self.days) else self.current_day+pd.Timedelta(days=1)
        boundary=min(next_day,self.study_end+pd.Timedelta(days=1))
        days=max(1,(boundary-self.current_day).days)
        debit=max(-float(state.settled_cash),0.)
        charge=debit*float(annual_rate)*days/360.
        state.settled_cash-=charge
        return charge

    def reconciliation_error(self):
        # Unsold positions retain entry costs; do not pretend they are closed cash.
        if self.unvalued_claims:
            raise ValueError('Unvalued corporate-action claim prevents complete wealth')
        expected=self.config.initial_equity+sum(t['pnl'] for t in self.state.closed_trades)-self.interest
        expected-=sum(p.entry_cost for p in self.state.positions.values())
        return self.state.settled_cash+self.state.unsettled_cash-expected


class MarginAwareSession(OraclePortfolioSession):
    def __init__(self,*args,ledger_ref,**kwargs):
        self.ledger_ref=ledger_ref
        super().__init__(*args,**kwargs)

    def decide(self,day,*,scores,**kwargs):
        if self.ledger_ref[0].margin_breached:
            scores=scores.iloc[:0]
        return super().decide(day,scores=scores,**kwargs)


def margin_policy(day,ledger,frames):
    # Called after today's intraday protections; evaluate observed close only.
    equity=ledger.equity_unchecked()
    requirement=maintenance_requirement(ledger.state.positions,frames['close'].loc[day])
    ledger.margin_breached=equity<requirement
    ledger.margin_audits.append(dict(date=str(day.date()),equity=equity,required=requirement,
        breach=ledger.margin_breached))
    return [dict(symbol=symbol,entry_date=p.entry_date,decision_date=day,
        policy_reason='MAINTENANCE_MARGIN_FULL_EXIT_NEXT_OPEN')
        for symbol,p in ledger.state.positions.items()] if ledger.margin_breached else []


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'ready.json').exists():
        saved=read(output/'ready.json');verify_hashes(Path('.'),saved['sources']);verify_hashes(output,saved['files'])
        return saved
    if (output/'protocol.json').exists():
        raise ValueError('Incomplete preparation: use a fresh output ID')
    old=read(BASE/'manifest.json')
    verify_hashes(Path('.'),old['source_hashes']);verify_hashes(Path('.'),old['code_hashes'])
    source_profile=read(Path(read(ARCHIVE/'plan.json')['source'])/'models/oracle-path-comparison/oracle_path/feature_profile.json')
    contracts={}
    sources={str(BASE/'manifest.json'):digest(BASE/'manifest.json')}
    for p in [ARCHIVE/'plan.json',ARCHIVE/'scores.parquet',
              Path(read(ARCHIVE/'plan.json')['source'])/'models/oracle-path-comparison/oracle_path/feature_profile.json']:
        sources[str(p)]=digest(p)
    for year,batch in MODELS.items():
        root,protocol,profile,folds=load_contract('artifacts/models',batch)
        if profile['generator_options']!=source_profile['generator_options'] or profile['feature_columns']!=source_profile['feature_columns']:
            raise ValueError('Historical feature cache contract differs from supplied model')
        if set(protocol['universe'])!=set(read(ARCHIVE/'plan.json')['universe']):
            raise ValueError('Universes differ; no partial-universe cross-sectional ranks')
        first=nyse_sessions(f'{year}-01-01',ENDS[year])[0]
        chosen=select_fold(first,folds)
        if any(select_fold(day,folds)!=chosen for day in nyse_sessions(f'{year}-01-01',ENDS[year])):
            raise ValueError('Annual frozen-fold protocol needs update for an intra-year refresh')
        fold=folds[chosen]
        contracts[str(year)]=dict(batch_id=batch,fold=chosen,backend=fold['backend'],
            train_available_max=fold['metrics']['train_available_max'],val_available_max=fold['metrics']['val_available_max'],
            model_file=fold['model_file'],model_sha256=fold['model_sha256'])
        for p in [root/'protocol.json',root/'feature_profile.json',root/'report.json',root/'folds'/chosen/'done.json',Path(fold['model_file'])]:
            sources[str(p)]=digest(p)
    sources.update(code_hashes())
    for name in ['us_concentrated_live_portfolio.py','us_concentrated_fixed_stop.py','us_oracle_barrier_exit_grid.py',
                 'us_oracle_barrier_trailing_grid.py','us_oracle_path_top5_leverage_grid.py']:
        p=Path('scripts/research')/name;sources[str(p)]=digest(p)
    protocol=dict(models=contracts,top=5,direction='LONG_EXPLICIT_NOT_LEARNED',years=ENDS,
        grid={'sl':SLS,'trailing':TRAILS,'tp':TPS},cases=144,capital_usd=4000.,max_entry_leverage=2.,
        position_cap_equity=.4,sl_risk_budget_formula='.4 * SL fraction, before native regime/vol/circuit limits',
        sector_cap_equity=1.,max_positions=8,no_same_symbol_reinforcement=True,
        reject_constrained_entries=True,quantity_policy='native whole-order rejection if next-open portfolio budget cannot honor J approval',
        forced_h20_exit=False,terminal_liquidation=False,annual_capital_reset=True,
        margin_rate_annual=.065,interest_basis='calendar days ACT/360, debit EOD; no historical rate/settlement reconstruction',
        maintenance='assumed price tiers 100% below2.5;50% through6;30% above6; breach exit next open, no new approvals',
        trailing='prior-session running high only; never loosen initial SL; activation from no-looser threshold',
        sources=sources,sql_writes=False,broker_calls=False,training=False,
        selection_warning='best grid result is in-sample exploratory selection, not validated optimal exits',
        reserves=['current survivor universe and sectors; adjusted vendor OHLC, no real bid/ask/fills',
            'historical broker marginability and individual maintenance requirements unverified',
            'dividend data incomplete (40 source records at audit); excludes unqualified cash distributions, NOT total return',
            'macro vintages not PIT-certified; 2026 partial; corporate actions fail closed on missing cash',
            'macro/risk guards may reduce entries and leverage; end-of-day leverage can drift beyond2 after price changes'])
    atomic_json(output/'protocol.json',protocol)
    observable=pd.read_parquet(ARCHIVE/'scores.parquet',columns=['date','symbol'])
    observable.date=pd.to_datetime(observable.date)
    score_parts=[]
    for year,contract in contracts.items():
        year=int(year);profile=load_contract('artifacts/models',contract['batch_id'])[2]
        parts=[]
        for i,folder in enumerate(sorted((ARCHIVE/'chunks').iterdir())):
            done=read(folder/'done.json');verify_hashes(folder,{'features.parquet':done['files']['features.parquet']})
            sources[str(folder/'done.json')]=digest(folder/'done.json')
            p=folder/'features.parquet';sources[str(p)]=digest(p)
            f=pd.read_parquet(p);f.date=pd.to_datetime(f.date)
            f=f[f.date.between(f'{year}-01-01',ENDS[year])].copy()
            f=f.drop(columns=[c for c in f if c.endswith('_xs_rank')])
            parts.append(f)
            if i%12==0:
                atomic_json(output/'progress.json',dict(status='PREPARING',year=year,chunks=i,total_chunks=72))
        matrix=restore_ranks(pd.concat(parts,ignore_index=True),profile['generator_options'])
        del parts;gc.collect()
        matrix=matrix.merge(observable,on=['date','symbol'],how='inner',validate='one_to_one')
        cols=profile['feature_columns'];matrix[cols]=matrix[cols].replace([np.inf,-np.inf],np.nan).astype(np.float32)
        if contract['backend']=='catboost':
            from catboost import CatBoostClassifier
            model=CatBoostClassifier().load_model(contract['model_file'])
            names=model.feature_names_
        else:
            import lightgbm as lgb
            model=lgb.Booster(model_file=contract['model_file']);names=model.feature_name()
        if names!=cols:
            raise ValueError('Feature order differs')
        scores=matrix[['date','symbol']].copy()
        scores['score']=(model.predict_proba(matrix[cols],thread_count=4)[:,1]
            if contract['backend']=='catboost' else model_probabilities(model,contract['backend'],matrix[cols]))
        scores['proba_extreme']=scores.groupby('date').score.rank(method='average',pct=True)
        scores=scores.sort_values(['date','score','symbol'],ascending=[True,False,True])
        scores['oracle_rank']=scores.groupby('date').cumcount()+1
        scores=scores[scores.oracle_rank.le(5)].copy();scores['selected']=True
        scores['year']=year;scores['fold_start']=contract['fold'];scores['backend']=contract['backend']
        score_parts.append(scores)
        del matrix,model;gc.collect()
        LOG.info('Scored %s TOP5 %s rows',year,len(scores))
    prices_path=Path(old['tapes'])/'prices.parquet'
    prices=pd.read_parquet(prices_path);prices.date=pd.to_datetime(prices.date)
    calendar=nyse_sessions('2023-01-01','2026-10-09')
    candidates=qualify_entries(pd.concat(score_parts,ignore_index=True),prices,calendar)
    candidates.to_parquet(output/'candidates.parquet',index=False)
    macro=pd.read_parquet(BASE/'macro.parquet');macro.trade_date=pd.to_datetime(macro.trade_date)
    for year,end in ENDS.items():
        days=nyse_sessions(f'{year}-01-01',end)
        if len(days.difference(pd.DatetimeIndex(macro.trade_date))):
            raise ValueError('Missing macro date; never forward-fill')
        if set(days)!=set(candidates.loc[candidates.year.eq(year),'date']):
            raise ValueError('Missing scoring day')
    # Shared tapes are read in workers; no redundant full-price rewrite.
    sources[str(prices_path)]=digest(prices_path);sources[str(BASE/'macro.parquet')]=digest(BASE/'macro.parquet')
    sources[str(SECTORS)]=digest(SECTORS)
    ready=dict(sources=sources,files={'candidates.parquet':digest(output/'candidates.parquet')},
        prices=str(prices_path),macro=str(BASE/'macro.parquet'),events=old['events'],market=old['market'])
    atomic_json(output/'ready.json',ready)
    verify_hashes(Path('.'),sources)
    atomic_json(output/'progress.json',dict(status='READY',cases=144))
    return ready


_CACHE=None


def worker_init(output):
    global _CACHE
    root=Path(output);ready=read(root/'ready.json')
    prices=pd.read_parquet(ready['prices']);prices.date=pd.to_datetime(prices.date)
    candidates=pd.read_parquet(root/'candidates.parquet')
    required=set(candidates.symbol)|{'SPY','VMRK'}
    for event in ready['events']:
        if event['source'] in required:required.add(event['target'])
    prices=prices[prices.symbol.isin(required)].copy()
    sectors=pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict();sectors['VMRK']=sectors['EQR']
    sectors['TELWY']=sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    calendar=nyse_sessions('2023-01-01','2026-10-09')
    frames={key:prices.pivot(index='date',columns='symbol',values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    _CACHE=dict(root=root,ready=ready,prices=prices,candidates=candidates,sectors=sectors,frames=frames,
        macro=ArchivedMacro(pd.read_parquet(ready['macro'])),market=parse_market_regimes(ready['market']))


def run_case(case):
    year,sl,trail,tp=case;root=_CACHE['root']/key(case);root.mkdir(exist_ok=True)
    marker=root/'case-report.json'
    if marker.exists():
        saved=read(marker)
        if saved['status']=='COMPLETED_SIMULATED_ASSUMPTIONS':
            verify_hashes(root,saved['files']);return saved
    ref=[]
    def ledger_factory(cfg,**kwargs):
        ledger=UnlimitedLedger(cfg,sl=sl,trail=trail,tp=tp,study_end=ENDS[year],
            cash_policy='STRICT',events=_CACHE['ready']['events'],**kwargs)
        ref.append(ledger);return ledger
    base=dict(case=key(case),year=year,sl=sl,trailing=trail,tp=tp,batch_id=MODELS[year])
    try:
        with (root/'stderr.log').open('a',encoding='utf-8') as log,redirect_stdout(log),redirect_stderr(log):
            logging.basicConfig(level=logging.WARNING,stream=log,force=True)
            result=run_portfolio(frames=_CACHE['frames'],scores=_CACHE['candidates'].loc[_CACHE['candidates'].year.eq(year)],
                sectors=_CACHE['sectors'],macro=_CACHE['macro'],market_config=_CACHE['market'],policy='selected',
                variant='CURRENT_NO_EXPIRY',output=root,start_date=f'{year}-01-01',end_date=ENDS[year],
                quality=_CACHE['prices'][['date','symbol','is_filled','instrument_id']],ledger_factory=ledger_factory,
                session_factory=partial(MarginAwareSession,ledger_ref=ref),
                protection_options=dict(take_profit_enabled=tp is not None,trailing_enabled=trail is not None),
                daily_exit_policy=margin_policy,reject_constrained_entries=True)
        ledger=ref[0];daily=pd.read_parquet(root/'daily.parquet');trades=pd.read_parquet(root/'trades.parquet')
        # The last session has no next-open order, but its margin still matters.
        required=maintenance_requirement(ledger.state.positions,_CACHE['frames']['close'].loc[ENDS[year]])
        ledger.margin_audits.append(dict(date=ENDS[year],equity=float(daily.equity.iloc[-1]),
            required=required,breach=float(daily.equity.iloc[-1])<required,final_mark_only=True))
        open_rows=[dict(symbol=s,quantity=p.quantity,entry_date=str(p.entry_date.date()),entry_price=p.entry_price,
            entry_cost=p.entry_cost,mark=float(ledger.close.at[pd.Timestamp(ENDS[year]),s]),
            unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(ENDS[year]),s])-p.entry_cost)
            for s,p in ledger.state.positions.items()]
        atomic_json(root/'open-positions.json',open_rows);atomic_json(root/'maintenance.json',ledger.margin_audits)
        realized=float(trades.pnl.sum()) if not trades.empty else 0.
        unrealized=sum(x['unrealized_pnl_usd'] for x in open_rows)
        expected=4000.+realized+unrealized-ledger.interest
        if not np.isclose(expected,daily.equity.iloc[-1],atol=1e-6,rtol=1e-10):raise ValueError('Open-MTM equity reconciliation failure')
        if not trades.empty:
            if trades.exit_reason.isin(['terminal_close','expiry_open','expiry_20_after_entry']).any():raise ValueError('Forbidden time/terminal exit')
            if not trades.side.eq('buy').all():raise ValueError('Unexpected short')
            if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*(1-sl),rtol=1e-7,atol=1e-6).all():raise ValueError('SL anchor changed')
        gross=daily.gross_notional/daily.equity
        result.update(base,status='COMPLETED_SIMULATED_ASSUMPTIONS',final_capital_usd=float(daily.equity.iloc[-1]),
            net_return_pct=100*result['return_pct'],dd_pct=100*result['max_drawdown'],
            realized_pnl_usd=realized,unrealized_pnl_usd=unrealized,open_positions=len(open_rows),
            mean_gross_leverage=float(gross.mean()),max_gross_leverage=float(gross.max()),
            leveraged_days=int(gross.gt(1).sum()),margin_breaches=sum(x['breach'] for x in ledger.margin_audits),
            terminal_exits_suppressed=ledger.terminal_exits_suppressed,
            historical_marginability_certified=False,dividends_complete=False,
            sizing_unchanged=False,trailing_unchanged=trail is None,
            files={p.name:digest(p) for p in root.iterdir() if p.suffix in ['.json','.parquet'] and p.name!='case-report.json'})
    except Exception as exc:
        result=dict(base,status='FAILED',error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result)
    return result


def run(output,phase='all',workers=3):
    output=Path(output)
    with exclusive_run(output):
        ready=prepare(output)
        if phase=='prepare':return
        cases=planned_cases()
        reports=[]
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(output),)) as pool:
            futures={pool.submit(run_case,c):c for c in cases}
            for future in as_completed(futures):
                result=future.result();reports.append(result)
                failures=sum(x['status']=='FAILED' for x in reports)
                atomic_json(output/'progress.json',dict(status='RUNNING',completed=len(reports),failed=failures,total=len(cases),last=result['case']))
                atomic_json(output/'report.partial.json',dict(cases=reports,completed=len(reports),total=len(cases)))
                LOG.info('%s %s/%s %s',result['case'],len(reports),len(cases),result['status'])
        verify_hashes(Path('.'),ready['sources']);verify_hashes(output,ready['files'])
        complete=[x for x in reports if x['status']=='COMPLETED_SIMULATED_ASSUMPTIONS']
        pd.DataFrame(complete).drop(columns=['files','unvalued_fractional_claims'],errors='ignore').to_csv(output/'annual-summary.csv',index=False)
        best={str(y):sorted([r for r in complete if r['year']==y],key=lambda r:r['net_return_pct'],reverse=True)[:5] for y in MODELS}
        stability=[]
        for sl in SLS:
            for trail in TRAILS:
                for tp in TPS:
                    rows=[r for r in complete if (r['sl'],r['trailing'],r['tp'])==(sl,trail,tp)]
                    if len(rows)!=len(MODELS):continue
                    stability.append(dict(sl=sl,trailing=trail,tp=tp,completed_years=len(rows),
                        mean_annual_net_return_pct=float(np.mean([r['net_return_pct'] for r in rows])),
                        worst_year_net_return_pct=min(r['net_return_pct'] for r in rows),
                        worst_dd_pct=min(r['dd_pct'] for r in rows),
                        positive_years=sum(r['net_return_pct']>0 for r in rows),
                        mean_gross_leverage=float(np.mean([r['mean_gross_leverage'] for r in rows])),
                        margin_breaches=sum(r['margin_breaches'] for r in rows)))
        stability.sort(key=lambda r:r['mean_annual_net_return_pct'],reverse=True)
        pd.DataFrame(stability).to_csv(output/'cross-year-summary.csv',index=False)
        failed=[x for x in reports if x['status']=='FAILED']
        status='COMPLETED_EXPLORATORY' if not failed else 'PARTIAL_FAILED'
        atomic_json(output/'report.json',dict(status=status,cases=reports,best_observed_by_year=best,cross_year_profiles=stability,
            completed=len(complete),failed=len(failed),total=len(cases),source_hashes_verified=True,
            optimal_out_of_sample_proven=False,production_changed=False))
        atomic_json(output/'progress.json',dict(status=status,completed=len(complete),failed=len(failed),total=len(cases)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--phase',choices=['all','prepare','run'],default='all')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=3)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    try:
        run(**vars(args))
    except Exception as exc:
        Path(args.output).mkdir(parents=True,exist_ok=True)
        atomic_json(Path(args.output)/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
