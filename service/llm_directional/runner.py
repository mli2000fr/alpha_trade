"""Persist each answer before parsing; partial failure never feeds paper trading."""
import argparse
import json
import logging
import math
import struct
import uuid
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import text, bindparam
from .config import load_filter_config, FilterConfig
from .repository import Repository, dumps, digest, utcnow
from .openai_client import ResponsesClient, build_request, PROTOCOL_VERSION
from .validation import parse_response, select_symbols, FRESH_QUALIFICATIONS


def assert_paper_account(account_id='default'):
    from service.alpaca.accounts import AccountRegistry
    account = AccountRegistry.get().resolve(account_id)
    if account.account_id != 'default' or account.mode != 'paper':
        raise ValueError('Le compte principal default doit être PAPER; LIVE interdit au filtre LLM')


def load_inputs(engine, batch_id, trade_date, symbol_source, config, capital_preset_key):
    from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
    horizon = resolve_oracle_artifact_horizon(batch_id, 'artifacts/models')
    if horizon != config.horizon:
        raise ValueError(f'Horizon Oracle {horizon} incompatible avec filtre H{config.horizon}')
    from modelFactory.oracle_path.train import is_path_batch
    path_oracle = is_path_batch('artifacts/models', batch_id)
    if path_oracle:
        from modelFactory.oracle.predictions_store import load_oracle_predictions
        # Do not bypass path lineage just because Web analysis reads raw SQL.
        load_oracle_predictions(engine, batch_id=batch_id, start_date=str(trade_date), end_date=str(trade_date))
    from modelFactory.db_registry import load_symbols_for_source
    symbols = load_symbols_for_source(engine, symbol_source, trade_date=trade_date,
                                     capital_preset_key=capital_preset_key)
    if not symbols:
        raise ValueError('Univers vide')
    query = text('''SELECT symbol, proba_extreme FROM oracle_extreme_predictions
        WHERE batch_id=:batch AND prediction_date=:day AND symbol IN :symbols
        ORDER BY proba_extreme DESC, symbol ASC''').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(query, {'batch': batch_id, 'day': trade_date,
                                    'symbols': symbols}).mappings().all()
        if len(rows) / len(symbols) < config.min_oracle_coverage_ratio:
            raise ValueError(f'Couverture Oracle insuffisante: {len(rows)}/{len(symbols)}; pas de classement partiel')
        # No realized-return, label or future-price column is ever read here.
        result = []
        for rank, row in enumerate(rows[:config.oracle_top_n], 1):
            score = float(row['proba_extreme'])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('Score Oracle invalide')
            # Restrict bars to J and earlier; identity is checked independently on the Web.
            bars = conn.execute(text('''SELECT date, close FROM stock_bars_daily
                WHERE symbol=:symbol AND date<=:day AND is_filled=0
                ORDER BY date DESC LIMIT 21'''), {'symbol': row['symbol'], 'day': trade_date}).mappings().all()
            if not bars or str(bars[0]['date'])[:10] != str(trade_date):
                raise ValueError(f'Cours J absent pour {row["symbol"]}')
            identity = conn.execute(text('''SELECT company_name, exchange FROM stock_metadata
                WHERE symbol=:symbol'''), {'symbol': row['symbol']}).mappings().first()
            if not identity or not identity['company_name']:
                raise ValueError(f'Identité locale absente pour {row["symbol"]}')
            result.append({'symbol': row['symbol'], 'oracle_rank': rank, 'oracle_score': score,
                           'issuer_reference': dict(identity), 'observed_at_utc': str(utcnow()),
                           'trade_date': str(trade_date), 'horizon_sessions': config.horizon,
                           'prices_through_decision_date': [dict(bar) for bar in bars]})
            if path_oracle:
                result[-1].update(oracle_target='path_amplitude_J1_J20', oracle_directional=False)
    if not result:
        raise ValueError('Oracle absent pour cette date/batch/univers; aucun fallback')
    from .fresh_evidence import enrich_contexts
    return enrich_contexts(engine,result,config,datetime.now(timezone.utc))


def validate_analysis_window(trade_date, *, now=None, calendar=None):
    """Prospective web analysis: session close <= now < next session open."""
    from common.market_calendar import get_market_calendar
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Horodatage timezone-aware requis')
    if trade_date not in calendar.session_dates(trade_date, trade_date):
        raise ValueError('Date hors séance US')
    _, close = calendar.session_bounds(trade_date)
    next_day = calendar.next_session(trade_date)
    next_open, _ = calendar.session_bounds(next_day)
    if now < close:
        raise ValueError('Attendre la clôture NYSE : les données J doivent être définitives')
    if now >= next_open:
        raise ValueError('Recherche Web prospective uniquement : la séance US suivante a déjà ouvert')


