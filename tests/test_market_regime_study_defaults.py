from ihm.pages.market_regime import _oracle_study_default_source_index


def test_preferred_study_universe_selected_not_first_file():
    sources = ['universe-file:a.txt', 'universe-file:univers_filtred_tradable.txt']
    assert _oracle_study_default_source_index(sources) == 1


def test_missing_preferred_universe_falls_back_to_first_available():
    assert _oracle_study_default_source_index(['universe-file:a.txt']) == 0


def test_preferred_universe_can_be_first():
    assert _oracle_study_default_source_index(['universe-file:univers_filtred_tradable.txt']) == 0
