import pytest
from scripts.research.us_activist_13d_review import annual_before,check_clause,identity


def test_annual_precedes_filing_and_no_future_cover():
    rows=[dict(form='10-K',filed='2023-02-01',accn='old'),dict(form='10-K',filed='2024-02-01',accn='future')]
    data={'facts':{'us-gaap':{'X':{'units':{'USD':rows}}}}}
    assert annual_before(data,'2024-01-18')['accession']=='old'
    assert annual_before(data,'2023-01-01') is None


def test_exact_clause_not_investor_or_other_exhibit():
    o={'parts':[{'filename':'a','text':'We may nominate.'},{'filename':'b','text':'We nominated.'}]}
    assert check_clause(o,'b','We nominated.')
    with pytest.raises(ValueError):check_clause(o,'a','We nominated.')


def test_original_identity_requires_issuer_and_trading_symbol():
    s=b'''<xbrli:context><xbrli:identifier>123</xbrli:identifier></xbrli:context><table><tr><td>Common stock</td><td><ix:nonNumeric name="dei:TradingSymbol">AAA</ix:nonNumeric></td></tr></table>'''
    assert identity(s,'0000000123','AAA')['symbol']=='AAA'
    assert identity(s,'0000000999','AAA') is None
    assert identity(s,'0000000123','BBB') is None
