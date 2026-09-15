import numpy as np
import pandas as pd
import pytest

from modelFactory.directional_complementarity_audit import aligned_panel, residual_oof, block_ci


def panel():
    rng = np.random.default_rng(42)
    rows = []
    for d in pd.bdate_range('2020-01-01', periods=20):
        for i in range(15):
            a, b = rng.random(2)
            rows.append({'date': d, 'symbol': str(i), 'a': a, 'b': b,
                'future_return': b-.5, 'realized_rank': b})
    return pd.DataFrame(rows)


def test_projection_never_uses_targets_or_future_scores():
    frame = panel()
    output, windows = residual_oof(frame, 'b', ['a'], 2, minimum_train=5, test_size=3)
    assert all(pd.Timestamp(w['train_end']) < pd.Timestamp(w['test_start']) for w in windows)
    changed = frame.copy()
    changed['future_return'] *= -100
    output_changed, _ = residual_oof(changed, 'b', ['a'], 2, minimum_train=5, test_size=3)
    np.testing.assert_allclose(output.residual, output_changed.residual)
    last_date = frame.date.max()
    changed.loc[changed.date.eq(last_date), ['a','b']] = 999
    changed_output, _ = residual_oof(changed, 'b', ['a'], 2, minimum_train=5, test_size=3)
    np.testing.assert_allclose(output[output.date.lt(last_date)].residual,
        changed_output[changed_output.date.lt(last_date)].residual)


def test_identical_scores_have_zero_residual_variation():
    frame = panel()
    frame.b = frame.a
    output, _ = residual_oof(frame, 'b', ['a'], 2, minimum_train=5, test_size=3)
    # Numerical roundoff must not become an apparent rank signal.
    assert output.groupby('date').residual.nunique().eq(1).all()


def test_alignment_rejects_incompatible_labels(tmp_path):
    frame = panel().rename(columns={'a':'score'})
    frame.to_parquet(tmp_path / 'a.parquet')
    changed = frame.copy()
    changed.future_return += .1
    changed.to_parquet(tmp_path / 'b.parquet')
    definitions = {name: {'path': f'{name}.parquet', 'score': {'column':'score'}} for name in ['a','b']}
    with pytest.raises(ValueError, match='Incompatible'):
        aligned_panel(tmp_path, definitions)


def test_block_interval_reproducible_and_insufficient_history():
    assert block_ci([1,2], 3) == [None,None]
    assert block_ci(np.arange(50), 4, 20) == block_ci(np.arange(50), 4, 20)
