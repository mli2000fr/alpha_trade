import pandas as pd
import pytest
from scripts.research.us_winner_grid_scores_2017_2026_20261023 import qualify, freeze_top10, START, END, BATCHES


def test_accepted_scope_and_model_allocation():
    assert str(START) == '2017-06-02' and str(END) == '2026-09-30'
    assert BATCHES[2017] == BATCHES[2024]
    assert BATCHES[2025] != BATCHES[2026]


def test_label_free_and_no_same_day_model():
    frame = pd.DataFrame(dict(date=['2017-06-02'], symbol=['AA'], score=[.8], fold_start=['2017-06-02'],
                              terminal_return=[999.], path_amplitude=[999.]))
    folds = {'2017-06-02': dict(metrics=dict(fold_start='2017-06-02', train_available_max='2016-11-29',
                                             val_available_max='2017-06-01'), model_sha256='abc')}
    out = qualify(frame, folds, source='OOF', profile_hash='profile')
    assert 'terminal_return' not in out and 'path_amplitude' not in out
    assert out.score.iloc[0] == .8
    assert str(out.fold_start.dtype) == 'datetime64[ns]'
    folds['2017-06-02']['metrics']['val_available_max'] = '2017-06-02'
    with pytest.raises(ValueError):
        qualify(frame, folds, source='OOF', profile_hash='profile')


def test_ranking_does_not_replace_missing_days_and_ties_are_stable():
    f = pd.DataFrame(dict(date=pd.to_datetime(['2017-06-02']*20), symbol=[f'S{i:02}' for i in range(20)],
                          score=[.5]*20))
    top, missing = freeze_top10(f.sample(frac=1, random_state=7), [START, pd.Timestamp('2017-06-05').date()])
    assert list(top.symbol) == [f'S{i:02}' for i in range(10)]
    assert missing == ['2017-06-05']
    with pytest.raises(ValueError):
        freeze_top10(pd.concat([f, f.iloc[:1]]), [START])


def test_nan_scores_rejected():
    f = pd.DataFrame(dict(date=['2017-06-02'],symbol=['AA'],score=[float('nan')],fold_start=['2017-06-02']))
    with pytest.raises(ValueError, match='Invalid Oracle'):
        qualify(f, {}, source='OOF', profile_hash='x')
