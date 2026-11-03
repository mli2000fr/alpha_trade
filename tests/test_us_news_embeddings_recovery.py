import json
from decimal import Decimal

import pytest

from scripts.research.us_news_embedding_cache import MODEL, sha
from scripts.research.us_news_embeddings_recovery import RecoveryCache


def test_explicit_429_keeps_receipt_allows_recovery_without_resetting_successes(tmp_path):
    c=RecoveryCache(tmp_path/'cache.sqlite')
    c.register('pilot',sha('frozen'))
    req=dict(model=MODEL,input=[[1]])
    call=c.reserve('pilot',req,1)
    c.rejected(call,dict(http_status=429,code='rate_limit_exceeded'))
    assert c.summary('pilot')['rejected_calls']==1
    assert Decimal(c.summary('pilot')['committed_usd'])==0
    assert json.loads((tmp_path/'rejections'/f'{call}.json').read_text())['http_status']==429
    next_call=c.reserve('pilot',req,1)
    assert next_call!=call
    assert c.summary('pilot')['unresolved_calls']==1
    c.close()


def test_unknown_transport_failure_cannot_be_marked_as_rate_rejection(tmp_path):
    c=RecoveryCache(tmp_path/'cache.sqlite');c.register('pilot',sha('frozen'))
    req=dict(model=MODEL,input=[[1]])
    call=c.reserve('pilot',req,1)
    with pytest.raises(ValueError,match='HTTP429'):
        c.rejected(call,dict(http_status=500))
    with pytest.raises(ValueError,match='Ambiguous'):
        c.reserve('pilot',req,1)
    assert Decimal(c.summary('pilot')['committed_usd'])>0
    c.close()


def test_recovery_cannot_exceed_original_cap_or_reregister_protocol(tmp_path):
    c=RecoveryCache(tmp_path/'cache.sqlite');c.register('pilot',sha('frozen'))
    with pytest.raises(ValueError,match='ceiling'):
        c.reserve('pilot',dict(model=MODEL,input=[[1]]),100_000_000)
    with pytest.raises(ValueError,match='changed'):
        c.register('pilot',sha('changed'))
    assert c.summary('pilot')['api_calls']==0
    c.close()
