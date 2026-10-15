"""Annual LONG-only replay of the 913 SQL-cached BULLISH candidate-days.

No GPT calls, training, SQL writes or broker orders. Shared native research
ledger; fixed TP20/SL5, 20 holding sessions, 2026 open positions marked at cutoff.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout,redirect_stderr
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event,text,bindparam

from service.llm_directional.news_cache import sha,request_identity
from service.llm_directional.stored_news import parse
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research.us_concentrated_live_portfolio import run_portfolio,ArchivedMacro

SOURCE=Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
MODELS={2024:'model-factory-20261014113215-437ed1',2025:'model-factory-20261014113226-102eca',
    2026:'model-factory-20261014113232-bc35a7'}
ARMS=('GPT_BULLISH_ONLY','ORACLE_TOP20_ALL_LONG')
LOG=logging.getLogger(__name__)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def eligible_bullish(row):
    return row.get('decision')=='BULLISH' and row.get('technical_status')=='VALID'


def load_sql_panel(engine,root):
    """Replay immutable SQL snapshots and revalidate bullish raw replies, no qualify()/DML."""
    local_protocol=read(SOURCE/'protocol.json');source_report=read(SOURCE/'report.json')
    if source_report['status']!='COMPLETED' or source_report['unresolved']!=0:raise ValueError('Complete sealed GPT campaign required')
    rows=[];manifests=[];sources={str(SOURCE/'protocol.json'):digest(SOURCE/'protocol.json'),
        str(SOURCE/'report.json'):digest(SOURCE/'report.json')}
    for month in sorted({s[:7] for s in local_protocol['sessions']}):
        source='us-news-top20-history-20261015-v1:'+month
        with engine.connect() as conn:
            snapshots={}
            for suffix in ('prepared','completed'):
                row=conn.execute(text('SELECT snapshot_json,snapshot_sha256 FROM llm_news_analysis_research_runs WHERE import_id=:id'),
                    dict(id=sha(source+':'+suffix))).mappings().one()
                value=json.loads(row['snapshot_json'])
                if sha(value)!=row['snapshot_sha256']:raise ValueError('SQL snapshot hash mismatch')
                snapshots[suffix]=value
            prepared,completed=snapshots['prepared'],snapshots['completed']
            if prepared['protocol']!=local_protocol or completed['protocol_sha256']!=sha(local_protocol):
                raise ValueError('SQL protocol does not match sealed analysis')
            values=completed['assessments']
            packet_map={(p['decision_date'],p['symbol']):p for p in prepared['packets']}
            if len(packet_map)!=len(values):raise ValueError('Incomplete SQL decision panel')
            for value in values:
                packet=packet_map[(value['decision_date'],value['symbol'])]
                if any(value[k]!=packet[k] for k in ('oracle_rank','batch_id')):raise ValueError('Changed candidate/rank')
                if value['batch_id']!=MODELS[int(month[:4])]:raise ValueError('Wrong annual model')
            selected=[v for v in values if eligible_bullish(v)]
            if selected:
                query=text('SELECT * FROM llm_news_analysis_cache WHERE cache_key IN :keys').bindparams(bindparam('keys',expanding=True))
                cached={r['cache_key']:dict(r) for r in conn.execute(query,dict(keys=[v['cache_key'] for v in selected])).mappings()}
                for value in selected:
                    saved=cached[value['cache_key']];request=json.loads(saved['request_json']);response=json.loads(saved['response_json'])
                    if (saved['status']!='VALID' or request_identity(request,'SYMBOL_DATE_BUNDLE')[0]!=value['cache_key']
                            or sha(response)!=saved['response_sha256'] or sha(response)!=value['raw_response_sha256']):
                        raise ValueError('Bullish response integrity failure')
                    assessment=parse(response,request)
                    if any(assessment[k]!=value[k] for k in assessment):raise ValueError('Reparsed bullish verdict differs')
        folder=SOURCE/'months'/month;path=folder/'candidates.parquet'
        expected=prepared['prepared']['files']['candidates.parquet']
        if digest(path)!=expected:raise ValueError('Frozen rank/score file changed')
        candidates=pd.read_parquet(path)
        decision_frame=pd.DataFrame(values);decision_frame['date']=pd.to_datetime(decision_frame.decision_date)
        candidates=candidates.merge(decision_frame[['date','symbol','decision','technical_status','confidence','batch_id','cache_key']],
            on=['date','symbol'],how='left',validate='one_to_one')
        if candidates.decision.isna().any():raise ValueError('Missing assessment')
        if not candidates.groupby('date').size().eq(20).all():raise ValueError('Expected frozen TOP20 each session')
        candidates['bullish']=candidates.apply(eligible_bullish,axis=1)
        # Preserve the actual Oracle score and ordering; never prioritize GPT confidence.
        candidates['proba_extreme']=candidates.score.astype(float)
        rows.append(candidates)
        manifests.append(dict(month=month,sql_prepared_id=sha(source+':prepared'),sql_completed_id=sha(source+':completed'),
            prepared_sha256=sha(prepared),completed_sha256=sha(completed),bullish=len(selected)))
        sources[str(path)]=expected
    panel=pd.concat(rows,ignore_index=True).sort_values(['date','oracle_rank'])
    if len(panel)!=13780 or int(panel.bullish.sum())!=913 or panel.duplicated(['date','symbol']).any():
        raise ValueError('Expected exact 13,780 candidate-days / 913 BULLISH')
    panel.to_parquet(root/'decisions.parquet',index=False)
    atomic_json(root/'sql-snapshots.json',manifests)
    return panel,sources


def prepare(root):
    marker=root/'ready.json'
    if marker.exists():
        p=read(marker);verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files']);return p
    from database.connection import get_sqlalchemy_engine
    from scripts.research.us_oracle_barrier_comparison import readonly_statement
    from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
    from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
    from scripts.research.us_news_gpt_q1_2025_prepare import j_history_admission
    from scripts.research import us_oracle_path_protection_dataset as data
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    event.listen(engine,'before_cursor_execute',readonly_statement);event.listen(engine,'begin',readonly_begin)
    try:panel,sources=load_sql_panel(engine,root)
    finally:
        event.remove(engine,'before_cursor_execute',readonly_statement);event.remove(engine,'begin',readonly_begin);engine.dispose()
    old=read('artifacts/research/us_oracle_path_protection_selector/20261014-v1/protocol.json')
    for name in (old['prices'],old['macro'],str(grid.SECTORS)):
        expected=next(v for k,v in old['sources'].items() if Path(k)==Path(name))
        if digest(name)!=expected:raise ValueError('Archived market tape changed: '+name)
        sources[name]=expected
    prices=pd.read_parquet(old['prices']);prices.date=pd.to_datetime(prices.date)
    required=set(panel.symbol)|{'SPY'}
    for item in old['events']:
        if item['source'] in required:required.add(item['target'])
    prices=prices[prices.symbol.isin(required)].copy()
    if prices.duplicated(['date','symbol']).any():raise ValueError('Duplicate price keys')
    days=grid.nyse_sessions('2023-01-01','2026-12-31')
    benchmark=prices[prices.symbol.eq('SPY')].set_index('date').close.reindex(days)
    admissions=[]
    for symbol,part in panel.groupby('symbol'):
        raw=prices[prices.symbol.eq(symbol)].set_index('date').reindex(days).assign(symbol=symbol).reset_index(names='date')
        features=data.decision_features(raw,benchmark)
        quality=data.j_history_quality(raw.set_index('date'),benchmark,days)
        admissions.extend(j_history_admission(part,features,quality,data))
    panel=panel.merge(pd.DataFrame(admissions),on=['date','symbol'],validate='one_to_one')
    sectors=pd.read_parquet(grid.SECTORS).set_index('symbol').sector.to_dict()
    panel['sector']=panel.symbol.map(sectors)
    bad_sector=panel.sector.isna()|panel.sector.str.lower().isin(['unknown','unqualified_pit_sector'])
    panel.loc[bad_sector,'selected']=False
    panel.loc[bad_sector,'entry_quality_reason']='CURRENT_SECTOR_UNQUALIFIED'
    panel['GPT_BULLISH_ONLY']=panel.selected & panel.bullish
    panel['ORACLE_TOP20_ALL_LONG']=panel.selected
    panel.to_parquet(root/'candidates.parquet',index=False)
    prices.to_parquet(root/'prices.parquet',index=False)
    ends={}
    for year in MODELS:
        decision_end=pd.Timestamp(f'{year}-12-31' if year!=2026 else '2026-09-30')
        last=days[days<=decision_end][-1];tail=days[days.get_loc(last)+21]
        ends[str(year)]=dict(decision_end=str(last.date()),requested_full_tail=str(tail.date()),
            terminal=str(tail.date()) if year<2026 else '2026-09-30',
            open_mtm_expected=year==2026)
    sources.update(code_hashes())
    for path in [Path(__file__),Path('tests/test_us_news_gpt_bullish_portfolio.py'),
        Path('scripts/research/us_news_gpt_q1_2025_evaluate.py'),
        Path('scripts/research/us_news_gpt_q1_2025_prepare.py'),Path(data.__file__),
        Path(grid.__file__),Path('service/llm_directional/stored_news.py'),Path('service/llm_directional/news_cache.py')]:
        sources[str(path)]=digest(path)
    p=dict(experiment='GPT_BULLISH_ONLY_ANNUAL_NATIVE_PORTFOLIO',source=str(SOURCE),models=MODELS,
        top=20,bullish_candidates=913,no_extra_confidence_threshold=True,arms=ARMS,years=ends,
        capital_usd=4000.,annual_capital_reset=True,max_leverage=2.,tp=.20,sl=.05,trailing=False,
        expiry_open_after_holding_sessions=20,no_reinforcement=True,no_replacement_outside_top20=True,
        priority='original Oracle probability descending, not GPT confidence',
        entry='next session open; native maximum 3% gap guard; contemporaneous admission only',
        admission='same Q1 test: finite causal price features, 121 clean stable-identity bars, 201 benchmark bars',
        prices=old['prices'],macro=old['macro'],sectors=str(grid.SECTORS),events=old['events'],market=old['market'],
        native_risk_regime_costs_unchanged=True,margin_interest_annual=.065,interest_basis='ACT/360 calendar debit',
        historical_marginability_certified=False,dividends_complete=False,current_sectors_non_pit=True,
        historical_news_pit_certified=False,llm_future_memory_excluded=False,independent_holdout=False,
        api_cost_total_historical_campaign=read(SOURCE/'report.json')['cost_usd'],
        api_cost_allocation='separate annual full-campaign cost, not new spending; cached requests are not charged twice',
        api_calls=0,training=False,sql_writes=False,broker_orders=False,production_changes=False,sources=sources,
        files={n:digest(root/n) for n in ['decisions.parquet','sql-snapshots.json','candidates.parquet','prices.parquet']})
    atomic_json(root/'protocol.json',p);atomic_json(marker,p)
    return p


class ExpiryMarkLedger(grid.UnlimitedLedger):
    """Same twenty-session open expiry, but allow unfinished final-year MTM.

    This research-only hook executes after corporate actions, before native gap
    protections/entries. It does not change any shared engine or live policy.
    """
    def __init__(self,*args,quality,holding_sessions=20,**kwargs):
        self.quality=quality;self.holding_sessions=holding_sessions;self.expiry_audits=[]
        super().__init__(*args,**kwargs)

    def corporate_action_open(self,session,pending,steps,day):
        pending,steps=super().corporate_action_open(session,pending,steps,day)
        due=[]
        for symbol,p in self.state.positions.items():
            if self.days.get_loc(day)-p.entry_idx<self.holding_sessions:continue
            # Keep the same fail-closed checks that precede expiry in the old loop.
            volume=self.volume.at[day,symbol]
            if not pd.notna(volume) or volume<=0:raise ValueError('Unqualified expiry volume '+symbol)
            observed=self.quality.loc[(self.quality.symbol==symbol)&self.quality.date.between(p.entry_date,day)]
            if observed.is_filled.fillna(0).ne(0).any() or observed.instrument_id.dropna().nunique()>1:
                raise ValueError('Unqualified expiry filled/identity '+symbol)
            due.append(dict(symbol=symbol,exit_date=day,exit_price=self.opens.at[day,symbol],exit_reason='expiry_open'))
        for trade in self.close_resolved(due,phase='open'):
            symbol=trade['symbol']
            if symbol in self.state.positions:raise ValueError('Expiry did not close the entire position')
            position_pnl=sum(t['pnl'] for t in self.state.closed_trades if t['symbol']==symbol and t['entry_date']==trade['entry_date'])
            session.record_fill(f'expiry-{symbol}-{trade["entry_date"]}-{day}',day=day.date(),symbol=symbol,
                entry=False,realized_pnl=position_pnl)
            self.expiry_audits.append(dict(symbol=symbol,entry_date=trade['entry_date'],exit_date=day,exit_price=trade['exit_price']))
        return pending,steps


def summarize(result,ledger,daily,trades,year,terminal):
    pnl=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    open_rows=[dict(symbol=s,entry_date=str(p.entry_date.date()),quantity=p.quantity,entry_price=p.entry_price,
        mark=float(ledger.close.at[pd.Timestamp(terminal),s]),
        unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(terminal),s])-p.entry_cost)
        for s,p in ledger.state.positions.items()]
    final=float(daily.equity.iloc[-1]);realized=float(pnl.sum());unrealized=sum(p['unrealized_pnl_usd'] for p in open_rows)
    if not np.isclose(4000+realized+unrealized-ledger.interest,final,atol=1e-6):raise ValueError('Final wealth not reconciled')
    if len(trades):
        if not trades.side.eq('buy').all() or trades.exit_reason.str.contains('trailing|terminal_close',regex=True).any():
            raise ValueError('Unexpected exit or direction')
        if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*.95,rtol=1e-7,atol=1e-6).all():
            raise ValueError('Fixed 5% initial stop changed')
    by_month=[];previous=4000.
    for month,part in daily.groupby(pd.to_datetime(daily.date).dt.strftime('%Y-%m')):
        end=float(part.equity.iloc[-1]);by_month.append(dict(month=month,initial_equity=previous,final_equity=end,
            net_change_usd=end-previous,return_pct=100*(end/previous-1)));previous=end
    wins=int(pnl.gt(0).sum());losses=int(pnl.lt(0).sum())
    calendar=daily[pd.to_datetime(daily.date).le(f'{year}-12-31' if year<2026 else '2026-09-30')]
    curve=pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
    year_end=float(calendar.equity.iloc[-1])
    result.update(year=year,initial_capital_usd=4000.,final_capital_usd=final,net_return_pct=100*(final/4000-1),
        calendar_end_capital_usd=year_end,calendar_end_return_pct=100*(year_end/4000-1),
        calendar_end_drawdown_pct=100*float((curve/curve.cummax()-1).min()),
        max_drawdown_pct=100*result['max_drawdown'],winning_positions=wins,losing_positions=losses,
        winning_pct=100*wins/len(pnl) if len(pnl) else None,losing_pct=100*losses/len(pnl) if len(pnl) else None,
        positive_closed_pnl_usd=float(pnl[pnl.gt(0)].sum()),negative_closed_pnl_usd=float(pnl[pnl.lt(0)].sum()),
        realized_pnl_usd=realized,unrealized_pnl_usd=unrealized,open_positions=open_rows,monthly=by_month,
        mean_gross_capital_usd=float(daily.gross_notional.mean()),max_gross_capital_usd=float(daily.gross_notional.max()),
        mean_gross_leverage=float((daily.gross_notional/daily.equity).mean()),
        max_gross_leverage=float((daily.gross_notional/daily.equity).max()),
        closed_exit_reasons=dict(Counter(trades.exit_reason)) if len(trades) else {},
        status='COMPLETED_EXPLORATORY_OPEN_MTM' if open_rows else 'COMPLETED_EXPLORATORY',
        historical_pit_certified=False,production_promotion=False,new_gpt_calls=0)
    return result


def run_case(root,p,panel,prices,year,arm):
    output=root/f'{year}-{arm}';output.mkdir(exist_ok=True);marker=output/'case-report.json'
    if marker.exists():
        saved=read(marker)
        if saved['status'].startswith('COMPLETED'):verify_hashes(output,saved['files']);return saved
    spec=p['years'][str(year)];subset=panel[panel.date.dt.year.eq(year)].copy()
    required=set(subset.symbol)|{'SPY'}
    for e in p['events']:
        if e['source'] in required:required.add(e['target'])
    bars=prices[prices.symbol.isin(required)&prices.date.le(spec['terminal'])].copy()
    days=grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames={k:bars.pivot(index='date',columns='symbol',values=v).reindex(days)
        for k,v in [('opens','open'),('high','high'),('low','low'),('close','close'),('volume','volume')]}
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict()
    sectors['VMRK']=sectors['EQR'];sectors['TELWY']=sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    quality=bars[['date','symbol','is_filled','instrument_id']]
    refs=[]
    def factory(cfg,**kwargs):
        value=ExpiryMarkLedger(cfg,quality=quality,sl=.05,trail=.15,tp=.20,study_end=spec['terminal'],events=p['events'],**kwargs)
        refs.append(value);return value
    try:
        with (output/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result=run_portfolio(frames=frames,scores=subset,sectors=sectors,
                macro=ArchivedMacro(pd.read_parquet(p['macro'])),market_config=grid.parse_market_regimes(p['market']),
                policy=arm,variant='CURRENT_NO_EXPIRY',output=output,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=partial(grid.MarginAwareSession,ledger_ref=refs),reject_constrained_entries=True,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=grid.margin_policy)
        daily=pd.read_parquet(output/'daily.parquet');trades=pd.read_parquet(output/'trades.parquet')
        result=summarize(result,refs[0],daily,trades,year,spec['terminal'])
        result.update(arm=arm,batch_id=MODELS[year],candidate_days=int(subset[arm].sum()),
            raw_bullish_days=int(subset.bullish.sum()),entry_quality_rejected_bullish=int((subset.bullish&~subset.selected).sum()))
        if year<2026 and result['open_positions']:raise ValueError('Historical expiry tail is incomplete')
        opened=[(pd.Timestamp(a['date']),s) for a in read(output/'executions.json') for s in a['opened']]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in subset[subset[arm]].itertuples()
            if days.get_loc(r.date)+1<len(days)}
        if any(key not in allowed for key in opened):raise ValueError('Entry outside original filtered next-session candidates')
        result['actual_entries']=len(opened)
        atomic_json(output/'open-positions.json',result['open_positions']);atomic_json(output/'expiry-audit.json',refs[0].expiry_audits)
        result['files']={name:digest(output/name) for name in ['daily.parquet','trades.parquet','executions.json',
            'decisions.json','regimes.json','open-positions.json','expiry-audit.json']}
    except Exception as exc:
        result=dict(status='FAILED',year=year,arm=arm,batch_id=MODELS[year],error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(root,phase):
    root.mkdir(parents=True,exist_ok=True);p=prepare(root)
    if phase=='prepare':return dict(status='READY',bullish=913,api_calls=0)
    panel=pd.read_parquet(root/'candidates.parquet');prices=pd.read_parquet(root/'prices.parquet');reports=[]
    for arm in ARMS:
        for year in MODELS:
            atomic_json(root/'progress.json',dict(status='RUNNING',year=year,arm=arm,completed=len(reports),total=6,api_calls=0))
            reports.append(run_case(root,p,panel,prices,year,arm))
            summary=dict(status='RUNNING',completed=len(reports),total=6,reports=reports,api_calls=0)
            atomic_json(root/'report.json',summary)
    summary.update(status='COMPLETED' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
        historical_pit_certified=False,no_new_gpt_calls=True,sql_writes=False,annual_capital_reset=True)
    atomic_json(root/'report.json',summary);atomic_json(root/'progress.json',{k:v for k,v in summary.items() if k!='reports'})
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run'],default='run');args=parser.parse_args()
    # Offline replay must never silently fall back to a new paid/public HTTP call.
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden in cached-news backtest')
    requests.Session.request=forbidden
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):
        try:print(json.dumps(run(args.output,args.phase),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':main()
