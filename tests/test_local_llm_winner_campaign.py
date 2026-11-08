import json

from service.local_ai.research_veto import Cache
from scripts.research.us_local_llm_winner_campaign import run,cache_counts


def test_incomplete_analyses_never_start_an_economic_replay(tmp_path):
    (tmp_path/'protocol.json').write_text('{}',encoding='utf8')
    (tmp_path/'requests.json').write_text(json.dumps([
        dict(key='good',context=dict(news=[1])),dict(key='bad',context=dict(news=[1])),
        dict(key='pending',context=dict(news=[1]))]),encoding='utf8')
    cache=Cache(tmp_path/'analyses.sqlite3')
    cache.put('good',{},None,dict(valid=True,veto=False))
    cache.put('bad',{},None,dict(valid=False,veto=False))
    cache.close()
    calls=[]
    def fake_runner(root,phase,monitor):
        calls.append(phase)
        (root/'analysis-report.json').write_text(json.dumps(dict(status='ANALYSIS_INCOMPLETE')),encoding='utf8')
        return 0
    result=run(tmp_path,runner=fake_runner)
    assert calls==['analyze']
    assert result['status']=='INCOMPLETE_ANALYSIS_NO_REPLAY'
    assert (result['valid'],result['invalid'],result['pending'])==(1,1,1)
    assert not (tmp_path/'replay').exists()


def test_latest_attempt_is_counted_without_duplicates(tmp_path):
    (tmp_path/'requests.json').write_text(json.dumps([dict(key='k',context=dict(news=[]))]),encoding='utf8')
    cache=Cache(tmp_path/'analyses.sqlite3')
    cache.put('k',{},None,dict(valid=False,veto=False))
    cache.put('k',{},None,dict(valid=True,veto=True))
    cache.close()
    assert cache_counts(tmp_path)==dict(total=1,valid=1,invalid=0,pending=0,no_news=1,vetoes=1)
