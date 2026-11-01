"""Explicit, previewed PAPER recovery. No broker order/cancel or data deletion."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

import psutil
from sqlalchemy import text

from service.options_directional.accounts import consumer_directory, require_paper_account, validate_risk_binding
from service.options_directional.risk_attempts import risk_lock
from service.options_directional.store import sealed_report, digest, write_new

RISK_FILES = ('risk.claim.json', 'risk_summary.json', 'risk_binding.json')
EXECUTION_FILES = ('execution.claim.json', 'execution.result.json')


def _require_us(engine):
    if engine.dialect.name=='mysql' and engine.url.database!='alpha_trade':
        raise ValueError('Reprise réservée à la base US alpha_trade')


def _files(folder, phase):
    names = (*RISK_FILES,*EXECUTION_FILES) if phase == 'risk' else EXECUTION_FILES
    return [p for p in [*(folder/name for name in names),*folder.glob('execution.effects_possible.*.json')]
            if p.is_file()]


def list_locked_scopes(engine, accounts, options_run_id=None):
    """Lightweight presence check. Does not certify or alter a lock."""
    _require_us(engine)
    result=[]
    for account in accounts:
        with engine.connect() as conn:
            lease=conn.execute(text('SELECT locked_by_run_id FROM execution_locks WHERE account_id=:scope'),
                               dict(scope=f'watcher:{account}')).mappings().first()
        if lease:
            result.append(dict(kind='watcher',account_id=account,run_id=None,
                label=f'{account} — Watcher protections'))
        if not options_run_id:
            continue
        folder=consumer_directory(options_run_id,account)
        if any((folder/name).is_file() for name in RISK_FILES):
            result.append(dict(kind='risk',account_id=account,run_id=options_run_id,
                label=f'{account} — Réinitialiser 11 (relancer 11 puis 12) — {options_run_id}'))
        if any((folder/name).is_file() for name in EXECUTION_FILES):
            result.append(dict(kind='execute',account_id=account,run_id=options_run_id,
                label=f'{account} — Reprendre 12 (conserver le risque) — {options_run_id}'))
    return result


def _require_no_active_attempt(account, run_id, risk_run_id):
    for process in psutil.process_iter(['cmdline']):
        command=process.info.get('cmdline') or []
        if not any('service.options_directional.pipeline' in arg or Path(arg).name=='run_execution.py'
                   or arg=='risk_management' for arg in command):
            continue
        try:
            candidate=command[command.index('--account')+1] if '--account' in command else 'default'
        except IndexError:
            raise RuntimeError('Commande active non vérifiable ; reprise bloquée')
        if candidate==account and (run_id in command or risk_run_id in command or 'risk_management' in command):
            raise RuntimeError('Étape risque/exécution encore active sur ce compte')


def inspect_unlock(engine, candidate, *, broker_factory=None):
    """Read-only review. Its fingerprint must still match at confirmation."""
    _require_us(engine)
    account=candidate['account_id']
    require_paper_account(account)
    if candidate['kind']=='watcher':
        from execution_engine.watcher_lease import release_dead_local_watcher_lease
        with engine.connect() as conn:
            lease=conn.execute(text('SELECT * FROM execution_locks WHERE account_id=:scope'),dict(scope=f'watcher:{account}')).mappings().first()
            beat=conn.execute(text("SELECT * FROM watcher_heartbeats WHERE account_id=:account AND watcher_name='execution_protection_watcher'"),dict(account=account)).mappings().first()
        if not lease:
            raise ValueError('Ce verrou n’existe plus')
        if not release_dead_local_watcher_lease(engine,account,dry_run=True):
            raise ValueError('Watcher actif, distant ou non vérifiable : verrou conservé')
        return dict(candidate=candidate, fingerprint=digest([dict(lease),dict(beat or {})]),
            message='Ancien watcher local arrêté. Seul son verrou abandonné sera libéré.')
    run_id=candidate['run_id']
    if candidate['kind'] not in ('risk','execute'):
        raise ValueError('Type de reprise inconnu')
    report=sealed_report(run_id)
    folder=consumer_directory(run_id,account)
    files=_files(folder,candidate['kind'])
    if not files:
        raise ValueError('Aucun verrou à libérer')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    risk_claim_path=folder/'risk.claim.json'
    if risk_claim_path.exists():
        risk_claim=json.loads(risk_claim_path.read_text(encoding='utf-8'))
        if (risk_claim.get('run_id')!=run_id or risk_claim.get('account_id','default')!=account
                or risk_claim.get('report_sha256')!=digest(report)):
            raise ValueError('Verrou risque hors compte ou sélection : reprise bloquée')
    risk_id=None
    binding_path=folder/'risk_binding.json'
    if binding_path.exists():
        binding=json.loads(binding_path.read_text(encoding='utf-8'))
        summary=json.loads((folder/'risk_summary.json').read_text(encoding='utf-8'))
        validate_risk_binding(report,binding,summary,account)
        risk_id=binding['risk_run_id']
        exec_path=folder/'execution.claim.json'
        if exec_path.exists():
            execution_claim=json.loads(exec_path.read_text(encoding='utf-8'))
            attempt=execution_claim.get('attempt_id','')
            if (not isinstance(attempt,str) or len(attempt)!=32
                or any(c not in '0123456789abcdef' for c in attempt)
                or execution_claim.get('run_id')!=run_id or execution_claim.get('risk_run_id')!=risk_id
                or execution_claim.get('account_id','default')!=account
                or execution_claim.get('report_sha256')!=digest(report)
                or execution_claim.get('binding_sha256')!=digest(binding)):
                raise ValueError('Verrou d’exécution incompatible avec le risque : reprise bloquée')
            for effect_path in folder.glob('execution.effects_possible.*.json'):
                effect=json.loads(effect_path.read_text(encoding='utf-8'))
                if (effect_path.name!=f'execution.effects_possible.{attempt}.json'
                    or effect.get('attempt_id')!=attempt or effect.get('risk_run_id')!=risk_id
                    or effect.get('claim_sha256')!=digest(execution_claim)):
                    raise ValueError('Trace d’exécution ambiguë : reprise bloquée')
            result_path=folder/'execution.result.json'
            if result_path.exists():
                result=json.loads(result_path.read_text(encoding='utf-8'))
                if (result.get('attempt_id')!=attempt or result.get('risk_run_id')!=risk_id
                    or result.get('run_id')!=run_id or result.get('account_id','default')!=account
                    or result.get('claim_sha256')!=digest(execution_claim)):
                    raise ValueError('Bilan d’exécution incompatible : reprise bloquée')
        elif (folder/'execution.result.json').exists() or list(folder.glob('execution.effects_possible.*.json')):
            raise ValueError('Trace d’exécution sans tentative liée : reprise bloquée')
    else:
        # A failed pre-publication attempt needs its native failure receipt.
        claim=json.loads((folder/'risk.claim.json').read_text(encoding='utf-8'))
        attempt=claim.get('attempt_id','')
        if not isinstance(attempt,str) or len(attempt)!=32 or any(c not in '0123456789abcdef' for c in attempt):
            raise ValueError('Tentative sans preuve native de reprise')
        proof_path=folder/f'risk.prepublication_failure.{attempt}.json'
        if not proof_path.is_file() or (folder/'risk_summary.json').exists() or any((folder/n).exists() for n in EXECUTION_FILES):
            raise ValueError('Issue risque non qualifiée ; aucune reprise autorisée')
        proof=json.loads(proof_path.read_text(encoding='utf-8'))
        if (proof.get('claim_sha256')!=digest(claim) or proof.get('report_sha256')!=digest(report)
            or proof.get('run_id')!=run_id or proof.get('account_id','default')!=account
            or claim.get('account_id','default')!=account or claim.get('run_id')!=run_id
            or proof.get('attempt_id')!=attempt or proof.get('retryable') is not True
            or proof.get('phase') not in ('universe_lookup_before_publication','factor_lookup_before_publication')):
            raise ValueError('Preuve de reprise risque incompatible')
    _require_no_active_attempt(account,run_id,risk_id)
    campaigns=[]
    targets=[]
    if risk_id:
        with engine.connect() as conn:
            params=dict(account=account,risk=risk_id)
            requests=conn.execute(text('SELECT COUNT(*) FROM execution_order_requests WHERE account_id=:account AND risk_run_id=:risk'),params).scalar_one()
            running=conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id=:account AND risk_run_id=:risk AND status='RUNNING'"),params).scalar_one()
            rows=conn.execute(text('SELECT campaign_id,symbol,active_key,state_json FROM execution_winner_campaigns WHERE account_id=:account AND risk_run_id=:risk'),params).mappings().all()
            targets=list(conn.execute(text('SELECT symbol FROM portfolio_targets WHERE account_id=:account AND run_id=:risk'),params).scalars())
        if requests or running:
            raise ValueError('Ordres déjà journalisés ou exécution en cours : reprise bloquée')
        for row in rows:
            state=json.loads(row['state_json'])
            if not row['active_key'] or state.get('status')!='PENDING' or state.get('lots') or state.get('operations'):
                raise ValueError('Campagne déjà engagée ou incertaine : reprise bloquée')
            campaigns.append(dict(campaign_id=row['campaign_id'],symbol=row['symbol']))
        if broker_factory is None:
            from common.verified_http import verified_session
            from service.alpaca.trading_client import AlpacaTradingClient
            broker=AlpacaTradingClient(broker_mode='paper',account_id=account,session=verified_session())
        else:
            broker=broker_factory(account)
        positions=broker.get_positions()
        orders=broker.list_orders(status='open')
        if any(p['symbol'] in targets and float(p['qty'])!=0 for p in positions):
            raise ValueError('Une cible est déjà détenue chez le broker : reprise bloquée')
        if any(o['symbol'] in targets and o['side']=='buy' for o in orders):
            raise ValueError('Ordre d’achat déjà ouvert sur une cible : reprise bloquée')
        started_path=folder/('execution.claim.json' if (folder/'execution.claim.json').exists() else 'risk.claim.json')
        started=json.loads(started_path.read_text(encoding='utf-8')).get('started_at')
        try:
            start=datetime.fromisoformat(str(started).replace('Z','+00:00'))
            if start.tzinfo is None:
                raise ValueError('Date sans fuseau')
        except (TypeError,ValueError) as exc:
            raise ValueError('Heure de tentative non qualifiée ; reprise bloquée') from exc
        if targets:
            history=broker.list_orders(status='all',limit=500,symbols=targets)
            if len(history)>=500:
                raise ValueError('Historique broker tronqué ; reprise bloquée')
            for order in history:
                if order['symbol'] not in targets or order['side']!='buy' or float(order.get('filled_qty') or 0)==0:
                    continue
                try:
                    filled=datetime.fromisoformat(str(order.get('filled_at')).replace('Z','+00:00'))
                    if filled.tzinfo is None:
                        raise ValueError('Date sans fuseau')
                except (TypeError,ValueError) as exc:
                    raise ValueError('Achat exécuté non daté chez le broker : reprise bloquée') from exc
                if filled>=start:
                    raise ValueError('Achat déjà exécuté depuis cette tentative : reprise bloquée')
    stamp=dict(files=hashes,report=digest(report),risk_id=risk_id,campaigns=campaigns,targets=targets)
    return dict(candidate=candidate,fingerprint=digest(stamp),files=hashes,risk_run_id=risk_id,
        pending_campaigns_preserved=len(campaigns),
        message=('Archiver cette tentative pour recalculer le risque puis relancer 12.' if candidate['kind']=='risk'
                 else 'Archiver cette tentative pour relancer uniquement l’étape 12.')+
                 ' Les plans en attente et toutes les protections sont conservés.')


def confirm_unlock(engine, preview, *, broker_factory=None):
    _require_us(engine)
    candidate=preview['candidate']
    if candidate['kind']=='watcher':
        fresh=inspect_unlock(engine,candidate)
        if fresh['fingerprint']!=preview['fingerprint']:
            raise ValueError('État modifié depuis la vérification ; vérifier à nouveau')
        from execution_engine.watcher_lease import release_dead_local_watcher_lease
        if not release_dead_local_watcher_lease(engine,candidate['account_id']):
            raise ValueError('Verrou modifié ou watcher redevenu actif ; aucune libération')
        return 'Verrou du watcher arrêté libéré. Tu peux démarrer le service local.'
    from execution_engine.db_io import ExecutionRepository
    repo=ExecutionRepository(engine=engine)
    account=candidate['account_id']
    folder=consumer_directory(candidate['run_id'],account)
    with ExitStack() as stack:
        stack.enter_context(risk_lock(folder))
        stack.enter_context(risk_lock(folder,lock_name='execution.lock'))
        owner='unlock-'+uuid.uuid4().hex[:25]
        if not repo.acquire_execution_lock(account_id=account,exec_run_id=owner):
            raise ValueError('Compte occupé par une exécution ou le watcher ; réessayer après son cycle')
        try:
            fresh=inspect_unlock(engine,candidate,broker_factory=broker_factory)
            if fresh['fingerprint']!=preview['fingerprint']:
                raise ValueError('État modifié depuis la vérification ; vérifier à nouveau')
            archive=folder/'manual_rearms'/('ihm-'+uuid.uuid4().hex)
            archive.mkdir(parents=True,exist_ok=False)
            write_new(archive/'authorization.json',dict(**fresh,confirmed_at=datetime.now(timezone.utc).isoformat(),
                action='Explicit IHM confirmation',existing_campaigns_preserved=True))
            for path in _files(folder,candidate['kind']):
                if hashlib.sha256(path.read_bytes()).hexdigest()!=fresh['files'][path.name]:
                    raise ValueError('Fichier modifié pendant la reprise ; arrêt')
                path.rename(archive/path.name)
            return fresh['message']+' Archive : '+str(archive)
        finally:
            repo.release_execution_lock(account_id=account,exec_run_id=owner)
