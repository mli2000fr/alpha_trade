"""One frozen entry-context protection rule versus the identical fixed TOP5 ledger.

No training, SQL, broker calls or production changes. Protections are chosen
at J close and anchored to the actual J+1 fill, then retained for that position.
The already inspected 2024-2026 periods are exploratory, not a new holdout.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import parametric_protections
from scripts.research.us_oracle_barrier_trailing_grid import trailing_protections
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes

LOG=logging.getLogger(__name__)
SOURCE=Path('artifacts/research/us_oracle_path_top5_leverage/20261014-v3')
PROFILES={'REFERENCE':(.15,.20),'DEFENSIVE':(.10,.10),'TREND':(.20,.30)}


@dataclass(frozen=True)
class Rules:
    minimum_breadth_coverage: float=.8
    weak_breadth: float=.4
    strong_breadth: float=.6
    stress_vix: float=30.
    calm_vix: float=20.


RULES=Rules()


def choose_profile(context, mode, rules=RULES):
    """Pure rule: no outcome, year or next-open data may affect selection."""
    columns=('vix','spy_close','spy_sma200','spy_ret20','breadth50',
             'breadth_coverage','stock_close','stock_sma50','relative_ret20')
    if any(context.get(c) is None or not np.isfinite(float(context[c])) for c in columns):
        return 'REFERENCE','MISSING_INPUT_BASELINE'
    if context['breadth_coverage']<rules.minimum_breadth_coverage:
        return 'REFERENCE','LOW_BREADTH_COVERAGE_BASELINE'
    mode=getattr(mode,'value',mode)
    if mode not in {'normal','capital_preservation','close_only','cash_only'}:
        raise ValueError('Unknown causal market regime')
    if (mode!='normal' or context['vix']>=rules.stress_vix
        or context['breadth50']<rules.weak_breadth
        or (context['spy_close']<context['spy_sma200'] and context['breadth50']<.5)):
        return 'DEFENSIVE','REGIME_OR_MARKET_WEAKNESS'
    if (context['vix']<=rules.calm_vix and context['spy_close']>context['spy_sma200']
        and context['spy_ret20']>0 and context['breadth50']>=rules.strong_breadth
        and context['relative_ret20']>0 and context['stock_close']>context['stock_sma50']):
        return 'TREND','BROAD_TREND_AND_POSITIVE_RELATIVE_STRENGTH'
    return 'REFERENCE','INTERMEDIATE_CONTEXT'


def build_context(prices, macro, universe, candidates):
    """Rolling/backward windows only; full frozen universe, never TOP5 breadth."""
    prices=prices.copy();prices['date']=pd.to_datetime(prices.date)
    if prices.duplicated(['date','symbol']).any():raise ValueError('Duplicate price')
    calendar=grid.nyse_sessions('2023-01-01','2026-10-09')
    prices=prices[prices.symbol.isin(set(universe)|{'SPY'})].copy()
    valid=(prices.close.gt(0)&prices.volume.gt(0)&prices.is_filled.fillna(0).eq(0))
    prices.loc[~valid,'close']=np.nan
    closes=prices.pivot(index='date',columns='symbol',values='close').reindex(calendar)
    sma50=closes.rolling(50,min_periods=50).mean()
    returns20=closes/closes.shift(20)-1
    population=closes.reindex(columns=universe)
    population_ma=sma50.reindex(columns=universe)
    eligible=population.notna()&population_ma.notna()
    count=eligible.sum(axis=1)
    breadth=(population.gt(population_ma)&eligible).sum(axis=1)/count.replace(0,np.nan)
    coverage=count/len(universe)
    m=macro.copy();m['trade_date']=pd.to_datetime(m.trade_date)
    if m.trade_date.duplicated().any():raise ValueError('Duplicate macro')
    market=pd.DataFrame({'spy_close':closes.SPY,'spy_sma200':closes.SPY.rolling(200,min_periods=200).mean(),
        'spy_ret20':returns20.SPY,'breadth50':breadth,'breadth_coverage':coverage,
        'breadth_count':count,'vix':m.set_index('trade_date').vix.reindex(calendar)})
    rows=[]
    for row in candidates.itertuples(index=False):
        day=pd.Timestamp(row.date);symbol=row.symbol
        values=market.loc[day].to_dict()
        values.update(date=day,symbol=symbol,stock_close=closes.at[day,symbol],
            stock_sma50=sma50.at[day,symbol],relative_ret20=returns20.at[day,symbol]-returns20.at[day,'SPY'])
        rows.append(values)
    context=pd.DataFrame(rows)
    if context.duplicated(['date','symbol']).any():raise ValueError('Duplicate context')
    return context


class ContextSession(grid.MarginAwareSession):
    def decide(self,day,*,scores,regime,**kwargs):
        # Native risk still observes its own same-date, backward-only history.
        entries=super().decide(day,scores=scores,regime=regime,**kwargs)
        ledger=self.ledger_ref[0]
        for row in scores.itertuples(index=False):
            date=pd.Timestamp(day);context=ledger.context.loc[(date,row.symbol)].to_dict()
            profile,reason=(choose_profile(context,regime.mode) if ledger.dynamic else ('REFERENCE','FIXED_CONTROL'))
            audit=dict(decision_date=str(date.date()),symbol=row.symbol,profile=profile,reason=reason,
                regime=regime.mode,inputs={k:float(v) if pd.notna(v) else None for k,v in context.items()},
                approved=any(e.symbol==row.symbol and e.approved_shares>0 for e in entries),
                sl=.05,trailing=PROFILES[profile][0],tp=PROFILES[profile][1])
            ledger.profile_audits.append(audit)
            ledger.approval_profiles[(date,row.symbol)]=audit
        return entries


def subset_protection(protection,symbol):
    frames={}
    for name in ('signals_df','protection_frame','order_lifecycle_frame','broker_event_frame'):
        frame=getattr(protection,name)
        if not frame.empty:
            if 'symbol' not in frame:raise ValueError(f'Unscoped protection frame {name}')
            frame=frame.loc[frame.symbol.eq(symbol)].copy()
        frames[name]=frame
    return replace(protection,**frames)


class ContextLedger(grid.UnlimitedLedger):
    def __init__(self,*args,context,dynamic,**kwargs):
        self.context=context.set_index(['date','symbol'])
        self.dynamic=dynamic
        self.approval_profiles={}
        self.profile_audits=[]
        self.fill_profile_audits=[]
        super().__init__(*args,sl=.05,trail=.15,tp=.20,**kwargs)

    def _build_entry_protections(self,phase3,*,execution_config):
        if not self.dynamic:
            return super()._build_entry_protections(phase3,execution_config=execution_config)
        native=OraclePortfolioLedger._build_entry_protections(self,phase3,execution_config=execution_config)
        if native.signals_df.empty:return native
        parts=[]
        for row in native.signals_df.itertuples(index=False):
            decision=pd.Timestamp(row.trade_date).normalize()
            if decision>=self.current_day:raise ValueError('Protection context must precede fill session')
            audit=self.approval_profiles[(decision,row.symbol)]
            if not audit['approved']:raise ValueError('Protection without native risk approval')
            trail,tp=PROFILES[audit['profile']]
            protection=parametric_protections(subset_protection(native,row.symbol),tp_pct=tp,sl_pct=.05)
            protection=trailing_protections(protection,trail)
            parts.append(protection)
            self.fill_profile_audits.append(dict(audit,fill_date=str(self.current_day.date()),
                fill_price=float(row.fill_price),planned_fill_qty=float(row.filled_qty),
                note='synthetic fill attempt; portfolio commit status in executions.json'))
        frames={name:pd.concat([getattr(p,name) for p in parts],ignore_index=True)
            for name in ('signals_df','protection_frame','order_lifecycle_frame','broker_event_frame')}
        return replace(native,**frames,diagnostics=dict(native.diagnostics,
            research_dynamic_entry_profiles=True,sl_never_widened=True,profile_fixed_until_exit=True))


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'ready.json').exists():
        ready=grid.read(output/'ready.json')
        verify_hashes(Path('.'),ready['sources']);verify_hashes(output,ready['files']);return ready
    if (output/'protocol.json').exists():raise ValueError('Incomplete prepare; use a fresh output ID')
    ready=grid.read(SOURCE/'ready.json');report=grid.read(SOURCE/'report.json')
    if report['status']!='COMPLETED_EXPLORATORY' or report['completed']!=144:raise ValueError('Incomplete reference campaign')
    verify_hashes(Path('.'),ready['sources']);verify_hashes(SOURCE,ready['files'])
    sources=dict(ready['sources']);sources.update(code_hashes())
    for path in [SOURCE/'ready.json',SOURCE/'report.json',SOURCE/'candidates.parquet',Path(__file__),
                 Path('tests/test_us_oracle_path_dynamic_protections.py')]:
        sources[str(path)]=digest(path)
    for year in grid.MODELS:
        folder=SOURCE/grid.key((year,.05,.15,.20))
        baseline=grid.read(folder/'case-report.json');verify_hashes(folder,baseline['files'])
        for name in ['case-report.json','daily.parquet','trades.parquet']:
            sources[str(folder/name)]=digest(folder/name)
    protocol=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),models=grid.MODELS,
        years=grid.ENDS,source=str(SOURCE),arms=['FIXED','DYNAMIC'],cases=6,
        rules=asdict(RULES),profiles=PROFILES,initial_stop_pct=.05,
        timing='choose at J close with native regime, fill J+1; profile retained for whole position',
        breadth='fraction above SMA50 on frozen full model universe; >=80% usable-price coverage',
        defensive='non-normal regime OR VIX>=30 OR breadth<40% OR SPY<SMA200 AND breadth<50%',
        trend='VIX<=20 AND SPY>SMA200 AND SPY20return>0 AND breadth>=60% AND stock>SMA50 AND stock20return-SPY20return>0',
        priority='missing input/low coverage => reference; defensive => trend => reference',
        no_add_to_held_symbol=True,no_h20_or_terminal_exit=True,capital_usd=4000.,max_entry_leverage=2.,
        exposure_sizing_costs_unchanged=True,training=False,sql_writes=False,broker_calls=False,
        new_holdout=False,prospectively_observed_data_required_for_certification=True,
        reserves=grid.read(SOURCE/'protocol.json')['reserves'],
        selection_warning='baseline/profiles and periods already inspected; frozen now but still exploratory',sources=sources)
    atomic_json(output/'protocol.json',protocol)  # before computing any new PnL
    prices=pd.read_parquet(ready['prices']);macro=pd.read_parquet(ready['macro'])
    candidates=pd.read_parquet(SOURCE/'candidates.parquet')
    first_model=next(iter(grid.MODELS.values()))
    universe=grid.load_contract('artifacts/models',first_model)[1]['universe']
    context=build_context(prices,macro,universe,candidates)
    context.to_parquet(output/'context.parquet',index=False)
    coverage=context.groupby(context.date.dt.year).agg(rows=('symbol','size'),
        vix_present=('vix','count'),minimum_breadth_coverage=('breadth_coverage','min'))
    atomic_json(output/'input-coverage.json',coverage.reset_index().to_dict('records'))
    prepared=dict(sources=sources,files={'context.parquet':digest(output/'context.parquet')})
    atomic_json(output/'ready.json',prepared);verify_hashes(Path('.'),sources)
    atomic_json(output/'progress.json',dict(status='READY',total=6,completed=0))
    return prepared


_CACHE=None


def worker_init(output):
    global _CACHE
    grid.worker_init(SOURCE)
    _CACHE=dict(grid._CACHE,root=Path(output),context=pd.read_parquet(Path(output)/'context.parquet'))


def case_key(case):
    year,arm=case;return f'{year}-{arm}'


def run_case(case):
    year,arm=case;folder=_CACHE['root']/case_key(case);folder.mkdir(exist_ok=True)
    marker=folder/'case-report.json'
    if marker.exists():
        prior=grid.read(marker)
        if prior['status']=='COMPLETED':verify_hashes(folder,prior['files']);return prior
    ref=[]
    def factory(cfg,**kwargs):
        ledger=ContextLedger(cfg,context=_CACHE['context'],dynamic=arm=='DYNAMIC',study_end=grid.ENDS[year],
            cash_policy='STRICT',events=_CACHE['ready']['events'],**kwargs)
        ref.append(ledger);return ledger
    try:
        with (folder/'stderr.log').open('a',encoding='utf-8') as log,redirect_stderr(log),redirect_stdout(log):
            logging.basicConfig(level=logging.WARNING,stream=log,force=True)
            result=run_portfolio(frames=_CACHE['frames'],scores=_CACHE['candidates'][_CACHE['candidates'].year.eq(year)],
                sectors=_CACHE['sectors'],macro=_CACHE['macro'],market_config=_CACHE['market'],policy='selected',
                variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=grid.ENDS[year],
                quality=_CACHE['prices'][['date','symbol','is_filled','instrument_id']],ledger_factory=factory,
                session_factory=partial(ContextSession,ledger_ref=ref),
                protection_options=dict(take_profit_enabled=True,trailing_enabled=True),
                daily_exit_policy=grid.margin_policy,reject_constrained_entries=True)
        ledger=ref[0];daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        open_rows=[dict(symbol=s,quantity=p.quantity,entry_date=str(p.entry_date.date()),entry_cost=p.entry_cost,
            unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(grid.ENDS[year]),s])-p.entry_cost)
            for s,p in ledger.state.positions.items()]
        unrealized=sum(p['unrealized_pnl_usd'] for p in open_rows)
        realized=float(trades.pnl.sum()) if len(trades) else 0.
        required=grid.maintenance_requirement(ledger.state.positions,_CACHE['frames']['close'].loc[grid.ENDS[year]])
        ledger.margin_audits.append(dict(date=grid.ENDS[year],equity=float(daily.equity.iloc[-1]),
            required=required,breach=float(daily.equity.iloc[-1])<required,final_mark_only=True))
        if not np.isclose(4000+realized+unrealized-ledger.interest,daily.equity.iloc[-1],atol=1e-6,rtol=1e-10):
            raise ValueError('Open equity reconciliation failed')
        if len(trades):
            if not trades.side.eq('buy').all():raise ValueError('Unexpected short')
            if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*.95,atol=1e-6).all():
                raise ValueError('Hard SL5 changed')
            if trades.exit_reason.isin(['terminal_close','expiry_open']).any():raise ValueError('Forbidden time exit')
        if arm=='FIXED':
            baseline=SOURCE/grid.key((year,.05,.15,.20))
            pd.testing.assert_frame_equal(daily,pd.read_parquet(baseline/'daily.parquet'))
            pd.testing.assert_frame_equal(trades,pd.read_parquet(baseline/'trades.parquet'))
        for name,value in [('profiles.json',ledger.profile_audits),('fill-profiles.json',ledger.fill_profile_audits),
                           ('open-positions.json',open_rows),('maintenance.json',ledger.margin_audits)]:
            atomic_json(folder/name,value)
        gross=daily.gross_notional/daily.equity
        attempts=Counter(x['profile'] for x in ledger.fill_profile_audits)
        result.update(case=case_key(case),year=year,arm=arm,net_return_pct=100*result['return_pct'],
            dd_pct=100*result['max_drawdown'],final_capital_usd=float(daily.equity.iloc[-1]),
            realized_pnl_usd=realized,unrealized_pnl_usd=unrealized,open_positions=len(open_rows),
            mean_gross_leverage=float(gross.mean()),max_gross_leverage=float(gross.max()),
            profile_fill_attempts=dict(attempts),fixed_control_exact_parity=arm=='FIXED',
            trailing_unchanged=arm=='FIXED',take_profit_unchanged=arm=='FIXED',sizing_policy_unchanged_vs_control=True,
            daily_protection_updates=False,dividends_complete=False,historical_marginability_certified=False,
            files={p.name:digest(p) for p in folder.iterdir() if p.suffix in ['.json','.parquet'] and p.name!='case-report.json'})
    except Exception as exc:
        import traceback
        LOG.error('Case %s failed: %s',case_key(case),exc)
        (folder/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        result=dict(status='FAILED',case=case_key(case),year=year,arm=arm,error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(output,phase='all',workers=3):
    output=Path(output)
    with exclusive_run(output):
        ready=prepare(output)
        if phase=='prepare':return
        reports=[]
        cases=[(y,arm) for y in grid.MODELS for arm in ['FIXED','DYNAMIC']]
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(output),)) as pool:
            futures=[pool.submit(run_case,case) for case in cases]
            for future in as_completed(futures):
                result=future.result();reports.append(result)
                atomic_json(output/'progress.json',dict(status='RUNNING',completed=len(reports),
                    total=6,failed=sum(r['status']=='FAILED' for r in reports),last=result['case']))
                atomic_json(output/'report.partial.json',dict(cases=reports))
                LOG.info('%s %s/6 %s',result['case'],len(reports),result['status'])
        verify_hashes(Path('.'),ready['sources']);verify_hashes(output,ready['files'])
        comparisons=[]
        for year in grid.MODELS:
            rows={r['arm']:r for r in reports if r['year']==year and r['status']=='COMPLETED'}
            if len(rows)!=2:continue
            fixed,dynamic=rows['FIXED'],rows['DYNAMIC']
            comparisons.append(dict(year=year,fixed_net_pct=fixed['net_return_pct'],dynamic_net_pct=dynamic['net_return_pct'],
                delta_net_points=dynamic['net_return_pct']-fixed['net_return_pct'],fixed_dd_pct=fixed['dd_pct'],
                dynamic_dd_pct=dynamic['dd_pct'],delta_dd_points=dynamic['dd_pct']-fixed['dd_pct']))
        failed=sum(r['status']=='FAILED' for r in reports)
        status='COMPLETED_EXPLORATORY' if not failed else 'PARTIAL_FAILED'
        atomic_json(output/'report.json',dict(status=status,cases=reports,comparisons=comparisons,
            source_hashes_verified=True,independent_holdout=False,production_changed=False))
        atomic_json(output/'progress.json',dict(status=status,completed=6-failed,failed=failed,total=6))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--phase',choices=['all','prepare','run'],default='all')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=3)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    try:run(**vars(args))
    except Exception as exc:
        Path(args.output).mkdir(parents=True,exist_ok=True)
        atomic_json(Path(args.output)/'failure.json',dict(status='FAILED',error=str(exc)));raise
