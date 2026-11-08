import pytest
from scripts.research.us_local_llm_winner_resume import transport_recoveries


def test_resume_retries_only_transport_without_receipt():
    packets=[dict(key=str(i),context=dict(news=[{}])) for i in range(4)]
    records={
        '0':dict(response=None,validation=dict(valid=False,error_type='RuntimeError',error='LM Studio HTTP 400')),
        '1':dict(response={},validation=dict(valid=False,error_type='ValueError',error='Citation absente')),
        '2':dict(response={},validation=dict(valid=True)),
    }
    assert transport_recoveries(packets,records)==packets[:1]
    assert records['0']['validation']['valid'] is False
    records['0']['response']={}
    assert not transport_recoveries(packets,records)


def test_multiple_transport_errors_require_diagnosis():
    packets=[dict(key=str(i),context=dict(news=[{}])) for i in range(2)]
    records={str(i):dict(response=None,validation=dict(valid=False,error_type='RuntimeError',
        error='LM Studio HTTP 400')) for i in range(2)}
    with pytest.raises(ValueError,match='Plusieurs'):transport_recoveries(packets,records)
