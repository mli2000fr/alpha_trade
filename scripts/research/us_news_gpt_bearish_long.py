"""Invert cached GPT BEARISH to LONG, TP10/SL10; offline, no SQL/API/orders."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_bullish_portfolio as native
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

SOURCE = Path('artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1')
POLICY = 'GPT_BEARISH_AS_LONG'
TP, SL = .10, .10


def eligible(row):
    # All valid BEARISH opinions, including lower confidence; no optimized cutoff.
    return row.get('decision')=='BEARISH' and row.get('technical_status')=='VALID'


def prepare(root):
    if (root/'ready.json').exists():
        p=native.read(root/'ready.json')
        if p['experiment']!='GPT_BEARISH_AS_LONG_TP10_SL10':raise ValueError('Wrong output protocol')
        verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files']);return p
    if (root/'protocol.json').exists():raise ValueError('Incomplete preparation: use a fresh output ID')
    old=native.read(SOURCE/'ready.json')
    verify_hashes(Path('.'),old['sources']);verify_hashes(SOURCE,old['files'])
    report=native.read(SOURCE/'report.json');audit=native.read(SOURCE/'audit.json')
    if report['status']!='COMPLETED' or not audit['status'].startswith('AUDITED'):
        raise ValueError('Completed audited BEARISH source required')
    verify_hashes(SOURCE,audit['files'])
    panel=pd.read_parquet(SOURCE/'candidates.parquet')
    panel['bearish']=panel.apply(eligible,axis=1);panel[POLICY]=panel.selected & panel.bearish
    if len(panel)!=13780 or int(panel.bearish.sum())!=734 or int(panel[POLICY].sum())!=732:
        raise ValueError('Frozen 13,780 / 734 raw / 732 admissible populations differ')
    for row in panel.itertuples():
        if row.batch_id!=old['models'][str(row.date.year)]:raise ValueError('Wrong annual model')
    panel.to_parquet(root/'candidates.parquet',index=False)
    sources=dict(old['sources'])
    for path in [SOURCE/name for name in ['ready.json','report.json','audit.json','candidates.parquet','sql-bearish-validation.json']]+[
            Path(__file__),Path('tests/test_us_news_gpt_bearish_long.py')]:
        sources[str(path)]=digest(path)
    p=dict(experiment='GPT_BEARISH_AS_LONG_TP10_SL10',models=old['models'],years=old['years'],
        raw_bearish_candidates=734,admissible_candidates=732,no_extra_confidence_threshold=True,
        side='LONG',strategy='invert BEARISH opinion, not a SHORT model or a new Oracle prediction',
        tp=TP,sl=SL,trailing=False,holding_sessions=20,expiry='open after twenty holding sessions',
        annual_capital_reset=True,capital_usd=4000.,max_entry_leverage=2.,position_cap_equity=.4,
        risk_budget_formula='.4 * SL before native guards',interest_annual=.065,interest_basis='ACT/360 debit cash',
        no_reinforcement=True,no_replacement_outside_top20=True,
        priority='original Oracle score descending; not GPT confidence',entry='next session open, native 3 percent gap guard',
        prices=old['prices'],macro=old['macro'],sectors=old['sectors'],events=old['events'],market=old['market'],
        current_sectors_non_pit=True,historical_pit_certified=False,llm_future_memory_excluded=False,
        dividends_complete=False,historical_marginability_certified=False,independent_holdout=False,
        comparison_warning='Exploratory inversion after observing original losses; TP/SL also changed; not isolated direction effect',
        api_calls=0,sql_writes=False,training=False,broker_orders=False,production_changes=False,
        sources=sources,files={'candidates.parquet':digest(root/'candidates.parquet')})
    atomic_json(root/'protocol.json',p);atomic_json(root/'ready.json',p);return p


def summarize(result,ledger,daily,trades,year,terminal):
    opened=[dict(symbol=s,entry_date=str(p.entry_date.date()),quantity=p.quantity,entry_price=p.entry_price,
        mark=float(ledger.close.at[pd.Timestamp(terminal),s]),
        unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(terminal),s])-p.entry_cost)
        for s,p in ledger.state.positions.items()]
    pnl=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    open_keys={(p['symbol'],pd.Timestamp(p['entry_date'])) for p in opened}
    closed=pnl[[key not in open_keys for key in pnl.index]]
    latent=sum(p['unrealized_pnl_usd'] for p in opened);final=float(daily.equity.iloc[-1])
    if not np.isclose(4000+float(pnl.sum())+latent-ledger.interest,final,atol=1e-6):
        raise ValueError('LONG wealth not reconciled')
    if len(trades):
        if not trades.side.eq('buy').all() or trades.exit_reason.str.contains('terminal|trailing').any():
            raise ValueError('Unexpected SHORT/terminal/trailing exit')
        if not np.allclose(trades.replay_initial_stop_price,trades.entry_price*(1-SL)):
            raise ValueError('Wrong SL10')
        if not np.allclose(trades.replay_take_profit_price,trades.entry_price*(1+TP)):
            raise ValueError('Wrong TP10')
        if not trades.borrow_cost.eq(0).all():raise ValueError('Borrow charges on LONG')
    calendar=daily[daily.date.le(f'{year}-12-31' if year<2026 else '2026-09-30')]
    curve=pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
    wins,losses=int(closed.gt(0).sum()),int(closed.lt(0).sum())
    result.update(status='COMPLETED_EXPLORATORY_OPEN_MTM' if opened else 'COMPLETED_EXPLORATORY',year=year,
        initial_capital_usd=4000.,final_capital_usd=final,net_return_pct=100*(final/4000-1),
        calendar_end_capital_usd=float(calendar.equity.iloc[-1]),
        calendar_end_return_pct=100*(float(calendar.equity.iloc[-1])/4000-1),
        calendar_end_drawdown_pct=100*float((curve/curve.cummax()-1).min()),max_drawdown_pct=100*result['max_drawdown'],
        calendar_end_positions=int(calendar.positions.iloc[-1]),closed_positions=len(closed),winning_positions=wins,losing_positions=losses,
        flat_positions=int(closed.eq(0).sum()),winning_pct=100*wins/len(closed) if len(closed) else None,
        losing_pct=100*losses/len(closed) if len(closed) else None,
        positive_closed_pnl_usd=float(closed[closed.gt(0)].sum()),negative_closed_pnl_usd=float(closed[closed.lt(0)].sum()),
        realized_pnl_usd=float(pnl.sum()),unrealized_pnl_usd=latent,partial_realized_open_positions_usd=float(pnl.sum()-closed.sum()),
        open_positions=opened,mean_gross_leverage=float((daily.gross_notional/daily.equity).mean()),
        mean_gross_capital_usd=float(daily.gross_notional.mean()),tp=TP,sl=SL,side='LONG',new_gpt_calls=0,
        historical_pit_certified=False,production_promotion=False)
    return result


def run_case(root,p,panel,prices,year):
    folder=root/str(year);folder.mkdir(exist_ok=True);marker=folder/'case-report.json'
    if marker.exists():
        saved=native.read(marker)
        if saved['status'].startswith('COMPLETED'):verify_hashes(folder,saved['files']);return saved
    spec=p['years'][str(year)];subset=panel[panel.date.dt.year.eq(year)].copy()
    bars=prices[prices.date.le(spec['terminal'])].copy()
    days=native.grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames={key:bars.pivot(index='date',columns='symbol',values=field).reindex(days)
        for key,field in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    quality=bars[['date','symbol','is_filled','instrument_id']]
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict()
    sectors['VMRK']=sectors['EQR'];sectors['TELWY']=sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    refs=[]
    def factory(cfg,**kwargs):
        ledger=native.ExpiryMarkLedger(cfg,quality=quality,sl=SL,trail=None,tp=TP,study_end=spec['terminal'],events=p['events'],**kwargs)
        refs.append(ledger);return ledger
    try:
        with (folder/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result=native.run_portfolio(frames=frames,scores=subset,sectors=sectors,
                macro=native.ArchivedMacro(pd.read_parquet(p['macro'])),market_config=native.grid.parse_market_regimes(p['market']),
                policy=POLICY,variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=partial(native.grid.MarginAwareSession,ledger_ref=refs),reject_constrained_entries=True,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=native.grid.margin_policy)
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        result=summarize(result,refs[0],daily,trades,year,spec['terminal'])
        opened=[(pd.Timestamp(e['date']),s) for e in native.read(folder/'executions.json') for s in e['opened']]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in subset[subset[POLICY]].itertuples()
                 if days.get_loc(r.date)+1<len(days)}
        if any(pair not in allowed for pair in opened):raise ValueError('Entry not a BEARISH next-open candidate')
        if year<2026 and result['open_positions']:raise ValueError('Incomplete old-year expiry tail')
        result.update(batch_id=p['models'][str(year)],actual_entries=len(opened),raw_bearish_days=int(subset.bearish.sum()),
            candidate_days=int(subset[POLICY].sum()))
        atomic_json(folder/'open-positions.json',result['open_positions']);atomic_json(folder/'expiry-audit.json',refs[0].expiry_audits)
        atomic_json(folder/'maintenance.json',refs[0].margin_audits)
        result['files']={name:digest(folder/name) for name in ['daily.parquet','trades.parquet','executions.json','decisions.json',
            'regimes.json','open-positions.json','expiry-audit.json','maintenance.json','corporate-actions.json']}
    except Exception as exc:result=dict(status='FAILED',year=year,error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(root,phase):
    root.mkdir(parents=True,exist_ok=True);p=prepare(root)
    if phase=='prepare':return dict(status='READY',bearish=734,admissible=732,api_calls=0)
    panel=pd.read_parquet(root/'candidates.parquet');prices=pd.read_parquet(p['prices']);reports=[]
    for year in (2024,2025,2026):
        atomic_json(root/'progress.json',dict(status='RUNNING',year=year,completed=len(reports),total=3,api_calls=0))
        reports.append(run_case(root,p,panel,prices,year))
        atomic_json(root/'report.json',dict(status='RUNNING',completed=len(reports),total=3,reports=reports))
    result=dict(status='COMPLETED' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
        completed=len(reports),total=3,reports=reports,api_calls=0,sql_writes=False,training=False)
    atomic_json(root/'report.json',result);atomic_json(root/'progress.json',{k:v for k,v in result.items() if k!='reports'})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run'],default='run');args=parser.parse_args()
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden in cached BEARISH-to-LONG replay')
    requests.Session.request=forbidden
    with exclusive_run(args.output):
        try:print(json.dumps(run(args.output,args.phase),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
