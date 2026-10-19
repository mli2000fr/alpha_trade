from scripts.research.us_earnings_release_reconstruction_audit import selection_known_at_decision


def test_later_original_top10_selection_cannot_seed_earlier_release_backtest():
    assert not selection_known_at_decision('2026-05-11','2026-05-08')


def test_equal_or_earlier_date_not_a_future_selection_but_not_global_qualification():
    assert selection_known_at_decision('2026-05-08','2026-05-08')
    assert selection_known_at_decision('2026-05-07','2026-05-08')


def test_missing_corrected_date_is_not_causal_proof():
    assert not selection_known_at_decision('2026-05-11',None)
