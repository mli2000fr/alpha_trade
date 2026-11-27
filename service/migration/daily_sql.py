"""Reduced US snapshot: complete schema, bounded context, intact account state.

All row reads share ONE read-only consistent snapshot. No temporary tables,
DELETE, source staging database, provider requests or source table locks.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import gzip
import math
import re
import subprocess
import tempfile

import pymysql

from .mysql import identifier
from .tracking import emit

KEEP_ALL = set('''markets instruments instrument_provider_symbols instrument_status_history
market_execution_rules market_sessions alembic_version stock_metadata stock_scores
stock_earnings_calendar stock_earnings_calendar_date_corrections cleaning_audit_latest
news_ingestion_checkpoint model_registry model_training_batch model_training_run
model_serving_batch champion_history model_metrics model_governance model_directional_oos_metrics
model_batch_diagnostics pit_collection_runs tradable_universe_runs tradable_universe_history
execution_broker_orders execution_order_requests execution_events execution_winner_campaigns
execution_position_lots execution_broker_fills execution_positions execution_runs
execution_winner_account_guards execution_reconciliation_results execution_targets_snapshot
portfolio_targets portfolio_cash_ledger risk_decisions account_risk_snapshots
broker_account_snapshots broker_positions_snapshots broker_statements audit_chain_events
execution_kill_switch_runs corporate_actions_events corporate_actions_applications
corporate_actions_audit_runs llm_directional_runs llm_directional_assessments
llm_directional_evaluations llm_news_analysis_cache llm_news_analysis_articles
llm_news_analysis_uses eodhd_ipo_collection_windows analyst_snapshot_collection_run
run_summaries run_business_summaries weights_calibration_runs weights_calibration_segment_drifts
ml_drift_runs shadow_drift_runs option_contract_adjustments'''.split())
SCHEMA_ONLY = set('''pit_raw_payloads model_metrics_full global_oracle_labels global_rank_history
llm_news_analysis_research_runs execution_locks watcher_heartbeats'''.split())
DATES = {
    'stock_bars': ('timestamp', 1120), 'stock_bars_daily': ('date', 1120),
    'stock_bars_intraday': ('trade_date', 7),
    'ticker_daily_sentiment_features': ('trade_date', 1120),
    'sector_daily_sentiment_features': ('trade_date', 1120),
    'stock_macro_indicators_daily': ('trade_date', 1120),
    'oracle_atr_market_regime_daily': ('trade_date', 1120),
    'stock_fundamentals_daily': ('trade_date', 1120),
    'stock_market_cap_daily': ('observation_date', 1120),
    'macro_vintage_observations': ('observation_date', 1120),
    'macro_public_observation_versions': ('period_end', 1120),
    'stock_risk_factor_inputs': ('asof_date', 90),
    'stock_analyst_consensus_eodhd_history': ('snapshot_date', 90),
    'stock_analyst_estimate_history': ('snapshot_date', 90),
    'stock_analyst_recommendation_history': ('snapshot_date', 90),
    'stock_analyst_eps_trend_history': ('snapshot_date', 90),
    'stock_analyst_eps_revision_history': ('snapshot_date', 90),
    'stock_analyst_target_history': ('snapshot_date', 90),
    'stock_analyst_consensus_snapshots': ('observed_at', 90),
    'stock_opening_window_bars': ('bar_timestamp', 7),
    'stock_opening_window_bar_versions': ('bar_timestamp', 7),
    'stock_bars_daily_versions': ('trade_date', 7),
    'stock_quote_snapshots': ('quote_date', 7),
    'stock_borrow_status_snapshots': ('observed_at', 90),
    'stock_option_snapshots': ('observed_at', 90),
    'stock_option_contract_versions': ('observed_at', 90),
    'stock_option_bars_delayed': ('bar_timestamp', 90),
    'stock_short_volume_daily': ('trade_date', 90),
    'security_master_snapshots': ('snapshot_date', 90),
    'security_master_changes': ('detected_date', 90),
    'stock_scores_history': ('snapshot_date', 90),
    'cleaning_audit_runs': ('created_at', 90),
    'cleaning_audit_quotes_runs': ('started_at', 90),
    'cleaning_audit_earnings_runs': ('started_at', 90),
    'news_raw': ('published_at_utc', 90),
    'news_raw_versions': ('first_observed_at', 90),
    'news_ticker_map_versions': ('first_observed_at', 90),
    'news_archive_observations': ('observed_at', 90),
    'macro_event_audit': ('trade_date', 90),
    'sec_filing_raw': ('filing_date', 90),
    'sec_ownership_snapshots': ('available_at', 90),
    'sec_corporate_events': ('filing_date', 90),
    'stock_ipo_eodhd_history': ('snapshot_date', 90),
    'corporate_action_source_events': ('effective_date', 90),
    'pit_data_quality_issues': ('detected_at', 90),
    'pit_data_quality_metrics': ('metric_date', 90),
}
MODEL_PREDICTIONS = {'oracle_extreme_predictions', 'oracle_path_prediction_lineage',
                     'oracle_path_directional_predictions', 'oracle_path_anti_sl_predictions'}


def column(table, name):
    return identifier(table)+'.'+identifier(name)


def build_policy(columns, foreign_keys, batch, cutoff,news_days=100,consensus_days=14,sec_days=30):
    """Fail on an unknown table instead of silently losing new runtime data."""
    if not isinstance(batch,str) or not re.fullmatch(r'model-factory-[A-Za-z0-9_-]+',batch):
        raise ValueError('Identifiant de modèle invalide pour la sélection SQL')
    grouped = defaultdict(set)
    for c in columns:
        grouped[c['table_name']].add(c['column_name'])
    predicates = {}
    for table, names in grouped.items():
        if table in KEEP_ALL:
            predicates[table] = '1'
        elif table in SCHEMA_ONLY:
            predicates[table] = '0'
        elif table in DATES:
            key, days = DATES[table]
            if table in ('news_raw','news_raw_versions','news_ticker_map_versions','news_archive_observations','macro_event_audit'):
                days=news_days
            elif table.startswith('stock_analyst_'):
                days=consensus_days
            elif table.startswith('stock_option_'):
                days=7
            elif table in ('sec_filing_raw','sec_corporate_events'):
                days=sec_days
            if key not in names:
                raise ValueError('Colonne de rétention absente : '+table+'.'+key)
            since = (cutoff-timedelta(days=days)).date().isoformat()
            # SEC has legacy YYYYMMDD strings as well as DATE schemas.
            if table == 'sec_filing_raw':
                predicates[table] = f"REPLACE({column(table,key)},'-','') >= '{since.replace('-','')}'"
            else:
                predicates[table] = f"{column(table,key)} >= '{since}'"
        elif table in MODEL_PREDICTIONS:
            since = (cutoff-timedelta(days=30)).date().isoformat()
            # batch is validated by model_folder, not interpolated user SQL.
            predicates[table] = f"{column(table,'batch_id')}='{batch}' AND {column(table,'prediction_date')}>='{since}'"
        elif table == 'model_predictions':
            since = (cutoff-timedelta(days=30)).date().isoformat()
            predicates[table] = f"{column(table,'prediction_date')}>='{since}'"
        elif table in ('news_ticker_map', 'news_sentiment', 'news_ticker_sentiment'):
            since = (cutoff-timedelta(days=news_days)).date().isoformat()
            predicates[table] = (f"EXISTS (SELECT 1 FROM `news_raw` WHERE `news_raw`.`article_id`="
                f"{column(table,'article_id')} AND `news_raw`.`published_at_utc`>='{since}')")
        elif table == 'sec_filing_documents':
            since = (cutoff-timedelta(days=sec_days)).date().strftime('%Y%m%d')
            predicates[table] = (f"EXISTS (SELECT 1 FROM `sec_filing_raw` WHERE `sec_filing_raw`.`accession_number`="
                f"{column(table,'accession_number')} AND REPLACE(`sec_filing_raw`.`filing_date`,'-','')>='{since}')")
        else:
            raise ValueError('Table sans politique de sauvegarde quotidienne US : '+table)
    # Keep every parent referenced by retained children, including composite FKs.
    incoming = defaultdict(dict)
    for fk in foreign_keys:
        key = (fk['table_name'], fk['fk'])
        incoming[fk['parent']].setdefault(key, []).append(fk)
    visiting = set()
    resolved = {}
    def close(table):
        if table in resolved:
            return resolved[table]
        if table in visiting:
            raise ValueError('Cycle de dépendances SQL à qualifier avant sauvegarde')
        if predicates[table] == '1':
            resolved[table] = '1'
            return '1'
        visiting.add(table)
        parts = [predicates[table]]
        for (child, _), fields in incoming[table].items():
            if child not in predicates:
                raise ValueError('Table enfant non qualifiée : '+child)
            child_filter = close(child)
            if child_filter == '0':
                continue
            equal = ' AND '.join(column(child,f['column_name'])+'='+column(table,f['parent_column']) for f in fields)
            parts.append(f'EXISTS (SELECT 1 FROM {identifier(child)} WHERE ({child_filter}) AND {equal})')
        visiting.remove(table)
        resolved[table] = '('+') OR ('.join(parts)+')' if len(parts)>1 else parts[0]
        return resolved[table]
    for table in predicates:
        close(table)
    return resolved


def sql_value(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (bytes, bytearray)):
        return "X'"+bytes(value).hex()+"'"
    if isinstance(value, (int, Decimal)):
        if isinstance(value,Decimal) and not value.is_finite():raise ValueError('Décimal SQL non fini')
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Valeur numérique SQL non finie')
        return repr(value)
    if isinstance(value, (date, datetime)):
        value = value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    if isinstance(value,timedelta):
        micros=round(value.total_seconds()*1_000_000);negative=micros<0;micros=abs(micros)
        seconds,fraction=divmod(micros,1_000_000)
        value=('-' if negative else '')+f'{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}.{fraction:06d}'
    return "CONVERT(X'"+str(value).encode('utf-8').hex()+"' USING utf8mb4)"


def dump_ddl(db, name, stream, *, triggers, check):
    args, env = db.args(name, db.dump_tool)
    args += ['--skip-lock-tables', '--no-data', '--skip-events', '--set-gtid-purged=OFF', '--no-tablespaces']
    args += ['--no-create-info', '--skip-routines', '--triggers'] if triggers else ['--routines', '--skip-triggers']
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args+[name], stdout=subprocess.PIPE, stderr=errors, env=env)
        try:
            while block := process.stdout.read(1024*1024):
                check(); stream.write(block)
            if process.wait() != 0:
                raise RuntimeError('Export du schéma US échoué')
        except BaseException:
            process.kill(); process.wait(); raise
        finally:
            process.stdout.close()


def dump_daily(db, name, output, *, batch, cutoff, news_days=100,consensus_days=14,sec_days=30,check=lambda:None):
    if name != 'alpha_trade':
        raise ValueError('Snapshot quotidien limité à la base US')
    with db.connect(name) as conn, conn.cursor() as cur:
        cur.execute('USE '+identifier(name))
        cur.execute("SELECT TABLE_NAME table_name,COLUMN_NAME column_name,EXTRA extra FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,ORDINAL_POSITION", (name,))
        columns = cur.fetchall()
        cur.execute("SELECT TABLE_NAME table_name,COLUMN_NAME column_name,REFERENCED_TABLE_NAME parent,REFERENCED_COLUMN_NAME parent_column,CONSTRAINT_NAME fk FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY ORDINAL_POSITION", (name,))
        foreign_keys = cur.fetchall()
        cur.execute("SELECT TABLE_NAME name FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME", (name,))
        tables = [r['name'] for r in cur.fetchall()]
        columns=[c for c in columns if c['table_name'] in tables]
        # Views have schema definitions but no exported row selection.
        policy=build_policy(columns, foreign_keys, batch, cutoff,news_days=news_days,
            consensus_days=consensus_days,sec_days=sec_days)
        cur.execute("SET SESSION time_zone='+00:00'")
        cur.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        cur.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
        rows = {}
        try:
            with gzip.GzipFile(fileobj=output, mode='wb', mtime=0) as packed:
                dump_ddl(db, name, packed, triggers=False, check=check)
                packed.write(b"\nSET FOREIGN_KEY_CHECKS=0;\nSET NAMES utf8mb4;\nSET time_zone='+00:00';\nSET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n")
                for index, table in enumerate(tables):
                    check(); rows[table] = 0
                    emit(db.on_progress, database=name, item=table, files_done=index, files_total=len(tables), unit='tables')
                    if policy[table] == '0':
                        continue
                    names = [c['column_name'] for c in columns if c['table_name']==table
                             and not any(kind in c['extra'] for kind in ('VIRTUAL GENERATED','STORED GENERATED'))]
                    projection = ','.join(identifier(c) for c in names)
                    # Server-side cursor bounds RAM independently of table size.
                    with conn.cursor(pymysql.cursors.SSCursor) as reader:
                        reader.execute(f'SELECT {projection} FROM {identifier(name)}.{identifier(table)} WHERE {policy[table]}')
                        while records := reader.fetchmany(32):
                            check()
                            prefix='INSERT INTO '+identifier(table)+' ('+projection+') VALUES '
                            values=[];statement_bytes=0
                            for row in records:
                                value='('+','.join(sql_value(v) for v in row)+')'
                                if values and statement_bytes+len(value)>4*1024*1024:
                                    packed.write((prefix+','.join(values)+';\n').encode('ascii'))
                                    values=[];statement_bytes=0
                                values.append(value);statement_bytes+=len(value)
                            if values:packed.write((prefix+','.join(values)+';\n').encode('ascii'))
                            rows[table] += len(records)
                            emit(db.on_progress, item=table, completed=rows[table], unit='lignes exportées')
                packed.write(b'\nSET FOREIGN_KEY_CHECKS=1;\n')
                # Install identity/other business triggers only AFTER data loading.
                dump_ddl(db, name, packed, triggers=True, check=check)
            return dict(rows=rows, row_policy=policy, snapshot='single_read_only_transaction')
        finally:
            conn.rollback()
