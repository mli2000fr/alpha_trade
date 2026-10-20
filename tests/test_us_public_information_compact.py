import pytest
from scripts.research import us_public_information_compact as s


@pytest.mark.parametrize('url',[
    'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/index.json',
    'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm'])
def test_expected_official_compact_urls(url):assert s.allowed(url)


@pytest.mark.parametrize('url',[
    'http://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm',
    'https://www.sec.gov.evil/Archives/edgar/data/123/000000012326000001/report.htm',
    'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/../../report.htm',
    'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm?token=secret'])
def test_no_redirect_or_auth_or_untrusted_source(url):assert not s.allowed(url)


def test_attachment_listing_no_silent_truncation():
    def listing(n):return {'directory':{'item':[{'name':f'ex99-{i}.htm'} for i in range(n)]}}
    assert len(s.filenames(listing(4),'primary.htm'))==4
    assert s.filenames(listing(5),'primary.htm') is None
