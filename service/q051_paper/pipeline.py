"""Scheduled Q051 10/11/12 with immutable selection and per-account admissions.

No training, no cloud LLM, no options filter, no global profile mutation. The
existing Winner OMS/watcher owns fills, standing SL5 and the open11 deadline.
"""
import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import uuid

import pandas as pd
from sqlalchemy import MetaData, Table

from common.q051_paper import (ROOT, reference, settings, require_paper,
                               execution_config, validate_frozen)
from common.winner_pyramiding import aware

LOG = logging.getLogger(__name__)
ARTIFACTS = ROOT / 'artifacts/q051_paper'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, default=str, ensure_ascii=False)


def directory(run_id):
    if not re.fullmatch(r'q051-[a-f0-9]{32}', run_id):
        raise ValueError('Q051 : identifiant de sélection exact requis')
    return ARTIFACTS / run_id


def contract(batch, artifacts_dir, day):
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import enabled, load_manifest
    root, protocol, profile, folds = load_contract(artifacts_dir, batch)
    if protocol['horizon'] != 10 or not enabled(protocol):
        raise ValueError('Q051 exige Oracle parcours H10 avec bundle per-symbol LONG')
    manifest, _ = load_manifest(root)
    if not any(r['side'] == 'long' and r['year'] == day.year and pd.Timestamp(r['available']).date() < day
               for r in manifest['models']):
        raise ValueError('Q051 : aucun modèle LONG causal pour cette année')
    return root, protocol


def rank_selection(verified, model_root, universe_size):
    from backtesting.per_symbol_selection import PerSymbolSelection, attach_calibration_auc, select_per_symbol
    policy = reference()['selection']
    config = PerSymbolSelection(oracle_top_n=max(1, math.ceil(universe_size*policy['oracle_fraction'])),
        long_top_n=policy['long_top_n'], allow_short=False,
        min_long_probability=policy['min_long_probability'], min_long_auc=policy['min_long_auc'])
    return select_per_symbol(attach_calibration_auc(verified, model_root), config), config


