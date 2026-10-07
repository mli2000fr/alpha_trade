import pandas as pd
import pytest

from scripts.research.us_concentrated_live_parity_preflight import (
    current_sector_coverage, run,
)


def test_current_sector_coverage_is_explicit_and_preserves_unknowns():
    candidates = pd.DataFrame({'date': ['2025-01-02'] * 4,
                               'symbol': ['AAA', 'BBB', 'CCC', 'AAA']})
    result = current_sector_coverage(candidates, {'AAA': 'Technology', 'BBB': 'Unknown'})
    assert result['candidate_days'] == 3
    assert result['qualified_sector_days'] == 1
    assert result['missing_sector_days'] == 2
    assert result['missing_symbols'] == ['BBB', 'CCC']
    assert result['first_missing'] == '2025-01-02'


def test_invalid_policy_fails_before_database_access(tmp_path):
    with pytest.raises(ValueError, match='Unknown sector policy'):
        run(tmp_path, tmp_path / 'output', sector_policy='implicit_current')
