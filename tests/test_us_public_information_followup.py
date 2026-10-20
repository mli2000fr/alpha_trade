import pytest
from scripts.research import us_public_information_followup as s


def test_same_month_normalization_without_invented_next_month_threshold():
    assert s.same_month_anchor('2026-09-26','2026-09-30')
    assert not s.same_month_anchor('2026-10-02','2026-09-30')
    assert not s.same_month_anchor('2026-09-26','2026-09-26')


def test_quarter_period_not_annual_only_and_guidance_separated():
    assert s.quarter_dates('Results for the quarter ended September 26, 2026')[0]['end']=='2026-09-26'
    assert not s.quarter_dates('Results for the year ended September 30, 2026')
    assert not s.quarter_dates('Revenue guidance for the quarter ending September 30, 2026')
    assert s.quarter_dates('Revenue guidance for the quarter ending September 30, 2026',prospective=True)


def test_earnings_population_not_conditioned_on_later_10q_or_membership():
    assert s.candidate_event(dict(form='8-K',items='2.02,9.01'))
    assert s.candidate_event(dict(form='6-K',items=''))
    assert not s.candidate_event(dict(form='8-K',items='1.01,9.01'))
    assert not s.candidate_event(dict(form='8-K/A',items='2.02'))


def inline(unit='USD',dim=False):
    return f'''<DOCUMENT><TYPE>10-Q
<TEXT><html><xbrli:unit id="u"><xbrli:measure>iso4217:{unit}</xbrli:measure></xbrli:unit>
<xbrli:context id="c"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate>
<xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period>
{'<xbrldi:explicitMember>segment</xbrldi:explicitMember>' if dim else ''}</xbrli:context>
<ix:nonFraction name="us-gaap:Revenues" unitRef="u" contextRef="c">100</ix:nonFraction>
</html></TEXT></DOCUMENT>'''


@pytest.mark.parametrize('currency',['USD','EUR','JPY'])
def test_reporting_currency_from_real_revenue_unit_not_us_listing(currency):
    result=s.inline_currencies(inline(currency))
    assert result['currency']==currency and result['proofs'][0]['end']=='2026-06-30'


def test_dimensional_currency_and_conflicting_currency_are_not_promoted():
    assert s.inline_currencies(inline(dim=True))['currency'] is None
    assert s.inline_currencies(inline('USD')+inline('EUR'))['currency'] is None


@pytest.mark.parametrize('cik,acc',[('x','0000000001-26-000001'),('0000000001','../escape')])
def test_source_urls_strict(cik,acc):
    with pytest.raises(ValueError):s.document_url(cik,acc)


def test_standalone_quarter_table_uses_original_amounts_not_later_10q():
    body='''<DOCUMENT><TYPE>EX-99.1
<table><tr><td>Three months ended September 30, in millions</td></tr>
<tr><td>2026</td><td>2025</td></tr>
<tr><td>Revenue</td><td>120</td><td>100</td></tr>
<tr><td>Operating income</td><td>12</td><td>8</td></tr></table></DOCUMENT>'''
    assert s.standalone_tables(body,2026)['values']==[120e6,100e6,12e6,8e6]
    assert s.standalone_tables(body.replace('Three months','Year'),2026)['values'] is None


def test_git_newlines_explicitly_reconciled_but_content_change_rejected(tmp_path):
    import hashlib
    file=tmp_path/'example.py';file.write_bytes(b'x=1\r\n')
    recorded=hashlib.sha256(b'x=1\n').hexdigest()
    assert s.ancestor_sources({str(file):recorded})[0]['original_sha256']==recorded
    file.write_bytes(b'x=2\r\n')
    with pytest.raises(ValueError,match='content changed'):
        s.ancestor_sources({str(file):recorded})
