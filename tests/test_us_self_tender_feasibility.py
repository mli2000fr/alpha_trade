from scripts.research.us_self_tender_feasibility import distinct_initials,choose,parse_original


def row(cik='0000000001',form='SC TO-I',day='2025-01-02',acc='0000000001-25-000001'):
    return dict(cik=cik,name='Example',form=form,filed=day,accession=acc,path=f'edgar/data/1/{acc}.txt')


def test_dedup_cofilers_before_current_mapping_and_ignore_amendments():
    data=[row(),row(cik='0000000002'),row(form='SC TO-I/A')]
    result=distinct_initials(data,{'0000000002':{'XYZ'}})
    assert len(result)==1
    assert result[0]['mapped_symbols']==['XYZ']
    assert result[0]['indexed_ciks']==['0000000001','0000000002']


def test_selection_is_current_all_plus_fixed_hash_probe_no_price_argument():
    data=distinct_initials([row(),row(cik='0000000002',acc='0000000002-25-000002'),row(cik='0000000003',acc='0000000003-25-000003')],{'0000000002':{'XYZ'}})
    picked=choose(data,n=1)
    assert len(picked)==2
    assert sum(x['cohort']=='CURRENT_UNIVERSE_INDEX_ROUTE' for x in picked)==1


def test_original_must_have_subject_and_complete_initial_form():
    import pytest
    with pytest.raises(ValueError,match='Incomplete'):
        parse_original(b'partial original')
    body=b'''<SEC-DOCUMENT>\n<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20250102170000
SUBJECT COMPANY:\n COMPANY CONFORMED NAME: Example Co\n CENTRAL INDEX KEY: 1
FILED BY:\n CENTRAL INDEX KEY: 2\n</SEC-HEADER>
<DOCUMENT>\n<TYPE>SC TO-I\n<FILENAME>offer.htm\n<TEXT><p>Offer to purchase shares.</p></TEXT></DOCUMENT>
</SEC-DOCUMENT>'''
    result=parse_original(body)
    assert result['subject_cik']=='0000000001'
    assert result['accepted_utc']=='2025-01-02T22:00:00+00:00'