def predict(engine, *, run_id, batch, day, artifacts_dir, account='default'):
    from modelFactory.oracle_path.predict import predict_oracle_path_history
    from modelFactory.oracle.predictions_store import load_oracle_predictions
    from modelFactory.oracle_path.directional import read_predictions
    folder = directory(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    write(folder/'started.json', dict(profile=reference(), batch_id=batch, trade_date=day, started_at=datetime.now(UTC)))
    root, protocol = contract(batch, artifacts_dir, day)
    from service.q051_paper.coverage import capture as capture_coverage
    _, broker, _ = make_broker(engine, account)
    coverage, assets = capture_coverage(broker._client, protocol['universe'], account=account, day=day)
    write(folder/'alpaca_assets.json', assets)
    write(folder/'coverage.json', coverage)
    predict_oracle_path_history(engine, batch, str(day), str(day), artifacts_dir=artifacts_dir,
                               symbols=protocol['universe'], horizon=10, paper_serving_coverage=coverage)
    cutoff = datetime.now(UTC)
    oracle = load_oracle_predictions(engine, batch_id=batch, start_date=str(day), end_date=str(day),
                                     artifacts_dir=artifacts_dir)
    from modelFactory.oracle_path.predict import prediction_coverage_ratio
    covered = set(oracle.symbol) & set(coverage['eligible'])
    minimum = math.ceil(len(coverage['eligible'])*prediction_coverage_ratio())
    if len(covered) < minimum:
        raise ValueError('Q051 : couverture Oracle insuffisante')
    verified = read_predictions(engine, root, oracle, batch, cutoff=cutoff)
    ranked, policy = rank_selection(verified, root, len(protocol['universe']))
    ranked.to_parquet(folder/'selection.parquet', index=False)
    selected = ranked[ranked.selected].sort_values('rank')
    report = dict(status='COMPLETED', stage='predict', strategy_profile=reference()['profile_id'],
        run_id=run_id, batch_id=batch, trade_date=str(day), cutoff=cutoff.isoformat(),
        profile=reference(), policy=asdict(policy), universe_count=len(protocol['universe']),
        coverage=dict(scope=coverage['scope'], observed=len(covered), denominator=len(coverage['eligible']),
            ratio=len(covered)/len(coverage['eligible']), minimum=minimum, threshold=prediction_coverage_ratio(),
            excluded_count=len(coverage['excluded']), receipt_sha256=digest(folder/'coverage.json'),
            assets_sha256=digest(folder/'alpaca_assets.json')),
        selected=selected.symbol.tolist(), protocol_sha256=digest(root/'protocol.json'),
        directional_manifest_sha256=digest(root/'directional/manifest.json'),
        selection_sha256=digest(folder/'selection.parquet'))
    write(folder/'selection.json', report)
    write(folder/'seal.json', dict(report_sha256=digest(folder/'selection.json')))
    LOG.info('Q051 : TOP%d Oracle → %d LONG (TOP5 puis score>0.50/AUC>=0.50, sans remplissage)',
             policy.oracle_top_n, len(selected))
    return report


def qualified(run_id, *, batch, day, artifacts_dir):
    folder = directory(run_id)
    report = json.loads((folder/'selection.json').read_text(encoding='utf-8'))
    seal = json.loads((folder/'seal.json').read_text())
    root, protocol = contract(batch, artifacts_dir, day)
    validate_frozen(report['profile'])
    if (report['status'] != 'COMPLETED' or report['trade_date'] != str(day) or report['batch_id'] != batch
            or seal['report_sha256'] != digest(folder/'selection.json')
            or report['selection_sha256'] != digest(folder/'selection.parquet')
            or report['protocol_sha256'] != digest(root/'protocol.json')
            or report['directional_manifest_sha256'] != digest(root/'directional/manifest.json')
            or aware(report['cutoff']) > datetime.now(UTC)):
        raise ValueError('Q051 : sélection incomplète, modifiée ou autre modèle/date')
    from service.q051_paper.coverage import validate, fingerprint, timestamp
    coverage = json.loads((folder/'coverage.json').read_text(encoding='utf-8'))
    assets = json.loads((folder/'alpaca_assets.json').read_text(encoding='utf-8'))
    if (report['coverage']['receipt_sha256'] != digest(folder/'coverage.json')
            or report['coverage']['assets_sha256'] != digest(folder/'alpaca_assets.json')
            or coverage['source_payload_sha256'] != fingerprint(assets)):
        raise ValueError('Q051 : preuve de couverture modifiée')
    validate(coverage, protocol['universe'], [day], now=timestamp(coverage['observed_at']))
    return folder, report


def make_broker(engine, account):
    from execution_engine.db_io import ExecutionRepository
    from execution_engine.broker_adapter import BrokerAdapter
    from service.alpaca.trading_client import AlpacaTradingClient
    from common.verified_http import verified_session
    cfg = execution_config(account)
    return ExecutionRepository(engine), BrokerAdapter(AlpacaTradingClient(broker_mode='paper', account_id=account,
        session=verified_session()), cfg), cfg


def risk(engine, folder, selection, account, day):
    from service.q051_paper.risk import capture, complete_context, quantity
    from execution_engine.winner_live_risk import concentration_allowed
    from common.q051_paper import risk_config
    from sqlalchemy import text
    repo, broker, config = make_broker(engine, account)
    account_folder = folder/'accounts'/account
    account_folder.mkdir(parents=True, exist_ok=True)
    path = account_folder/'risk.json'
    if path.exists():
        saved = json.loads(path.read_text())
        seal = account_folder/'risk.seal.json'
        if (saved.get('status') == 'COMPLETED' and saved.get('selection_sha256') == digest(folder/'selection.json')
                and seal.exists() and json.loads(seal.read_text())['risk_sha256'] == digest(path)):
            return saved
        raise ValueError('Q051 : risque précédent incomplet ; réconciliation requise')
    owner = uuid.uuid4().hex
    if not repo.acquire_execution_lock(account_id=account, exec_run_id=owner):
        raise ValueError('Q051 : compte déjà en cours d’exécution')
    try:
        write(account_folder/'risk.claim.json', dict(account_id=account, run_id=owner, started_at=datetime.now(UTC)))
        ranked = pd.read_parquet(folder/'selection.parquet')
        selected = ranked[ranked.selected].sort_values('rank')
        now = datetime.now(UTC)
        context = capture(repo, broker, account, day, now)
        context = complete_context(context, engine, selected.symbol.tolist()) if len(selected) else context
        decisions, targets = [], []
        for row in selected.to_dict('records'):
            symbol = row['symbol']
            price = context['reference_closes'].get(symbol)
            if price is None or not math.isfinite(float(price)) or price <= 0:
                LOG.warning('Q051 %s : clôture J absente, entrée refusée', symbol)
                continue
            asset = broker._client.get_asset(symbol)
            if asset.get('tradable') is not True or asset.get('status') != 'active':
                decision = dict(quantity=0, reason='BROKER_ASSET_NOT_TRADABLE')
            else:
                with engine.connect() as c:
                    fills = c.execute(text('SELECT f.symbol,r.request_id,r.side,r.intent_role,f.filled_qty,'
                        'f.avg_fill_price,f.fill_timestamp FROM execution_broker_fills f '
                        'JOIN execution_order_requests r ON r.request_id=f.request_id '
                        'JOIN execution_runs e ON e.exec_run_id=r.exec_run_id '
                        'WHERE f.account_id=:account AND e.broker_mode=\'paper\' AND f.symbol=:symbol '
                        'AND f.fill_timestamp<=:now ORDER BY f.fill_timestamp,f.fill_id'),
                        dict(account=account, symbol=symbol, now=now)).mappings().all()
                context['concentration_allowed'] = concentration_allowed(fills, risk_config(context['equity']), symbol, day, 'ENTRY')
                decision = quantity(symbol=symbol, price=float(price), proposed=math.floor(context['equity']/price), context=context)
            q = decision['quantity']
            record = dict(run_id=owner, account_id=account, trade_date=day, symbol=symbol,
                decision='APPROVED' if q else 'REJECTED', reason=decision['reason'][:255],
                shares=q, approved_shares=q, proposed_shares=q, entry_price=float(price),
                target_weight=q*price/context['equity'], target_notional=q*price,
                score_used=float(row['long_probability']), score_source='q051_per_symbol_long',
                conviction_score=float(row['long_probability']), predicted_proba=float(row['long_probability']),
                sizing_method='q051_sl5_cov60_vol20', selection_rank=int(row['rank']), decision_rank=int(row['rank']),
                sector=context['sector_map'].get(symbol, 'UNKNOWN'), side='long',
                selector_signal_mode='q051_vol20_regime', selection_explanation='TOP10% Oracle → TOP5 LONG; score>0.50; AUC>=0.50',
                selector_earnings_blackout=False, price_asof_date=day, prediction_asof_date=day,
                stop_price_initial=float(price)*.95, risk_per_share=float(price)*.05,
                risk_budget_dollars=context['equity']*.0125, initial_risk_dollars=q*price*.05,
                take_profit_price=None)
            decisions.append(record)
            if q:
                targets.append(record)
                context['pending_entries'].append(dict(symbol=symbol, side='buy', notional=q*price))
                context['available_buying_power'] -= q*price*1.0025
        # Canonical decisions and targets commit together. A publication failure
        # leaves the claim ambiguous, never permission for another set of buys.
        with engine.begin() as conn:
            for table_name, records in [('risk_decisions', decisions), ('portfolio_targets', targets)]:
                if records:
                    table = Table(table_name, MetaData(), autoload_with=conn)
                    conn.execute(table.insert(), [{k:v for k,v in r.items() if k in table.c} for r in records])
        report = dict(status='COMPLETED', stage='risk', run_id=owner, risk_run_id=owner,
            q051_run_id=selection['run_id'], account_id=account, trade_date=str(day),
            strategy_profile=reference()['profile_id'], selection_sha256=digest(folder/'selection.json'),
            equity=context['equity'], decisions=decisions, targets=len(targets), approved_count=len(targets),
            rejected_count=len(decisions)-len(targets), selected_count=len(selected),
            regime_allowed=context['regime_allowed'], profile_sha256=reference()['sha256'],
            finished_at=datetime.now(UTC).isoformat())
        write(path, report)
        write(account_folder/'risk.seal.json', dict(risk_sha256=digest(path)))
        return report
    finally:
        repo.release_execution_lock(account_id=account, exec_run_id=owner)


def execute(engine, folder, selection, account, day):
    from execution_engine.winner_plans import stage_targets, require_campaign_watcher
    from execution_engine.winner_campaign_store import WinnerCampaignStore
    from execution_engine.winner_standard_entry import submit_standard_plans
    from common.q051_paper import entry_window
    p = folder/'accounts'/account
    risk_path = p/'risk.json'
    result = json.loads(risk_path.read_text())
    if json.loads((p/'risk.seal.json').read_text())['risk_sha256'] != digest(risk_path):
        raise ValueError('Q051 : bilan de risque modifié après publication')
    if (result.get('status') != 'COMPLETED' or result['account_id'] != account
            or result['trade_date'] != str(day) or result['q051_run_id'] != selection['run_id']
            or result['selection_sha256'] != digest(folder/'selection.json')
            or result['profile_sha256'] != reference()['sha256']):
        raise ValueError('Q051 : risque exact du compte/date/sélection requis')
    if not result['targets']:
        return dict(status='COMPLETED', stage='execution', targets=0, submitted=0, reason='NO_RISK_TARGETS')
    if (p/'execution.json').exists():
        saved = json.loads((p/'execution.json').read_text())
        if saved.get('risk_run_id') != result['risk_run_id']:
            raise ValueError('Q051 : exécution antérieure d’un autre risque')
        return saved
    repo, broker, cfg = make_broker(engine, account)
    require_campaign_watcher(repo, cfg)
    owner = uuid.uuid4().hex
    if not repo.acquire_execution_lock(account_id=account, exec_run_id=owner):
        raise ValueError('Q051 : verrou d’exécution du compte actif')
    try:
        write(p/'execution.claim.json', dict(exec_run_id=owner, risk_run_id=result['risk_run_id'], started_at=datetime.now(UTC)))
        targets = repo.load_portfolio_targets(risk_run_id=result['risk_run_id'], trade_date=day, account_id=account)
        if (len(targets) != result['targets'] or {t.symbol for t in targets} !=
                {d['symbol'] for d in result['decisions'] if d['approved_shares'] > 0}):
            raise ValueError('Q051 : cibles SQL différentes du risque publié')
        expected = {r['symbol']:r for r in result['decisions'] if r['approved_shares'] > 0}
        for target in targets:
            record = expected[target.symbol]
            if (target.side not in ('long','buy') or target.target_shares != record['shares']
                    or target.entry_price != record['entry_price']
                    or target.risk_budget_dollars != record['risk_budget_dollars']):
                raise ValueError('Q051 : quantité/prix/budget SQL modifié après le risque')
        repo.insert_execution_run(exec_run_id=owner, risk_run_id=result['risk_run_id'], trade_date=day,
            broker_mode='paper', dry_run=False, total_targets=len(targets), account_id=account,
            execution_profile=cfg.execution_profile, submission_window=cfg.submission_window)
        repo.snapshot_execution_targets(exec_run_id=owner, account_id=account, targets=targets)
        store = WinnerCampaignStore(engine)
        _, plans = stage_targets(store, targets, cfg, owner)
        runtime = submit_standard_plans(store, repo, broker, cfg, plans)
        if runtime.get('requires_reconciliation'):
            repo.update_execution_run_status(owner, 'FAILED')
            raise ValueError('Q051 : soumission ambiguë, campagnes conservées ; aucune relance automatique')
        report = dict(status='COMPLETED', stage='execution', exec_run_id=owner,
            risk_run_id=result['risk_run_id'], account_id=account, trade_date=str(day),
            targets=len(targets), plans=plans, winner_standard_entry=runtime,
            submitted=runtime['winner_buys_submitted'], profile_sha256=reference()['sha256'])
        write(p/'execution.json', report)
        repo.update_execution_run_status(owner, 'COMPLETED')
        return report
    finally:
        repo.release_execution_lock(account_id=account, exec_run_id=owner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['predict','risk','execution'], required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--artifacts-dir', default='artifacts/models')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    require_paper(args.account)
    policy = settings()
    if (not policy['enabled'] or policy['model_batch_id'] != args.batch_id
            or Path(args.artifacts_dir).resolve() != Path(policy['artifacts_dir']).resolve()):
        raise ValueError('Q051 : profil désactivé ou batch différent du paramétrage actif')
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('Q051 exclusivement alpha_trade US')
    day = date.fromisoformat(args.trade_date)
    if args.stage == 'predict':
        report = predict(engine, run_id=args.run_id, batch=args.batch_id, day=day,
                         artifacts_dir=args.artifacts_dir, account=args.account)
    else:
        folder, selected = qualified(args.run_id, batch=args.batch_id, day=day, artifacts_dir=args.artifacts_dir)
        report = risk(engine, folder, selected, args.account, day) if args.stage == 'risk' else execute(engine, folder, selected, args.account, day)
    from database.run_business_summaries import emit_run_summary, persist_run_business_summary
    summary = dict(report, step_key={'predict':'ml_predict','risk':'risk_management','execution':'execution'}[args.stage])
    summary.update(account_id=args.account, trade_date=str(day), run_mode='paper',
                   execution_mode='paper', broker_mode='paper', dry_run=False)
    if args.stage == 'execution':
        summary['run_id'] = report.get('exec_run_id', args.run_id)
    persist_run_business_summary(engine=engine, summary=summary, step_key=summary['step_key'],
        account_id=args.account, trade_date=day, entity_run_id=summary.get('run_id'), status=report['status'])
    emit_run_summary(summary)
    if args.stage in ('risk','execution'):
        from service.pipeline_telegram import notify_risk, notify_execution
        if args.stage == 'risk':
            notify_risk(engine, summary, args.account)
        else:
            notify_execution(engine, summary)


if __name__ == '__main__':
    main()
