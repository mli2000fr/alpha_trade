import gzip
import pytest
from scripts.research import us_cash_merger_completion as s


def test_scope_only_public_source_no_query_or_new_quarter():
    assert s.allowed(s.INDEX_URL(2))
    assert not s.allowed(s.INDEX_URL(2)+'?retry=1')
    assert not s.allowed(s.INDEX_URL(1))
    assert not s.allowed('https://api.alpaca.markets/v2/orders')


def test_all_amendments_not_only_successes_and_bound_never_truncates():
    case=dict(target_cik='0000000001',initial_filed='2024-01-01')
    def row(i,form='SC TO-T/A',cik='0000000001'):
        return dict(cik=cik,form=form,filed='2024-02-01',accession=str(i),path=str(i),future_outcome='FAILED')
    rows=[row(1),row(2,'8-K'),row(3,cik='0000000002'),row(4,'SC TO-I')]
    assert s.lifecycle_candidates(rows,case,2)['candidate_count']==2
    v=s.lifecycle_candidates(rows,case,1)
    assert not v['bound_pass'] and v['candidates']==[] and v['candidate_count']==2


def test_quarter_format_and_dates_bound():
    text='CIK|Company Name|Form Type|Date Filed|Filename\n1|X|8-K|2024-04-03|edgar/data/1/0000000001-24-000001.txt\n'
    assert len(s.parse_quarter(gzip.compress(text.encode()),2,10000))==1
    with pytest.raises(ValueError,match='quarter'):s.parse_quarter(gzip.compress(text.encode()),3,10000)
