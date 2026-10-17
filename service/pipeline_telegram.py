"""US PAPER pipeline notifications. Read-only business data, best-effort delivery.

These messages describe a completed stage, never authorize an order. The local
outbox freezes each message and remembers accepted chunks; Telegram itself does
not offer exactly-once delivery (a timeout after acceptance remains ambiguous).
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time

from sqlalchemy import text

from service import telegram

LOGGER = logging.getLogger(__name__)
OUTBOX = Path(__file__).resolve().parents[1] / 'artifacts/notifications/pipeline_telegram'


@contextmanager
def _locked(path):
    # OS locks are released on process death; no permanent stale lock file.
    with path.open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _chunks(message):
    # Conservative UTF-16 limit, including supplementary-plane emoji.
    chunks, current, size = [], '', 0
    for char in message:
        units = len(char.encode('utf-16-le')) // 2
        if size + units > 3500:
            chunks.append(current)
            current, size = '', 0
        current += char
        size += units
    if current:
        chunks.append(current)
    return [f'[{i}/{len(chunks)}]\n{chunk}' for i, chunk in enumerate(chunks, 1)]


def _deliver(stage, run_id, account_id, message):
    if not run_id or not account_id:
        raise ValueError('Identifiant exact de run et compte requis')
    if not telegram.is_telegram_configured() or not telegram.get_default_chat_id():
        LOGGER.warning('Telegram étape %s non envoyé : token/chat non configuré', stage)
        return False
    key = hashlib.sha256(json.dumps([stage, run_id, account_id]).encode()).hexdigest()
    directory = OUTBOX / key
    directory.mkdir(parents=True, exist_ok=True)
    with _locked(directory / 'delivery.lock'):
        payload = directory / 'payload.json'
        if not payload.exists():
            content = {'stage': stage, 'run_id': run_id, 'account_id': account_id,
                       'chunks': _chunks(message)}
            temporary = directory / 'payload.tmp'
            temporary.write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
            temporary.replace(payload)
        content = json.loads(payload.read_text(encoding='utf-8'))
        sent_in_call = False
        for i, chunk in enumerate(content['chunks'], 1):
            marker = directory / f'sent-{i}.flag'
            if marker.exists():
                continue
            if sent_in_call:
                time.sleep(1.1)  # Space multipart messages to the same chat.
            if not telegram.send_telegram_message(chunk, parse_mode=None):
                LOGGER.warning('Telegram étape %s non confirmé run=%s partie=%s', stage, run_id, i)
                return False
            marker.write_text('accepted', encoding='ascii')
            sent_in_call = True
    LOGGER.info('Telegram étape %s envoyé run=%s', stage, run_id)
    return True


def _best_effort(callback):
    try:
        return callback()
    except Exception as exc:
        # No raw provider/SQL/HTTP exception: it may contain credentials.
        LOGGER.warning('Notification pipeline indisponible (%s) ; résultat métier inchangé',
                       type(exc).__name__)
        return False


def _us_engine(engine):
    return engine.dialect.name != 'mysql' or engine.url.database == 'alpha_trade'


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _fmt(value, places=6):
    number = _number(value)
    return '?' if number is None else f'{number:.{places}f}'.rstrip('0').rstrip('.')


def _direction(side, role='entry'):
    side, role = str(side or '').lower(), str(role or '').lower()
    if side not in ('buy', 'sell', 'long', 'short'):
        return 'sens non qualifié'
    buy = side in ('buy', 'long')
    if role in ('exit', 'adopted_exit', 'take_profit', 'initial_stop', 'trailing_stop'):
        return 'clôture/réduction SHORT' if buy else 'clôture/réduction LONG'
    if role in ('entry', 'adopted_entry', 'rebalance_buy'):
        return 'LONG' if buy else 'SHORT'
    return f'{side.upper()} — sens de position non qualifié'


BLOCKERS = {
    'insufficient_fresh_sources': 'sources récentes qualifiées insuffisantes',
    'excluded_untraceable_sources': 'sources non traçables exclues',
    'confidence_below_threshold': 'note de confiance sous le seuil',
    'short_not_allowed': 'SHORT non autorisé',
}


def llm_message(run, items):
    config = json.loads(run['config_json'])
    provider = 'DeepSeek' if config.get('provider') == 'deepseek' else 'GPT'
    model = config.get('deepseek_model') if provider == 'DeepSeek' else config.get('model')
    selected = json.loads(run.get('selected_json') or '[]')
    completed = run['status'] == 'COMPLETED'
    lines = [f'10. ML Predict — {provider} — PAPER',
             f"Séance {run['trade_date']} · compte {run['account_id']}",
             f"Analyse {run['run_id']} · modèle {model}",
             f"État : {run['status']}"]
    by_symbol = {row['symbol']: row for row in items}
    if completed and selected:
        lines.append(f'Titres retenus : {len(selected)}')
        for symbol in selected:
            parsed = json.loads(by_symbol[symbol]['assessment_json'])
            lines.append(f"• {symbol} — {parsed['decision']} — note de confiance {_fmt(parsed['confidence'], 3)}")
        lines.append('Note déclarée par le LLM, pas une probabilité calibrée. Validation risque encore requise.')
    else:
        lines.append('Aucun titre publié.')
        if not completed:
            lines.append('Échec technique ou analyse interrompue : sélection bloquée, pas une abstention directionnelle.')
        if not items:
            lines.append('Aucune évaluation archivée disponible.')
        for row in items:
            parsed = json.loads(row['assessment_json']) if row.get('assessment_json') else None
            if not parsed or row.get('status') != 'VALID':
                reason = 'réponse invalide / erreur technique'
            else:
                reasons = [BLOCKERS.get(code, str(code)) for code in parsed.get('selection_blockers', [])]
                if parsed.get('decision') == 'ABSTAIN':
                    reasons.insert(0, 'ABSTAIN : le LLM ne retient pas de direction')
                reason = '; '.join(reasons) or 'éligible mais non publié (limite de sélection ou échec global)'
            lines.append(f"• {row['symbol']} : {reason}")
            if parsed and row.get('status') == 'VALID' and parsed.get('decision') == 'ABSTAIN':
                for field, label in [('bull_case', 'Argument haussier'), ('bear_case', 'Argument baissier')]:
                    argument = ' '.join(str(parsed.get(field) or '').split())
                    if argument:
                        lines.append(f'  {label} déclaré par le LLM : {argument[:220]}')
        if config.get('max_selected') == 0:
            lines.append('Nombre maximal de titres configuré à zéro.')
    return '\n'.join(lines)


def notify_llm(engine, run_id, *, attempted_at=None, trade_date=None, provider_label=None):
    def send():
        if not _us_engine(engine):
            return False
        from service.llm_directional.repository import Repository
        try:
            run, items = Repository(engine).get(run_id)
            started = run.get('started_at')
            # MySQL DATETIME in this archive has second precision, not microseconds.
            if attempted_at is not None and (started is None or
                    started.replace(microsecond=0) < attempted_at.replace(microsecond=0)):
                raise ValueError('Ancienne analyse : ne pas annoncer sa sélection comme nouvelle')
        except Exception:
            if attempted_at is None:
                raise
            return _deliver('10', run_id, 'default',
                f'10. ML Predict — {provider_label or "LLM"} — PAPER\n'
                f'Séance {trade_date} · analyse {run_id}\n'
                'Aucune nouvelle sélection confirmée pour cette tentative : '
                'échec avant archivage ou résultat archivé inaccessible. '
                'Ce n’est pas une abstention directionnelle ; consulter les logs.')
        return _deliver('10', run_id, run['account_id'], llm_message(run, items))
    return _best_effort(send)


def risk_message(summary, rows, account_id):
    lines = ['11. Risk Management — PAPER',
             f"Séance {summary['trade_date']} · compte {account_id}",
             f"Run risque {summary['run_id']}", f'Titres retenus : {len(rows)}']
    for row in rows:
        lines.append(f"• {row['symbol']} — {_direction(row['side'])} — quantité cible {_fmt(row['shares'])}")
    if not rows:
        lines.append('Aucune cible publiée : aucun titre validé pour cette exécution.')
    reasons = summary.get('rejection_reason_code_counts') or summary.get('rejection_reason_counts') or {}
    if reasons:
        lines.append('Rejets : ' + '; '.join(f'{key} : {count}' for key, count in reasons.items()))
    lines.append('Portefeuille cible, pas des ordres ni des exécutions confirmées.')
    return '\n'.join(lines)


def notify_risk(engine, summary, account_id):
    def send():
        if summary.get('dry_run') or summary.get('run_mode') != 'paper' or not _us_engine(engine):
            return False
        if not summary.get('run_id') or not account_id:
            raise ValueError('Run/compte risque absent')
        with engine.connect() as conn:
            rows = conn.execute(text('''SELECT symbol, side, shares FROM portfolio_targets
                WHERE run_id=:run AND account_id=:account AND trade_date=:day AND shares>0
                ORDER BY symbol'''), {'run': summary['run_id'], 'account': account_id,
                                     'day': summary['trade_date']}).mappings().all()
        return _deliver('11', summary['run_id'], account_id, risk_message(summary, rows, account_id))
    return _best_effort(send)


def execution_message(summary, rows):
    lines = ['12. Execution — PAPER',
             f"Séance {summary.get('trade_date') or '?'} · compte {summary['account_id']}",
             f"Run exécution {summary['run_id']} · risque {summary.get('risk_run_id')}",
             f"État : {summary.get('status', '?')} · ordres soumis : {summary.get('submitted_orders', 0)}"
             f" · échecs : {summary.get('failed_orders', 0)}"]
    total, filled = 0., 0
    for row in rows:
        label = f"• {row['symbol']} — {_direction(row['side'], row['intent_role'])}"
        qty, price = _number(row.get('filled_qty')), _number(row.get('avg_fill_price'))
        state = row.get('broker_status') or row.get('request_status') or 'inconnu'
        if qty is not None and qty > 0:
            filled += 1
            if price is not None and price > 0:
                amount = qty * price
                total += amount
                lines.append(f'{label} — exécuté {_fmt(qty)} à {_fmt(price)} USD — montant {amount:.2f} USD — état {state}')
            else:
                lines.append(f'{label} — quantité exécutée {_fmt(qty)}, prix non qualifié ; montant indisponible — état {state}')
        else:
            submission = 'soumis' if row.get('broker_order_id') else 'non soumis'
            lines.append(f"{label} — {submission}, état {state} — quantité demandée {_fmt(row['target_qty'])} ; aucune exécution confirmée")
    if not rows:
        lines.append('Aucun détail OMS disponible pour ce run ; ne pas en déduire une exécution.')
    elif not filled:
        lines.append('Aucune exécution confirmée à la fin de l’étape. Prix et montant exécutés encore indisponibles.')
    lines.append(f'Total brut des exécutions à prix qualifié : {total:.2f} USD (hors frais, pas un PnL).')
    lines.append('Photographie de fin d’étape ; les ordres en attente peuvent être exécutés ultérieurement.')
    return '\n'.join(lines)


def notify_execution(engine, summary):
    def send():
        if (summary.get('dry_run') or summary.get('execution_mode') != 'paper'
                or summary.get('broker_mode') != 'paper' or not _us_engine(engine)):
            return False
        run_id, account = summary.get('run_id'), summary.get('account_id')
        if not run_id or not account:
            raise ValueError('Run/compte exécution absent')
        with engine.connect() as conn:
            rows = conn.execute(text('''SELECT req.request_id, req.symbol, req.side,
                req.intent_role, req.target_qty, req.status AS request_status,
                bo.broker_order_id, bo.normalized_status AS broker_status,
                bo.filled_qty, bo.avg_fill_price
                FROM execution_order_requests req
                LEFT JOIN execution_broker_orders bo ON bo.request_id=req.request_id
                    AND bo.exec_run_id=req.exec_run_id AND bo.account_id=req.account_id
                WHERE req.exec_run_id=:run AND req.account_id=:account
                ORDER BY req.created_at, req.request_id, bo.broker_order_id'''),
                {'run': run_id, 'account': account}).mappings().all()
        return _deliver('12', run_id, account, execution_message(summary, rows))
    return _best_effort(send)


def notify_execution_skipped(run_id, trade_date, reason):
    return _best_effort(lambda: _deliver('12-skipped', run_id, 'default',
        f'12. Execution — PAPER\nSéance {trade_date} · compte default\nAnalyse {run_id}\n'
        f'Aucun ordre envoyé : {reason}'))
