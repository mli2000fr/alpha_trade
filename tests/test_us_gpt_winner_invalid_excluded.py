import pytest
from scripts.research.us_gpt_winner_invalid_excluded import decisions_for


def test_invalid_is_excluded_without_rewriting_validation_or_filling_ranks(monkeypatch):
    monkeypatch.setattr('scripts.research.us_gpt_winner_invalid_excluded.validate_response',
        lambda response,packet:dict(veto=response['veto']))
    packets=[dict(key=str(i),signal_date='2025-01-02',symbol=f'S{i}',context=dict(news=[{}] if i<3 else []))
        for i in range(4)]
    records={str(i):dict(validation=dict(valid=i!=0,veto=i==1),
        response=dict(veto=i==1) if i<3 else None) for i in range(4)}
    result=decisions_for(packets,records)
    assert [r['excluded'] for r in result]==[True,True,False,False]
    assert result[0]['reason']=='INVALID_RESPONSE_EXCLUDED'
    assert result[1]['reason']=='VALIDATED_GPT_VETO'
    assert result[3]['reason']=='NO_NEWS_KEEP_BASELINE'
    assert records['0']['validation']['valid'] is False
    with pytest.raises(ValueError,match='absente'):decisions_for(packets,{})
    with pytest.raises(ValueError,match='dupliquée'):decisions_for(packets[:1]*2,records)


def test_received_valid_answer_is_revalidated_before_trading_decision(monkeypatch):
    def reject(*args):raise ValueError('Citation absente')
    monkeypatch.setattr('scripts.research.us_gpt_winner_invalid_excluded.validate_response',reject)
    packet=dict(key='x',signal_date='2025-01-02',symbol='X',context=dict(news=[{}]))
    with pytest.raises(ValueError,match='Citation'):
        decisions_for([packet],{'x':dict(validation=dict(valid=True),response={})})