def analyze(*, engine, batch_id, trade_date, symbol_source, capital_preset_key='capital_2001_5000',
            config=None, run_id=None, client=None, inputs=None, check_account=True,
            research_parent_run_id=None):
    config = config or load_filter_config()
    if not config.enabled:
        raise ValueError('llm_directional_filter.enabled=false')
    if isinstance(trade_date, str):
        trade_date = date.fromisoformat(trade_date)
    validate_analysis_window(trade_date)
    if check_account:
        assert_paper_account(config.account_id)
    repo = Repository(engine)
    run_id = run_id or f'llm-{uuid.uuid4().hex}'
    contexts = inputs if inputs is not None else load_inputs(
        engine, batch_id, trade_date, symbol_source, config, capital_preset_key)
    if not contexts or len(contexts) > config.oracle_top_n:
        raise ValueError('Nombre de candidats incohérent')
    if len({c['symbol'] for c in contexts}) != len(contexts):
        raise ValueError('Candidats dupliqués')
    snapshot = {'symbol_source': symbol_source, 'capital_preset_key': capital_preset_key,
                'candidates': contexts}
    if research_parent_run_id is not None:
        snapshot.update(research_only=True, parent_run_id=research_parent_run_id)
    started = utcnow()
    repo.create(run_id=run_id, trade_date=trade_date, batch_id=batch_id,
        account_id=config.account_id, status='RUNNING', started_at=started,
        config_json=dumps(config.snapshot()), input_json=dumps(snapshot), input_sha256=digest(snapshot),
        protocol_version=_protocol(contexts))
    items, errors = [], []
    try:
        logging.info('Filtre %s modèle=%s ; mode=%s ; PAPER uniquement',
                     config.provider_label, config.analysis_model, config.analysis_mode)
        client = client or ResponsesClient(config)
        for context in contexts:
            request = build_request(json.loads(dumps(context)), config)
            response, parsed, error, status = None, None, None, 'FAILED'
            observed = utcnow()
            try:
                from .fresh_evidence import validate_fresh_packet
                validate_fresh_packet(context,config,observed,before_call=True)
                response = client(request)
                observed = utcnow()
            except Exception as exc:
                error = f'{type(exc).__name__}: {str(exc)[:600]}'
            # Commit raw answer BEFORE parsing or applying any decision rule.
            repo.record(run_id=run_id, symbol=context['symbol'], oracle_rank=context['oracle_rank'],
                oracle_score=context['oracle_score'], observed_at=observed, request_json=dumps(request),
                response_json=dumps(response) if response is not None else None,
                response_sha256=digest(response) if response is not None else None,
                status='RECEIVED', selected=False)
            try:
                if error:
                    raise RuntimeError(error)
                parsed = parse_response(response, context['symbol'], config, observed, context=context)
                parsed['oracle_rank'] = context['oracle_rank']
                items.append(parsed)
                status = 'VALID'
            except Exception as exc:
                # Our transport removes headers/error bodies; truncate any parser echoes.
                error = f'{type(exc).__name__}: {str(exc)[:600]}'
                errors.append(f'{context["symbol"]}: {error}')
            repo.finalize_assessment(run_id, context['symbol'], status=status, parsed=parsed, error=error)
            logging.info('LLM %d/%d %s %s outcome=%s fresh_web_sources=%s fresh_local_sources=%s blockers=%s',
                len(items)+len(errors), len(contexts), context['symbol'], status,
                parsed['assessment_outcome'] if parsed else 'TECHNICAL_ERROR',
                parsed['fresh_source_count'] if parsed else '-',
                parsed.get('fresh_local_source_count',0) if parsed else '-',
                ','.join(parsed['selection_blockers']) if parsed else error)
        # A slow Web call must not publish a selection after the next open.
        validate_analysis_window(trade_date)
        selected = [] if errors else select_symbols(items, config)
        repo.finish(run_id, 'FAILED' if errors else 'COMPLETED', selected, '\n'.join(errors) or None)
    except Exception as exc:
        # If persistence itself fails, leave RUNNING (never servable); do not continue to risk.
        try:
            repo.finish(run_id, 'FAILED', [], f'{type(exc).__name__}: traitement interrompu')
        except Exception:
            pass
        raise
    if errors:
        raise RuntimeError(f'Analyse {run_id} échouée; {len(errors)} réponses invalides; aucun candidat publié')
    return {'run_id': run_id, 'status': 'completed', 'requested': len(contexts),
            'received': len(items), 'persisted': len(items), 'selected': selected,
            'failed': 0, 'warning_count': 0,
            'analysis_mode': config.analysis_mode,
            'fresh_local_source_count': sum(item.get('fresh_local_source_count',0) for item in items),
            'eligible_count': sum(item['eligible'] for item in items),
            'abstained_count': sum(not item['eligible'] for item in items),
            'excluded_source_count': sum(len(item['excluded_sources']) for item in items),
            'unqualified_source_count': sum(
                q['qualification'] not in FRESH_QUALIFICATIONS
                for item in items for q in item['source_qualifications'])}


