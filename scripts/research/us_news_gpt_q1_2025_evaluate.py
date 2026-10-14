"""Paired local research portfolios after sealed Q1 GPT replies; no API or SQL.

All invalid LLM answers stay technical unknowns, never an inferred direction.
If present, this is an explicitly partial-signal diagnostic, not a qualified
historical/PIT backtest or a promotion of a production filter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr,redirect_stdout
from datetime import datetime,timezone
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_september_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

LOG=logging.getLogger(__name__)
ARMS=('ORACLE_ONLY','GPT_VALID_BEARISH_VETO')


def freeze(root):
    marker=root/'economic-protocol.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(Path('.'),saved['sources']);return saved
    from common.market_calendar import get_market_calendar
    from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
    from scripts.research.us_oracle_path_top5_leverage_grid import SECTORS
    prepared=pilot.read(root/'prepare.json');verify_hashes(root,prepared['files'])
    old=pilot.read(pilot.SOURCE/'protocol.json')
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    days=pd.DatetimeIndex([s.session_date for s in calendar.sessions('2025-01-01','2025-05-10') if s.is_open])
    tail=days[days.get_loc(pd.Timestamp('2025-03-31'))+21]
    sources=code_hashes()
    for path in [Path(__file__),Path('tests/test_us_news_gpt_q1_2025_evaluate.py'),
        Path('scripts/research/us_oracle_path_top5_leverage_grid.py'),
        root/'prepare.json',root/'protocol.json',root/'candidates.parquet']:
        sources[str(path)]=digest(path)
    p=dict(experiment='PAIRED_Q1_ORACLE_VS_VALIDATED_GPT_VETO',
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),entry_start='2025-01-02',entry_end='2025-03-31',
        terminal_date=str(tail.date()),arms=list(ARMS),top=10,capital_usd=4000.,max_leverage=2.,
        sl=.05,tp=.20,trailing=False,expiry_open_after_holding_sessions=20,
        native_costs_financing_risk_regime_unchanged=True,no_reinforcement=True,no_top11_replacement=True,
        invalid_reply_policy='UNKNOWN_INVALID_RESPONSE; never veto; label entire study partial signal if any',
        qualification_gate='no financial read until analysis.json sealed; no invalid answer reclassified bullish/bearish',
        price_source=old['prices'],macro_source=old['macro'],sectors=str(SECTORS),
        source_hashes={name:next(v for k,v in old['sources'].items() if Path(k)==Path(name))
                       for name in [old['prices'],old['macro']]},
        events=old['events'],market=old['market'],sources=sources,
        monthly='global continuous portfolio, no monthly reset; April tail reported separately',
        no_hypothesis_or_threshold_retuning=True,training=False,sql_writes=False,broker_orders=False,
        current_sectors_non_pit=True,macro_vintage_unqualified=True,historical_news_non_pit=True,
        llm_knowledge_after_test_period_possible=True,independent_holdout=False,
        user_authorized_api_cap_usd=1.,collector_enforced_cap_usd=.50,
        budget_note='User increased cap to 1 USD during collection; active stricter .50 cap unchanged; no paid retry',
        api_cost='separate conservative estimate subtracted only from filtered final wealth')
    atomic_json(marker,p)
    return p


def merge_decisions(candidates,assessments):
    decisions=pd.DataFrame(assessments)
    if decisions.duplicated(['decision_date','symbol']).any():raise ValueError('Duplicate LLM decision')
    decisions['date']=pd.to_datetime(decisions.decision_date)
    merged=candidates.merge(decisions[['date','symbol','decision','veto_long','technical_status']],
        on=['date','symbol'],how='left',validate='one_to_one')
    if merged.decision.isna().any() or len(merged)!=600:raise ValueError('Incomplete frozen LLM panel')
    invalid=merged.technical_status.eq('INVALID_PRESERVED')
    if merged.loc[invalid,'veto_long'].any():raise ValueError('Technical invalidity cannot trigger a veto')
    return merged


def unit_path(window,expiry_price,*,sl=.05,tp=.20):
    from backtesting.microstructure import resolve_intrabar_exit
    entry=float(window.iloc[0].open)
    if not np.isfinite(expiry_price) or expiry_price<=0:raise ValueError('Unqualified expiry open')
    stop,target=entry*(1-sl),entry*(1+tp)
    for i,(day,row) in enumerate(window.iterrows()):
        if i>0 and row.open<=stop:return day,float(row.open),'initial_stop_gap_open'
        if i>0 and row.open>=target:return day,target,'take_profit_gap_limit'
        result=resolve_intrabar_exit(day_high=float(row.high),day_low=float(row.low),
            take_profit_price=target,trailing_stop_price=-math.inf,initial_stop_price=stop,
            priority='conservative',side='buy',rng=None)
        if result.triggered:return day,float(result.exit_price),result.exit_reason
    return None,float(expiry_price),'expiry_open'


def unit_diagnostic(candidates,prices,days):
    from scripts.research.us_oracle_path_protection_headroom import qualify_window
    grouped={symbol:group.set_index('date').sort_index() for symbol,group in prices.groupby('symbol')}
    outputs=[]
    for row in candidates.itertuples(index=False):
        j=days.get_loc(row.date);holding=days[j+1:j+21];expiry=days[j+21]
        raw=grouped.get(row.symbol)
        base=dict(decision_date=str(row.date.date()),symbol=row.symbol,oracle_rank=int(row.oracle_rank),
            gpt=row.decision,veto_long=bool(row.veto_long),technical_status=row.technical_status)
        if raw is None:
            outputs.append(dict(base,status='UNQUALIFIED_MISSING_TAPE'));continue
        window=raw.reindex(holding)
        reason=qualify_window(window[['open','high','low','close','volume','is_filled','instrument_id']].to_numpy(dtype=object))
        if reason:
            outputs.append(dict(base,status=reason));continue
        entry=float(window.open.iloc[0]);previous=float(raw.at[row.date,'close'])
        if not np.isfinite(previous) or previous<=0 or abs(entry/previous-1)>.03:
            outputs.append(dict(base,status='NEXT_OPEN_GAP_GT3PCT'));continue
        if expiry not in raw.index or not pd.notna(raw.at[expiry,'open']):
            outputs.append(dict(base,status='MISSING_EXPIRY_OPEN'));continue
        day,price,reason=unit_path(window,float(raw.at[expiry,'open']))
        if day is None:day=expiry
        outputs.append(dict(base,status='QUALIFIED_EXPLORATORY_VENDOR_PATH',entry_date=str(holding[0].date()),
            exit_date=str(day.date()),entry_price=entry,exit_price=price,exit_reason=reason,
            gross_return_pct=100*(price/entry-1),tp_before_sl=reason.startswith('take_profit')))
    return outputs


def monthly_curves(daily,trades):
    frame=daily.copy();frame['date']=pd.to_datetime(frame.date)
    rows=[];previous=4000.
    for month,part in frame.groupby(frame.date.dt.strftime('%Y-%m'),sort=True):
        end=float(part.equity.iloc[-1])
        closed=trades[pd.to_datetime(trades.exit_date).dt.strftime('%Y-%m').eq(month)] if len(trades) else trades
        rows.append(dict(month=month,period='EXPIRY_TAIL' if month>'2025-03' else 'ENTRY_QUARTER',
            equity_start_usd=previous,equity_end_usd=end,return_pct=100*(end/previous-1),
            net_equity_change_usd=end-previous,closed_legs=len(closed)))
        previous=end
    return rows


def veto_attribution(candidates,days,executions,trades):
    """Describe blocked baseline entries, not an additive causal PnL estimate."""
    opened={(pd.Timestamp(row['date']),symbol) for row in executions for symbol in row['opened']}
    pnl=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
    pnl={(symbol,pd.Timestamp(day)):float(value) for (symbol,day),value in pnl.items()}
    rows=[]
    for row in candidates[candidates.veto_long].itertuples(index=False):
        entry=days[days.get_loc(row.date)+1]
        executed=(entry,row.symbol) in opened
        if executed and (row.symbol,entry) not in pnl:
            raise ValueError('Baseline entry without a fully closed position')
        rows.append(dict(decision_date=str(row.date.date()),symbol=row.symbol,oracle_rank=int(row.oracle_rank),
            next_session=str(entry.date()),baseline_opened=executed,
            baseline_position_pnl_usd=pnl[(row.symbol,entry)] if executed else None,
            interpretation='baseline position only; later sizing and reentries differ between arms'))
    return rows


def evaluate(root):
    p=freeze(root)
    analysis=pilot.read(root/'analysis.json');verify_hashes(root,analysis['files'])
    if analysis['actual_calls']!=213 or analysis['candidate_days']!=600:
        raise ValueError('Complete paid collection required for this diagnostic')
    from scripts.research import us_oracle_path_top5_leverage_grid as grid
    from scripts.research.us_concentrated_live_portfolio import ArchivedMacro,run_portfolio
    from service.market import parse_market_regimes
    verify_hashes(Path('.'),p['sources'])
    for path,expected in p['source_hashes'].items():
        if digest(path)!=expected:raise ValueError('Changed archived market tape')
    # First economic read, only after paid answers were sealed.
    candidates=merge_decisions(pd.read_parquet(root/'candidates.parquet'),pilot.read(root/'assessments.json'))
    prices=pd.read_parquet(p['price_source'],filters=[('date','<=',pd.Timestamp(p['terminal_date']))])
    prices['date']=pd.to_datetime(prices.date)
    required=set(candidates.symbol)|{'SPY'}
    prices=prices[prices.symbol.isin(required)].copy()
    days=grid.nyse_sessions('2023-01-01',p['terminal_date'])
    frames={key:prices.pivot(index='date',columns='symbol',values=column).reindex(days)
        for key,column in [('opens','open'),('high','high'),('low','low'),('close','close'),('volume','volume')]}
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict()
    macro=ArchivedMacro(pd.read_parquet(p['macro_source']));market=parse_market_regimes(p['market'])
    units=unit_diagnostic(candidates,prices,days)
    atomic_json(root/'q1-unit-outcomes.json',units)
    reports=[]
    for arm in ARMS:
        folder=root/arm;folder.mkdir(exist_ok=True)
        scores=candidates.copy()
        scores['keep']=scores.selected & (~scores.veto_long if arm==ARMS[1] else True)
        refs=[]
        def ledger_factory(cfg,**kwargs):
            ledger=grid.UnlimitedLedger(cfg,sl=.05,trail=.15,tp=.20,study_end=p['terminal_date'],events=p['events'],**kwargs)
            refs.append(ledger);return ledger
        def session_factory(*args,**kwargs):return grid.MarginAwareSession(*args,ledger_ref=refs,**kwargs)
        atomic_json(root/'economic-progress.json',dict(status='NATIVE_PORTFOLIO_RUNNING',arm=arm))
        with (folder/'research.log').open('a',encoding='utf-8') as log,redirect_stdout(log),redirect_stderr(log):
            logging.basicConfig(level=logging.WARNING,stream=log,force=True)
            result=run_portfolio(frames=frames,scores=scores,sectors=sectors,macro=macro,market_config=market,
                policy='keep',variant='CURRENT_NO_EXPIRY',output=folder,start_date=p['entry_start'],
                end_date=p['terminal_date'],decision_end_date=p['entry_end'],expiry_open_sessions=20,
                quality=prices[['date','symbol','is_filled','instrument_id']],reject_constrained_entries=True,
                ledger_factory=ledger_factory,session_factory=session_factory,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=grid.margin_policy)
        ledger=refs[0]
        if ledger.state.positions:raise ValueError('Incomplete expiry tail')
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        position_pnl=trades.groupby(['symbol','entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
        if len(trades) and (not trades.side.eq('buy').all() or trades.exit_reason.str.contains('trailing').any()):
            raise ValueError('Unexpected direction or trailing exit')
        final=float(daily.equity.iloc[-1])
        if not np.isclose(4000+position_pnl.sum()-ledger.interest,final,atol=1e-6):
            raise ValueError('Final wealth not reconciled')
        api_cost=analysis['gross_cost_estimate_usd'] if arm==ARMS[1] else 0.
        result.update(arm=arm,capital_initial_usd=4000.,capital_final_usd=final,
            net_return_pct=100*result['return_pct'],max_drawdown_pct=100*result['max_drawdown'],
            winning_positions=int(position_pnl.gt(0).sum()),losing_positions=int(position_pnl.lt(0).sum()),
            flat_positions=int(position_pnl.eq(0).sum()),positive_position_pnl_usd=float(position_pnl[position_pnl.gt(0)].sum()),
            negative_position_pnl_usd=float(position_pnl[position_pnl.lt(0)].sum()),
            api_cost_estimate_usd=api_cost,capital_final_after_api_estimate_usd=final-api_cost,
            monthly=monthly_curves(daily,trades),no_open_positions_at_end=True)
        atomic_json(folder/'case-report.json',result);reports.append(result)
    impacts=veto_attribution(candidates,days,pilot.read(root/ARMS[0]/'executions.json'),
        pd.read_parquet(root/ARMS[0]/'trades.parquet'))
    atomic_json(root/'veto-impact.json',impacts)
    valid=pd.DataFrame([item for item in units if item['status']=='QUALIFIED_EXPLORATORY_VENDOR_PATH'])
    by_opinion=[]
    if len(valid):
        for name,part in valid.groupby('gpt'):
            by_opinion.append(dict(gpt=name,decisions=len(part),tp_before_sl=int(part.tp_before_sl.sum()),
                tp_before_sl_pct=float(100*part.tp_before_sl.mean()),gross_return_mean_pct=float(part.gross_return_pct.mean())))
    delta=reports[1]['capital_final_usd']-reports[0]['capital_final_usd']
    invalid=analysis.get('invalid_responses',0)
    value=dict(status='COMPLETED_PARTIAL_SIGNAL_EXPLORATORY_NOT_PIT' if invalid else 'COMPLETED_EXPLORATORY_NOT_PIT',
        full_filter_qualified=not bool(invalid),analysis_status=analysis['status'],invalid_responses=invalid,
        signal_rule='unchanged valid BEARISH material fact + exact quotes + confidence>=0.75',
        api_calls=analysis['actual_calls'],gross_api_cost_estimate_usd=analysis['gross_cost_estimate_usd'],
        user_authorized_api_cap_usd=p['user_authorized_api_cap_usd'],
        collector_enforced_api_cap_usd=p['collector_enforced_cap_usd'],
        candidates=600,sessions=60,distinct_symbols=int(candidates.symbol.nunique()),
        decision_counts=analysis['decisions'],vetoed=analysis['vetoed'],portfolios=reports,
        delta_final_capital_usd=delta,delta_after_api_estimate_usd=delta-analysis['gross_cost_estimate_usd'],
        veto_baseline_opened=sum(row['baseline_opened'] for row in impacts),
        unit_diagnostic=dict(qualified=len(valid),unqualified=len(units)-len(valid),by_opinion=by_opinion,
            unit_returns_not_portfolio_pnl=True,future_quality_never_used_for_candidate_selection=True),
        verdict='POSITIVE_RETROSPECTIVE_DIFFERENCE_NOT_PROVEN_PREDICTIVE' if delta>0 else
            'NEGATIVE_RETROSPECTIVE_DIFFERENCE' if delta<0 else 'NO_INCREMENTAL_TRADING_EFFECT',
        historical_text_pit_certified=False,llm_knowledge_contamination_excluded=False,
        independent_holdout=False,production_promotion=False,training=False,sql_writes=False,broker_orders=False,
        files={name:digest(root/name) for name in ['economic-protocol.json','analysis.json','assessments.json',
            'usage.json','q1-unit-outcomes.json','veto-impact.json']})
    for arm in ARMS:
        for name in ['case-report.json','daily.parquet','trades.parquet','executions.json','decisions.json','regimes.json']:
            path=root/arm/name;value['files'][str(path.relative_to(root))]=digest(path)
    atomic_json(root/'q1-results.json',value)
    atomic_json(root/'economic-progress.json',dict(status=value['status'],verdict=value['verdict'],api_calls_new=0))
    return value


def main():
    from scripts.research.oracle_path_confirmation import exclusive_run
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['freeze','evaluate'],required=True)
    args=parser.parse_args()
    with exclusive_run(args.output):
        try:
            value=globals()[args.phase](args.output)
            print(json.dumps({key:item for key,item in value.items() if key not in ['sources','files','market']},default=str))
        except Exception as exc:
            atomic_json(args.output/'economic-progress.json',dict(status='BLOCKED',
                error=f'{type(exc).__name__}: {str(exc)[:500]}',api_calls_new=0))
            raise


if __name__=='__main__':main()
