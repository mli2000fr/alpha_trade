import pytest
from scripts.research.us_gpt_winner_favorable_only import classify


def test_only_favorable_is_bought_and_insufficient_is_separate(monkeypatch):
    monkeypatch.setattr('scripts.research.us_gpt_winner_favorable_only.validate_response',
        lambda response,packet:dict(analysis=response))
    assessments=[('FAVORABLE','SUFFICIENT'),('FAVORABLE','INSUFFICIENT'),
        ('INDETERMINABLE','SUFFICIENT'),('UNFAVORABLE','SUFFICIENT')]
    packets=[dict(key=str(i),signal_date='2025-01-02',symbol=f'S{i}',context=dict(news=[{}] if i!=5 else [])) for i in range(6)]
    records={str(i):dict(validation=dict(valid=i!=4),response=dict(assessment=a,evidence_quality=q))
        for i,(a,q) in enumerate(assessments+[('FAVORABLE','SUFFICIENT')]*2)}
    rows=classify(packets,records)
    assert [r['FAVORABLE_ONLY'] for r in rows]==[True,True,False,False,False,False]
    assert [r['FAVORABLE_SUFFICIENT_ONLY'] for r in rows]==[True,False,False,False,False,False]
    assert records['4']['validation']['valid'] is False
    with pytest.raises(ValueError,match='manquante'):classify(packets,{})
    with pytest.raises(ValueError,match='dupliquée'):classify(packets[:1]*2,records)
