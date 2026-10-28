from copy import deepcopy

import pytest

from test_winner_runtime import setup,tick

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def held():
    cfg,store,repo,broker=setup()
    tick(cfg,store,repo,broker)
    return store


def amend(store,row,**kw):
    return store.disable_trailing(row['state']['campaign_id'],row['version'],account_id='default',
        authorization='Human request: disable trailing only',protection_proof_sha256='a'*64,**kw)


def test_audited_disable_changes_only_trailing_and_preserves_tightened_stops():
    store=held();row=store.rows()[0]
    row['state']['lots'][0]['stop']=100.5  # A previously tightened stop must not loosen.
    row['version']=store.save(row['state'],row['version'])
    before=deepcopy(row['state'])
    changed=amend(store,row)
    assert changed['changed'] and changed['version']==row['version']+1
    after=changed['state']; comparable=deepcopy(after)
    audit=comparable.pop('policy_amendments')
    comparable['policy']['trailing_stop_pct']=before['policy']['trailing_stop_pct']
    assert comparable==before
    assert after['lots'][0]['stop']==100.5 and audit[0]['kind']=='DISABLE_TRAILING'
    assert audit[0]['protection_proof_sha256']=='a'*64
    same=store.disable_trailing(after['campaign_id'],changed['version'],account_id='default',
        authorization='Human request',protection_proof_sha256='b'*64)
    assert not same['changed'] and same['version']==changed['version']


def test_ordinary_runtime_save_still_cannot_mutate_frozen_policy_or_audit():
    store=held();row=store.rows()[0]
    changed=deepcopy(row['state']);changed['policy']['trailing_stop_pct']=None
    with pytest.raises(ValueError,match='Frozen campaign field'):store.save(changed,row['version'])
    result=amend(store,row)
    changed=deepcopy(result['state']);changed['policy_amendments']=[]
    with pytest.raises(ValueError,match='Frozen campaign field'):store.save(changed,result['version'])


def test_stale_version_wrong_account_or_unresolved_order_refuses_amendment():
    store=held();row=store.rows()[0]
    with pytest.raises(RuntimeError,match='changed'):amend(store,dict(row,version=row['version']-1))
    with pytest.raises(ValueError,match='exact account'):
        store.disable_trailing(row['state']['campaign_id'],row['version'],account_id='test1',
            authorization='Human request',protection_proof_sha256='a'*64)
    row['state']['operations'].append(dict(action='TIGHTEN',status='UNKNOWN'))
    row['version']=store.save(row['state'],row['version'])
    with pytest.raises(ValueError,match='reconciled'):amend(store,row)


def test_amendment_requires_authorization_and_real_evidence_digest():
    store=held();row=store.rows()[0]
    with pytest.raises(ValueError,match='authorization'):
        store.disable_trailing(row['state']['campaign_id'],row['version'],account_id='default',
            authorization='',protection_proof_sha256='a'*64)
    with pytest.raises(ValueError,match='evidence'):
        store.disable_trailing(row['state']['campaign_id'],row['version'],account_id='default',
            authorization='Human request',protection_proof_sha256='not-a-hash')
