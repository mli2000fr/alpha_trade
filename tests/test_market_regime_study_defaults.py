from ihm.pages.market_regime import _oracle_study_default_source_index
from ihm.pages.market_regime import _oracle_study_command


def test_preferred_study_universe_selected_not_first_file():
    sources = ['universe-file:a.txt', 'universe-file:univers_filtred_tradable.txt']
    assert _oracle_study_default_source_index(sources) == 1


def test_missing_preferred_universe_falls_back_to_first_available():
    assert _oracle_study_default_source_index(['universe-file:a.txt']) == 0


def test_preferred_universe_can_be_first():
    assert _oracle_study_default_source_index(['universe-file:univers_filtred_tradable.txt']) == 0


def test_command_exposes_partial_policy_and_strict_override():
    arguments = ('2026-03-30', '2026-09-30', 'universe-file:univers_filtred_tradable.txt', 'batch', 'artifacts/models')
    assert '--missing-returns-policy partial' in _oracle_study_command(*arguments)
    assert '--missing-returns-policy strict' in _oracle_study_command(*arguments, missing_returns_policy='strict')
