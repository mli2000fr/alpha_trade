import pytest
from service.forward_pit.batch import _sec_filing_index_documents
from service.forward_pit import batch

BASE = 'https://www.sec.gov/Archives/edgar/data/123/000000012325000001'


@pytest.mark.parametrize('href', [
    'release.htm',
    '/Archives/edgar/data/123/000000012325000001/release.htm',
    BASE + '/release.htm',
    '../000000012325000001/release.htm',
    '/ix?doc=/Archives/edgar/data/123/000000012325000001/release.htm',
])
def test_sec_document_href_preserves_accession_directory(href):
    index=f'<tr><td>2</td><td>Release</td><td><a href="{href}">file</a></td><td>EX-99.1</td><td>100</td></tr>'
    rows=_sec_filing_index_documents(index,BASE)
    assert len(rows)==1
    assert rows[0]['url']==BASE+'/release.htm'
    assert rows[0]['filename']=='release.htm'


@pytest.mark.parametrize('href', [
    'https://evil.example/release.htm', '//evil.example/release.htm',
    'javascript:alert(1)', 'https://www.sec.gov.evil.example/release.htm',
    'https://user:password@www.sec.gov/Archives/edgar/data/123/release.htm',
    '/unrelated/release.htm',
])
def test_sec_document_external_or_unsafe_href_is_rejected(href):
    index=f'<tr><td>2</td><td>Release</td><td><a href="{href}">file</a></td><td>EX-99.1</td></tr>'
    assert _sec_filing_index_documents(index,BASE)==[]


def test_exhibit_collector_passes_canonical_directory_for_relative_links(monkeypatch):
    captured=[]
    class Response:
        status_code=200
        text='index'
        def raise_for_status(self): pass
        def close(self): pass
    class Session:
        def get(self,*args,**kwargs):return Response()
    monkeypatch.setattr(batch,'_sec_filing_index_documents',lambda html,base: captured.append(base) or [])
    monkeypatch.setattr(batch.time,'sleep',lambda n:None)
    from datetime import datetime
    batch._download_sec_exhibits(None,Session(),accession_number='0000000123-25-000001',
        submission_url='https://www.sec.gov/Archives/edgar/data/123/0000000123-25-000001.txt',
        headers={},observed=datetime(2025,1,1),run_id='test',prefixes=('EX-99',),
        max_exhibits=2,max_exhibit_bytes=1000,max_requests_per_second=1)
    assert captured==[BASE]
