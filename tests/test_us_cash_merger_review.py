import pytest
from scripts.research.us_cash_merger_review import normalized,dates_from_receipt


def test_nonbreaking_whitespace_not_fake_clause_mismatch():
    assert normalized('Class\u00a0A\u200b   Shares')==normalized('Class A Shares')


def test_missing_provider_not_zero_performance():
    assert dates_from_receipt(dict(status_code=403),'X')['status']=='HTTP_UNAVAILABLE'
    r=dict(status_code=200,payload=dict(bars={},next_page_token=None))
    assert dates_from_receipt(r,'X')['status'].startswith('EMPTY')


def test_incomplete_wrong_symbol_duplicate_cannot_be_coverage():
    r=dict(status_code=200,payload=dict(bars={},next_page_token='more'))
    assert dates_from_receipt(r,'X')['status']=='UNEXPECTED_TRUNCATION'
    r['payload']=dict(bars={'Y':[]})
    with pytest.raises(ValueError,match='wrong symbol'):dates_from_receipt(r,'X')
    r['payload']=dict(bars={'X':[dict(t='2024-01-10T05:00:00Z')]*2})
    with pytest.raises(ValueError,match='Duplicate'):dates_from_receipt(r,'X')
