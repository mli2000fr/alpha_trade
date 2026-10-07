import pandas as pd
import pytest

from scripts.research.us_oracle_price_repair_plan import (
    propose_existing, select_candidates, validate_prices,
)


def test_candidates_do_not_select_real_large_moves_or_small_rounding():
    fresh = pd.DataFrame(dict(symbol=['KNTK'] * 3,
        date=['2018-11-12', '2018-11-13', '2020-11-10'], close=[99., 91., 300.]))
    local = fresh.copy()
    local['close'] = [.002, 91.01, 300.]
    result = select_candidates(local, fresh)
    assert len(result) == 1
    assert result.review_group.iloc[0] == 'KNOWN_2018_SCALE_ANOMALY'


def test_later_amtb_is_separate_review():
    old = pd.DataFrame(dict(symbol=['AMTB'], date=['2023-09-11'], close=[10.]))
    new = old.assign(close=20.)
    assert select_candidates(old, new).review_group.iloc[0] == 'SEPARATE_REVIEW_REQUIRED'


def test_exact_key_proposal_preserves_identity_and_is_idempotent():
    old = pd.DataFrame(dict(symbol=['X'], date=['2020-01-01'], close=[.002], instrument_id=[123]))
    new = old.assign(close=99.)
    proposal, diff = propose_existing(old, new, ['symbol', 'date'], ['close'])
    assert proposal.instrument_id.iloc[0] == 123
    assert old.close.iloc[0] == .002
    assert len(diff) == 1
    _, second_diff = propose_existing(proposal, new, ['symbol', 'date'], ['close'])
    assert second_diff == []


def test_missing_key_blocks_insertion():
    old = pd.DataFrame(dict(symbol=['X'], date=['2020-01-01'], close=[1.]))
    with pytest.raises(ValueError, match='Missing existing key'):
        propose_existing(old, old.assign(date='2020-01-02'), ['symbol', 'date'], ['close'])


def test_invalid_range_blocked_but_large_real_price_allowed():
    frame = pd.DataFrame(dict(symbol=['X'], date=['2020-01-01'],
                              open=[100.], high=[300.], low=[99.], close=[300.], volume=[10]))
    validate_prices(frame)
    with pytest.raises(ValueError, match='range'):
        validate_prices(frame.assign(high=200.))


def test_duplicate_proposal_blocked():
    frame = pd.DataFrame(dict(symbol=['X'], date=['2020-01-01'], close=[1.]))
    with pytest.raises(ValueError, match='Ambiguous'):
        propose_existing(frame, pd.concat([frame, frame]), ['symbol', 'date'], ['close'])
