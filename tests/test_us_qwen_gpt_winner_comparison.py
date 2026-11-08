from scripts.research.us_qwen_gpt_winner_comparison_20261108 import decisions


def test_invalid_never_becomes_favorable_and_no_news_only_stays_in_veto_arm(monkeypatch):
    monkeypatch.setattr('scripts.research.us_gpt_winner_favorable_only.validate_response',
        lambda response,packet:dict(analysis=response))
    packets=[dict(key=str(i),symbol=f'S{i}',signal_date='2025-01-02',context=dict(news=[{}] if i<4 else [])) for i in range(5)]
    records={str(i):dict(validation=dict(valid=i!=2,veto=i==3),
        response=dict(assessment='FAVORABLE' if i<3 else 'UNFAVORABLE',evidence_quality='SUFFICIENT')) for i in range(5)}
    rows=decisions(packets,records)
    assert [r['FAVORABLE_ONLY'] for r in rows]==[True,True,False,False,False]
    assert [r['VETO_INVALID_EXCLUDED'] for r in rows]==[True,True,False,False,True]
