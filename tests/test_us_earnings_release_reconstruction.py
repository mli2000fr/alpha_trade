import pandas as pd
import pytest
from scripts.research import us_earnings_release_reconstruction as s


@pytest.mark.parametrize('url',[
    'https://data.sec.gov/submissions/CIK0001751008.json',
    'https://data.sec.gov/submissions/CIK0001751008-submissions-001.json',
    'https://www.sec.gov/Archives/edgar/data/1751008/000175100824000043/0001751008-24-000043.txt'])
def test_only_expected_official_urls(url):assert s.allowed(url)


@pytest.mark.parametrize('url',['http://data.sec.gov/submissions/CIK0001751008.json',
    'https://evil.example/submissions/CIK0001751008.json','https://data.sec.gov.evil/submissions/CIK0001751008.json',
    'https://data.sec.gov/submissions/../secrets','https://data.sec.gov/submissions/CIK0001751008.json?token=x',
    'https://me@data.sec.gov/submissions/CIK0001751008.json'])
def test_no_untrusted_or_authenticated_url(url):assert not s.allowed(url)


def test_no_invented_timezone():
    assert s.acceptance('2024-05-01 16:00:00') is None
    assert s.acceptance('2024-05-01T20:00:00Z')==pd.Timestamp('2024-05-01T20:00Z')


def test_full_session_after_acceptance_before_open_same_day_after_open_next_day():
    schedule=pd.DataFrame({'market_open':pd.to_datetime(['2024-05-01T13:30Z','2024-05-02T13:30Z'],utc=True)},index=pd.to_datetime(['2024-05-01','2024-05-02']))
    assert s.reaction_day('2024-05-01T12:00Z',schedule)==pd.Timestamp('2024-05-01')
    assert s.reaction_day('2024-05-01T14:00Z',schedule)==pd.Timestamp('2024-05-02')
    assert s.reaction_day('2024-05-01T13:30Z',schedule)==pd.Timestamp('2024-05-02')


def test_metadata_parallel_arrays_not_silently_zipped_shorter():
    assert s.rows_from_metadata({'accessionNumber':['A'],'form':['8-K']})==[dict(accessionNumber='A',form='8-K')]
    with pytest.raises(ValueError):s.rows_from_metadata({'accessionNumber':['A'],'form':[]})


def test_only_preceding_original_event_reports_in_fiscal_window():
    c=dict(filed='2024-05-08',fiscal_period_end='2024-03-31')
    rows=[dict(form=f,filingDate=d,accessionNumber=str(i)) for i,(f,d) in enumerate([
        ('8-K','2024-05-01'),('8-K','2024-05-09'),('8-K/A','2024-05-01'),('8-K','2024-03-01'),('6-K','2024-05-08')])]
    assert [r['accessionNumber'] for r in s.case_filings(c,rows)]==['0','4']


def test_target_quarter_prose_not_arbitrary_balance_sheet_date():
    assert s.quarter_mentioned('Results for the first quarter ended March 31, 2024','2024-03-31')
    assert not s.quarter_mentioned('Balance sheet March 31, 2024','2024-03-31')
    assert not s.quarter_mentioned('quarter ended March 31, 2023','2024-03-31')


def test_only_exhibit_release_not_cover_sheet_or_general_sentiment():
    b='<DOCUMENT>\n<TYPE>8-K\n<TEXT>financial results quarter ended March31</TEXT></DOCUMENT><DOCUMENT>\n<TYPE>EX-99.1\n<TEXT>announced financial results first quarter ended March 31,2024</TEXT></DOCUMENT>'
    out=s.release_parts(b);assert len(out)==1 and out[0]['document_type']=='EX-99.1'
