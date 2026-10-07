import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_numeric_effect import (
    daily_metrics, fit_pair_member, merge_targets, paired_summary, partition_indices,
)


def sample():
    return pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02'] * 20),
        symbol=[f'S{i:02d}' for i in range(20)], score=np.arange(20),
        atr20_pct=np.arange(20), oracle_extreme10=[0] * 16 + [1] * 4,
        oracle_decile=[5] * 16 + [10, 10, 1, 1],
        future_return=[.01] * 16 + [.2, .3, -.2, -.3], fold_start='2024-01-02'))


def test_missing_future_label_not_removed_before_top20():
    data = sample()
    data.loc[19, ['oracle_extreme10', 'oracle_decile', 'future_return']] = np.nan
    result = daily_metrics(data)
    assert result.selected_count.tolist() == [4, 4, 4]
    assert result.evaluated_count.tolist() == [3, 3, 3]
    assert result.precision.tolist() == [1, 1, 1]
    assert result.coverage.tolist() == [.75, .75, .75]


def test_intersection_not_replaced_with_top20_product_score():
    data = sample()
    data['atr20_pct'] = data.atr20_pct[::-1].to_numpy()
    result = daily_metrics(data)
    intersection = result[result.policy.eq('ORACLE_AND_ATR_TOP20')].iloc[0]
    assert intersection.selected_count == 0
    assert intersection.evaluated_count == 0
    assert pd.isna(intersection.precision)


def test_ties_are_symbol_stable():
    data = sample()
    data['score'] = 1.
    left = daily_metrics(data)
    right = daily_metrics(data.sample(frac=1, random_state=123))
    pd.testing.assert_frame_equal(left, right)


def test_unknown_outcomes_are_not_valid_training_targets():
    features = sample()[['date', 'symbol', 'atr20_pct']]
    labels = sample().drop(columns=['score', 'atr20_pct', 'fold_start'])
    labels['target_quality_valid'] = 1
    labels['oracle_available_date'] = pd.Timestamp('2024-02-05')
    labels.loc[0, 'target_quality_valid'] = 0
    labels.loc[1, 'oracle_available_date'] = pd.Timestamp('2024-01-02')
    labels.loc[2, 'oracle_decile'] = 20
    result = merge_targets(features, labels)
    assert len(result) == 20
    assert result.oracle_extreme10.isna().sum() == 3


def test_duplicate_labels_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        merge_targets(pd.DataFrame(), pd.concat([sample(), sample()]))


def test_partition_purges_label_availability_and_keeps_unlabeled_test_pool():
    data = pd.DataFrame(dict(date=pd.to_datetime(['2024-01-01', '2024-01-02',
        '2024-02-01', '2024-02-02', '2024-03-01']),
        oracle_extreme10=[0, 1, 0, 1, np.nan],
        oracle_available_date=pd.to_datetime(['2024-01-20', '2024-02-01',
            '2024-02-20', '2024-03-01', None])))
    fold = dict(train_dates=pd.to_datetime(['2024-01-01', '2024-01-02']),
        val_dates=pd.to_datetime(['2024-02-01', '2024-02-02']),
        test_dates=pd.to_datetime(['2024-03-01']), val_start='2024-02-01', t_start='2024-03-01')
    train, val, test = partition_indices(data, fold)
    assert train.tolist() == [0]
    assert val.tolist() == [2]
    assert test.tolist() == [4]


def test_identical_predictions_have_exactly_zero_paired_delta():
    data = daily_metrics(sample())
    overall, annual, _ = paired_summary(data, data, repetitions=10)
    assert all(item['delta_precision_pp'] == 0 for item in overall)
    assert all(item['descriptive_block20_ci_pp'] == [0, 0] for item in overall)
    assert annual.delta_precision_pp.eq(0).all()


def test_unpaired_test_dates_rejected():
    data = daily_metrics(sample())
    other = data.copy()
    other['date'] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match='Unpaired'):
        paired_summary(data, other)


def test_duplicate_oof_dates_rejected():
    data = daily_metrics(sample())
    with pytest.raises(ValueError, match='Overlapping'):
        paired_summary(pd.concat([data, data]), data)


def test_small_pool_explicitly_rejected():
    with pytest.raises(ValueError, match='smaller than 20'):
        daily_metrics(sample().head(19))


def test_fit_never_uses_test_labels_for_early_stopping():
    dates = pd.bdate_range('2024-01-01', periods=12)
    data = pd.DataFrame([(day, f'S{i:03d}', float(i)) for day in dates for i in range(100)],
                        columns=['date', 'symbol', 'x'])
    data['oracle_extreme10'] = (data.x % 3 == 0).astype(int)
    data['oracle_decile'] = np.where(data.oracle_extreme10, 10, 5)
    data['future_return'] = np.where(data.oracle_extreme10, .15, .01)
    data['atr20_pct'] = data.x / 1000
    data['oracle_available_date'] = data.date + pd.Timedelta(days=1)
    fold = dict(train_dates=dates[:6], val_dates=dates[6:9], test_dates=dates[9:],
                val_start=str(dates[6].date()), t_start=str(dates[9].date()),
                t_end=str(dates[-1].date()))
    model, predicted, metrics = fit_pair_member(data, ['x'], fold, threads=1)
    altered = data.copy()
    test = altered.date.isin(fold['test_dates'])
    altered.loc[test, 'oracle_extreme10'] = 1 - altered.loc[test, 'oracle_extreme10']
    other_model, other_predictions, other_metrics = fit_pair_member(altered, ['x'], fold, threads=1)
    np.testing.assert_array_equal(predicted.score.to_numpy(), other_predictions.score.to_numpy())
    assert model.best_iteration == other_model.best_iteration
    assert metrics['train_rows'] == other_metrics['train_rows']
    assert pd.Timestamp(metrics['train_max_available']) < pd.Timestamp(fold['val_start'])
    assert pd.Timestamp(metrics['val_max_available']) < pd.Timestamp(fold['t_start'])
