import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_h20_dataset_audit import label_checks, restore_ranks, summarize_features


def test_global_ranks_not_per_chunk():
    frame = pd.DataFrame(dict(date=pd.to_datetime(['2024-01-01'] * 3), symbol=['A', 'B', 'C'], momentum_5=[1., 2., 2.]))
    result = restore_ranks(frame, ['momentum_5', 'momentum_5_xs_rank'])
    assert result.momentum_5_xs_rank.tolist() == pytest.approx([1/3, 5/6, 5/6])


def test_duplicate_feature_keys_blocked():
    frame = pd.DataFrame(dict(date=['2024-01-01'] * 2, symbol=['A', 'A'], x=[1., 2.]))
    with pytest.raises(ValueError, match='Duplicate'):
        restore_ranks(frame, ['x'])


def test_missing_rank_source_blocked():
    with pytest.raises(ValueError, match='source'):
        restore_ranks(pd.DataFrame(), ['x_xs_rank'])


def test_feature_counts_do_not_hide_nonfinite():
    frame = pd.DataFrame(dict(date=pd.date_range('2024-01-01', periods=4), symbol=['X'] * 4, x=[0., 2., np.nan, np.inf]))
    row = summarize_features(frame, ['x'])[0]
    assert (row['rows'], row['finite'], row['null'], row['infinite'], row['zeros']) == (4, 2, 1, 1, 1)
    assert row['quantiles']['0.5'] == 1


def labels():
    return pd.DataFrame(dict(symbol=['A', 'B'], prediction_date=['2024-01-01'] * 2,
        oracle_exit_date=['2024-01-30'] * 2, oracle_available_date=['2024-01-31'] * 2,
        future_return=[-.1, .1], future_return_raw=[-.1, .1], oracle_pct_rank=[.5, 1.],
        oracle_decile=[5, 10], oracle_extreme10=[0, 1], target_quality_valid=[1, 1],
        target_quality_reason=[None, None], start_px=[10., 10.], end_px=[9., 11.],
        start_source=['eodhd'] * 2, end_source=['eodhd'] * 2))


def test_rank_validation_keeps_original_universe():
    result = label_checks(labels(), {'B'}, {})
    assert result['current_universe_rows'] == 1
    assert all(c['original_batch'] == 0 for c in result['checks'].values())


def test_missing_dates_and_wrong_returns_are_counted():
    data = labels()
    data.loc[0, 'oracle_available_date'] = None
    data.loc[1, 'end_px'] = 15.
    result = label_checks(data, {'A', 'B'}, {})
    assert result['checks']['valid_missing_or_invalid_dates']['original_batch'] == 1
    assert result['checks']['valid_return_mismatch_current_bars']['original_batch'] == 1


def test_empty_label_scope_is_explicit():
    result = label_checks(labels().iloc[:0], {'A'}, {})
    assert result['rows'] == 0
    assert result['original_batch_symbols'] == 0
