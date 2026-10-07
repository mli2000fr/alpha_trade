import pandas as pd
import pytest
from modelFactory.meta_oracle import assemble, keep_quota, training_rows
from modelFactory.meta_oracle import MetaConfig, evaluate, report_selections
from modelFactory.meta_oracle import oracle_band_ids, oracle_band_diagnostics, refresh_oracle_bands


def test_target_is_authoritative_not_decile():
    gate = pd.DataFrame({'date': pd.to_datetime(['2020-01-01']), 'symbol': ['A'],
        'directional_oracle_oof_available': [True], 'directional_oracle_eligible': [True]})
    labels = pd.DataFrame({'prediction_date': gate.date, 'symbol': ['A'],
        'oracle_extreme10': [0], 'oracle_decile': [10], 'target_quality_valid': [1],
        'oracle_available_date': pd.to_datetime(['2020-02-01'])})
    assert assemble(gate, labels).oracle_extreme10.iloc[0] == 0
    with pytest.raises(ValueError):
        assemble(pd.concat([gate, gate]), labels)


def test_availability_strictly_precedes_test():
    panel = pd.DataFrame({'date': pd.to_datetime(['2020-01-01'] * 2),
        'oracle_available_date': pd.to_datetime(['2020-02-01', '2020-02-02'])})
    assert len(training_rows(panel, panel.date, pd.Timestamp('2020-02-02'))) == 1


def test_quota_shared_and_ties_stable():
    panel = pd.DataFrame({'date': pd.to_datetime(['2020-01-01'] * 5),
        'symbol': list('EDCBA'), 'score': [1] * 5})
    quotas = (panel.groupby('date').size() * .8).astype(int)
    result = keep_quota(panel, 'score', quotas)
    assert result.symbol.tolist() == list('ABCD')


def test_end_to_end_f0_outputs_and_controls():
    import numpy as np
    dates = pd.bdate_range('2020-01-01', periods=5)
    panel = pd.DataFrame([
        {'date': date, 'symbol': f'S{i:04}', 'oracle_available_date': date,
         'directional_oracle_eligible': True, 'oracle_extreme10': i % 2,
         'oracle_decile': 10 if i % 2 else 5, 'future_return': .1,
         'directional_oracle_proba_extreme': (i % 17) / 17,
         'directional_oracle_extreme_pct': .8 + (i % 11) / 50}
        for date in dates for i in range(1001)])
    config = MetaConfig(horizon=1, minimum_train_sessions=2, test_sessions=1,
                        maximum_folds=1, iterations=2, bootstrap_samples=10)
    scored, metrics = evaluate(panel, [], config)
    assert 'placebo_shuffle' in scored
    assert metrics.test_rows.nunique() == 1
    comparisons, _, _, _ = report_selections(scored, config)
    assert comparisons.retention.nunique() == 1


def test_oracle_bands_boundaries_and_index():
    values = pd.Series([.8, .849999, .85, .899999, .9, .949999, .95, 1.], index=range(10, 18))
    result = oracle_band_ids(values)
    assert result.tolist() == [0, 0, 1, 1, 2, 2, 3, 3]
    assert result.index.equals(values.index)


@pytest.mark.parametrize('value', [.79, 1.01, float('nan'), float('inf'), 'invalid'])
def test_oracle_bands_reject_invalid_percentiles(value):
    with pytest.raises(ValueError, match='percentiles'):
        oracle_band_ids(pd.Series([value]))


def test_band_refresh_preserves_primary_artifacts_and_single_class(tmp_path):
    frame = pd.DataFrame({'date': pd.to_datetime(['2020-01-01'] * 8),
        'directional_oracle_extreme_pct': [.8, .84, .85, .89, .9, .94, .95, 1.],
        'directional_oracle_proba_extreme': [.1, .2, .3, .4, .5, .6, .7, .8],
        'random_score': [.5] * 8, 'placebo_shuffle': [.5] * 8,
        'oracle_extreme10': [0, 1, 0, 1, 0, 1, 1, 1]})
    frame.to_parquet(tmp_path / 'candidates.parquet', index=False)
    (tmp_path / 'report.json').write_text('{"verdict":"NO_GO"}', encoding='utf-8')
    (tmp_path / 'veto_comparison.csv').write_text('unchanged', encoding='utf-8')
    original_candidates = (tmp_path / 'candidates.parquet').read_bytes()
    result = refresh_oracle_bands(tmp_path)
    baseline = result[result.variant.eq('oracle_score_keep80')]
    assert baseline.oracle_band.tolist() == [0, 1, 2, 3]
    assert baseline.events.sum() == len(frame)
    assert baseline.auc.iloc[:3].eq(1).all()
    assert not baseline.auc_valid.iloc[3]
    assert pd.isna(baseline.auc.iloc[3])
    assert (tmp_path / 'report.json').read_text(encoding='utf-8') == '{"verdict":"NO_GO"}'
    assert (tmp_path / 'veto_comparison.csv').read_text(encoding='utf-8') == 'unchanged'
    assert (tmp_path / 'candidates.parquet').read_bytes() == original_candidates
    assert (tmp_path / 'oracle_band_diagnostics.json').exists()
