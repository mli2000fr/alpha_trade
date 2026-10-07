import pandas as pd

from scripts.research.us_original_directional_monthly_audit import long_mask, summarize


def test_long_filter_strict_probability_flat_and_margin():
    frame = pd.DataFrame({'proba_long': [.55, .7, .7, .7, .7],
                          'proba_short': [.1, .69, .2, .1, .1],
                          'proba_flat': [.1, .1, .7, .1, .8]})
    assert long_mask(frame).tolist() == [False, False, False, True, False]


def test_missing_labels_not_treated_as_losses_or_deciles():
    frame = pd.DataFrame({'date': ['2026-01-02']*3, 'symbol': ['A','B','C'],
                          'target_quality_valid': [1,1,0], 'oracle_decile': [1,10,None],
                          'future_return': [-.1,.2,None]})
    result = summarize(frame, 'test')[0]
    assert result['evaluated'] == 2
    assert result['unknown'] == 1
    assert result['d1_pct'] == result['d10_pct'] == 50
    assert abs(result['mean_return_h20_pct']-5) < 1e-9
