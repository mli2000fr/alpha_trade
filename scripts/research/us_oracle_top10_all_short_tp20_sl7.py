"""Offline annual Oracle amplitude TOP10 -> forced SHORT, TP20/SL7.

Not a SHORT-head ranking, GPT filter or broker-certified historical shortability.
Only new research artifacts; no training, SQL, HTTP, orders or core changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout,redirect_stderr
from dataclasses import asdict,replace
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_bullish_portfolio as source
from scripts.research import us_news_gpt_bearish_portfolio as short
from scripts.research.us_oracle_short_replay import ShortLedger,BORROW_ANNUAL,verify_short_trades
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.oracle_path_confirmation import exclusive_run

INPUT=Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1')
POLICY='ORACLE_TOP10_ALL_SHORT'
TP=.20
SL=.07


def freeze_top10(panel):
    """Discard GPT/future-label fields BEFORE selection; no replacement outside TOP10."""
    columns=['date','symbol','score','oracle_rank','fold_start','model_available_date',
        'model_sha256','feature_profile_sha256','batch_id','selected','entry_quality_reason']
    values=panel[columns].copy()
    values.date=pd.to_datetime(values.date)
    if values.duplicated(['date','symbol']).any() or not np.isfinite(values.score).all():
        raise ValueError('Duplicate/invalid archived candidates')
    if not values.score.between(0,1).all():raise ValueError('Invalid Oracle amplitude score')
    for day,part in values.groupby('date'):
        ranked=part.sort_values(['score','symbol'],ascending=[False,True])
        if list(ranked.oracle_rank)!=list(range(1,21)):
            raise ValueError('Missing/changed original TOP20 ranks')
        if not pd.to_datetime(part.model_available_date).lt(day).all():
            raise ValueError('Noncausal model availability')
        if not part.batch_id.eq(source.MODELS[day.year]).all():raise ValueError('Wrong annual model')
    values=values.loc[values.oracle_rank.le(10)].sort_values(['date','oracle_rank']).copy()
    values['proba_extreme']=values.score
    values[POLICY]=values.selected
    if not values.groupby('date').size().eq(10).all():raise ValueError('Incomplete daily TOP10')
    return values


def prepare(root):
    marker=root/'ready.json'
    if marker.exists():
        saved=source.read(marker);verify_hashes(Path('.'),saved['sources']);verify_hashes(root,saved['files'])
        return saved
    old=source.read(INPUT/'ready.json')
    # Immutable data/model artifacts must match. Code/config drift is explicitly
    # recorded and the CURRENT runtime is frozen, never falsely called bitwise old parity.
    verified={str(INPUT/'ready.json'):digest(INPUT/'ready.json')};drift=[]
    for name,expected in old['sources'].items():
        path=Path(name)
        if not path.is_file():raise ValueError('Missing inherited source: '+name)
        actual=digest(path)
        if actual!=expected:
            if path.suffix not in ('.py','.yaml','.yml') or 'artifacts' in path.parts:
                raise ValueError('Changed immutable artifact: '+name)
            drift.append(dict(path=name,archived_sha256=expected,current_sha256=actual,
                status='DOCUMENTED_RUNTIME_DRIFT_NOT_CHANGED_MARKET_DATA'))
        verified[name]=actual
    verify_hashes(INPUT,old['files'])
    for name in old['files']:verified[str(INPUT/name)]=digest(INPUT/name)
    panel=freeze_top10(pd.read_parquet(INPUT/'candidates.parquet'))
    panel.to_parquet(root/'candidates.parquet',index=False)
    for name in (old['prices'],old['macro'],old['sectors']):
        expected=next(value for key,value in old['sources'].items() if Path(key)==Path(name))
        if digest(name)!=expected:raise ValueError('Archived market data changed: '+name)
        verified[name]=expected
    for folder in ('backtesting','risk_management','execution_engine'):
        for path in Path(folder).rglob('*.py'):verified[str(path)]=digest(path)
    for path in (Path(__file__),Path(short.__file__),Path(source.grid.__file__),
                 Path('scripts/research/us_oracle_short_replay.py'),
                 Path('scripts/research/us_concentrated_live_portfolio.py'),
                 Path('scripts/research/us_concentrated_contract_audit.py'),Path('config.yaml')):
        verified[str(path)]=digest(path)
    protocol=dict(experiment='ORACLE_AMPLITUDE_TOP10_FORCED_SHORT_TP20_SL7',models=old['models'],years=old['years'],
        source=str(INPUT),top=10,side='SHORT_EXPLICIT_NOT_PREDICTED',tp=TP,sl=SL,trailing=False,
        capital_usd=4000.,annual_reset=True,max_entry_leverage=2.,position_cap_equity=.4,max_positions=8,
        expiry_after_holding_sessions=20,entry='next session open; no same-symbol reinforcement',
        no_replacement_outside_top10=True,gpt_used=False,dedicated_short_head=False,
        research_allow_short_normal=True,other_risk_and_regime_gates_active=True,
        borrow_availability_assumed=True,historical_shortability_certified=False,
        borrow_fee_annual=BORROW_ANNUAL,borrow_basis='entry notional * sessions held /252',
        borrow_recalls_modelled=False,dividend_compensation_modelled=False,
        margin_interest_annual=.065,maintenance='research price tiers, cover at next open on breach',
        prices=old['prices'],macro=old['macro'],sectors=old['sectors'],market=old['market'],events=old['events'],
        data_provenance='Unchanged sealed market tapes and annual amplitude scores; current runtime frozen separately',
        code_drift=drift,sources=verified,files={'candidates.parquet':digest(root/'candidates.parquet')},
        reservations=['Current survivor universe/sectors, not a historical PIT universe.',
            'Macro vintages and historical quotes/fills are not independently PIT-certified.',
            'No historical borrow/locates, recalls or complete dividend compensation; exploratory returns only.',
            '2026 stops at 30 September, remaining positions marked, not forced-closed.',
            '2024/2025 cohort expiry tails extend into next year; calendar-end metrics are separate.',
            'Historical periods already explored; no new independent holdout.',
            'Open borrow deducted in reported equity; native intrarun risk sees the fee at cover.'],
        training=False,sql_writes=False,api_calls=0,broker_orders=False,production_changes=False)
    atomic_json(root/'protocol.json',protocol);atomic_json(marker,protocol)
    return protocol


class Top10ShortLedger(short.ShortMarkLedger):
    """Reuse the audited SHORT lifecycle, changing only explicit SL and risk sizing."""
    def __init__(self,cfg,*args,quality,study_end,holding_sessions=20,events=(),**kwargs):
        source.grid.configure_leverage(cfg,SL)
        cfg.risk_config=replace(cfg.risk_config,short_selling_enabled=True,allow_fractional_shares=False,
            max_short_exposure=2.)
        cfg.exec_config=replace(cfg.exec_config,allow_fractional_shares=False)
        self.quality=quality;self.study_end=pd.Timestamp(study_end);self.holding_sessions=holding_sessions
        self.margin_breached=False;self.margin_audits=[];self.expiry_audits=[];self.terminal_suppressed=0
        ShortLedger.__init__(self,cfg,*args,tp_pct=TP,sl_pct=SL,borrow_annual=BORROW_ANNUAL,events=events,**kwargs)


class Top10ShortSession(short.ShortMarginSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.decision_audits=[]

    def decide(self,*args,**kwargs):
        entries=super().decide(*args,**kwargs)
        self.decision_audits.append(dict(date=str(args[0]),candidates=len(kwargs['scores']),
            returned=len(entries),approved=sum(e.approved_shares>0 for e in entries),
            reasons=dict(Counter(str(e.decision_reason_code) for e in entries)),
            max_short_positions=self.resolved_config.max_short_positions,
            max_short_exposure=self.resolved_config.max_short_exposure,
            max_gross_exposure=self.resolved_config.max_gross_exposure,
            risk_multiplier=self.resolved_config.risk_multiplier,
            risk_per_trade_pct=self.resolved_config.risk_per_trade_pct,
            regime_mode=kwargs['regime'].mode,
            details=[dict(symbol=e.symbol,shares=e.approved_shares,reason=e.decision_reason,
                          code=str(e.decision_reason_code)) for e in entries]))
        return [replace(e,selection_explanation='Research forced SHORT; original TOP10 Oracle amplitude; no GPT/SHORT-head')
                for e in entries]


def summarize(result,ledger,daily,trades,bars,days,year,terminal):
    if len(trades):
        if not trades.side.eq('sell').all() or trades.exit_reason.str.contains('terminal|trailing').any():
            raise ValueError('Unexpected side/exit')
        regular=trades[~trades.exit_reason.eq('learned_exit_next_open')]
        verify_short_trades(regular,bars,days,TP,SL,BORROW_ANNUAL)
        if not np.allclose(trades.replay_initial_stop_price,trades.entry_price*(1+SL)):
            raise ValueError('SL7 not anchored to actual fill')
        if not np.allclose(trades.replay_take_profit_price,trades.entry_price*(1-TP)):
            raise ValueError('TP20 not anchored to actual fill')
        if not np.allclose(trades.quantity,trades.quantity.round()):raise ValueError('Fractional SHORT quantity')
        ages=days.get_indexer(pd.to_datetime(trades.exit_date))-days.get_indexer(pd.to_datetime(trades.entry_date))
        if not np.allclose(trades.borrow_cost,trades.quantity*trades.entry_price*BORROW_ANNUAL*ages/252):
            raise ValueError('Borrow accounting mismatch')
        if not np.allclose(trades.pnl,2*trades.quantity*trades.entry_price-trades.entry_cost+trades.proceeds-trades.borrow_cost):
            raise ValueError('SHORT cash-flow mismatch')
        indexed=bars.set_index(['symbol','date'])
        for row in trades[trades.exit_reason.eq('learned_exit_next_open')].itertuples():
            if not np.isclose(row.exit_price,indexed.at[(row.symbol,row.exit_date),'open']):
                raise ValueError('Margin cover not at next open')
    closed=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    terminal=pd.Timestamp(terminal)
    opened=[dict(symbol=s,quantity=p.quantity,entry_date=str(p.entry_date.date()),entry_price=p.entry_price,
        mark=float(ledger.close.at[terminal,s]),unrealized_pnl_usd=p.entry_cash_flow-p.quantity*float(ledger.close.at[terminal,s]),
        accrued_borrow_usd=p.quantity*p.entry_price*BORROW_ANNUAL*(days.get_loc(terminal)-p.entry_idx)/252)
        for s,p in ledger.state.positions.items()]
    latent=sum(p['unrealized_pnl_usd'] for p in opened);native=float(daily.equity.iloc[-1])
    if not np.isclose(4000+float(closed.sum())+latent-ledger.interest,native,atol=1e-6):
        raise ValueError('SHORT total wealth mismatch')
    curve=pd.concat([pd.Series([4000.]),daily.equity_net_accrued_borrow],ignore_index=True)
    cutoff=f'{year}-12-31' if year<2026 else '2026-09-30'
    calendar=daily[pd.to_datetime(daily.date).le(cutoff)]
    cc=pd.concat([pd.Series([4000.]),calendar.equity_net_accrued_borrow],ignore_index=True)
    final=float(curve.iloc[-1]);wins=int(closed.gt(0).sum());losses=int(closed.lt(0).sum());flat=int(closed.eq(0).sum())
    result.update(status='COMPLETED_EXPLORATORY_OPEN_SHORT_MTM' if opened else 'COMPLETED_EXPLORATORY',
        initial_capital_usd=4000.,final_capital_usd=final,net_return_pct=100*(final/4000-1),
        calendar_end_capital_usd=float(cc.iloc[-1]),calendar_end_return_pct=100*(float(cc.iloc[-1])/4000-1),
        max_drawdown_pct=100*float((curve/curve.cummax()-1).min()),
        calendar_end_drawdown_pct=100*float((cc/cc.cummax()-1).min()),
        winning_positions=wins,losing_positions=losses,flat_positions=flat,
        winning_pct=100*wins/len(closed) if len(closed) else None,losing_pct=100*losses/len(closed) if len(closed) else None,
        positive_closed_pnl_usd=float(closed[closed.gt(0)].sum()),negative_closed_pnl_usd=float(closed[closed.lt(0)].sum()),
        realized_pnl_usd=float(closed.sum()),unrealized_pnl_usd=latent,open_positions=opened,
        closed_borrow_usd=float(trades.borrow_cost.sum()) if len(trades) else 0.,
        accrued_open_borrow_usd=sum(p['accrued_borrow_usd'] for p in opened),
        mean_gross_capital_usd=float(daily.gross_notional.mean()),max_gross_capital_usd=float(daily.gross_notional.max()),
        mean_gross_leverage=float((daily.gross_notional/daily.equity_net_accrued_borrow).mean()),
        max_gross_leverage=float((daily.gross_notional/daily.equity_net_accrued_borrow).max()),
        exit_reasons=dict(Counter(trades.exit_reason)) if len(trades) else {},
        annual_closed_trades_including_expiry_tail=True,dividend_compensation_modelled=False,
        historical_shortability_verified=False)
    return result


def run_case(root,p,panel,prices,year):
    folder=root/str(year);folder.mkdir(exist_ok=True);marker=folder/'case-report.json'
    if marker.exists():
        saved=source.read(marker)
        if saved['status'].startswith('COMPLETED'):verify_hashes(folder,saved['files']);return saved
    spec=p['years'][str(year)];candidates=panel[panel.date.dt.year.eq(year)].copy()
    bars=prices[prices.symbol.isin(set(candidates.symbol)|{'SPY'})&prices.date.le(spec['terminal'])].copy()
    days=source.grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames={k:bars.pivot(index='date',columns='symbol',values=v).reindex(days)
        for k,v in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    quality=bars[['date','symbol','is_filled','instrument_id']]
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict();refs=[];sessions=[]
    def factory(cfg,**kwargs):
        value=Top10ShortLedger(cfg,quality=quality,study_end=spec['terminal'],events=p['events'],**kwargs)
        refs.append(value)
        atomic_json(folder/'runtime-configuration.json',dict(risk=asdict(cfg.risk_config),execution=asdict(cfg.exec_config),
            cost_model=asdict(value._cost_model),margin_interest_rate_annual=cfg.margin_interest_rate_annual))
        return value
    def session_factory(cfg,**kwargs):
        value=Top10ShortSession(cfg,ledger_ref=refs,study_arm=POLICY,**kwargs)
        sessions.append(value);return value
    base=dict(year=year,batch_id=source.MODELS[year],side='SHORT',tp=TP,sl=SL,top=10,trailing=False,
        decision_end=spec['decision_end'],terminal=spec['terminal'],research_allow_short_normal=True)
    try:
        with (folder/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result=source.run_portfolio(frames=frames,scores=candidates,sectors=sectors,
                macro=source.ArchivedMacro(pd.read_parquet(p['macro'])),market_config=source.grid.parse_market_regimes(p['market']),
                policy=POLICY,variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=session_factory,reject_constrained_entries=True,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=short.margin_policy,
                research_allow_short_normal=True)
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        result=summarize(result,refs[0],daily,trades,bars,days,year,spec['terminal'])
        result.update(base,candidate_days=len(candidates),admissible_candidate_days=int(candidates[POLICY].sum()))
        opened=[(pd.Timestamp(a['date']),s) for a in source.read(folder/'executions.json') for s in a['opened']]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in candidates[candidates[POLICY]].itertuples()
            if days.get_loc(r.date)+1<len(days)}
        if any(key not in allowed for key in opened):raise ValueError('Entry outside actual TOP10 next-open decisions')
        if len(opened)!=len(set(opened)):raise ValueError('Duplicate same-day SHORT opening')
        if year<2026 and result['open_positions']:raise ValueError('Incomplete expiry tail')
        result['actual_entries']=len(opened)
        atomic_json(folder/'open-positions.json',result['open_positions']);atomic_json(folder/'maintenance.json',refs[0].margin_audits)
        atomic_json(folder/'expiry-audit.json',refs[0].expiry_audits)
        atomic_json(folder/'decision-audit.json',sessions[0].decision_audits)
        result['files']={n:digest(folder/n) for n in ['daily.parquet','trades.parquet','executions.json','decisions.json',
            'regimes.json','open-positions.json','maintenance.json','expiry-audit.json','runtime-configuration.json',
            'decision-audit.json']}
    except Exception as exc:
        result=dict(base,status='FAILED',error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(root,phase):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with exclusive_run(root):
        p=prepare(root)
        if phase=='prepare':return dict(status='READY',models=p['models'])
        panel=pd.read_parquet(root/'candidates.parquet');prices=pd.read_parquet(p['prices']);reports=[]
        for year in source.MODELS:
            atomic_json(root/'progress.json',dict(status='RUNNING',year=year,completed=len(reports),total=3))
            reports.append(run_case(root,p,panel,prices,year))
            atomic_json(root/'report.json',dict(status='RUNNING',reports=reports))
        verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files'])
        final=dict(status='COMPLETED_EXPLORATORY' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
            reports=reports,completed=sum(r['status'].startswith('COMPLETED') for r in reports),total=3,
            input_hashes_verified=True,sql_writes=False,api_calls=0,training=False,broker_orders=False)
        atomic_json(root/'report.json',final)
        atomic_json(root/'progress.json',{k:v for k,v in final.items() if k!='reports'})
        return final


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--phase',choices=['prepare','run'],default='run')
    args=parser.parse_args()
    import requests,socket
    def forbidden(*a,**k):raise RuntimeError('Network forbidden in offline TOP10 SHORT replay')
    requests.Session.request=forbidden;socket.socket.connect=forbidden;socket.socket.connect_ex=forbidden
    result=run(args.output,args.phase)
    print(json.dumps(result,ensure_ascii=False,default=str))
    if result['status'] not in ('READY','COMPLETED_EXPLORATORY'):raise SystemExit(1)


if __name__=='__main__':main()
