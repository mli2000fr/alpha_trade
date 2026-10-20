import gzip
import pytest
from scripts.research import us_cash_merger_feasibility as s


def row(acc,day='2024-01-03',form='SC TO-T',cik='1'):
    return dict(accession=acc,filed=day,form=form,path=f'edgar/data/{cik}/{acc}.txt')


def test_selection_excludes_amendments_self_tenders_and_outcome_filter():
    rows=[row('0000000001-24-000003',form='SC TO-I'),row('0000000001-24-000002',form='SC TO-T/A'),
          row('0000000001-24-000004'),row('0000000001-24-000001')]
    rows[2]['future_outcome']='FAILED';rows[3]['future_outcome']='COMPLETED'
    assert [r['accession'] for r in s.select(rows,2)]==['0000000001-24-000001','0000000001-24-000004']
    rows[2]['future_outcome']='COMPLETED';rows[3]['future_outcome']='FAILED'
    assert len(s.select(rows,2))==2


def test_accession_collapse_not_current_survivor_filter():
    rows=[row('0000000001-24-000001',cik='2'),row('0000000001-24-000001',cik='1')]
    assert len(s.select(rows,8))==1
    assert s.select(rows,8)[0]['path'].startswith('edgar/data/1/')


def test_allowlist_no_broker_or_alternate_host_or_queries():
    assert s.allowed(s.INDEX)
    assert s.allowed('https://www.sec.gov/Archives/edgar/data/1/0000000001-24-000001.txt')
    assert not s.allowed('https://api.alpaca.markets/v2/orders')
    assert not s.allowed(s.INDEX+'?bypass=1')


def test_index_empty_outside_window_truncated_or_too_big_rejected():
    header='CIK|Company Name|Form Type|Date Filed|Filename\n'
    body=header+'1|X|SC TO-T|2024-01-03|edgar/data/1/0000000001-24-000001.txt\n'
    assert len(s.parse_index(gzip.compress(body.encode()),10000))==1
    with pytest.raises(ValueError,match='size'):s.parse_index(gzip.compress(body.encode()),10)
    with pytest.raises(ValueError):s.parse_index(gzip.compress(header.encode()),10000)
    with pytest.raises(ValueError,match='quarter'):s.parse_index(gzip.compress(body.replace('2024-01-03','2025-01-03').encode()),10000)


def test_complete_original_and_conservative_timing_required():
    body=b'<SEC-DOCUMENT>\n<ACCEPTANCE-DATETIME>20240105150000\n<DOCUMENT><TYPE>SC TO-T\n<FILENAME>t.htm\n<TEXT><p>Offer</p></TEXT></DOCUMENT></SEC-DOCUMENT>'
    x=s.parse_filing(body)
    assert x['accepted_utc']=='2024-01-05 20:00:00+00:00'
    assert x['first_full_session']=='2024-01-08'
    with pytest.raises(ValueError,match='Truncated'):s.parse_filing(body[:-15])


def test_no_missing_acceptance_invented():
    x=s.parse_filing(b'<SEC-DOCUMENT><DOCUMENT><TYPE>SC TO-T\n<TEXT>Offer</TEXT></DOCUMENT></SEC-DOCUMENT>')
    assert x['accepted_utc'] is None and x['first_full_session'] is None
