import gzip
import pytest
from scripts.research.us_activist_13d_extension import allowed, parse_quarter, distinct, choose


def encoded(day='2024-04-01'):
    return gzip.compress(('CIK|Company Name|Form Type|Date Filed|Filename\n'
        f'12|Issuer|SC 13D|{day}|edgar/data/12/0000000012-24-000001.txt\n').encode())


def test_official_bounded_allowlist():
    assert allowed('https://www.sec.gov/Archives/edgar/full-index/2025/QTR4/master.gz')
    assert allowed('https://www.sec.gov/Archives/edgar/data/12/0000000012-24-000001.txt')
    for bad in ['https://www.sec.gov.evil/Archives/edgar/full-index/2024/QTR1/master.gz',
                'https://www.sec.gov/Archives/edgar/full-index/2026/QTR1/master.gz',
                'https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/master.gz?x=1',
                'http://www.sec.gov/Archives/edgar/full-index/2024/QTR1/master.gz']:
        assert not allowed(bad)


def test_quarter_validation_and_decompression_bound():
    assert parse_quarter(encoded(),2024,2)[0]['cik']=='0000000012'
    with pytest.raises(ValueError,match='quarter'):
        parse_quarter(encoded(),2024,1)
    with pytest.raises(ValueError,match='size'):
        parse_quarter(encoded(),2024,2,cap=10)


def test_dedup_cfilers_before_selection():
    rows=parse_quarter(encoded(),2024,2)
    rows.append(dict(rows[0],cik='0000000013',name='Investor',path='edgar/data/13/0000000012-24-000001.txt'))
    out=distinct(rows,{'0000000012':{'ABC'}})
    assert len(out)==1 and out[0]['mapped_symbols']==['ABC']
    assert len(out[0]['indexed_ciks'])==2


def test_conflicting_date_never_silently_deduped():
    rows=parse_quarter(encoded(),2024,2)
    with pytest.raises(ValueError,match='Conflicting'):
        distinct(rows+[dict(rows[0],filed='2024-04-02')],{})


def test_current_census_and_deterministic_outside_probe():
    base=distinct(parse_quarter(encoded(),2024,2),{'0000000012':{'ABC'}})[0]
    rows=[base]+[dict(base,accession=f'outside{i}',mapped_symbols=[]) for i in range(20)]
    picked=choose(rows,3)
    assert len(picked)==4
    assert picked==choose(list(reversed(rows)),3)
    assert sum(x['cohort']=='CURRENT_UNIVERSE_INDEX_ROUTE' for x in picked)==1
    assert len({x['accession'] for x in picked})==4
