"""Inventory and reset explicitly authorized US ML artefacts, preserving source data.

The default is a read-only database inventory. Each destructive operation must
use a frozen plan, an explicit table scope and validated workspace paths.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


WORKSPACE = Path(__file__).resolve().parents[2]
SCHEMA = 'alpha_trade'
OUTPUT = WORKSPACE / 'artifacts/operations/us_models_reset/20261013-v1'
MODEL_ROOTS = ('models', 'models_s7_bl', 'models_s7_dc', 'models_s7_dv',
               'models_screening_ps_h20', 'models_screening_ps_h20_expert',
               'psv2_f1', 'psv2_f2', 'psv2_f3a', 'psv2_f3b')
TABLES = ('model_predictions', 'model_metrics', 'model_metrics_full', 'model_governance',
          'model_directional_oos_metrics', 'model_batch_diagnostics', 'global_rank_history',
          'global_oracle_labels', 'oracle_extreme_predictions', 'oracle_atr_market_regime_daily',
          'champion_history', 'ml_drift_runs', 'model_serving_batch', 'model_training_run',
          'model_training_batch', 'model_registry')
US_RESEARCH_PREFIXES = ('us_', 'oracle_', 'pmath', 'meta_oracle', 'directional_alpha_',
                        'directional_complementarity', 'fundamental_alpha_book',
                        'fundamental_value_confirmation')
DATA_NAMES = {'features.parquet', 'labels.parquet', 'scores.parquet', 'oof.parquet',
              'oof_predictions.parquet', 'entry-training.parquet', 'exit-training.parquet',
              'entries.parquet', 'states.parquet', 'filter-decisions.parquet',
              'profile-decisions.parquet', 'observed-features.parquet'}
MODEL_EXTENSIONS = {'.pt', '.pth', '.ckpt', '.joblib', '.cbm', '.ubj', '.pkl'}


def safe_target(path):
    original = Path(path)
    if original.is_symlink():
        raise ValueError(f'Symlink cannot be a reset target: {original}')
    resolved = original.resolve()
    artifacts = (WORKSPACE / 'artifacts').resolve()
    relative = resolved.relative_to(artifacts)
    if not relative.parts or relative.parts[0] in {'cn', 'fr', 'operations', 'backups'}:
        raise ValueError(f'Unsafe or protected reset target: {resolved}')
    if any(p.lower().startswith(('cn_', 'fr_')) for p in relative.parts):
        raise ValueError(f'Non-US research target: {resolved}')
    return resolved


def source_digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def model_file(path):
    if path.suffix.lower() in MODEL_EXTENSIONS:
        return True
    if path.suffix.lower() == '.txt':
        with path.open('rb') as stream:
            return stream.read(16).startswith((b'tree\n', b'tree\r\n'))
    return False


def filesystem_targets(report):
    targets = {safe_target(row['path']) for row in report['model_directories']}
    for name in MODEL_ROOTS:
        root = WORKSPACE / 'artifacts' / name
        if root.is_dir():
            targets.update(safe_target(path) for path in root.iterdir()
                           if path.is_dir() and path.name.startswith('model-factory-'))
    champion = WORKSPACE / 'artifacts/models/oracle'
    if champion.is_dir():
        targets.add(safe_target(champion))
    research = WORKSPACE / 'artifacts/research'
    for root in research.iterdir():
        if not root.is_dir() or not root.name.startswith(US_RESEARCH_PREFIXES):
            continue
        for path in root.rglob('*'):
            # A generic research feature/label cache is not necessarily a
            # model-owned training dataset. Only identifiable fitted weights
            # are selected here. Explicit challenger fit-data is handled below.
            if path.is_file() and model_file(path):
                targets.add(safe_target(path))
    challenger = research/'us_oracle_challengers'
    if challenger.is_dir():
        for campaign in challenger.iterdir():
            contract = campaign/'challenger-protocol.json'
            if not campaign.is_dir() or not contract.is_file():
                continue
            metadata = json.loads(contract.read_text(encoding='utf-8'))
            if metadata.get('original_batch') != 'model-factory-20261012183840-6d6569':
                continue
            fit = campaign/'fit-data'
            if fit.is_dir():
                targets.add(safe_target(fit))
    # Parent model directories already contain their per-symbol files.
    ordered = sorted(targets, key=lambda path: (len(path.parts), str(path)))
    selected = []
    for path in ordered:
        if not any(path.is_relative_to(parent) for parent in selected if parent.is_dir()):
            selected.append(path)
    return selected


def amend_for_direct_deletion():
    """Narrow the prior rejected file scope before any destructive step.

    This function only reads the database and rewrites the operation plan.
    It does not delete a file, delete a SQL row or create a model archive.
    """
    if (OUTPUT/'database-progress.json').exists() or (OUTPUT/'filesystem-progress.json').exists():
        raise ValueError('Cannot amend a reset after execution started')
    plan_path = OUTPUT/'plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    inventory_report = json.loads((OUTPUT/'inventory.json').read_text(encoding='utf-8'))
    engine = get_sqlalchemy_engine(db_name=SCHEMA)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != SCHEMA:
                raise ValueError('Wrong database')
            present = {row['table_name'] for row in inventory_report['tables']}
            for name in ('execution_broker_orders', 'execution_broker_fills', 'execution_events',
                         'execution_order_requests', 'execution_position_lots', 'execution_positions',
                         'broker_positions_snapshots'):
                if name in present:
                    plan['protected_table_counts'][name] = int(conn.execute(text(
                        f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
            # Verify incoming links for ALL target tables, including Oracle
            # tables not covered by the first model_* inventory query.
            fks = conn.execute(text('''
                SELECT TABLE_SCHEMA,TABLE_NAME,REFERENCED_TABLE_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_SCHEMA=:schema
            '''), {'schema': SCHEMA}).mappings()
            for row in fks:
                if row['REFERENCED_TABLE_NAME'] in TABLES and (
                        row['TABLE_SCHEMA'] != SCHEMA or row['TABLE_NAME'] not in TABLES):
                    raise ValueError(f'Protected external dependency: {dict(row)}')
    finally:
        engine.dispose()
    refined = filesystem_targets(inventory_report)
    plan.update(filesystem_action='DELETE', recovery_files_root=None,
                superseded_plan_sha256=source_digest(plan_path),
                file_deletion_authorization='User explicitly requested direct deletion without creating an archive',
                scope_refinement='Generic research datasets are preserved. Primary US model directories, identifiable fitted weights and explicitly owned challenger fit-data only.',
                filesystem=[dict(source=str(path)) for path in refined])
    write_json(plan_path, plan)
    print(json.dumps(dict(status=plan['status'], action='DELETE', file_targets=len(plan['filesystem']),
                         protected_table_counts=plan['protected_table_counts']), ensure_ascii=False))
    return plan


def prepare():
    path = OUTPUT / 'plan.json'
    if path.exists():
        raise ValueError('Frozen reset plan already exists')
    inventory_path = OUTPUT / 'inventory.json'
    report = json.loads(inventory_path.read_text(encoding='utf-8'))
    table_columns = {}
    for row in report['columns']:
        table_columns.setdefault(row['table_name'], set()).add(row['column_name'])
    existing = {row['table_name'] for row in report['tables']}
    targets = [name for name in TABLES if name in existing]
    for fk in report['foreign_keys']:
        if fk['parent_table'] in targets and (fk['child_schema'] != SCHEMA or fk['child_table'] not in targets):
            raise ValueError(f'Protected table references target: {fk}')
    engine = get_sqlalchemy_engine(db_name=SCHEMA)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != SCHEMA:
                raise ValueError('Wrong database')
            tables = []
            for name in targets:
                if 'market_code' in table_columns.get(name, set()):
                    other = conn.execute(text(f'''SELECT COUNT(*) FROM alpha_trade.`{name}`
                        WHERE market_code IS NOT NULL AND market_code<>:market'''), {'market': 'US_EQ'}).scalar()
                    if other:
                        raise ValueError(f'{name} contains {other} non-US rows; no whole-table purge')
                has_instrument = conn.execute(text('''SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=:schema AND TABLE_NAME=:table AND COLUMN_NAME='instrument_id'
                '''), {'schema': SCHEMA, 'table': name}).scalar()
                if has_instrument:
                    other = conn.execute(text(f'''SELECT COUNT(*) FROM alpha_trade.`{name}` AS t
                        JOIN alpha_trade.instruments AS i ON i.instrument_id=t.instrument_id
                        WHERE i.market_code<>:market'''), {'market': 'US_EQ'}).scalar()
                    if other:
                        raise ValueError(f'{name} has non-US instruments; no whole-table purge')
                count = int(conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
                incoming = [fk for fk in report['foreign_keys'] if fk['parent_table'] == name]
                method = 'TRUNCATE' if name in {'global_oracle_labels', 'oracle_extreme_predictions', 'global_rank_history'} and not incoming else 'DELETE'
                tables.append(dict(table=name, rows_before=count, method=method))
            for name in ('model_training_batch', 'model_training_run'):
                active = conn.execute(text(f'''SELECT COUNT(*) FROM alpha_trade.`{name}`
                    WHERE LOWER(status) IN ('running','starting','training','pending')''')).scalar()
                if active:
                    raise ValueError(f'{name} has {active} active registrations; stop and inspect before reset')
            protected = {}
            for name in ('execution_runs', 'orders', 'fills', 'positions', 'risk_decisions', 'portfolio_targets'):
                if name in existing:
                    protected[name] = int(conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
            metadata = {}
            for row in tables:
                if row['table'] in {'global_oracle_labels', 'oracle_extreme_predictions', 'model_predictions'}:
                    continue  # Large histories are covered by the existing weekly SQL backup.
                metadata[row['table']] = [dict(item) for item in conn.execute(text(
                    f'SELECT * FROM alpha_trade.`{row["table"]}`')).mappings()]
            run_paths = [str(value) for row in conn.execute(text('''
                SELECT checkpoint_path,scaler_path,config_path FROM alpha_trade.model_training_run
            ''')) for value in row if value]
    finally:
        engine.dispose()
    targets_fs = filesystem_targets(report)
    for value in run_paths:
        p = Path(value)
        if not p.is_absolute():
            p = WORKSPACE / p
        if p.exists() and not any(p.resolve().is_relative_to(parent) for parent in targets_fs):
            targets_fs.append(safe_target(p))
    targets_fs = sorted(set(targets_fs), key=str)
    archive = WORKSPACE / 'backups/us_models_reset/20261013-v1'
    if archive.exists():
        raise ValueError('Recovery archive already exists')
    files = [dict(source=str(path), destination=str(archive/'files'/path.relative_to(WORKSPACE)))
             for path in targets_fs]
    plan = dict(status='READY_FOR_AUTHORIZED_RESET', created_at=datetime.now(timezone.utc).isoformat(),
                schema=SCHEMA, authorization='User explicitly requested all US models and their training data, predictions and metrics',
                inventory_sha256=source_digest(inventory_path), tables=tables, filesystem=files,
                protected_table_counts=protected, model_batches=[row['batch_id'] for row in report['batches']],
                recovery_files_root=str(archive), weekly_sql_backup='backups/db/alpha_trade_without_news_20261010_230004.sql.gz',
                latest_sql_metadata_backup='sql-metadata-before.json',
                protected_data=['CN/FR schemas and artefacts','source prices/news/consensus','order/fill/position history',
                                'LLM evidence and assessments','historical research reports/trade ledgers','existing backups'])
    write_json(OUTPUT/'sql-metadata-before.json', metadata)
    write_json(path, plan)
    print(json.dumps(dict(status=plan['status'], tables=tables, file_targets=len(files),
                         recovery=str(archive), protected_tables=protected), ensure_ascii=False, indent=2))
    return plan


def apply_database():
    plan_path = OUTPUT / 'plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan['schema'] != SCHEMA or plan['status'] != 'READY_FOR_AUTHORIZED_RESET':
        raise ValueError('Invalid plan')
    if source_digest(OUTPUT/'inventory.json') != plan['inventory_sha256']:
        raise ValueError('Inventory changed')
    if any(row['table'] not in TABLES or row['method'] not in {'DELETE', 'TRUNCATE'} for row in plan['tables']):
        raise ValueError('Unapproved table or method')
    progress_path = OUTPUT / 'database-progress.json'
    progress = json.loads(progress_path.read_text(encoding='utf-8')) if progress_path.exists() else {
        'status': 'RUNNING', 'plan_sha256': source_digest(plan_path), 'tables': []}
    if progress['plan_sha256'] != source_digest(plan_path):
        raise ValueError('Frozen plan changed')
    if progress['status'] == 'COMPLETED':
        return progress
    engine = get_sqlalchemy_engine(db_name=SCHEMA)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != SCHEMA:
                raise ValueError('Wrong database')
            conn.execute(text('SET SESSION innodb_lock_wait_timeout=30'))
            conn.commit()
            completed = {row['table'] for row in progress['tables']}
            for row in plan['tables']:
                name = row['table']
                if name in completed:
                    continue
                # For large histories, the authorized scope is the whole US
                # table, already counted and market-qualified in the frozen
                # plan. Re-counting tens of millions of rows under a concurrent
                # old cleanup is needlessly slow. Verify emptiness afterwards.
                current = row['rows_before'] if row['method'] == 'TRUNCATE' else int(
                    conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
                if current > row['rows_before']:
                    raise ValueError(f'{name} gained rows since inventory; reset paused')
                # An older, already-active per-batch cleanup can remove some of
                # these same authorized US rows. A decrease is safe to record;
                # a new model or foreign-market writer is not silently accepted.
                columns = conn.execute(text('''SELECT COLUMN_NAME FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=:schema AND TABLE_NAME=:table'''),
                    {'schema': SCHEMA, 'table': name}).scalars().all()
                if 'market_code' in columns:
                    other = conn.execute(text(f'''SELECT COUNT(*) FROM alpha_trade.`{name}`
                        WHERE market_code IS NOT NULL AND market_code<>:market'''), {'market': 'US_EQ'}).scalar()
                    if other:
                        raise ValueError(f'Non-US rows appeared in {name}')
                if row['method'] == 'TRUNCATE':
                    conn.execute(text(f'TRUNCATE TABLE alpha_trade.`{name}`'))
                    conn.commit()
                    removed = current
                else:
                    removed = 0
                    while True:
                        result = conn.execute(text(f'DELETE FROM alpha_trade.`{name}` LIMIT 20000'))
                        conn.commit()
                        removed += result.rowcount
                        if result.rowcount < 20000:
                            break
                remaining = int(conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
                if remaining:
                    raise ValueError(f'{name} still contains rows after reset')
                progress['tables'].append(dict(table=name, removed=removed, remaining=remaining, method=row['method'],
                    already_removed_by_prior_cleanup=None if row['method'] == 'TRUNCATE' else row['rows_before']-current,
                    count_scope='frozen inventory, including concurrent cleanup' if row['method'] == 'TRUNCATE' else 'this reset process'))
                write_json(progress_path, progress)
                print(json.dumps(progress['tables'][-1]), flush=True)
            protected_after = {}
            for name, before in plan['protected_table_counts'].items():
                after = int(conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
                protected_after[name] = dict(before=before, after=after, unchanged=before == after)
                if before != after:
                    raise ValueError(f'Protected table changed: {name}')
            progress.update(status='COMPLETED', protected_tables=protected_after,
                            removed_rows=sum(row['removed'] for row in progress['tables']),
                            rows_cleared_since_inventory=sum(row['rows_before'] for row in plan['tables']))
            write_json(progress_path, progress)
    finally:
        engine.dispose()
    return progress


def verify_reset():
    """Final read-only checks, recorded separately from destructive progress."""
    plan_path = OUTPUT/'plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    database = json.loads((OUTPUT/'database-progress.json').read_text(encoding='utf-8'))
    files = json.loads((OUTPUT/'filesystem-progress.json').read_text(encoding='utf-8-sig'))
    if database['status'] != 'COMPLETED' or files['status'] != 'COMPLETED':
        raise ValueError('Both reset phases must be completed')
    checksum = source_digest(plan_path)
    if any(item['plan_sha256'] != checksum for item in (database, files)):
        raise ValueError('Reset phases do not match the same frozen plan')
    remaining_files = [row['source'] for row in plan['filesystem'] if safe_target(row['source']).exists()]
    if remaining_files:
        raise ValueError(f'Planned files still exist: {remaining_files}')
    remaining_models = []
    for name in MODEL_ROOTS:
        root = WORKSPACE/'artifacts'/name
        if root.is_dir():
            remaining_models.extend(str(path) for path in root.iterdir()
                                    if path.is_dir() and path.name.startswith('model-factory-'))
    if remaining_models:
        raise ValueError(f'US models remain: {remaining_models}')
    engine = get_sqlalchemy_engine(db_name=SCHEMA)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != SCHEMA:
                raise ValueError('Wrong database')
            counts = {row['table']: int(conn.execute(text(
                f'SELECT COUNT(*) FROM alpha_trade.`{row["table"]}`')).scalar()) for row in plan['tables']}
            if any(counts.values()):
                raise ValueError(f'ML rows remain: {counts}')
            protected = {name: int(conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{name}`')).scalar())
                         for name in plan['protected_table_counts']}
            if protected != plan['protected_table_counts']:
                raise ValueError('Protected histories changed since inventory')
    finally:
        engine.dispose()
    from modelFactory.config import load_oracle_barrier_config
    from service.llm_directional.config import load_filter_config
    barrier, llm = load_oracle_barrier_config(), load_filter_config()
    if (barrier.take_profit_pct, barrier.stop_loss_pct, barrier.max_sessions) != (.20, .10, 20):
        raise ValueError('Training default must now be TP20/SL10 over 20 sessions')
    report = dict(status='US_MODEL_RESET_VERIFIED', plan_sha256=checksum,
        ml_table_remaining_counts=counts, protected_table_counts=protected,
        remaining_model_directories=remaining_models, remaining_planned_files=remaining_files,
        archive_created=files['archive_created'], deleted_file_targets=files['deleted_targets'],
        already_absent_file_targets=files['already_absent'],
        rows_cleared_since_inventory=database['rows_cleared_since_inventory'],
        training_defaults=dict(tp=barrier.take_profit_pct, sl=barrier.stop_loss_pct, sessions=barrier.max_sessions),
        llm_enabled=llm.enabled, llm_default_marker=llm.default_oracle_batch_id,
        preserved_schemas=['alpha_trade_cn', 'alpha_trade_fr'],
        source_tables_never_targeted=True)
    write_json(OUTPUT/'verification.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def inventory():
    output = OUTPUT / 'inventory.json'
    if output.exists():
        raise ValueError('Inventory already exists; preserve it before making another plan')
    engine = get_sqlalchemy_engine(db_name=SCHEMA)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != SCHEMA:
                raise ValueError('US reset must connect to alpha_trade explicitly')
            columns = [dict(row) for row in conn.execute(text('''
                SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, DATA_TYPE AS data_type
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=:schema
                  AND (COLUMN_NAME IN ('batch_id','oracle_batch_id','run_id','market_code','model_id','model_run_id')
                       OR TABLE_NAME LIKE 'model_%')
                ORDER BY TABLE_NAME,ORDINAL_POSITION
            '''), {'schema': SCHEMA}).mappings()]
            batch_columns = [row['column_name'] for row in columns if row['table_name'] == 'model_training_batch']
            fields = [column for column in ('batch_id', 'status', 'market_code', 'started_at', 'finished_at',
                                           'artifacts_dir', 'training_mode', 'symbol_source') if column in batch_columns]
            batches = [dict(row) for row in conn.execute(text(
                'SELECT ' + ','.join(fields) + ' FROM alpha_trade.model_training_batch ORDER BY started_at'
            )).mappings()]
            run_markets = [dict(row) for row in conn.execute(text('''
                SELECT batch_id,market_code,status,COUNT(*) AS rows_count
                FROM alpha_trade.model_training_run
                GROUP BY batch_id,market_code,status ORDER BY batch_id,market_code,status
            ''')).mappings()]
            tables = [dict(row) for row in conn.execute(text('''
                SELECT TABLE_NAME AS table_name, TABLE_ROWS AS estimated_rows, ENGINE AS engine
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA=:schema AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            '''), {'schema': SCHEMA}).mappings()]
            foreign_keys = [dict(row) for row in conn.execute(text('''
                SELECT k.TABLE_SCHEMA AS child_schema,k.TABLE_NAME AS child_table,
                       k.COLUMN_NAME AS child_column,k.REFERENCED_TABLE_SCHEMA AS parent_schema,
                       k.REFERENCED_TABLE_NAME AS parent_table,k.REFERENCED_COLUMN_NAME AS parent_column,
                       k.CONSTRAINT_NAME AS constraint_name,r.DELETE_RULE AS delete_rule
                FROM information_schema.KEY_COLUMN_USAGE AS k
                JOIN information_schema.REFERENTIAL_CONSTRAINTS AS r
                  ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA
                 AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME
                WHERE k.REFERENCED_TABLE_SCHEMA=:schema
                  AND (k.REFERENCED_TABLE_NAME LIKE 'model_%' OR k.TABLE_NAME LIKE 'model_%')
                ORDER BY k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION
            '''), {'schema': SCHEMA}).mappings()]
    finally:
        engine.dispose()
    directories = []
    for name in MODEL_ROOTS:
        root = WORKSPACE / 'artifacts' / name
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_dir() and path.name.startswith('model-factory-'):
                directories.append(dict(path=str(path.resolve()), batch_id=path.name))
    report = dict(status='INVENTORIED_READ_ONLY', created_at=datetime.now(timezone.utc).isoformat(),
                  schema=SCHEMA, columns=columns, batches=batches, run_markets=run_markets,
                  tables=tables, foreign_keys=foreign_keys, model_directories=directories,
                  preserved_schemas=['alpha_trade_cn', 'alpha_trade_fr'],
                  source_data_and_order_history_preserved=True)
    write_json(output, report)
    print(json.dumps(dict(status=report['status'], report=str(output),
                         batches=len(batches), directories=len(directories)), ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inventory', action='store_true')
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--apply-database', action='store_true')
    group.add_argument('--direct-delete-files', action='store_true')
    group.add_argument('--refine-plan', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.inventory:
        inventory()
    elif args.prepare:
        prepare()
    elif args.direct_delete_files or args.refine_plan:
        amend_for_direct_deletion()
    elif args.verify:
        verify_reset()
    else:
        apply_database()
