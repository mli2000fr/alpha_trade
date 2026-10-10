"""Explicit-ID orchestration; no latest-target lookup and no LIVE route."""
import argparse
from dataclasses import replace
import json
import subprocess
import sys
import uuid
import math
from sqlalchemy import text
from pathlib import Path
from .config import load_filter_config
from .repository import Repository
from .runner import analyze, qualified_selection, assert_paper_account


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['predict', 'risk', 'execute'], required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--batch-id')
    parser.add_argument('--symbol-source', default='tradable-universe')
    parser.add_argument('--capital-preset-key', default='capital_2001_5000')
    parser.add_argument('--command-json', required=True)
    parser.add_argument('--specific-protections', action=argparse.BooleanOptionalAction, default=None)
    args = parser.parse_args()
    if args.run_id == 'auto':
        if args.phase != 'predict':
            raise ValueError('Indiquer le run_id exact de l’analyse LLM pour risque/exécution')
        args.run_id = f'llm-{uuid.uuid4().hex}'
    if not all(c.isalnum() or c in '-_' for c in args.run_id) or len(args.run_id) > 80:
        raise ValueError('Identifiant run invalide')
    command = json.loads(args.command_json)
    if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
        raise ValueError('Commande invalide')
    if args.phase == 'execute' and (len(command) < 4 or Path(command[2]).name != 'run_execution.py' or command[3] != 'paper'):
        raise ValueError('Le filtre LLM autorise exclusivement run_execution.py paper')
    if args.phase == 'risk' and (len(command) < 4 or command[2:4] != ['-m', 'risk_management']):
        raise ValueError('Commande risque invalide')
    if args.phase == 'predict' and (len(command) < 4 or command[2:4] != ['-m', 'modelFactory']):
        raise ValueError('Commande prédiction invalide')
    assert_paper_account()
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    repo = Repository(engine)
    if args.phase == 'predict':
        if not args.batch_id:
            raise ValueError('Batch Oracle explicite requis')
        if '--training-start-date' in command or '--oracle-shadow' in command:
            raise ValueError('Filtre Web incompatible avec historique ou Oracle shadow')
        subprocess.run(command, check=True)
        config = replace(load_filter_config(), enabled=True)  # explicit IHM opt-in
        if config.protections is not None and args.specific_protections is not None:
            config = replace(config, protections=replace(config.protections, enabled=args.specific_protections))
        elif args.specific_protections:
            raise ValueError('Configuration des protections GPT absente')
        from database.run_business_summaries import emit_run_summary
        emit_run_summary(analyze(engine=engine, batch_id=args.batch_id, trade_date=args.trade_date,
            symbol_source=args.symbol_source, capital_preset_key=args.capital_preset_key,
            run_id=args.run_id, config=config))
    elif args.phase == 'risk':
        from datetime import date
        run, _ = qualified_selection(engine, args.run_id, date.fromisoformat(args.trade_date), 'default')
        _check_protection_choice(run, args.specific_protections)
        summary_path = Path('artifacts/llm_directional') / args.run_id / 'risk_summary.json'
        # Reusing an old summary would bind the wrong portfolio after a failed process.
        if summary_path.exists():
            raise ValueError('Résumé risque déjà présent; vérifier avant reprise')
        repo.claim_risk(args.run_id)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([*command, '--run-mode', 'paper', '--account', 'default',
            '--llm-filter-run-id', args.run_id, '--summary-path', str(summary_path)], check=True)
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        if not summary.get('run_id'):
            raise ValueError('Identifiant risque absent du résumé')
        if summary.get('dry_run') or summary.get('run_mode') != 'paper':
            raise ValueError('Risque non publié en PAPER; exécution interdite')
        repo.bind_risk(args.run_id, summary['run_id'])
        print(f'LLM {args.run_id} → risque {summary["run_id"]}', flush=True)
    else:
        from datetime import timedelta, date
        run, selected_items = qualified_selection(engine, args.run_id, date.fromisoformat(args.trade_date),
                                      'default', allow_consumed=True)
        _check_protection_choice(run, args.specific_protections)
        from .repository import utcnow
        config = load_filter_config()
        if not run['completed_at'] or not run['completed_at'] <= utcnow() <= run['completed_at'] + timedelta(hours=config.max_run_age_hours):
            raise ValueError('Analyse LLM expirée; exécution interdite')
        if str(run['trade_date']) != args.trade_date or run['account_id'] != 'default':
            raise ValueError('Date/compte du run incompatible')
        if not run['risk_run_id'] or run['status'] != 'COMPLETED':
            raise ValueError('Risque exact non lié; aucun fallback latest')
        if not json.loads(run['selected_json']):
            print('Abstention LLM : aucune nouvelle exécution.', flush=True)
            return
        with engine.connect() as conn:
            targets = conn.execute(text('''SELECT symbol, side, shares, trade_date, account_id
                FROM portfolio_targets WHERE run_id=:run'''), {'run': run['risk_run_id']}).mappings().all()
        if not targets:
            print('Risque : aucune cible publiée, aucune exécution.', flush=True)
            return
        _check_watcher_ready(engine, run)
        from service.alpaca.trading_client import AlpacaTradingClient
        broker = AlpacaTradingClient(broker_mode='paper', account_id='default')
        holdings = {p['symbol']: p for p in broker.get_positions()}
        selected = {i['symbol']: json.loads(i['assessment_json'])['decision'].lower() for i in selected_items}
        shorts = _validate_targets(targets, holdings, selected, args.trade_date)
        if shorts:
            from .risk_adapter import validate_short_broker
            validate_short_broker(broker, shorts)
        # A consumed claim is deliberately not reset on transport errors (order state unknown).
        repo.claim_execution(args.run_id)
        subprocess.run([*command, '--run-id', run['risk_run_id'], '--account', 'default'], check=True)


