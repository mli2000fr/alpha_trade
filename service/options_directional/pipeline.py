"""Prospective PAPER-only Oracle -> options -> risk -> exact execution binding."""
import argparse
from datetime import datetime, timezone
import json
import subprocess
import uuid
from pathlib import Path

from .config import load_options_filter_config
from .store import directory, digest, validate_window, write_new
from .accounts import (BINDING_PROTOCOL, consumer_directory, require_paper_account,
    shared_qualified, shared_latest_matching, validate_risk_binding)


def _flag(command, name, value):
    result, index = [], 0
    while index < len(command):
        item = command[index]
        if item == name:
            if index+1 >= len(command) or command[index+1].startswith('--'):
                raise ValueError(f'Valeur manquante : {name}')
            index += 2
        elif item.startswith(name+'='):
            index += 1
        else:
            result.append(item)
            index += 1
    return [*result, name, str(value)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['predict', 'risk', 'execute'])
    parser.add_argument('--run-id', default='auto')
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--symbol-source', required=True)
    parser.add_argument('--capital-preset-key', default='capital_2001_5000')
    parser.add_argument('--artifacts-dir', default='artifacts/models')
    parser.add_argument('--account', default='default')
    parser.add_argument('--command-json', required=True)
    args = parser.parse_args()
    config = load_options_filter_config()
    if not config.enabled:
        raise ValueError('Filtre options désactivé dans config.yaml')
    command = json.loads(args.command_json)
    if not isinstance(command, list) or len(command) < 4 or any(not isinstance(s, str) for s in command):
        raise ValueError('Commande pipeline invalide')
    expected = {'predict': ['-m', 'modelFactory'], 'risk': ['-m', 'risk_management']}
    if args.phase in expected and command[2:4] != expected[args.phase]:
        raise ValueError('Commande imbriquée invalide')
    if args.phase == 'execute' and (Path(command[2]).name != 'run_execution.py' or command[3] != 'paper'
                                   or '--run-plan-file' in command):
        raise ValueError('Filtre options : exécution PAPER sans plan externe exclusivement')
    from common.us_signal_date import pin_command_date, resolve_us_signal_date
    account_id=require_paper_account(args.account)
    inner_accounts=[command[i+1] for i,item in enumerate(command[:-1]) if item=='--account']
    inner_accounts += [item.split('=',1)[1] for item in command if item.startswith('--account=')]
    if any(value!=account_id for value in inner_accounts):
        raise ValueError('Compte imbriqué différent du compte options demandé')
    if args.phase == 'predict':
        if any(s in command for s in ('--training-start-date', '--training-end-date', '--oracle-shadow')):
            raise ValueError('Filtre options prospectif incompatible avec prédictions historiques/shadow')
        args.trade_date = resolve_us_signal_date(args.trade_date).isoformat()
    validate_window(args.trade_date)
    command = pin_command_date(command, args.phase, args.trade_date)
    context = dict(trade_date=args.trade_date, batch_id=args.batch_id, account_id=account_id,
                   symbol_source=args.symbol_source, capital_preset_key=args.capital_preset_key)
    from database.connection import get_sqlalchemy_engine
    from database.run_business_summaries import emit_run_summary
    engine = get_sqlalchemy_engine()
    if engine.url.database != 'alpha_trade':
        raise ValueError('Filtre options réservé à la base US alpha_trade')
    if args.phase == 'predict':
        from .runner import analyze, OracleCoverageError
        run_id = f'opt-{uuid.uuid4().hex}' if args.run_id == 'auto' else args.run_id
        if directory(run_id).exists():
            raise ValueError('Run options déjà présent ; pas de remplacement implicite')
        subprocess.run(command, check=True)
        try:
            report = analyze(engine, run_id=run_id, batch_id=args.batch_id, trade_date=args.trade_date,
                symbol_source=args.symbol_source, capital_preset_key=args.capital_preset_key,
                artifacts_dir=args.artifacts_dir, config=config, producer_account_id=account_id)
        except OracleCoverageError as exc:
            folder = directory(run_id)
            folder.mkdir(parents=True, exist_ok=False)
            failure = dict(context, run_id=run_id, status='FAILED', phase='ORACLE_COVERAGE',
                cutoff_utc=datetime.now(timezone.utc).isoformat(), diagnostics=exc.diagnostics,
                error=str(exc), selection_published=False)
            write_new(folder/'failure.json', failure)
            emit_run_summary(dict(run_id=run_id, options_filter_run_id=run_id, status='failed',
                requested=exc.diagnostics['requested_count'], received=exc.diagnostics['prediction_count'],
                persisted=0, failed=len(exc.diagnostics['missing_symbols']), trade_date=args.trade_date,
                diagnostics=exc.diagnostics, failure_path=str(folder/'failure.json')))
            raise
        emit_run_summary(dict(run_id=run_id, options_filter_run_id=run_id, status='completed',
            requested=len(report['rows']), received=report['covered'], selected=report['selected'],
            persisted=len(report['rows']), failed=0, trade_date=args.trade_date,
            report_path=str(directory(run_id)/'report.json')))
        return
    report = shared_latest_matching(**context) if args.run_id == 'auto' else shared_qualified(args.run_id, **context)
    run_id = report['run_id']
    folder=consumer_directory(run_id,account_id,create=args.phase=='risk')
    print(f'Filtre options partagé : {run_id} ; compte {account_id} ; séance {args.trade_date} ; cutoff {report["cutoff_utc"]}', flush=True)
    if args.phase == 'risk':
        command = _flag(command, '--run-mode', 'paper')
        command = _flag(command, '--account', account_id)
        command = _flag(command, '--options-filter-run-id', run_id)
        command = _flag(command, '--oracle-batch-id', args.batch_id)
        command = _flag(command, '--oracle-tradable-policy', 'filter_then_top20')
        command = _flag(command, '--oracle-artifacts-dir', args.artifacts_dir)
        command = _flag(command, '--summary-path', str(folder/'risk_summary.json'))
        from .risk_attempts import risk_attempt
        with risk_attempt(folder, report,account_id=account_id) as attempt:
            command = _flag(command, '--options-risk-attempt-id', attempt['attempt_id'])
            subprocess.run(command, check=True)
            summary = json.loads((folder/'risk_summary.json').read_text(encoding='utf-8'))
            if (summary.get('options_filter_run_id') != run_id or not summary.get('run_id')
                    or summary.get('account_id')!=account_id
                    or summary.get('dry_run') or summary.get('run_mode') != 'paper'):
                raise ValueError('Résumé risque options non publié ou incompatible')
            write_new(folder/'risk_binding.json', dict(risk_run_id=summary['run_id'],
                account_id=account_id,binding_protocol=BINDING_PROTOCOL,
                summary_sha256=digest(summary), report_sha256=digest(report)))
    else:
        binding = json.loads((folder/'risk_binding.json').read_text(encoding='utf-8'))
        summary = json.loads((folder/'risk_summary.json').read_text(encoding='utf-8'))
        validate_risk_binding(report,binding,summary,account_id)
        from sqlalchemy import text
        with engine.connect() as conn:
            targets = [dict(r) for r in conn.execute(text('''SELECT symbol,side,shares,trade_date,account_id
                FROM portfolio_targets WHERE run_id=:run'''), dict(run=binding['risk_run_id'])).mappings()]
        if not targets:
            print('Filtre options : aucune cible risque, aucune exécution.', flush=True)
            emit_run_summary(dict(run_id=binding['risk_run_id'], options_filter_run_id=run_id,
                account_id=account_id,status='completed', skipped=True, skip_reason='NO_RISK_TARGETS', trade_date=args.trade_date))
            return
        from service.alpaca.trading_client import AlpacaTradingClient
        from service.llm_directional.pipeline import _validate_targets
        broker = AlpacaTradingClient(broker_mode='paper', account_id=account_id)
        holdings = {p['symbol']: p for p in broker.get_positions()}
        _validate_targets(targets, holdings, {s: 'long' for s in report['selected']}, args.trade_date,account_id=account_id)
        command = _flag(_flag(command, '--run-id', binding['risk_run_id']), '--account', account_id)
        from .execution_attempts import execution_attempt
        with execution_attempt(folder, report, binding) as attempt:
            command = _flag(command, '--options-filter-run-id', run_id)
            command = _flag(command, '--options-execution-attempt-id', attempt['attempt_id'])
            subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
