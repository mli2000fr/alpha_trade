import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_barrier_comparison_summary import (
    paired_date_interval, portfolio_periods, tp_summary, summarize_remediation,
)


def test_unknown_outcomes_produce_bounds_not_synthetic_wins_or_losses():
    result = tp_summary(pd.DataFrame({'long_tp_before_sl': [1., 0., np.nan, np.nan]}))
    assert result['tp_rate'] == .5
    assert result['tp_lower_all_selected'] == .25
    assert result['tp_upper_all_selected'] == .75


def test_block_bootstrap_preserves_identical_arms_and_is_deterministic():
    frame = pd.DataFrame({'date': pd.bdate_range('2025-01-01', periods=40),
                          'long_tp_before_sl': [0., 1.]*20})
    a = paired_date_interval(frame, frame, repetitions=30)
    b = paired_date_interval(frame, frame, repetitions=30)
    assert a == b
    assert a['point_delta'] == a['lower'] == a['upper'] == 0.
    with pytest.raises(ValueError, match='Unpaired'):
        paired_date_interval(frame, frame.iloc[1:], repetitions=30)


def test_calendar_marking_is_distinct_from_tail_cohort_return():
    daily = pd.DataFrame({'date': pd.to_datetime(['2025-12-30', '2025-12-31', '2026-01-30']),
                          'equity': [4400., 4500., 4200.]})
    result = portfolio_periods(daily, 2025, '2025-12-31')
    assert result['calendar_mark_to_market_return'] == .125
    assert result['cohort_fully_closed_return'] == pytest.approx(.05)
    assert result['calendar_max_drawdown'] == 0.
    assert result['cohort_max_drawdown'] == pytest.approx(4200./4500.-1)


def test_partial_prefix_does_not_claim_a_fully_closed_return(tmp_path):
    (tmp_path/'report.json').write_text('{}', encoding='utf-8')
    row = portfolio_periods(pd.DataFrame({'date': pd.to_datetime(['2026-08-14']), 'equity': [4100.]}),
                            2026, '2026-08-14')
    report = dict(status='PARTIAL_BLOCKED_CORPORATE_ACTION', complete_runs=9, failures=[{'error': 'merger'}],
        summary=[], paired_prefix_diagnostic_not_confirmation=[dict(row, count=10, arm='NEW_BARRIER_LONG')])
    result = summarize_remediation(tmp_path, report)
    prefix = result['paired_partial_prefix'][0]
    assert prefix['mark_to_market_only']
    assert prefix['fully_closed'] is False
    assert 'cohort_fully_closed_return' not in prefix