def _oracle_score_matches_snapshot(stored, reference):
    """Accept only known representations of the immutable snapshot score.

    MySQL FLOAT stores binary32; its text protocol may return six significant
    digits. No generic tolerance: other score changes remain incompatible, and
    neither the ranking nor the request is rebuilt from the rounded SQL column.
    """
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or not 0 <= value <= 1 for value in (stored, reference)):
        return False
    binary32 = struct.unpack('!f', struct.pack('!f', reference))[0]
    return stored in (reference, binary32, float(format(binary32, '.6g')))


def qualified_selection(engine, run_id, trade_date, account_id, *, now=None, allow_consumed=False):
    assert_paper_account(account_id)
    run, items = Repository(engine).get(run_id)
    config = FilterConfig(**json.loads(run['config_json']))
    now = now or utcnow()
    if run['status'] != 'COMPLETED' or run['account_id'] != account_id or run['trade_date'] != trade_date:
        raise ValueError('Run LLM non finalisé ou date/compte incompatible')
    if not run['completed_at'] or not run['completed_at'] <= now <= run['completed_at'] + timedelta(hours=config.max_run_age_hours):
        raise ValueError('Analyse LLM expirée ou datée du futur')
    if not allow_consumed and (run['risk_run_id'] or run['execution_started_at']):
        raise ValueError('Run LLM déjà consommé; pas de nouvelles cibles implicites')
    snapshot = json.loads(run['input_json'])
    if digest(snapshot) != run['input_sha256']:
        raise ValueError('Snapshot LLM altéré')
    if run['protocol_version'] != _protocol(snapshot.get('candidates')):
        raise ValueError('Version du protocole LLM incompatible')
    if snapshot.get('research_only'):
        raise ValueError('Run LLM de recherche uniquement : risque/exécution interdits')
    expected = snapshot['candidates']
    if len(items) != len(expected) or any(i['status'] != 'VALID' for i in items):
        raise ValueError('Archivage incomplet')
    expected_by_symbol = {context['symbol']: context for context in expected}
    if len(expected_by_symbol) != len(expected) or {i['symbol'] for i in items} != set(expected_by_symbol):
        raise ValueError('Candidats archivés incompatibles avec le snapshot')
    for item in items:
        context = expected_by_symbol[item['symbol']]
        if item['oracle_rank'] != context['oracle_rank']:
            raise ValueError(f"Rang Oracle incompatible avec le snapshot : {item['symbol']}")
        if not _oracle_score_matches_snapshot(item['oracle_score'], context['oracle_score']):
            raise ValueError(f"Score Oracle incompatible avec le snapshot : {item['symbol']}")
        if json.loads(item['request_json']) != build_request(context, config):
            raise ValueError(f"Requête LLM incompatible avec le snapshot : {item['symbol']}")
        if digest(json.loads(item['response_json'])) != item['response_sha256']:
            raise ValueError('Réponse LLM altérée')
        parsed = parse_response(json.loads(item['response_json']), item['symbol'], config, item['observed_at'],context=context)
        saved = json.loads(item['assessment_json'])
        if any(saved.get(key) != value for key, value in parsed.items()):
            raise ValueError('Assessment LLM incohérent avec réponse brute')
    selected = json.loads(run['selected_json'])
    decisions = [dict(json.loads(i['assessment_json']), oracle_rank=i['oracle_rank']) for i in items]
    if selected != select_symbols(decisions, config):
        raise ValueError('Sélection LLM incohérente')
    # Preserve the full-precision, hashed evidence in downstream risk lineage.
    # SQL archives are never rewritten and selected order remains unchanged.
    return run, [dict(next(i for i in items if i['symbol'] == symbol),
                      oracle_score=expected_by_symbol[symbol]['oracle_score'])
                 for symbol in selected]


def _protocol(contexts):
    from .prompts import VERSION, DEEPSEEK_SEARCH_VERSION,FRESH_VERSION
    if not isinstance(contexts,list) or not contexts or any(not isinstance(c,dict) for c in contexts):
        raise ValueError('Candidats de protocole LLM invalides')
    versions={context.get('analysis_protocol',PROTOCOL_VERSION) for context in contexts}
    if len(versions)!=1 or not versions.issubset({PROTOCOL_VERSION,VERSION,DEEPSEEK_SEARCH_VERSION,FRESH_VERSION}):
        raise ValueError('Protocoles LLM absents/incompatibles/mélangés')
    return next(iter(versions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--symbol-source', required=True)
    parser.add_argument('--capital-preset-key', default='capital_2001_5000')
    parser.add_argument('--run-id')
    args = parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    logging.basicConfig(level=logging.INFO)
    from database.run_business_summaries import emit_run_summary
    emit_run_summary(analyze(engine=get_sqlalchemy_engine(), **vars(args)))


if __name__ == '__main__':
    main()
