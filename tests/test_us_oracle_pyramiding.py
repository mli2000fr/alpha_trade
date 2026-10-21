import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_pyramiding import tapes, simulate, planned_full_quantity, annual_summary
from scripts.research.us_oracle_pyramiding_audit import independent_exit


def fixture_paths(paths, entries=None, symbols=None, ranks=None, start='2025-01-02 14:30Z'):
    entries = entries or [0]*len(paths)
    symbols = symbols or [f'S{i}' for i in range(len(paths))]
    ranks = ranks or list(range(1, len(paths)+1))
    n = len(paths[0])
    times = pd.date_range(start, periods=n, freq='5min')
    rows, candidates = [], []
    for pid, path in enumerate(paths):
        for k, values in enumerate(path):
            op, high, low, close = values
            rows.append(dict(pair_id=pid, bar_index=k, bar_timestamp=times[k],
                bar_end_timestamp=times[k]+pd.Timedelta(minutes=5), session_offset=1,
                open=op, high=high, low=low, close=close))
        candidates.append(dict(pair_id=pid, symbol=symbols[pid], date=times[0].tz_localize(None).normalize(),
            rank=ranks[pid], year=times[0].year, expiry=times[-1], entry_index=entries[pid],
            entry_time=times[entries[pid]] if entries[pid] >= 0 else pd.NaT))
    calendar = pd.DataFrame([dict(date=times[0].tz_localize(None).normalize(), market_open=times[0],
        market_close=times[-1]+pd.Timedelta(minutes=5))])
    bars = pd.DataFrame(rows)
    return tapes(bars, pd.DataFrame(candidates), calendar), bars


def flat(n=8, p=100.):
    return [(p, p, p, p)]*n


def test_full_quantity_cash_costs_and_risk():
    assert planned_full_quantity(4000, 4000, 100, .0008) == 10
    assert planned_full_quantity(4000, 99, 100, .0008) == 0
    assert planned_full_quantity(4000, 4000, 2000, .0008) == 0
    assert planned_full_quantity(1000, 1000, 1, .0008) == 250


@pytest.mark.parametrize('arm,quantity', [('FULL_BASE', 10), ('HALF_CONTROL', 5), ('HALF_ADD_ONE', 5)])
def test_flat_expiry_and_cash_conservation(arm, quantity):
    tape, _ = fixture_paths([flat()])
    out = simulate(tape, arm, .0008)
    lot = out['lots'].iloc[0]
    assert lot.quantity == quantity
    assert lot.exit_reason == 'EXPIRY'
    assert lot.exit_price == 100
    assert lot.net == pytest.approx(-quantity*100*.0016)
    assert out['marks'].equity.iloc[-1] == pytest.approx(4000+lot.net)
    assert out['marks'].cash.min() >= 0


def test_stop_known_before_current_high():
    path = [(100, 200, 96, 100), (100, 101, 90, 95)]+flat(4)
    tape, bars = fixture_paths([path])
    out = simulate(tape, 'FULL_BASE', .0008)
    lot = out['lots'].iloc[0]
    assert lot.exit_bar_index == 1
    assert lot.exit_price == 100  # Previous high raises next-bar stop to170; adverse gap.
    assert lot.exit_reason == 'GAP_STOP'
    idx, price, reason, _ = independent_exit(bars, 0)
    assert (idx, price, reason) == (1, 100, 'GAP_STOP')


def test_gap_loss_can_exceed_budget():
    tape, _ = fixture_paths([[(100, 101, 99, 100), (60, 61, 59, 60)]+flat(4, 60)])
    lot = simulate(tape, 'FULL_BASE', .0008)['lots'].iloc[0]
    assert lot.exit_price == 60
    assert lot.net < -lot.budget


def winning_path():
    return [(100, 102, 99, 101), (105, 107, 104, 106), (107, 109, 106, 108),
        (108, 110, 107, 109), (109, 112, 108, 111), (111, 112, 110, 111),
        (111, 112, 110, 111), (111, 112, 110, 111)]


