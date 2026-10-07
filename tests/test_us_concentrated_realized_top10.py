import numpy as np
import pandas as pd
import pytest

from scripts.research.us_concentrated_realized_top10 import realized_membership, replay_scores


def labels():
    return pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'), symbol=[f'S{i:02}' for i in range(12)],
        future_return=[(-1)**i*(i+1)/100 for i in range(12)], target_quality_valid=1,
        local_endpoint_ok=True, oracle_exit_date=pd.Timestamp('2025-01-31')))


def test_ranks_absolute_actual_moves_of_both_signs_not_positive_only():
    data = realized_membership(labels())
    assert data.symbol.tolist() == [f'S{i:02}' for i in range(11,1,-1)]
    assert data.future_return.gt(0).sum() == 5
    assert data.future_return.lt(0).sum() == 5
    assert data.REALIZED_TOP10.sum() == 10
    scores = replay_scores(data)
    assert scores.proba_extreme.is_monotonic_decreasing
    assert 'future_return' not in scores


def test_invalid_original_winner_not_replenished_by_eleventh():
    source = labels()
    source.loc[source.symbol.eq('S11'),'local_endpoint_ok'] = False
    data = realized_membership(source)
    assert len(data) == 10 and data.REALIZED_TOP10.sum() == 9
    assert 'S01' not in data.symbol.values


def test_unknown_returns_not_ranked_and_duplicate_keys_rejected():
    source = labels()
    source.loc[11,'future_return'] = np.nan
    data = realized_membership(source)
    assert 'S11' not in data.symbol.values
    with pytest.raises(ValueError, match='Duplicate'):
        realized_membership(pd.concat([source, source.iloc[:1]]))


def test_positive_filter_is_applied_after_top10_and_keeps_original_rank_scores():
    data = realized_membership(labels())
    scores = replay_scores(data, positive_only=True)
    chosen = scores.loc[scores.REALIZED_POSITIVE_TOP10]
    assert len(chosen) == 5
    assert 'S00' not in chosen.symbol.values  # positive but outside original ten
    assert chosen.symbol.tolist() == ['S10','S08','S06','S04','S02']
    assert chosen.proba_extreme.iloc[0] == pytest.approx(.998)
    assert 'future_return' not in scores


def test_positive_filter_does_not_accept_flat_or_invalid_endpoint():
    source = labels()
    source.loc[source.symbol.eq('S10'),'local_endpoint_ok'] = False
    data = realized_membership(source)
    scores = replay_scores(data, positive_only=True)
    assert scores.REALIZED_POSITIVE_TOP10.sum() == 4
    source['future_return'] = 0.
    assert not replay_scores(realized_membership(source), positive_only=True).REALIZED_POSITIVE_TOP10.any()
