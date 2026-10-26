from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.research import us_gpt_veto_direct_open_august_2026 as experiment
from tests.test_winner_intraday import fixture
from tests.test_winner_runtime import setup
from backtesting.simulator import BacktestEngine


def test_direct_action_uses_only_exact_open_and_preserves_native_guards():
    cfg,store,_,_ = setup()
    state = store.rows()[0]['state']
    opening = experiment.runtime.aware(state['earliest_entry_open'])
    assert experiment.direct_action(state,[],now=opening)['action'] == 'ENTRY_SIGNAL'
    assert experiment.direct_action(state,[],now=opening-timedelta(seconds=1))['action'] == 'WAIT_ENTRY_SESSION'
    assert experiment.direct_action(state,[],now=opening+timedelta(minutes=5))['action'] == 'WAIT_DIRECT_OPEN_NO_LATE_RETRY'
    assert experiment.direct_action(state,[],now=opening,new_entries_enabled=False)['action'] == 'ENTRIES_DISABLED'
    state['operations'].append(dict(status='RESERVED'))
    assert experiment.direct_action(state,[],now=opening)['action'] == 'RECONCILE_FIRST'


def test_real_direct_fill_is_open_not_winner_confirmation_and_patches_restore():
    cfg,args,raw = fixture(initial_position_fraction=.5,stop_loss_pct=.07)
    native,rt = experiment.grid.native,experiment.runtime
    before = native.WinnerCampaignRuntime,rt.next_plan_action
    with experiment.corrected_runtime(),experiment.direct_entry_adapter() as receipts:
        result = BacktestEngine(cfg).run(**args)
    buys = result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys) == len(receipts['fills']) == 1
    official_open = raw[cfg.start_date,'AAA'].timestamp.iloc[0]
    assert buys.iloc[0].time == official_open and buys.iloc[0].price == 100.
    assert buys.iloc[0].quantity <= receipts['fills'][0]['initial_quantity']
    assert before == (native.WinnerCampaignRuntime,rt.next_plan_action)
    assert result.tracker_snapshot['winner_replay']['costs'] > 0


def test_rejected_open_is_not_retried_at_935_or_with_old_plan(monkeypatch):
    cfg,args,raw = fixture(initial_position_fraction=.5,stop_loss_pct=.07)
    native = experiment.grid.native
    attempts = []
    def reject(state,version,quantity,snapshot,now,kind,*,context):
        attempts.append(now)
        return dict(max_quantity=0,reason='TEST_RISK_REFUSAL')
    monkeypatch.setattr(native,'reapprove_campaign',reject)
    with experiment.direct_entry_adapter() as receipts:
        result = BacktestEngine(cfg).run(**args)
    assert attempts == [raw[cfg.start_date,'AAA'].timestamp.iloc[0]]
    assert result.tracker_snapshot['winner_replay']['open_positions'] == []
    assert len(receipts['refused_or_missed']) == 1


def test_next_daily_signal_can_stage_after_rejected_previous_open(monkeypatch):
    cfg,args,raw = fixture(initial_position_fraction=.5,stop_loss_pct=.07)
    args['signals_df'] = pd.concat([args['signals_df'],pd.DataFrame([dict(trade_date=cfg.start_date,
        symbol='AAA',selected=True,rank=1)])],ignore_index=True)
    attempts = []
    def reject(state,version,quantity,snapshot,now,kind,*,context):
        attempts.append((state['signal_date'],now))
        return dict(max_quantity=0,reason='TEST_RISK_REFUSAL')
    monkeypatch.setattr(experiment.grid.native,'reapprove_campaign',reject)
    with experiment.direct_entry_adapter():
        BacktestEngine(cfg).run(**args)
    assert len(attempts) == 2 and attempts[0][0] != attempts[1][0]
    assert all(pd.Timestamp(stamp).minute == 30 for _,stamp in attempts)


def test_direct_filter_preserves_rank_cohort_and_invalid_scores():
    cohort = pd.DataFrame(dict(date=[pd.Timestamp('2026-08-03')]*5,symbol=list('ABCDE'),oracle_rank=range(1,6),
        gpt_score=[3,4,5,6,3],gpt_status=['VALID']*4+['INVALID'],selected=[True]*5))
    expected = {None:[True]*5,3:[False,True,True,True,True],
        4:[False,False,True,True,True],5:[False,False,False,True,True]}
    for cutoff,mask in expected.items():
        selected = experiment.signals_for(cohort,cutoff)
        assert selected.selected.tolist() == mask
        assert selected['rank'].tolist() == list(range(1,6)) and selected.side.eq('long').all()


def test_direct_audit_checks_exact_open_signal_and_scalar_lifecycle(monkeypatch):
    cfg,args,raw = fixture(initial_position_fraction=.5,stop_loss_pct=.07)
    cfg = replace(cfg,cost_round_trip_bps=16.)
    with experiment.corrected_runtime(),experiment.direct_entry_adapter() as receipts:
        result = BacktestEngine(cfg).run(**args)
    summary = experiment.prior.previous.metrics(result,4000.)
    frames = {symbol:pd.concat([frame.rename(columns={'timestamp':'bar_timestamp'}).assign(trade_date=pd.Timestamp(day))
        for (day,s),frame in raw.items() if s == symbol],ignore_index=True)
        for symbol in ['AAA']}
    cohort = args['signals_df'].rename(columns={'trade_date':'date'}).copy();cohort.date = pd.to_datetime(cohort.date)
    sessions = [s for s in experiment.grid.calendar().sessions(cfg.start_date-timedelta(days=14),cfg.end_date+timedelta(days=100)) if s.is_open]
    checks = experiment.audit(result,summary,cohort,frames,sessions,receipts)
    assert checks['buy_checks'] == 1
    receipts['fills'][0]['signal_date'] = str(cfg.start_date)
    with pytest.raises(ValueError,match=r'official J\+1'):
        experiment.audit(result,summary,cohort,frames,sessions,receipts)


def test_direct_horizon_remains_open21_from_actual_fill():
    cfg,args,raw = fixture(last=date(2026,11,18),initial_position_fraction=.5,stop_loss_pct=.07)
    with experiment.corrected_runtime(),experiment.direct_entry_adapter():
        result = BacktestEngine(cfg).run(**args)
    assert len(result.closed_trades_df) == 1
    trade = result.closed_trades_df.iloc[0]
    assert trade.entry_date == raw[cfg.start_date,'AAA'].timestamp.iloc[0]
    assert trade.exit_date == pd.Timestamp('2026-11-16T14:30Z')
    assert trade.exit_reason == 'HORIZON_OPEN'


def test_direct_first_open_has_a_stop_during_the_first_bar():
    cfg,args,raw = fixture(initial_position_fraction=.5,stop_loss_pct=.07)
    raw[cfg.start_date,'AAA'].loc[0,'low'] = 90.
    with experiment.corrected_runtime(),experiment.direct_entry_adapter():
        result = BacktestEngine(cfg).run(**args)
    assert len(result.closed_trades_df) == 1
    trade = result.closed_trades_df.iloc[0]
    assert trade.exit_reason == 'STOP' and trade.exit_price == 93.
    assert trade.exit_date == trade.entry_date+pd.Timedelta(minutes=5)
    assert trade.entry_fees > 0 and trade.exit_fees > 0
