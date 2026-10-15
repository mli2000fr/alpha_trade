"""Offline SHORT-only replay of 734 cached BEARISH candidate-days.

No new GPT calls, SQL writes, training or broker orders. Borrow availability,
rates, maintenance and missing dividend liabilities are explicit assumptions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout,redirect_stderr
from dataclasses import replace
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam,event,text

from scripts.research import us_news_gpt_bullish_portfolio as long
from scripts.research.us_oracle_short_replay import ShortLedger,ShortSession,BORROW_ANNUAL,verify_short_trades
from service.llm_directional.news_cache import sha,request_identity
from service.llm_directional.stored_news import parse
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.oracle_path_confirmation import exclusive_run

LONG=Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1')
PROFILES=('NATIVE_REGIME','RESEARCH_SHORT_NORMAL')
ARMS=('GPT_BEARISH_ONLY','ORACLE_TOP20_ALL_SHORT')


def eligible_bearish(row):return row.get('decision')=='BEARISH' and row.get('technical_status')=='VALID'


def prepare(root):
    marker=root/'ready.json'
    if marker.exists():
        p=long.read(marker);verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files']);return p
    old=long.read(LONG/'ready.json');verify_hashes(Path('.'),old['sources']);verify_hashes(LONG,old['files'])
    frame=pd.read_parquet(LONG/'candidates.parquet')
    frame['bearish']=frame.apply(eligible_bearish,axis=1)
    frame['GPT_BEARISH_ONLY']=frame.selected & frame.bearish
    frame['ORACLE_TOP20_ALL_SHORT']=frame.selected
    if int(frame.bearish.sum())!=734 or len(frame)!=13780:raise ValueError('Expected exact 734 BEARISH / 13,780 cohort')
    from database.connection import get_sqlalchemy_engine
    from scripts.research.us_oracle_barrier_comparison import readonly_statement
    from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    event.listen(engine,'before_cursor_execute',readonly_statement);event.listen(engine,'begin',readonly_begin)
    audits=[]
    try:
        query=text('SELECT * FROM llm_news_analysis_cache WHERE cache_key IN :keys').bindparams(bindparam('keys',expanding=True))
        for month,group in frame[frame.bearish].groupby(frame[frame.bearish].date.dt.strftime('%Y-%m')):
            with engine.connect() as conn:
                cached={r['cache_key']:dict(r) for r in conn.execute(query,dict(keys=group.cache_key.tolist())).mappings()}
            for r in group.itertuples():
                saved=cached[r.cache_key];request=json.loads(saved['request_json']);response=json.loads(saved['response_json'])
                context=json.loads(request['input'])
                if (saved['status']!='VALID' or request_identity(request,'SYMBOL_DATE_BUNDLE')[0]!=r.cache_key
                        or sha(response)!=saved['response_sha256'] or context['symbol']!=r.symbol
                        or context['decision_date']!=str(r.date.date())):raise ValueError('Bearish raw response integrity failure')
                assessment=parse(response,request)
                if assessment['decision']!='BEARISH' or assessment['confidence']!=r.confidence:raise ValueError('Reparsed bearish verdict differs')
                if r.batch_id!=long.MODELS[r.date.year]:raise ValueError('Wrong annual model')
                audits.append(dict(date=str(r.date.date()),symbol=r.symbol,cache_key=r.cache_key,
                    response_sha256=saved['response_sha256'],confidence=r.confidence))
    finally:
        event.remove(engine,'before_cursor_execute',readonly_statement);event.remove(engine,'begin',readonly_begin);engine.dispose()
    frame.to_parquet(root/'candidates.parquet',index=False);atomic_json(root/'sql-bearish-validation.json',audits)
    sources=dict(old['sources'])
    for name in (LONG/'ready.json',LONG/'candidates.parquet',LONG/'prices.parquet',Path(__file__),
        Path('scripts/research/us_news_gpt_bullish_portfolio.py'),Path('scripts/research/us_oracle_short_replay.py'),
        Path('tests/test_us_news_gpt_bearish_portfolio.py')):sources[str(name)]=digest(name)
    p=dict(experiment='GPT_BEARISH_ONLY_ANNUAL_SHORT',models=long.MODELS,profiles=PROFILES,arms=ARMS,
        bearish_candidates=734,years=old['years'],capital_usd=4000.,annual_capital_reset=True,max_entry_leverage=2.,
        tp=.20,sl=.05,trailing=False,expiry_open_sessions=20,no_reinforcement=True,no_extra_confidence_threshold=True,
        priority='frozen original Oracle score, not GPT confidence',prices=str(LONG/'prices.parquet'),
        macro=old['macro'],sectors=old['sectors'],events=old['events'],market=old['market'],
        short_normal_policy='NATIVE_REGIME unchanged; RESEARCH_SHORT_NORMAL only permits normal-mode short entry locally',
        borrow_fee_annual=BORROW_ANNUAL,borrow_basis='entry notional * sessions held / 252, native cover charge',
        open_borrow_accrual='also deducted in reported MTM; native intrarun risk sees fee at cover',
        borrow_availability_assumed=True,borrow_recall_modelled=False,dividend_compensation_modelled=False,
        historical_marginability_certified=False,maintenance_assumption='below5: max(2.5,mark) per share; otherwise max(5,.30*mark)',
        margin_interest_annual=.065,whole_shares=True,position_cap_equity=.4,
        historical_news_pit_certified=False,current_sectors_non_pit=True,production_changes=False,
        api_calls=0,sql_writes=False,training=False,broker_orders=False,sources=sources,
        files={n:digest(root/n) for n in ['candidates.parquet','sql-bearish-validation.json']})
    atomic_json(root/'protocol.json',p);atomic_json(marker,p);return p


def short_maintenance(positions,marks):
    required=0.
    for symbol,p in positions.items():
        price=float(marks[symbol])
        if not np.isfinite(price) or price<=0:raise ValueError('Unknown SHORT maintenance mark')
        required+=float(p.quantity)*(max(2.5,price) if price<5 else max(5.,.30*price))
    return required


class ShortMarginSession(ShortSession):
    def __init__(self,*args,ledger_ref,study_arm='GPT_BEARISH_ONLY',**kwargs):
        self.ledger_ref=ledger_ref;self.study_arm=study_arm;super().__init__(*args,**kwargs)
    def decide(self,day,*,scores,**kwargs):
        if self.ledger_ref[0].margin_breached:scores=scores.iloc[:0]
        entries=super().decide(day,scores=scores,**kwargs)
        # The shared legacy SHORT session mentions a SHORT head. Here direction
        # comes only from the GPT filter (or the explicit control policy), not
        # from a separate trained SHORT model. Preserve quantities and risk.
        explanation=('GPT BEARISH valid; Oracle path amplitude ranking only; no SHORT head'
            if self.study_arm=='GPT_BEARISH_ONLY' else 'Control: explicit SHORT; Oracle path amplitude ranking only; no SHORT head')
        return [replace(entry,selection_explanation=explanation) for entry in entries]


class ShortMarkLedger(ShortLedger):
    def __init__(self,cfg,*args,quality,study_end,holding_sessions=20,**kwargs):
        long.grid.configure_leverage(cfg,.05)
        cfg.risk_config=replace(cfg.risk_config,short_selling_enabled=True,allow_fractional_shares=False,
            max_short_exposure=2.)
        cfg.exec_config=replace(cfg.exec_config,allow_fractional_shares=False)
        self.quality=quality;self.study_end=pd.Timestamp(study_end);self.holding_sessions=holding_sessions
        self.margin_breached=False;self.margin_audits=[];self.expiry_audits=[];self.terminal_suppressed=0
        super().__init__(cfg,*args,tp_pct=.20,sl_pct=.05,borrow_annual=BORROW_ANNUAL,**kwargs)

    def corporate_action_open(self,session,pending,steps,day):
        pending,steps=super().corporate_action_open(session,pending,steps,day)
        due=[]
        for symbol,p in self.state.positions.items():
            if self.days.get_loc(day)-p.entry_idx<self.holding_sessions:continue
            volume=self.volume.at[day,symbol]
            observed=self.quality.loc[(self.quality.symbol==symbol)&self.quality.date.between(p.entry_date,day)]
            if not pd.notna(volume) or volume<=0 or observed.is_filled.fillna(0).ne(0).any() or observed.instrument_id.dropna().nunique()>1:
                raise ValueError('Unqualified SHORT expiry tape '+symbol)
            due.append(dict(symbol=symbol,exit_date=day,exit_price=self.opens.at[day,symbol],exit_reason='expiry_open'))
        for trade in self.close_resolved(due,phase='open'):
            symbol=trade['symbol'];total=sum(t['pnl'] for t in self.state.closed_trades
                if t['symbol']==symbol and t['entry_date']==trade['entry_date'])
            session.record_fill(f'expiry-{symbol}-{trade["entry_date"]}-{day}',day=day.date(),symbol=symbol,entry=False,realized_pnl=total)
            self.expiry_audits.append(dict(symbol=symbol,entry_date=trade['entry_date'],exit_date=day,exit_price=trade['exit_price']))
        return pending,steps

    def close_resolved(self,exits,*,phase):
        actual=[e for e in exits if e['exit_reason']!='terminal_close']
        self.terminal_suppressed+=len(exits)-len(actual)
        return super().close_resolved(actual,phase=phase)

    def _accrue_margin_interest(self,state,*,annual_rate,sessions_per_year=252):
        index=self.days.get_loc(self.current_day)
        end=self.days[index+1] if index+1<len(self.days) else self.current_day+pd.Timedelta(days=1)
        elapsed=max(1,(min(end,self.study_end+pd.Timedelta(days=1))-self.current_day).days)
        charge=max(-float(state.settled_cash),0.)*float(annual_rate)*elapsed/360
        state.settled_cash-=charge;return charge

    def open_borrow(self,day):
        return sum(p.quantity*p.entry_price*BORROW_ANNUAL*(self.days.get_loc(day)-p.entry_idx)/252
            for p in self.state.positions.values())

    def finish_day(self):
        day=self.current_day;accrual=self.open_borrow(day);equity=super().finish_day()
        self.daily[-1].update(open_borrow_accrual=accrual,equity_net_accrued_borrow=equity-accrual)
        return equity

    def reconciliation_error(self):
        expected=self.config.initial_equity+sum(t['pnl'] for t in self.state.closed_trades)-self.interest
        expected+=sum(p.entry_cash_flow for p in self.state.positions.values())
        return self.state.settled_cash+self.state.unsettled_cash-expected


def margin_policy(day,ledger,frames):
    required=short_maintenance(ledger.state.positions,frames['close'].loc[day])
    equity=ledger.equity_unchecked()-ledger.open_borrow(day);ledger.margin_breached=equity<required
    ledger.margin_audits.append(dict(date=str(day.date()),equity=equity,required=required,breach=ledger.margin_breached))
    return [dict(symbol=s,entry_date=p.entry_date,decision_date=day,policy_reason='SHORT_MARGIN_FULL_COVER_NEXT_OPEN')
        for s,p in ledger.state.positions.items()] if ledger.margin_breached else []


def summarize(result,ledger,daily,trades,bars,days,year,terminal):
    if len(trades):
        if not trades.side.eq('sell').all() or trades.exit_reason.str.contains('terminal|trailing').any():raise ValueError('Unexpected side/exit')
        if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*1.05).all():raise ValueError('Wrong SHORT SL')
        if not np.isclose(trades.replay_take_profit_price,trades.entry_price*.80).all():raise ValueError('Wrong SHORT TP')
        if not np.isclose(trades.quantity,trades.quantity.round()).all():raise ValueError('Fractional SHORT quantity')
        age=days.get_indexer(pd.to_datetime(trades.exit_date))-days.get_indexer(pd.to_datetime(trades.entry_date))
        expected=trades.quantity*trades.entry_price*BORROW_ANNUAL*age/252
        if not np.isclose(trades.borrow_cost,expected).all():raise ValueError('SHORT borrow charge mismatch')
        flows=2*trades.quantity*trades.entry_price-trades.entry_cost+trades.proceeds-trades.borrow_cost
        if not np.isclose(trades.pnl,flows).all():raise ValueError('SHORT cash-flow mismatch')
        # Native verifier checks actual OHLC gap/intrabar/expiry semantics. Margin
        # exits use a separate next-open check instead of relabelling their cause.
        regular=trades[~trades.exit_reason.eq('learned_exit_next_open')]
        verify_short_trades(regular,bars,days,.20,.05,BORROW_ANNUAL)
        indexed=bars.set_index(['symbol','date'])
        for row in trades[trades.exit_reason.eq('learned_exit_next_open')].itertuples():
            if not np.isclose(row.exit_price,indexed.at[(row.symbol,row.exit_date),'open']):raise ValueError('Margin cover not at open')
    pnl=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    terminal=pd.Timestamp(terminal)
    opened=[dict(symbol=s,quantity=p.quantity,entry_date=str(p.entry_date.date()),entry_price=p.entry_price,
        mark=float(ledger.close.at[terminal,s]),unrealized_pnl_usd=p.entry_cash_flow-p.quantity*float(ledger.close.at[terminal,s]),
        accrued_borrow_usd=p.quantity*p.entry_price*BORROW_ANNUAL*(days.get_loc(terminal)-p.entry_idx)/252)
        for s,p in ledger.state.positions.items()]
    native=float(daily.equity.iloc[-1]);latent=sum(v['unrealized_pnl_usd'] for v in opened)
    if not np.isclose(4000+float(pnl.sum())+latent-ledger.interest,native,atol=1e-6):raise ValueError('SHORT wealth not reconciled')
    curve=pd.concat([pd.Series([4000.]),daily.equity_net_accrued_borrow],ignore_index=True)
    calendar=daily[pd.to_datetime(daily.date).le(f'{year}-12-31' if year<2026 else '2026-09-30')]
    cc=pd.concat([pd.Series([4000.]),calendar.equity_net_accrued_borrow],ignore_index=True)
    final=float(curve.iloc[-1]);cal=float(cc.iloc[-1]);wins=int(pnl.gt(0).sum());losses=int(pnl.lt(0).sum())
    result.update(status='COMPLETED_EXPLORATORY_OPEN_SHORT_MTM' if opened else 'COMPLETED_EXPLORATORY',year=year,
        initial_capital_usd=4000.,final_capital_usd=final,native_equity_before_open_borrow_usd=native,
        calendar_end_capital_usd=cal,calendar_end_return_pct=100*(cal/4000-1),net_return_pct=100*(final/4000-1),
        calendar_end_drawdown_pct=100*float((cc/cc.cummax()-1).min()),max_drawdown_pct=100*float((curve/curve.cummax()-1).min()),
        calendar_end_positions=int(calendar.positions.iloc[-1]),winning_positions=wins,losing_positions=losses,
        winning_pct=100*wins/len(pnl) if len(pnl) else None,positive_closed_pnl_usd=float(pnl[pnl>0].sum()),
        negative_closed_pnl_usd=float(pnl[pnl<0].sum()),realized_pnl_usd=float(pnl.sum()),unrealized_pnl_usd=latent,
        open_positions=opened,closed_borrow_usd=float(trades.borrow_cost.sum()) if len(trades) else 0.,
        accrued_open_borrow_usd=sum(v['accrued_borrow_usd'] for v in opened),
        mean_gross_capital_usd=float(daily.gross_notional.mean()),
        mean_gross_leverage=float((daily.gross_notional/daily.equity_net_accrued_borrow).mean()),
        historical_shortability_verified=False,dividend_compensation_modelled=False,new_gpt_calls=0)
    return result


def run_case(root,p,panel,prices,year,profile,arm):
    folder=root/f'{year}-{profile}-{arm}';folder.mkdir(exist_ok=True);marker=folder/'case-report.json'
    if marker.exists():
        saved=long.read(marker)
        if saved['status'].startswith('COMPLETED'):verify_hashes(folder,saved['files']);return saved
    spec=p['years'][str(year)];candidates=panel[panel.date.dt.year.eq(year)].copy()
    bars=prices[prices.symbol.isin(set(candidates.symbol)|{'SPY'})&prices.date.le(spec['terminal'])].copy()
    days=long.grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames={k:bars.pivot(index='date',columns='symbol',values=v).reindex(days)
        for k,v in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    quality=bars[['date','symbol','is_filled','instrument_id']]
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict();refs=[]
    def factory(cfg,**kwargs):
        value=ShortMarkLedger(cfg,quality=quality,study_end=spec['terminal'],events=p['events'],**kwargs)
        refs.append(value);return value
    base=dict(year=year,profile=profile,arm=arm,batch_id=long.MODELS[year],side='SHORT')
    try:
        with (folder/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result=long.run_portfolio(frames=frames,scores=candidates,sectors=sectors,
                macro=long.ArchivedMacro(pd.read_parquet(p['macro'])),market_config=long.grid.parse_market_regimes(p['market']),
                policy=arm,variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=partial(ShortMarginSession,ledger_ref=refs,study_arm=arm),reject_constrained_entries=True,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=margin_policy,
                research_allow_short_normal=profile=='RESEARCH_SHORT_NORMAL')
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        result=summarize(result,refs[0],daily,trades,bars,days,year,spec['terminal'])
        result.update(base,raw_bearish_days=int(candidates.bearish.sum()),candidate_days=int(candidates[arm].sum()))
        opened=[(pd.Timestamp(a['date']),s) for a in long.read(folder/'executions.json') for s in a['opened']]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in candidates[candidates[arm]].itertuples()
            if days.get_loc(r.date)+1<len(days)}
        if any(key not in allowed for key in opened):raise ValueError('SHORT entry outside allowed next-open cohort')
        if year<2026 and result['open_positions']:raise ValueError('Incomplete old-year SHORT expiry tail')
        result['actual_entries']=len(opened)
        atomic_json(folder/'open-positions.json',result['open_positions']);atomic_json(folder/'maintenance.json',refs[0].margin_audits)
        atomic_json(folder/'expiry-audit.json',refs[0].expiry_audits)
        result['files']={n:digest(folder/n) for n in ['daily.parquet','trades.parquet','executions.json','decisions.json',
            'regimes.json','open-positions.json','maintenance.json','expiry-audit.json']}
    except Exception as exc:result=dict(base,status='FAILED',error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(root,phase):
    root.mkdir(parents=True,exist_ok=True);p=prepare(root)
    if phase=='prepare':return dict(status='READY',bearish=734,api_calls=0)
    panel=pd.read_parquet(root/'candidates.parquet');prices=pd.read_parquet(p['prices']);reports=[]
    for arm in ARMS:
        for profile in PROFILES:
            for year in long.MODELS:
                atomic_json(root/'progress.json',dict(status='RUNNING',year=year,profile=profile,arm=arm,completed=len(reports),total=12,api_calls=0))
                reports.append(run_case(root,p,panel,prices,year,profile,arm))
                atomic_json(root/'report.json',dict(status='RUNNING',completed=len(reports),total=12,reports=reports,api_calls=0))
    result=dict(status='COMPLETED' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
        completed=len(reports),total=12,reports=reports,api_calls=0,sql_writes=False,historical_shortability_verified=False)
    atomic_json(root/'report.json',result);atomic_json(root/'progress.json',{k:v for k,v in result.items() if k!='reports'})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run'],default='run');args=parser.parse_args()
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden in cached-news SHORT replay')
    requests.Session.request=forbidden
    with exclusive_run(args.output):
        try:print(json.dumps(run(args.output,args.phase),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':main()
