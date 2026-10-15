"""Frozen LONG confidence >=0.90, TP20/SL10 replay; offline and no SQL writes."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_bullish_portfolio as previous
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1')
POLICY = 'GPT_BULLISH_CONFIDENCE_GE_090'
CONFIDENCE, TP, SL = .90, .20, .10


def eligible(row):
    confidence = row.get('confidence')
    return (row.get('decision') == 'BULLISH' and row.get('technical_status') == 'VALID'
            and type(confidence) in (int, float) and math.isfinite(confidence)
            and CONFIDENCE <= confidence <= 1)


def prepare(root):
    marker = root / 'ready.json'
    if marker.exists():
        saved = previous.read(marker)
        verify_hashes(Path('.'), saved['sources']); verify_hashes(root, saved['files'])
        return saved
    old = previous.read(SOURCE / 'ready.json')
    verify_hashes(Path('.'), old['sources']); verify_hashes(SOURCE, old['files'])
    if previous.read(SOURCE / 'report.json')['status'] != 'COMPLETED':
        raise ValueError('Completed original LONG replay required')
    frame = pd.read_parquet(SOURCE / 'candidates.parquet')
    frame['bullish_confident'] = frame.apply(eligible, axis=1)
    frame[POLICY] = frame.selected & frame.bullish_confident
    if len(frame) != 13780 or int(frame.bullish.sum()) != 913 or int(frame.bullish_confident.sum()) != 163:
        raise ValueError('Frozen 13,780 / 913 / 163 populations differ')
    frame.to_parquet(root / 'candidates.parquet', index=False)
    sources = dict(old['sources'])
    for name in (SOURCE/'ready.json', SOURCE/'report.json', SOURCE/'candidates.parquet', SOURCE/'prices.parquet',
                 Path(__file__), Path('tests/test_us_news_gpt_bullish_confidence.py')):
        sources[str(name)] = digest(name)
    protocol = dict(experiment='GPT_BULLISH_CONFIDENCE_GE_090_TP20_SL10', models=old['models'],
        years=old['years'], confidence_min=CONFIDENCE, threshold_inclusive=True, tp=TP, sl=SL,
        direction='LONG', top=20, bullish_original=913, confident_original=163,
        annual_capital_reset=True, capital_usd=4000., max_entry_leverage=2., position_cap_equity=.4,
        risk_budget_formula='.4 * SL before native guards; same sizing formula as original replay',
        trailing=False, holding_sessions=20, expiry='open after twenty sessions from next-open entry',
        no_reinforcement=True, priority='original Oracle score descending, not GPT confidence',
        no_replacement_outside_top20=True, initial_gap_guard_pct=3.,
        prices=str(SOURCE/'prices.parquet'), macro=old['macro'], sectors=old['sectors'],
        events=old['events'], market=old['market'], interest_annual=.065, interest_basis='ACT/360 debit cash',
        historical_pit_certified=False, independent_holdout=False, confidence_is_profit_probability=False,
        current_sectors_non_pit=True, marginability_certified=False, dividends_complete=False,
        comparison_warning='Two simultaneous changes versus earlier LONG: confidence and SL; no isolated effect claimed',
        api_calls=0, sql_writes=False, training=False, broker_orders=False, production_changes=False,
        sources=sources, files={'candidates.parquet':digest(root/'candidates.parquet')})
    atomic_json(root/'protocol.json', protocol); atomic_json(marker, protocol)
    return protocol


def summarize(result, ledger, daily, trades, year, terminal):
    open_rows = [dict(symbol=s, entry_date=str(p.entry_date.date()), quantity=p.quantity, entry_price=p.entry_price,
                     mark=float(ledger.close.at[pd.Timestamp(terminal), s]),
                     unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(terminal), s])-p.entry_cost)
                 for s,p in ledger.state.positions.items()]
    all_pnl = trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    open_keys = {(p['symbol'],pd.Timestamp(p['entry_date'])) for p in open_rows}
    closed_pnl = all_pnl[[key not in open_keys for key in all_pnl.index]]
    realized, latent = float(all_pnl.sum()), sum(p['unrealized_pnl_usd'] for p in open_rows)
    final = float(daily.equity.iloc[-1])
    if not np.isclose(4000+realized+latent-ledger.interest, final, atol=1e-6):
        raise ValueError('Wealth not reconciled')
    if len(trades):
        if not trades.side.eq('buy').all() or trades.exit_reason.str.contains('trailing|terminal').any():
            raise ValueError('Unexpected side/exit')
        if not np.allclose(trades.replay_initial_stop_price, trades.entry_price*(1-SL)):
            raise ValueError('Wrong SL10')
        if not np.allclose(trades.replay_take_profit_price, trades.entry_price*(1+TP)):
            raise ValueError('Wrong TP20')
    calendar = daily[daily.date.le(f'{year}-12-31' if year<2026 else '2026-09-30')]
    curve = pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
    wins, losses = int(closed_pnl.gt(0).sum()), int(closed_pnl.lt(0).sum())
    result.update(year=year, initial_capital_usd=4000., final_capital_usd=final, net_return_pct=100*(final/4000-1),
        calendar_end_capital_usd=float(calendar.equity.iloc[-1]),
        calendar_end_return_pct=100*(float(calendar.equity.iloc[-1])/4000-1),
        calendar_end_drawdown_pct=100*float((curve/curve.cummax()-1).min()),
        max_drawdown_pct=100*result['max_drawdown'], realized_pnl_usd=realized, unrealized_pnl_usd=latent,
        closed_positions=len(closed_pnl), winning_positions=wins, losing_positions=losses,
        flat_positions=int(closed_pnl.eq(0).sum()), winning_pct=100*wins/len(closed_pnl) if len(closed_pnl) else None,
        losing_pct=100*losses/len(closed_pnl) if len(closed_pnl) else None,
        positive_closed_pnl_usd=float(closed_pnl[closed_pnl.gt(0)].sum()),
        negative_closed_pnl_usd=float(closed_pnl[closed_pnl.lt(0)].sum()),
        partial_realized_open_positions_usd=realized-float(closed_pnl.sum()), open_positions=open_rows,
        mean_gross_leverage=float((daily.gross_notional/daily.equity).mean()),
        status='COMPLETED_EXPLORATORY_OPEN_MTM' if open_rows else 'COMPLETED_EXPLORATORY',
        historical_pit_certified=False, production_promotion=False, new_gpt_calls=0, tp=TP, sl=SL, confidence_min=CONFIDENCE)
    return result


def run_case(root, protocol, panel, prices, year):
    folder = root/str(year); folder.mkdir(exist_ok=True)
    marker = folder/'case-report.json'
    if marker.exists():
        saved = previous.read(marker)
        if saved['status'].startswith('COMPLETED'):
            verify_hashes(folder,saved['files']); return saved
    spec = protocol['years'][str(year)]
    subset = panel[panel.date.dt.year.eq(year)].copy()
    bars = prices[prices.date.le(spec['terminal'])].copy()
    days = previous.grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames = {key:bars.pivot(index='date',columns='symbol',values=value).reindex(days)
              for key,value in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    quality = bars[['date','symbol','is_filled','instrument_id']]
    sectors = pd.read_parquet(protocol['sectors']).set_index('symbol').sector.to_dict()
    sectors['VMRK'] = sectors['EQR']; sectors['TELWY'] = sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    refs = []
    def factory(cfg,**kwargs):
        ledger = previous.ExpiryMarkLedger(cfg,quality=quality,sl=SL,trail=None,tp=TP,
            study_end=spec['terminal'],events=protocol['events'],**kwargs)
        refs.append(ledger); return ledger
    try:
        with (folder/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result = previous.run_portfolio(frames=frames,scores=subset,sectors=sectors,
                macro=previous.ArchivedMacro(pd.read_parquet(protocol['macro'])),
                market_config=previous.grid.parse_market_regimes(protocol['market']), policy=POLICY,
                variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=partial(previous.grid.MarginAwareSession,ledger_ref=refs),
                reject_constrained_entries=True,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
                daily_exit_policy=previous.grid.margin_policy)
        daily = pd.read_parquet(folder/'daily.parquet'); trades = pd.read_parquet(folder/'trades.parquet')
        result = summarize(result,refs[0],daily,trades,year,spec['terminal'])
        opened = [(pd.Timestamp(e['date']),s) for e in previous.read(folder/'executions.json') for s in e['opened']]
        allowed = {(days[days.get_loc(r.date)+1],r.symbol) for r in subset[subset[POLICY]].itertuples()
                   if days.get_loc(r.date)+1<len(days)}
        if any(pair not in allowed for pair in opened): raise ValueError('Unqualified next-open entry')
        if year<2026 and result['open_positions']: raise ValueError('Incomplete expiry tail')
        result.update(batch_id=protocol['models'][str(year)],actual_entries=len(opened),
            raw_confident_days=int(subset.bullish_confident.sum()),candidate_days=int(subset[POLICY].sum()))
        atomic_json(folder/'open-positions.json',result['open_positions'])
        atomic_json(folder/'expiry-audit.json',refs[0].expiry_audits)
        atomic_json(folder/'maintenance.json',refs[0].margin_audits)
        result['files'] = {name:digest(folder/name) for name in ['daily.parquet','trades.parquet','executions.json',
            'decisions.json','regimes.json','open-positions.json','expiry-audit.json','maintenance.json','corporate-actions.json']}
    except Exception as exc:
        result = dict(status='FAILED',year=year,error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result); return result


def run(root,phase):
    root.mkdir(parents=True,exist_ok=True); protocol=prepare(root)
    if phase=='prepare': return dict(status='READY',raw_candidates=163,api_calls=0)
    panel=pd.read_parquet(root/'candidates.parquet'); prices=pd.read_parquet(protocol['prices']); reports=[]
    for year in (2024,2025,2026):
        atomic_json(root/'progress.json',dict(status='RUNNING',year=year,completed=len(reports),total=3,api_calls=0))
        reports.append(run_case(root,protocol,panel,prices,year))
        atomic_json(root/'report.json',dict(status='RUNNING',completed=len(reports),total=3,reports=reports))
    result=dict(status='COMPLETED' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
        completed=len(reports),total=3,reports=reports,api_calls=0,sql_writes=False,training=False)
    atomic_json(root/'report.json',result)
    atomic_json(root/'progress.json',{key:value for key,value in result.items() if key!='reports'})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run'],default='run'); args=parser.parse_args()
    import requests
    def forbidden(*args,**kwargs): raise RuntimeError('HTTP forbidden in cached-confidence replay')
    requests.Session.request=forbidden
    with exclusive_run(args.output):
        try: print(json.dumps(run(args.output,args.phase),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            raise
