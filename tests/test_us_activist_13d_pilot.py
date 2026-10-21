import pytest
from scripts.research.us_activist_13d_pilot import allowed,select,parse,item4,normalized


@pytest.mark.parametrize('url,ok',[
 ('https://www.sec.gov/Archives/edgar/data/123/0000000001-24-000001.txt',True),
 ('https://www.sec.gov/Archives/edgar/data/123/000000000124000001/issuer.htm',True),
 ('http://www.sec.gov/Archives/edgar/data/123/0000000001-24-000001.txt',False),
 ('https://evil.sec.gov/Archives/edgar/data/123/0000000001-24-000001.txt',False),
 ('https://www.sec.gov/Archives/edgar/data/123/0000000001-24-000001.txt?foo=bar',False),
 ('https://www.sec.gov/Archives/edgar/data/123/../../secret.htm',False)])
def test_url_allowlist(url,ok):assert allowed(url)==ok


def test_select_all_not_first_good_or_amendments():
    a=dict(cik='0000000123',form='SC 13D',filed='2024-01-02',accession='a')
    rows=[a,dict(a,form='SC 13D/A',accession='b'),dict(a,accession='c',cik='0000000999'),dict(a)]
    assert [x['accession'] for x in select(rows,{'0000000123':{'AAA'}})]==['a']


def filing():
    return b'''<SEC-DOCUMENT><SEC-HEADER><ACCEPTANCE-DATETIME>20240102163000
SUBJECT COMPANY:
 COMPANY CONFORMED NAME: TARGET INC
 CENTRAL INDEX KEY: 123
FILED BY:
 COMPANY CONFORMED NAME: FUND LLP
 CENTRAL INDEX KEY: 999
</SEC-HEADER>
<DOCUMENT><TYPE>SC 13D
<FILENAME>schedule.htm
<TEXT><html><body>Item 4. Purpose of Transaction We demand new directors. Item 5. Interest in Securities Shares.</body></html></TEXT></DOCUMENT></SEC-DOCUMENT>'''


def test_subject_not_investor_and_acceptance_timezone():
    p=parse(filing())
    assert p['subject_cik']=='0000000123' and p['subject_name']=='TARGET INC'
    assert p['accepted_utc']=='2024-01-02T21:30:00+00:00'
    assert 'We demand new directors.' in p['item4']


def test_truncation_and_ambiguous_primary_rejected():
    with pytest.raises(ValueError):parse(filing().replace(b'</SEC-DOCUMENT>',b''))
    with pytest.raises(ValueError):parse(filing().replace(b'<TYPE>SC 13D',b'<TYPE>SC 13D/A'))


def test_item4_keeps_generic_wording_for_manual_review():
    s=item4('Item 4 Purpose of Transaction We may discuss Item 5 of this schedule with management. Item 5 Interest in Securities Remaining.')
    assert 'We may discuss Item 5 of this schedule' in s and 'Remaining' not in s
    assert item4('No section present') is None


def test_quote_normalization_is_not_semantic_rewrite():
    assert normalized('cash\u00a0  distribution\n plan')=='cash distribution plan'
    assert normalized('no plan')!='plan'
