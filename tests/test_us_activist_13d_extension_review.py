import pandas as pd
import pytest
from scripts.research.us_activist_13d_extension_review import section4, block_issuers


def test_structured_xml_purpose_not_missing():
    obj={'item4':None,'parts':[]}
    text,method=section4(obj,b'<root><transactionPurpose>Current exact action</transactionPurpose></root>')
    assert text=='Current exact action' and method=='STRUCTURED_TRANSACTIONPURPOSE'


def test_alternate_legacy_item5_heading():
    obj={'item4':None,'parts':[{'type':'SC 13D','text':'Item 4 Purpose of Transaction Concrete demand. Item 5 Ownership'}]}
    text,method=section4(obj)
    assert text.strip().endswith('Concrete demand.') and method=='LEGACY_ALTERNATE_ITEM5'


def test_no_section_invention_for_mislabeled13g():
    assert section4({'item4':None,'parts':[{'type':'SC 13D','text':'SCHEDULE 13G Item 4 ownership only'}]})[0]==''


def test_shared_issuer_block_even_if_symbol_changes_or_prices_unknown():
    sessions=pd.bdate_range('2024-01-01',periods=150)
    base=dict(cik='000001',decision='PRIMARY_EXPLICIT_INTERVENTION')
    rows=[dict(base,accession='first',filed='2024-01-01',entry=str(sessions[1].date()),symbol='OLD'),
          dict(base,accession='second',filed='2024-01-02',entry=str(sessions[20].date()),symbol='NEW'),
          dict(base,accession='third',filed='2024-04-01',entry=str(sessions[61].date()),symbol='NEW')]
    result=block_issuers(rows,sessions)
    assert [r['admitted'] for r in result]==[True,False,True]


def test_exclusion_does_not_start_position_block():
    days=pd.bdate_range('2024-01-01',periods=100)
    rows=[dict(cik='1',accession='a',filed='2024-01-01',entry=str(days[1].date()),decision='EXCLUDE_GENERIC'),
          dict(cik='1',accession='b',filed='2024-01-02',entry=str(days[2].date()),decision='PRIMARY_EXPLICIT_INTERVENTION')]
    assert block_issuers(rows,days)[1]['admitted']
