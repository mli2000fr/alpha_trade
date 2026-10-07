import pandas as pd

from scripts.research.us_concentrated_perfect_direction import hindsight_membership


def fixture():
    return pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'), symbol=s, proba_extreme=1-i*.01,
        fold_start=pd.Timestamp('2024-01-01'), ORACLE_TOP20=True, ORACLE_TOP10=i<10,
        INTERSECTION_ORACLE_TOP10=False, future_return=.2 if i%2 else -.1,
        target_quality_valid=1, local_endpoint_ok=True, oracle_exit_date=pd.Timestamp('2025-01-31'),
        oracle_decile=10 if i%2 else 1) for i,s in enumerate([f'S{i}' for i in range(12)])])


def test_perfect_filter_never_replenishes_outside_original_ten():
    frame = fixture()
    result = hindsight_membership(frame)
    assert result.OBSERVED_TOP10.sum() == 10
    assert result.PERFECT_POSITIVE_TOP10.sum() == 5
    assert not result.loc[result.symbol.isin(['S10','S11']), 'PERFECT_POSITIVE_TOP10'].any()


def test_unknown_invalid_and_flat_labels_are_not_assumed_winners():
    frame = fixture()
    frame.loc[1,'future_return'] = float('nan')
    frame.loc[3,'target_quality_valid'] = 0
    frame.loc[5,'local_endpoint_ok'] = False
    frame.loc[7,'oracle_exit_date'] = pd.NaT
    frame.loc[9,'future_return'] = 0.
    result = hindsight_membership(frame)
    assert result.OBSERVED_TOP10.sum() == 6
    assert result.PERFECT_POSITIVE_TOP10.sum() == 0
