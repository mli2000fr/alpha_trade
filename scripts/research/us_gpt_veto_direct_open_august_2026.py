"""Four paired August2026 portfolios: direct J+1 open instead of Winner entry.

Keep identical HALF sizing, native capital/risk/fees and SL7/noTP/noTR/open21.
Disable the breakout/wait strategy, not the safety and accounting machinery.
No SQL, APIs, LLM, production edits, independent deposits per hypothetical trade.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from scripts.research import us_winner_gpt_veto_1_5_august_2026 as prior
from scripts.research.us_winner_2020_cent_repair_20261023 import corrected_runtime
import execution_engine.winner_runtime as runtime

original,base,grid = prior.original,prior.base,prior.grid
ROOT = prior.PARENT.parent/'20261025-direct-open-v1'
PARENT = prior.ROOT
DOC = Path('doc/ml/gpt_veto_direct_open_aout_2026.md')
TEST = Path('tests/test_us_gpt_veto_direct_open_august_2026.py')
ARMS = {'DIRECT_ONLY':None,'DIRECT_GPT_VETO_1_3':3,'DIRECT_GPT_VETO_1_4':4,'DIRECT_GPT_VETO_1_5':5}


def direct_action(state,bars,*,now,**kwargs):
    # Preserve the native terminal/expiry/entry-switch/operation guards. Supplying
    # no breakout level prevents the original confirmation from firing.
    action = ORIGINAL_ACTION(state,bars,now=now,**dict(kwargs,prior_session_high=None))
    if action['action'] != 'WAIT_CONFIRMATION' or state['lots']:
        return action
    if runtime.aware(now) == runtime.aware(state['earliest_entry_open']):
        return dict(action='ENTRY_SIGNAL',max_quantity=state['initial_quantity'])
    return dict(action='WAIT_DIRECT_OPEN_NO_LATE_RETRY')


ORIGINAL_ACTION = runtime.next_plan_action


@contextmanager
def direct_entry_adapter():
    native = grid.native
    old_runtime,old_action = native.WinnerCampaignRuntime,runtime.next_plan_action
    receipts = dict(fills=[],refused_or_missed=[])

    class DirectRuntime(old_runtime):
        def cancel_unfilled(self,reason):
            if self.pending():
                raise ValueError('Direct order unresolved; cannot cancel and blindly retry')
            self.state['status'] = 'CANCELED';self.save()
            receipts['refused_or_missed'].append(dict(symbol=self.state['symbol'],signal_date=self.state['signal_date'],
                earliest_entry_open=self.state['earliest_entry_open'],time=self.now,reason=reason))

        def tick(self):
            if self.state['status'] in ('CLOSED','CANCELED','EXPIRED'):
                return super().tick()
            earliest = runtime.aware(self.state['earliest_entry_open'])
            if not self.state['lots'] and self.now > earliest:
                self.cancel_unfilled('MISSED_J_PLUS_1_OPEN_NO_DEFERRED_ENTRY')
                return
            super().tick()
            if not self.state['lots'] and self.now >= earliest:
                self.cancel_unfilled('J_PLUS_1_OPEN_NOT_FILLED_NO_INTRADAY_RETRY')

        def book_buy(self,intent,operation,raw):
            already = self.state['parents'][intent.intent_id]['booked_quantity']
            super().book_buy(intent,operation,raw)
            if self.state['parents'][intent.intent_id]['booked_quantity'] > already:
                receipts['fills'].append(dict(symbol=self.state['symbol'],campaign_id=self.state['campaign_id'],
                    signal_date=self.state['signal_date'],earliest_entry_open=self.state['earliest_entry_open'],
                    fill_time=self.state['first_fill_at'],initial_quantity=self.state['initial_quantity'],
                    risk_budget=self.state['risk_budget'],policy=deepcopy(self.state['policy'])))

    native.WinnerCampaignRuntime,runtime.next_plan_action = DirectRuntime,direct_action
    try:
        yield receipts
    finally:
        native.WinnerCampaignRuntime,runtime.next_plan_action = old_runtime,old_action


def signals_for(cohort,cutoff):
    selected = cohort[['date','symbol','oracle_rank']].rename(columns={'date':'trade_date','oracle_rank':'rank'}).copy()
    veto = pd.Series(False,index=cohort.index) if cutoff is None else (
        cohort.gpt_status.eq('VALID') & cohort.gpt_score.between(1,cutoff)).fillna(False)
    selected['selected'] = (cohort.selected & ~veto).to_numpy()
    selected['side'] = 'long'
    return selected


def prepare(root):
    if (root/'protocol.json').exists():
        protocol = base.read(root/'protocol.json');base.verify(protocol['sources']);return protocol
    parent = base.read(PARENT/'protocol.json');base.verify(parent['sources'])
    old = base.read(PARENT/'report.json')
    if old['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
        raise ValueError('All four audited Winner comparators required')
    sources = dict(parent['sources'])
    # Before using exact broker averages in the new replay, prove this does not
    # change the SL levels of any archived comparator entry. No audit tolerance
    # is relaxed to mask binary-float/cent-boundary problems.
    cent_checks = []
    for (folder,arm),case in zip([*prior.COMPARATORS,(PARENT/prior.ARM,prior.ARM)],old['cases']):
        base.verify({str(folder/name):sha for name,sha in case['files'].items()})
        events = pd.read_parquet(folder/'events.parquet')
        for buy in events[events.event.eq('BUY_FILL')].itertuples():
            raw,calculated = float(buy.price),float(buy.quantity)*float(buy.price)/float(buy.quantity)
            if round(raw*.93,2) != round(calculated*.93,2):
                raise ValueError('Comparator cent drift needs separate qualification: '+str((arm,buy.symbol,buy.time)))
            cent_checks.append(dict(arm=arm,symbol=buy.symbol,time=buy.time,stop=round(raw*.93,2)))
        sources[str(folder/'report.json')] = base.digest(folder/'report.json')
        sources.update({str(folder/name):sha for name,sha in case['files'].items()})
    for path in [Path(__file__),DOC,TEST,Path('scripts/research/us_winner_2020_cent_repair_20261023.py'),
            PARENT/'protocol.json',PARENT/'report.json',PARENT/'common-cohort.parquet',PARENT/'inputs/snapshot.json']:
        sources[str(path)] = base.digest(path)
    root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(PARENT/'inputs',root/'inputs')
    shutil.copy2(PARENT/'frozen-signals.parquet',root/'frozen-signals.parquet')
    grid.atomic_json(root/'comparator-cent-audit.json',dict(status='PASS_UNCHANGED_SL7_LEVELS',checks=cent_checks))
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),reference_config=parent['reference_config'],
        arms=ARMS,initial_equity=4000.,start=str(original.START),end=str(original.END),
        signal_period=parent['signal_period'],new_entry_rule='Exactly first official J+1 open; no completed-bar confirmation or delayed retry.',
        dimensioning='HALF retained to isolate entry method; same native approval, 8 slots and 1x gross cap.',
        lifecycle='SL7, noTP/noTR, open21 from actual entry; no averaging/addition; no forced final sale.',
        plumbing='Native campaign broker/risk retained ONLY for identical accounting and protection lifecycle; not Winner timing.',
        veto='Same VALID score veto at signal plan admission; invalid/missing retained; no rerank or TOP21 replacement.',
        first_full_fill_average='Exact archived broker fill; all comparator SL7 rounding levels verified unchanged.',
        historical_gpt_non_PIT=True,future_coverage_selection_bias=True,full_live_parity=False,independent_holdout=False,
        gpt_calls=0,provider_calls=0,SQL_reads=0,SQL_writes=False,orders=False,production_changed=False,
        sources=sources,files={n:base.digest(root/n) for n in ['frozen-signals.parquet','comparator-cent-audit.json']})
    base.save_new(root/'protocol.json',protocol)
    return protocol


def audit(result,summary,cohort,raw,sessions,receipts):
    events = result.trade_events_df
    flows = events[events.event.notna()]
    cash,fees,held = grid.event_cash(flows)
    grid.near(cash,summary['settled_cash']);grid.near(fees,summary['costs'])
    if held != {p['symbol']:p['qty'] for p in summary['open_positions']}:
        raise ValueError('Direct holdings mismatch')
    grid.near(summary['final_equity'],cash+sum(p['qty']*p['mark'] for p in summary['open_positions']))
    if summary['dividends_accrued'] or summary['unsettled_cash']:
        raise ValueError('Unqualified corporate-action/settlement lifecycle')
    dates = [s.session_date for s in sessions];indices = {d:i for i,d in enumerate(dates)}
    by_fill = {(r['symbol'],pd.Timestamp(r['fill_time'])):r for r in receipts['fills']}
    buys = flows[flows.event.eq('BUY_FILL')]
    if len(by_fill) != len(buys) or len(receipts['fills']) != len(buys):
        raise ValueError('Repeated or unrecorded direct fill')
    for buy in buys.itertuples():
        stamp = pd.Timestamp(buy.time);day = stamp.tz_convert('America/New_York').date()
        receipt = by_fill.get((buy.symbol,stamp))
        if receipt is None:
            raise ValueError('Direct entry missing receipt')
        signal_day = pd.Timestamp(receipt['signal_date']).date()
        if indices[day] != indices[signal_day]+1 or stamp != pd.Timestamp(sessions[indices[day]].open_at_utc):
            raise ValueError('Direct buy is not exact official J+1 open')
        if stamp != pd.Timestamp(receipt['earliest_entry_open']):
            raise ValueError('Entry used an older plan')
        eligible = cohort[cohort.symbol.eq(buy.symbol) & cohort.date.eq(pd.Timestamp(signal_day)) & cohort.selected]
        if len(eligible) != 1:
            raise ValueError('Direct buy has no retained prior-session signal')
        frame = raw[buy.symbol]
        bar = frame[frame.bar_timestamp.eq(stamp)]
        if len(bar) != 1 or buy.quantity < 1 or not float(buy.quantity).is_integer() or buy.quantity > receipt['initial_quantity']:
            raise ValueError('Invalid direct fill or quantity')
        grid.near(buy.price,bar.iloc[0].open);grid.near(buy.costs,buy.quantity*buy.price*.0008)
    wins,losses = [],[]
    for trade in result.closed_trades_df.itertuples():
        entry = pd.Timestamp(trade.entry_date);day = entry.tz_convert('America/New_York').date()
        due = pd.Timestamp(sessions[indices[day]+20].open_at_utc)
        actual = grid.scalar_exit(raw[trade.symbol],entry,trade.entry_price,due,sl=.07,tp=None,trail=None)
        if actual is None or actual[0] != trade.exit_date or actual[2] != trade.exit_reason:
            raise ValueError('Direct scalar exit mismatch: '+str((trade.symbol,actual)))
        grid.near(actual[1],trade.exit_price)
        grid.near(trade.pnl,trade.quantity*(trade.exit_price-trade.entry_price)-trade.entry_fees-trade.exit_fees+trade.dividends)
        count = indices[pd.Timestamp(trade.exit_date).tz_convert('America/New_York').date()]-indices[day]+1
        (wins if trade.pnl > 0 else losses).append(count)
    values = np.r_[4000.,result.intraday_equity_curve.equity.to_numpy()]
    grid.near(summary['max_drawdown_pct'],100*np.min(values/np.maximum.accumulate(values)-1))
    return dict(status='PASS_DIRECT_J1_OPEN_NATIVE_RISK_SCALAR_EXITS_CASH_FEES',buy_checks=len(buys),
        scalar_exit_checks=len(result.closed_trades_df),
        average_winning_holding_sessions=float(np.mean(wins)) if wins else None,
        average_losing_holding_sessions=float(np.mean(losses)) if losses else None)


def run(root):
    protocol = prepare(root)
    with prior.previous.run_lock(root):
        if (root/'report.json').exists():
            raise FileExistsError('Completed direct replay is immutable')
        cohort,groups,raw,actions,sectors,pivots,calendar = original.load_inputs(root)
        old_cohort = pd.read_parquet(PARENT/'common-cohort.parquet')
        pd.testing.assert_frame_equal(cohort,old_cohort)
        cfg = replace(base.engine_config(protocol['reference_config'],2026),
            start_date=original.START,end_date=original.END,cost_round_trip_bps=16.)
        if cfg.exec_config.winner_pyramiding.initial_position_fraction != .5 or cfg.exec_config.winner_pyramiding.reinforcement_enabled:
            raise ValueError('Unexpected initial fraction/addition policy')
        def bars(day,symbols):
            parts = [groups[s,day] for s in symbols if (s,day) in groups]
            return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
        summaries = []
        for arm,cutoff in ARMS.items():
            folder = root/arm;folder.mkdir(exist_ok=False)
            selected = signals_for(cohort,cutoff)
            def progress(done,total,day):
                grid.atomic_json(root/'progress.json',dict(status='RUNNING',arm=arm,completed_runs=len(summaries),total_runs=4,
                    completed_sessions=done,total_sessions=total,last_date=day,updated_at_utc=datetime.now(timezone.utc).isoformat()))
            with grid.runtime_adapter(2026,arm) as refusals,corrected_runtime(),direct_entry_adapter() as receipts:
                result = base.BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],
                    low=pivots['low'],volume=pivots['volume'],signals_df=selected,sector_map=sectors,
                    intraday_source=bars,winner_research_assumptions=True,winner_progress=progress,
                    winner_corporate_actions=actions.to_dict('records'))
                grid.atomic_json(folder/'entry-receipts.json',receipts)
                grid.atomic_json(folder/'whole-share-refusals.json',refusals)
            summary = prior.previous.metrics(result,4000.)
            if summary['status'] != 'COMPLETED_EXPLORATORY' or summary['coverage_gaps']:
                raise ValueError('Direct replay coverage incomplete')
            allowed = cohort.copy();allowed['selected'] = selected.selected.to_numpy()
            checks = audit(result,summary,allowed,raw,calendar,receipts)
            for name,frame in {'trades.parquet':result.closed_trades_df,'events.parquet':result.trade_events_df,
                    'equity-5m.parquet':result.intraday_equity_curve,'equity-daily.parquet':result.equity_curve.to_frame(),
                    'breaker.parquet':result.drawdown_breaker_df}.items():
                frame.to_parquet(folder/name,index=name == 'equity-daily.parquet')
            summary.update(arm=arm,veto_cutoff=cutoff,entry_rule='DIRECT_J_PLUS_1_OPEN',audit=checks,
                eligible_signals=int(selected.selected.sum()),
                files={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()})
            base.save_new(folder/'report.json',summary);summaries.append(summary)
        winner = base.read(PARENT/'report.json')['cases']
        base.verify(protocol['sources'])
        comparison = [dict(veto_cutoff=cutoff,winner=old,direct=new,
            direct_minus_winner_usd=new['final_equity']-old['final_equity'],
            direct_minus_winner_win_points=new['win_pct']-old['win_pct'])
            for cutoff,old,new in zip(ARMS.values(),winner,summaries)]
        base.save_new(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=summaries,
            comparison=comparison,gpt_calls=0,provider_calls=0,SQL_reads=0,SQL_writes=False,orders=False,
            production_changed=False,historical_gpt_non_PIT=True,future_coverage_selection_bias=True,
            independent_holdout=False,full_live_parity=False,sources=protocol['sources'],
            files={n:base.digest(root/n) for n in ['protocol.json','common-cohort.parquet','session-quality.parquet','comparator-cent-audit.json']}))
        grid.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=4,total_runs=4))


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT)
    args = parser.parse_args()
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    requests.Session.request = lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in direct-entry paired replay'))
    try:
        run(args.output)
    except BaseException as exc:
        if args.output.exists():
            grid.atomic_json(args.output/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            grid.atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__ == '__main__':
    main()
