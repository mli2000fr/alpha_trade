import gzip
import pytest
from scripts.research.us_activist_13d_confirmation import allowed,parse_quarter,choose,distinct


def test_sec_new_quarters_allowed_not_arbitrary_downloads():
    assert allowed('https://www.sec.gov/Archives/edgar/full-index/2026/QTR3/master.gz')
    assert allowed('https://www.sec.gov/Archives/edgar/data/123/0000000123-26-000001.txt')
    for url in ['https://www.sec.gov.evil/Archives/edgar/full-index/2026/QTR3/master.gz',
                'https://www.sec.gov/Archives/edgar/full-index/2027/QTR1/master.gz',
                'https://www.sec.gov/Archives/edgar/full-index/2026/QTR3/master.gz?x=1']:
        assert not allowed(url)


def test_quarter2026_requires_exact_year_quarter():
    body=gzip.compress(b'CIK|Company Name|Form Type|Date Filed|Filename\n123|Name|SCHEDULE 13D|2026-07-01|edgar/data/123/0000000123-26-000001.txt\n')
    rows=parse_quarter(body,2026,3)
    assert len(choose(distinct(rows,{'0000000123':{'ABC'}}),10))==1
    with pytest.raises(ValueError,match='quarter'):
        parse_quarter(body,2025,3)
