from scripts.research import us_public_information_review as s
from test_us_public_information_followup import inline


def test_tax_inclusive_revenue_is_reporting_currency_not_ignored():
    body=inline('EUR').replace('us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax')
    assert s.reporting_units(body)['currency']=='EUR'
    assert 'IncludingAssessedTax' in s.reporting_units(body)['proofs'][0]['tag']


def test_dimensions_cannot_supply_consolidated_currency():
    assert s.reporting_units(inline('USD',dim=True))['currency'] is None


def test_table_scale_in_preceding_statement_context_and_no_future_amount_match():
    body='''<DOCUMENT><TYPE>EX-99.1
<p>Condensed consolidated statements of operations (in thousands)</p>
<table><tr><td>Three months ended December 31, 2023 and December 31, 2022</td></tr>
<tr><td>Revenue</td><td>120000</td><td>100000</td></tr>
<tr><td>Operating income</td><td>12000</td><td>8000</td></tr></table></DOCUMENT>'''
    assert s.release_tables(body,2023)['values']==[120e6,100e6,12e6,8e6]
    assert s.release_tables(body,2024)['values'] is None
