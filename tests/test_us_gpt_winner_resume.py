import json
from decimal import Decimal

import pytest

from scripts.research import us_gpt_winner_resume as resume
from service.local_ai.research_veto import Cache


def make_packet(key,has_news=True):
    return dict(key=key,symbol='VAC',signal_date='2025-11-21',context=dict(news=[1] if has_news else []),
        request=dict(model='gpt-6-luna',max_output_tokens=16384))


def reply():
    return dict(model='gpt-6-luna',status='completed',service_tier='default',
        usage=dict(input_tokens=100,output_tokens=100),output=[dict(type='message',content=[dict(type='output_text',text='{}')])])


def test_recovery_only_fills_missing_receipt_and_keeps_old_answer_and_error(tmp_path,monkeypatch):
    packets=[make_packet('received'),make_packet('ambiguous'),make_packet('pending')]
    api=tmp_path/'api';api.mkdir()
    for p in packets[:2]:(api/(p['key']+'.request.json')).write_text(json.dumps(p['request']),encoding='utf8')
    old=reply();(api/'received.response.json').write_text(json.dumps(old),encoding='utf8')
    (api/'ambiguous.error.json').write_text('{"error":"ConnectionError"}',encoding='utf8')
    (tmp_path/'protocol.json').write_text('{}',encoding='utf8')
    cache=Cache(tmp_path/'analyses.sqlite3')
    cache.put('received',packets[0]['request'],dict(response=old),dict(valid=True,veto=False));cache.close()
    monkeypatch.setattr(resume.base,'verify',lambda root: (dict(maximum_reserved_usd='1.79'),packets))
    calls=[]
    def transport(request):calls.append(request);return reply()
    folder,result=resume.recover(tmp_path,transport=transport)
    assert len(calls)==1 and result['new_calls']==1
    assert json.loads((api/'received.response.json').read_text())==old
    assert (api/'ambiguous.error.json').exists()
    assert (api/'ambiguous.response.json').exists()
    assert not (api/'pending.request.json').exists()
    assert Decimal(result['authorization']['cumulative_maximum_reserved_usd'])<Decimal('2')


def test_extra_attempt_reservations_are_cumulative_and_block_before_network(tmp_path):
    (tmp_path/'protocol.json').write_text('{}',encoding='utf8')
    old=tmp_path/'resume-attempts/previous';old.mkdir(parents=True)
    (old/'authorization.json').write_text('{"extra_reservation_usd":"0.21"}',encoding='utf8')
    with pytest.raises(ValueError,match='avant appel'):
        resume.authorize(tmp_path,dict(maximum_reserved_usd='1.79'),[make_packet('retry')])


def test_transport_failure_does_not_retry_or_overwrite_original_journal(tmp_path,monkeypatch):
    p=make_packet('ambiguous');api=tmp_path/'api';api.mkdir()
    (api/'ambiguous.request.json').write_text(json.dumps(p['request']),encoding='utf8')
    (tmp_path/'protocol.json').write_text('{}',encoding='utf8')
    monkeypatch.setattr(resume.base,'verify',lambda root: (dict(maximum_reserved_usd='1.79'),[p]))
    calls=[]
    def unavailable(request):calls.append(request);raise TimeoutError('simulated')
    with pytest.raises(TimeoutError):resume.recover(tmp_path,transport=unavailable)
    assert len(calls)==1
    assert not (api/'ambiguous.response.json').exists()
    assert json.loads((api/'ambiguous.request.json').read_text())==p['request']
    assert json.loads((tmp_path/'report.json').read_text())['status']=='RESUME_FAILED_NO_AUTOMATIC_RETRY'
