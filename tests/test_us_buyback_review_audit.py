import pytest
from scripts.research.us_buyback_review_audit import normalized, require_quote


def test_whitespace_only_normalization():
    assert normalized('Class\u00a0A\n  shares') == 'Class A shares'
    require_quote('Cash flows\n  100', 'Cash flows 100')


def test_no_fuzzy_value_or_negation_match():
    with pytest.raises(ValueError): require_quote('100', '101')
    with pytest.raises(ValueError): require_quote('not repurchased', 'were repurchased')
