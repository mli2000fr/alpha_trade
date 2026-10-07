from copy import deepcopy
from decimal import Decimal

import pytest

from service.fr.robustness_13d import delayed_tape, VARIANTS
from service.fr.robustness_engine_13d import replay_assumed
from service.fr.provider_exploratory_engine_13b import replay_assumed as archived_replay
from tests.test_fr_provider_exploratory_13b import assumed_fixture


def test_baseline_exact_nonmutation(tmp_path):
    tape, costs, _ = assumed_fixture(tmp_path)
    original = deepcopy(tape)
    tax = {'known_positive': {}, 'unknown_liable': False}
    assert replay_assumed(tape, costs, tax) == archived_replay(tape, costs, tax)
    assert tape == original


def test_delay_keeps_original_exit_information_rank(tmp_path):
    tape, costs, _ = assumed_fixture(tmp_path)
    tape['horizon'] = 2
    changed = delayed_tape(tape, 1)
    assert changed['horizon'] == 1
    assert changed['candidates'][0]['session'] == tape['sessions'][1]
    assert changed['candidates'][0]['available_at'] == tape['candidates'][0]['available_at']
    assert changed['decision_at'][tape['sessions'][1]] == tape['decision_at'][tape['sessions'][0]]
    result = replay_assumed(changed, costs, {'known_positive': {}, 'unknown_liable': False})
    assert result['ledger']['trades'][0]['exit_session'] == tape['sessions'][2]
    assert tape['candidates'][0]['session'] == tape['sessions'][0]


def test_cap_all_in_and_no_rebalance(tmp_path):
    tape, costs, _ = assumed_fixture(tmp_path)
    for bar in tape['bars'].values():
        bar['A']['open'] = '10'
    result = replay_assumed(tape, costs, {'known_positive': {}, 'unknown_liable': False}, position_cap_pct='0.10')
    buy = next(o for o in result['ledger']['orders'] if o['side'] == 'BUY')
    assert buy['notional'] + buy['total'] <= Decimal('100')
    assert buy['quantity'] == 9
    assert result['net_pnl'] == result['final_equity']-result['initial_equity']


@pytest.mark.parametrize('cap', ['0','-1','1.1','NaN'])
def test_invalid_cap(tmp_path, cap):
    tape, costs, _ = assumed_fixture(tmp_path)
    with pytest.raises(ValueError):
        replay_assumed(tape, costs, {'known_positive': {}, 'unknown_liable': False}, position_cap_pct=cap)


def test_fixed_variants_and_delay_rejections(tmp_path):
    tape, _, _ = assumed_fixture(tmp_path)
    assert len(VARIANTS) == 4
    with pytest.raises(ValueError):
        delayed_tape(tape, 1)
    with pytest.raises(ValueError):
        delayed_tape(tape, 2)
