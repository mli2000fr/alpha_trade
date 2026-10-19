import pytest
from scripts.research import us_earnings_release_table_review as s


def table():
    return '<h3>Consolidated Statements of Operations</h3><table><tr><td>In thousands; Three months ended</td></tr><tr><td></td><td>2024</td><td>2023</td></tr><tr><td>Revenue</td><td>$</td><td>120,000</td><td>$</td><td>100,000</td></tr><tr><td>Income (loss) from operations</td><td>18,000</td><td>10,000</td></tr></table>'


def test_scaled_direct_quarter_values_matching_not_new_numbers():
    matches,_=s.table_matches(table(),2024,dict(revenue=(120e6,100e6),operating=(18e6,10e6)))
    assert {x['metric'] for x in matches}=={'revenue','operating'}
    assert all(x['scale']==1000 for x in matches)


@pytest.mark.parametrize('old,new',[('In thousands','No units'),('Three months','Six months'),('2024</td><td>2023','2023</td><td>2024'),('Revenue','Adjusted revenue')])
def test_ambiguous_wrong_or_non_gaap_table_not_admitted(old,new):
    matches,_=s.table_matches(table().replace(old,new),2024,dict(revenue=(120e6,100e6)))
    assert matches==[]


def test_mismatching_release_does_not_inherit_later_filing_value():
    matches,_=s.table_matches(table(),2024,dict(revenue=(130e6,100e6)))
    assert matches==[]


def test_parenthesized_negative_and_no_missing_dash_imputation():
    assert s.numbers('$ ( 18,000 ) $ 10,000')==[-18000,10000]
    assert s.numbers('$ — $ 10,000')==[]


def test_rounding_bound_not_arbitrary_percentage_tolerance():
    assert s.table_matches(table(),2024,dict(revenue=(120000499,100e6)))[0]
    assert not s.table_matches(table(),2024,dict(revenue=(120000501,100e6)))[0]


def test_second_exhibit_is_preserved_separately():
    body='<DOCUMENT>\n<TYPE>EX-99.2\n<TEXT>letter</TEXT></DOCUMENT>'
    assert s.exhibits(body)==[('EX-99.2','\n<TYPE>EX-99.2\n<TEXT>letter</TEXT>')]
