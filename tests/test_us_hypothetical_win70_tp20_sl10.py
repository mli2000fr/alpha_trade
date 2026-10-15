import numpy as np
import pytest

from scripts.research import us_hypothetical_win70_tp20_sl10 as study


def test_costs_use_both_notionals_once():
    assert study.net_return(.2) == pytest.approx((1.2 * .9992 - 1.0008) / 1.0008)
    assert study.net_return(-.1) == pytest.approx((.9 * .9992 - 1.0008) / 1.0008)
    assert study.net_return(.2, 0, 0) == pytest.approx(.2)


def test_exact_seventy_counts_and_compounding_closed_form():
    result = study.case(20, np.random.default_rng(42), 100, exact=True)
    expected = 4000 * (1 + .25 * study.net_return(.2)) ** 14 * (1 + .25 * study.net_return(-.1)) ** 6
    assert result['final_capital_usd']['median'] == pytest.approx(expected)
    assert all(x == .7 for x in result['realized_win_rate'].values())


def test_initial_capital_included_in_drawdown_and_no_leverage():
    flags = np.array([[False] * 30 + [True] * 70, [True] * 70 + [False] * 30])
    curve, dd = study.paths(flags)
    assert dd[0] == pytest.approx(1 - (1 + .25 * study.net_return(-.1)) ** 30)
    assert dd[1] == pytest.approx(dd[0])
    assert curve[0, -1] == pytest.approx(curve[1, -1])
    assert np.all(curve > 0)
    with pytest.raises(ValueError):
        study.paths(flags, allocation=2)


def test_smaller_winners_reduce_expectancy_and_break_even():
    g = ((1.0008 / .9992) - 1 + .3 * .10) / .7
    assert .7 * study.net_return(g) + .3 * study.net_return(-.1) == pytest.approx(0)
    assert .7 * study.net_return(.03) + .3 * study.net_return(-.1) < 0


def test_no_calendar_forecast_and_reproducible_binomial_sampling():
    a = study.case(50, np.random.default_rng(7), 1000, exact=False)
    b = study.case(50, np.random.default_rng(7), 1000, exact=False)
    assert a == b
    assert a['realized_win_rate']['p05'] < .7 < a['realized_win_rate']['p95']


def test_no_overwrite_and_report_is_explicitly_synthetic(tmp_path):
    root = tmp_path / 'projection'
    report = study.run(root, simulations=100)
    assert report['annual_return'] is None
    assert report['historical_year_results'] is None
    assert report['status'] == 'COMPLETED_HYPOTHETICAL_NOT_A_MODEL_RESULT'
    assert report['smaller_average_winner_sensitivity'][0]['return_pct']['median'] < 0
    with pytest.raises(FileExistsError):
        study.run(root, simulations=100)