def test_add_after_two_completed_closes_at_next_open_only_once():
    tape, _ = fixture_paths([winning_path()])
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    added = out['lots'][out['lots'].leg.eq('ADD')].iloc[0]
    assert added.entry_bar_index == 3
    assert added.entry_price == 108
    assert added.quantity == 4  # Current25%equity cap, not blindly another5.
    assert len(out['orders'][out['orders'].kind.eq('ADD')]) == 1
    add_order = out['orders'][out['orders'].kind.eq('ADD')].iloc[0]
    assert add_order.used_risk+added.quantity*108*(.05+.0008*2.05) <= added.budget+1e-8


def test_one_high_close_is_not_confirmation():
    path = flat()
    path[2] = (100, 107, 99, 106)
    tape, _ = fixture_paths([path])
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    assert not out['lots'].leg.eq('ADD').any()


def test_cancel_add_if_next_open_loses_trigger():
    path = winning_path()
    path[3] = (103, 110, 102, 109)
    tape, _ = fixture_paths([path])
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    adds = out['orders'][out['orders'].kind.eq('ADD')]
    assert adds.status.tolist() == ['CANCEL_GAP_BELOW_TRIGGER']
    assert not out['lots'].leg.eq('ADD').any()


def test_cancel_add_if_original_gap_stopped():
    path = winning_path()
    path[3] = (90, 110, 89, 109)
    tape, _ = fixture_paths([path])
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    adds = out['orders'][out['orders'].kind.eq('ADD')]
    assert adds.status.tolist() == ['CANCEL_ORIGINAL_EXITED']
    assert len(out['lots']) == 1


def test_half_without_add_matches_first_half_trade():
    tape, _ = fixture_paths([winning_path()])
    control = simulate(tape, 'HALF_CONTROL', .0008)['lots'].iloc[0]
    initial = simulate(tape, 'HALF_ADD_ONE', .0008)['lots'].query("leg=='INITIAL'").iloc[0]
    for field in ['quantity', 'entry_price', 'exit_price', 'exit_bar_index', 'net']:
        assert initial[field] == control[field]


def test_shared_cash_not_independent_4000_per_campaign():
    tape, _ = fixture_paths([flat() for _ in range(10)])
    out = simulate(tape, 'FULL_BASE', .0008)
    assert len(out['lots']) == 5
    assert len(out['orders']) == 10
    assert out['marks'].gross.max() <= out['marks'].equity.max()
    assert out['marks'].cash.min() >= 0
    assert out['lots'].quantity.tolist() == [10, 9, 9, 9, 2]


def test_max_positions_and_deterministic_rank_priority():
    tape, _ = fixture_paths([flat() for _ in range(10)], ranks=list(range(10, 0, -1)))
    out = simulate(tape, 'HALF_CONTROL', .0008)
    buys = out['fills'][out['fills'].side.eq('BUY')]
    assert buys.pair_id.tolist() == list(range(9, 1, -1))
    assert out['orders'].status.tolist()[-2:] == ['MAX_POSITIONS', 'MAX_POSITIONS']


def test_no_duplicate_held_symbol():
    tape, _ = fixture_paths([flat(), flat()], symbols=['SAME', 'SAME'])
    out = simulate(tape, 'FULL_BASE', .0008)
    assert len(out['lots']) == 1
    assert out['orders'].status.tolist() == ['FILLED', 'DUPLICATE_HELD_SYMBOL']


def test_whole_share_refusal_no_later_retry():
    path = flat(p=2000)
    path[-1] = (10, 10, 10, 10)
    tape, _ = fixture_paths([path])
    out = simulate(tape, 'FULL_BASE', .0008)
    assert out['lots'].empty
    assert out['orders'].status.tolist() == ['ZERO_WHOLE_SHARES']
    assert out['marks'].equity.iloc[-1] == 4000


def test_intrabar_sale_does_not_fund_same_bar_open():
    paths = [flat() for _ in range(6)]
    paths[0][2] = (100, 101, 90, 95)
    tape, _ = fixture_paths(paths, entries=[0, 0, 0, 0, 0, 2])
    out = simulate(tape, 'FULL_BASE', .0008)
    rejected = out['orders'][out['orders'].pair_id.eq(5)].iloc[0]
    assert rejected.status == 'ZERO_WHOLE_SHARES'


