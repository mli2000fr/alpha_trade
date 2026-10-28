"""No broker, SQL write, or real subprocess: retry requires a narrow receipt."""
import json
import subprocess

import pytest

from service.options_directional import pipeline, store
from service.options_directional.risk_attempts import (
    record_universe_lookup_failure, risk_attempt, risk_lock,
)
from tests.test_options_directional_orchestration import env, RUN


def read_claim(folder):
    return json.loads((folder/'risk.claim.json').read_text(encoding='utf-8'))


def test_lookup_failure_can_be_retried_without_overwriting_history(env, monkeypatch):
    invoke, calls, _, report = env
    original = pipeline.subprocess.run
    attempts = []
    def fail_lookup(command, check):
        folder = store.directory(RUN)
        claim = read_claim(folder)
        attempts.append(claim['attempt_id'])
        assert command[command.index('--options-risk-attempt-id')+1] == claim['attempt_id']
        record_universe_lookup_failure(folder, claim['attempt_id'], report, ValueError('missing universe'))
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(pipeline.subprocess, 'run', fail_lookup)
    with pytest.raises(subprocess.CalledProcessError):
        invoke('risk', ['python','-u','-m','risk_management'])
    folder = store.directory(RUN)
    old_claim = read_claim(folder)
    monkeypatch.setattr(pipeline.subprocess, 'run', original)
    invoke('risk', ['python','-u','-m','risk_management'])
    archived = folder/'risk_attempts'/attempts[0]/'risk.claim.json'
    assert json.loads(archived.read_text(encoding='utf-8')) == old_claim
    assert read_claim(folder)['attempt_id'] != attempts[0]
    assert (folder/'risk_binding.json').exists()
    with pytest.raises(FileExistsError):
        invoke('risk', ['python','-u','-m','risk_management'])
    assert len(calls) == 1


def test_unknown_subprocess_failure_cannot_be_retried(env, monkeypatch):
    invoke, _, _, _ = env
    count = []
    def ambiguous(command, check):
        count.append(command)
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(pipeline.subprocess, 'run', ambiguous)
    with pytest.raises(subprocess.CalledProcessError):
        invoke('risk', ['python','-u','-m','risk_management'])
    with pytest.raises(FileExistsError, match='issue non qualifiée'):
        invoke('risk', ['python','-u','-m','risk_management'])
    assert len(count) == 1


@pytest.mark.parametrize('output', ['risk_summary.json', 'risk_binding.json', 'execution.claim.json'])
def test_even_with_failure_receipt_outputs_block_retry(env, output):
    _, _, _, report = env
    folder = store.directory(RUN)
    with risk_attempt(folder, report) as claim:
        record_universe_lookup_failure(folder, claim['attempt_id'], report, ValueError('missing'))
    store.write_new(folder/output, {'partial':True})
    with pytest.raises(FileExistsError, match='issue ambiguë'):
        with risk_attempt(folder, report):
            pytest.fail('retry despite outputs')


def test_legacy_claim_without_proof_never_auto_unlocked(env):
    _, _, _, report = env
    folder = store.directory(RUN)
    store.write_new(folder/'risk.claim.json', {'started_at':'old'})
    with pytest.raises(FileExistsError, match='vérification manuelle'):
        with risk_attempt(folder, report):
            pytest.fail('legacy claim bypassed')


@pytest.mark.parametrize('change', [dict(claim_sha256='tampered'), dict(report_sha256='tampered'),
                                  dict(run_id='other'), dict(phase='after_publication'), dict(retryable=False)])
def test_tampered_or_wrong_checkpoint_receipt_blocks_retry(env, change):
    _, _, _, report = env
    folder = store.directory(RUN)
    with risk_attempt(folder, report) as claim:
        record_universe_lookup_failure(folder, claim['attempt_id'], report, ValueError('missing'))
    path = folder/f'risk.prepublication_failure.{claim["attempt_id"]}.json'
    receipt = json.loads(path.read_text(encoding='utf-8'))
    path.write_text(json.dumps({**receipt, **change}), encoding='utf-8')
    with pytest.raises(ValueError, match='altérée ou incompatible'):
        with risk_attempt(folder, report):
            pytest.fail('bad receipt accepted')


def test_nonce_mismatch_cannot_authorize_retry(env):
    _, _, _, report = env
    folder = store.directory(RUN)
    with risk_attempt(folder, report):
        with pytest.raises(ValueError, match='incompatible'):
            record_universe_lookup_failure(folder, 'd'*32, report, ValueError('missing'))


def test_parallel_risk_attempt_is_refused(env):
    _, _, _, report = env
    folder = store.directory(RUN)
    with risk_lock(folder):
        with pytest.raises(OSError):
            with risk_attempt(folder, report):
                pytest.fail('parallel risk entered')
    assert not (folder/'risk.claim.json').exists()
