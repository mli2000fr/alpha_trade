"""Durable exact execution attempts; only a child pre-effects failure can retry."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import re
import uuid

from .risk_attempts import risk_lock
from .store import digest, write_new
from .accounts import (consumer_directory,require_paper_account,shared_qualified,validate_risk_binding)

ACTIVE = ContextVar('options_execution_attempt', default=None)


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _attempt_id(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('Identifiant tentative exécution invalide')
    return value


def _failure(folder, attempt_id):
    return folder/f'execution.pre_effect_failure.{_attempt_id(attempt_id)}.json'


def _effects(folder, attempt_id):
    return folder/f'execution.effects_possible.{_attempt_id(attempt_id)}.json'


@contextmanager
def execution_attempt(folder, report, binding):
    account_id=binding.get('account_id','default')
    with risk_lock(folder, lock_name='execution.lock'):
        path = folder/'execution.claim.json'
        if (folder/'execution.result.json').exists():
            raise FileExistsError('Exécution déjà terminée ; aucune seconde exécution automatique')
        if path.exists():
            previous = _read(path)
            attempt_id = previous.get('attempt_id')
            if not attempt_id:
                raise FileExistsError('Ancienne tentative d’exécution à vérifier ; verrou conservé pour éviter un doublon')
            proof_path = _failure(folder, attempt_id)
            if not proof_path.exists() or _effects(folder, attempt_id).exists():
                raise FileExistsError('Exécution déjà tentée, issue ambiguë ou ordres possibles ; vérifier avant reprise')
            proof = _read(proof_path)
            expected = dict(attempt_id=attempt_id, run_id=report['run_id'],
                risk_run_id=binding['risk_run_id'], claim_sha256=digest(previous),
                report_sha256=digest(report), binding_sha256=digest(binding))
            if (any(previous.get(k) != v for k, v in expected.items() if k != 'claim_sha256')
                    or previous.get('account_id','default')!=account_id
                    or proof.get('account_id','default')!=account_id
                    or any(proof.get(k) != v for k, v in expected.items())
                    or proof.get('phase') != 'before_execution_side_effects' or proof.get('retryable') is not True):
                raise ValueError('Preuve de reprise exécution altérée ou incompatible')
            archive = folder/'execution_attempts'/attempt_id
            archive.mkdir(parents=True, exist_ok=False)
            path.rename(archive/'execution.claim.json')
        claim = dict(attempt_id=uuid.uuid4().hex, run_id=report['run_id'],
            account_id=account_id,
            risk_run_id=binding['risk_run_id'], report_sha256=digest(report),
            binding_sha256=digest(binding), started_at=datetime.now(timezone.utc).isoformat())
        write_new(path, claim)
        yield claim
        write_new(folder/'execution.result.json', dict(attempt_id=claim['attempt_id'],
            account_id=account_id,
            run_id=report['run_id'], risk_run_id=binding['risk_run_id'],
            claim_sha256=digest(claim), status='CHILD_COMPLETED',
            finished_at=datetime.now(timezone.utc).isoformat()))


@contextmanager
def execution_child_guard(run_id, attempt_id, *, risk_run_id, mode, account_id, trade_date):
    require_paper_account(account_id)
    folder = consumer_directory(run_id,account_id)
    _attempt_id(attempt_id)
    report=shared_qualified(run_id,trade_date=trade_date,account_id=account_id)
    binding,claim,summary=[_read(folder/name) for name in ('risk_binding.json','execution.claim.json','risk_summary.json')]
    validate_risk_binding(report,binding,summary,account_id)
    if (mode != 'paper' or claim.get('account_id','default')!=account_id or str(trade_date) != report['trade_date']
            or binding['risk_run_id'] != risk_run_id or claim.get('risk_run_id') != risk_run_id
            or claim.get('run_id') != run_id or claim.get('attempt_id') != attempt_id
            or claim.get('report_sha256') != digest(report) or claim.get('binding_sha256') != digest(binding)
            or binding.get('report_sha256') != digest(report)):
        raise ValueError('Contexte de tentative exécution incompatible')
    state = dict(folder=folder, claim=claim, financial_effects_possible=False)
    token = ACTIVE.set(state)
    try:
        yield
    except BaseException as error:
        # A killed child/unknown outcome has no receipt. A failure after this
        # checkpoint cannot authorize another execution, even if no fills appear.
        if not state['financial_effects_possible'] and not _effects(folder, attempt_id).exists():
            write_new(_failure(folder, attempt_id), dict(attempt_id=attempt_id, run_id=run_id,
                account_id=account_id,
                risk_run_id=risk_run_id, claim_sha256=digest(claim), report_sha256=digest(report),
                binding_sha256=digest(binding), phase='before_execution_side_effects', retryable=True,
                error_type=type(error).__name__, failed_at=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        ACTIVE.reset(token)


def mark_execution_effects_possible(*, risk_run_id, mode, account_id):
    """Call BEFORE transition orders, executor, or campaign staging, never after."""
    state = ACTIVE.get()
    if state is None:
        return  # Non-options callers retain their existing execution contract.
    claim = state['claim']
    if mode != 'paper' or account_id != claim.get('account_id','default') or risk_run_id != claim['risk_run_id']:
        raise ValueError('Routage différent de la tentative exécution approuvée')
    state['financial_effects_possible'] = True
    write_new(_effects(state['folder'], claim['attempt_id']), dict(attempt_id=claim['attempt_id'],
        claim_sha256=digest(claim), risk_run_id=risk_run_id,
        marked_at=datetime.now(timezone.utc).isoformat()))
