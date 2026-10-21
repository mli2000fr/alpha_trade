import pandas as pd
from scripts.research.us_activist_13d_confirmation_replay import annual_before,indexed_annual_before,primary_name,maturity,block_issuers


def test_annual_metadata_strictly_before_not_same_day_and_foreign_supported():
    p={'facts':{'dei':{'x':{'units':{'shares':[
       {'filed':'2025-03-01','accn':'foreign','form':'20-F'},
       {'filed':'2025-04-01','accn':'future','form':'10-K'}]}}}}}
    assert annual_before(p,'2025-04-01')['accession']=='foreign'


def test_foreign_primary_selection():
    body=b'<table><tr><td>1</td><td>annual</td><td><a href="annual.htm">annual.htm</a></td><td>20-F</td></tr></table>'
    assert primary_name(body,'20-F')=='annual.htm'


def test_index_metadata_no_missing_companyfacts_survivor_gate():
    rows=[dict(cik='1',form='10-K',filed='2025-03-14',accession='earlier'),
          dict(cik='1',form='10-K',filed='2025-10-10',accession='same-day')]
    assert indexed_annual_before(rows,'1','2025-10-10')['accession']=='earlier'
    assert indexed_annual_before(rows,'2','2025-10-10') is None


def test_maturity_includes_entry_no_peek_beyond_price_cutoff():
    sessions=pd.bdate_range('2026-09-01',periods=80)
    assert maturity(sessions[0],20,sessions,sessions[19])==(True,str(sessions[19].date()),'MATURE')
    assert maturity(sessions[0],20,sessions,sessions[18])[2]=='IMMATURE_HORIZON'
    assert maturity(sessions[0],60,sessions,sessions[19])[0] is False


def test_issuer_block_crosses_year_boundary():
    days=pd.bdate_range('2025-12-01',periods=100)
    rows=[dict(cik='1',decision='PRIMARY_EXPLICIT_INTERVENTION',filed='2025-12-01',entry=str(days[1].date()),accession='a'),
          dict(cik='1',decision='PRIMARY_EXPLICIT_INTERVENTION',filed='2026-01-02',entry='2026-01-05',accession='b')]
    assert [x['admitted'] for x in block_issuers(rows,days)]==[True,False]