def _validate_targets(targets, holdings, selected, trade_date):
    """New exposure must match the archived direction. Other targets only reduce.

    Never convert an opposite held position into a new position in one order.
    """
    shorts = []
    seen = set()
    for target in targets:
        if target['symbol'] in seen:
            raise ValueError('Cibles GPT dupliquées ; exécution bloquée')
        seen.add(target['symbol'])
        if str(target['trade_date']) != str(trade_date) or target['account_id'] != 'default':
            raise ValueError('Cible risque hors date/compte')
        side, qty = str(target['side']).lower(), float(target['shares'])
        if side not in ('long', 'buy', 'short', 'sell') or not math.isfinite(qty) or qty < 0:
            raise ValueError('Côté/quantité cible invalide')
        direction = 'long' if side in ('long', 'buy') else 'short'
        held = holdings.get(target['symbol'])
        held_qty = abs(float(held['qty'])) if held else 0.
        if held and (not math.isfinite(held_qty) or held_qty <= 0
                     or str(held.get('side')) not in ('long', 'short')):
            raise ValueError('Position broker non qualifiée ; exécution bloquée')
        if selected.get(target['symbol']) == direction:
            if direction == 'short' and not qty.is_integer():
                raise ValueError('SHORT GPT : quantité entière requise')
            if held and str(held.get('side')) != direction:
                raise ValueError('Position opposée existante : retournement GPT interdit')
            if direction == 'short' and qty > held_qty:
                shorts.append(target['symbol'])
            continue
        if not held or direction != str(held.get('side')) or qty > held_qty:
            raise ValueError('Cible nouvelle hors sélection/direction LLM; exécution bloquée')
    return shorts


def _check_protection_choice(run, choice):
    from .protections import archived_profile
    if choice is not None and choice != bool(archived_profile(run['config_json'])):
        raise ValueError('Protections différentes de l’analyse GPT figée ; utiliser le même choix ou une nouvelle analyse')


def _check_watcher_ready(engine, run):
    from .protections import archived_profile
    short_enabled = bool(json.loads(run['config_json']).get('allow_short', False))
    if archived_profile(run['config_json']) is None and not short_enabled:
        return
    from execution_engine.db_io import ExecutionRepository
    repo = ExecutionRepository(engine)
    if not repo.is_watcher_healthy(account_id='default'):
        raise ValueError('Protections GPT : watcher continu du compte default absent ou périmé. '
                         'Pipeline → Watcher protections → Démarrer service local, avant étape 12.')
    if short_enabled:
        _check_short_watcher_code(repo)


def _check_short_watcher_code(repo):
    """Do not trust a healthy heartbeat from a process running pre-SHORT code."""
    from service.forward_pit.watcher_startup import healthy_service, PROJECT_ROOT
    if not healthy_service(repo, 'default'):
        raise ValueError('Watcher local PAPER absent ; SHORT GPT bloqué')
    import psutil
    with repo.engine.connect() as conn:
        pid = conn.execute(text("""SELECT pid FROM watcher_heartbeats
            WHERE account_id='default' AND watcher_name='execution_protection_watcher'
            ORDER BY last_heartbeat_at DESC LIMIT 1""")).scalar_one()
    started = psutil.Process(int(pid)).create_time()
    modules = ('execution_engine/protection_watcher.py', 'execution_engine/order_intents.py',
               'execution_engine/db_io.py', 'execution_engine/models.py',
               'execution_engine/children_submission.py', 'service/llm_directional/protections.py')
    if any((PROJECT_ROOT / module).stat().st_mtime > started for module in modules):
        raise ValueError('Watcher démarré avant la mise à jour SHORT : arrêter puis redémarrer '
                         'le service local avant étape 12. Aucun ordre envoyé.')


if __name__ == '__main__':
    main()
