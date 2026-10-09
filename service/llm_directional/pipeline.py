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
        run, _ = qualified_selection(engine, args.run_id, date.fromisoformat(args.trade_date),
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
        selected = set(json.loads(run['selected_json']))
        for target in targets:
            if str(target['trade_date']) != args.trade_date or target['account_id'] != 'default':
                raise ValueError('Cible risque hors date/compte')
            side = str(target['side']).lower()
            if side not in ('long', 'buy', 'short', 'sell') or not math.isfinite(float(target['shares'])) or float(target['shares']) < 0:
                raise ValueError('Côté/quantité cible invalide')
            if target['symbol'] in selected and side in ('long', 'buy'):
                continue
            held = holdings.get(target['symbol'])
            held_side = str(held.get('side')) if held else None
            target_side = 'long' if side in ('long', 'buy') else 'short'
            if not held or target_side != held_side or abs(float(target['shares'])) > abs(float(held['qty'])):
                raise ValueError('Cible nouvelle hors sélection LLM; exécution bloquée')
        # A consumed claim is deliberately not reset on transport errors (order state unknown).
        repo.claim_execution(args.run_id)
        subprocess.run([*command, '--run-id', run['risk_run_id'], '--account', 'default'], check=True)


def _check_protection_choice(run, choice):
    from .protections import archived_profile
    if choice is not None and choice != bool(archived_profile(run['config_json'])):
        raise ValueError('Protections différentes de l’analyse GPT figée ; utiliser le même choix ou une nouvelle analyse')


def _check_watcher_ready(engine, run):
    from .protections import archived_profile
    if archived_profile(run['config_json']) is None:
        return
    from execution_engine.db_io import ExecutionRepository
    if not ExecutionRepository(engine).is_watcher_healthy(account_id='default'):
        raise ValueError('Protections GPT : watcher continu du compte default absent ou périmé. '
                         'Pipeline → Watcher protections → Démarrer service local, avant étape 12.')


if __name__ == '__main__':
    main()