def test_add_does_not_extend_expiry():
    tape, _ = fixture_paths([winning_path()])
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    assert out['lots'].exit_bar_index.tolist() == [7, 7]
    assert out['lots'].exit_reason.tolist() == ['EXPIRY', 'EXPIRY']


def test_cost_stress_recalculates_quantities():
    tape, _ = fixture_paths([flat() for _ in range(5)])
    base = simulate(tape, 'FULL_BASE', .0008)
    stress = simulate(tape, 'FULL_BASE', .0025)
    assert base['orders'].cash_before.tolist() != stress['orders'].cash_before.tolist()
    assert stress['marks'].equity.iloc[-1] < base['marks'].equity.iloc[-1]


def test_annual_summary_preserves_carried_equity():
    marks = pd.DataFrame([dict(year=2025, equity=4200., cash=200., gross=4000., positions=1),
        dict(year=2026, equity=4500., cash=4500., gross=0., positions=0)])
    lots = pd.DataFrame([dict(pair_id=0, exit_time=pd.Timestamp('2026-01-02', tz='UTC'), net=500.)])
    fills = pd.DataFrame([dict(bar_time=pd.Timestamp('2026-01-02', tz='UTC'), fee=1., side='SELL', leg='INITIAL')])
    orders = pd.DataFrame([dict(time=pd.Timestamp('2025-12-31', tz='UTC'), status='FILLED')])
    rows = annual_summary(marks, lots, orders, fills)
    assert rows[1]['start_equity'] == 4200
    assert rows[1]['return_pct'] == pytest.approx(100*(4500/4200-1))
    assert rows[0]['completed_campaigns'] == 0
    assert rows[1]['closed_campaign_gains'] == 500


def test_simulator_matches_separate_vector_stop_random_paths():
    rng = np.random.default_rng(20261020)
    for _ in range(80):
        prices = np.r_[100., 100*np.exp(np.cumsum(rng.normal(0, .04, 19))) ]
        path = [(float(p), float(p*1.03), float(p*.97), float(p)) for p in prices]
        tape, bars = fixture_paths([path])
        lot = simulate(tape, 'FULL_BASE', .0008)['lots'].iloc[0]
        idx, price, reason, _ = independent_exit(bars, 0)
        assert lot.exit_bar_index == idx
        assert lot.exit_price == pytest.approx(price)
        assert lot.exit_reason == reason


def test_no_signal_never_creates_trade():
    tape, _ = fixture_paths([flat()], entries=[-1])
    out = simulate(tape, 'FULL_BASE', .0008)
    assert out['lots'].empty
    assert out['orders'].empty
    assert out['marks'].equity.eq(4000).all()


def test_missing_held_bar_blocks_instead_of_fabricating_mark():
    tape, _ = fixture_paths([flat()])
    del tape['bytime'][tape['timeline'][2]][0]
    with pytest.raises(ValueError, match='Missing held bars'):
        simulate(tape, 'FULL_BASE', .0008)


def test_final_bar_high_close_not_used_at_expiry():
    path = flat()
    path[-1] = (101, 300, 90, 250)
    tape, _ = fixture_paths([path])
    lot = simulate(tape, 'FULL_BASE', .0008)['lots'].iloc[0]
    assert lot.exit_reason == 'EXPIRY'
    assert lot.exit_price == 101


def test_same_bar_initial_stop_not_improved_by_high():
    path = flat()
    path[0] = (100, 160, 94, 120)
    tape, _ = fixture_paths([path])
    lot = simulate(tape, 'FULL_BASE', .0008)['lots'].iloc[0]
    assert lot.exit_bar_index == 0
    assert lot.exit_price == 95


def test_session_boundary_does_not_supply_two_add_closes():
    path = flat()
    path[1] = (105, 107, 104, 106)
    path[2] = (106, 108, 105, 107)
    tape, _ = fixture_paths([path])
    from dataclasses import replace
    for k in range(2, len(path)):
        old = tape['bypair'][0][k]
        new = replace(old, session_offset=2)
        tape['bypair'][0][k] = new
        tape['bytime'][old.bar_timestamp][0] = new
    out = simulate(tape, 'HALF_ADD_ONE', .0008)
    assert not out['lots'].leg.eq('ADD').any()
