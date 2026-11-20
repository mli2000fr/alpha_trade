"""Optional batch/manual LONG veto after Q051 ranking; no alternative sizing/exits."""
from dataclasses import replace
from datetime import UTC, datetime
import json
import math
import uuid

from sqlalchemy import text

from service.llm_directional.config import load_filter_config
from service.llm_directional.repository import Repository
from service.llm_directional.runner import analyze, qualified_selection


def manual_config(horizon, count):
    """Enable via explicit batch policy or permitted manual opt-in."""
    cfg = load_filter_config()
    from service.forward_pit.us_pipeline import gpt_filter_enabled, load_pipeline_policy
    if not cfg.manual_opt_in_allowed and not gpt_filter_enabled(load_pipeline_policy()):
        raise ValueError('Activation LLM manuelle interdite dans config.yaml')
    return replace(cfg, enabled=True, horizon=horizon, account_id='default',
                   oracle_top_n=max(1, count), max_selected=min(count, cfg.max_selected),
                   allow_short=False, protections=None)


def contexts(engine, candidates, *, day, horizon, config, parent_run_id):
    """Only supplied preselected candidates; never labels/future returns."""
    from common.daily_bar_sources import daily_source_filter
    from service.llm_directional.fresh_evidence import enrich_contexts
    result = []
    source_filter, source_params = daily_source_filter()
    with engine.connect() as conn:
        for row in candidates.to_dict('records'):
            symbol, score = str(row['symbol']), float(row['proba_extreme'])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('Score Oracle du candidat LLM invalide')
            identity = conn.execute(text('SELECT company_name, exchange FROM stock_metadata WHERE symbol=:symbol'),
                                    dict(symbol=symbol)).mappings().first()
            bars = conn.execute(text(f'''SELECT date, close FROM stock_bars_daily
                WHERE symbol=:symbol AND date<=:day AND is_filled=0 {source_filter}
                ORDER BY date DESC LIMIT 21'''), dict(symbol=symbol, day=day, **source_params)).mappings().all()
            if not identity or not identity['company_name'] or not bars or str(bars[0]['date'])[:10] != str(day):
                raise ValueError(f'Identité ou cours J absent pour le candidat LLM {symbol}')
            result.append(dict(symbol=symbol, oracle_rank=int(row['oracle_rank']), oracle_score=score,
                issuer_reference=dict(identity), observed_at_utc=datetime.now(UTC).isoformat(),
                trade_date=str(day), horizon_sessions=horizon, oracle_target=f'path_amplitude_J1_J{horizon}',
                oracle_directional=False, prices_through_decision_date=[dict(b) for b in bars],
                parent_q051_run_id=parent_run_id))
    return enrich_contexts(engine, result, config, datetime.now(UTC))


def apply(engine, ranked, *, run_id, batch, day, horizon):
    """Keep B ranking order; LLM may only remove LONGs, never refill ranks."""
    frame = ranked.copy()
    frame['selected_before_llm'] = frame.selected.astype(bool)
    candidates = frame[frame.selected].sort_values('rank')
    cfg = manual_config(horizon, len(candidates))
    llm_id = 'llm-' + uuid.uuid4().hex
    source = 'q051-selection:' + run_id
    if candidates.empty:
        return frame, dict(enabled=True, run_id=None, requested=0, selected=[],
                           reason='NO_PER_SYMBOL_CANDIDATE', horizon=horizon)
    packets = contexts(engine, candidates, day=day, horizon=horizon, config=cfg, parent_run_id=run_id)
    if ({p['symbol'] for p in packets} != set(candidates.symbol) or len(packets) != len(candidates)):
        raise ValueError('Les candidats du filtre LLM diffèrent du classement LONG')
    from service.llm_directional.repository import utcnow
    from service.pipeline_telegram import notify_llm
    attempted = utcnow()
    try:
        analyze(engine=engine, batch_id=batch, trade_date=day, symbol_source=source,
                capital_preset_key='q051_frozen_profile', config=cfg, run_id=llm_id, inputs=packets)
    finally:
        notify_llm(engine, llm_id, attempted_at=attempted, trade_date=str(day), provider_label=cfg.provider_label)
    run, selected = qualified_selection(engine, llm_id, day, 'default')
    selected_symbols = {item['symbol'] for item in selected}
    if not selected_symbols.issubset(set(candidates.symbol)):
        raise ValueError('Le filtre LLM ne peut ajouter de nouveaux titres')
    _, items = Repository(engine).get(llm_id)
    assessments = {i['symbol']:json.loads(i['assessment_json']) for i in items}
    if any(assessments[s]['decision'] != 'LONG' for s in selected_symbols):
        raise ValueError('Q051 : seuls les avis LONG qualifiés peuvent être retenus')
    frame['llm_direction_score'] = frame.symbol.map(lambda s: assessments.get(s, {}).get('direction_score'))
    frame['llm_decision'] = frame.symbol.map(lambda s: assessments.get(s, {}).get('decision'))
    frame['llm_evidence_quality'] = frame.symbol.map(lambda s: assessments.get(s, {}).get('evidence_quality'))
    frame['llm_blockers'] = frame.symbol.map(lambda s: ', '.join(assessments.get(s, {}).get('selection_blockers', [])))
    excluded = frame.selected & ~frame.symbol.isin(selected_symbols)
    frame.loc[excluded, 'reason'] = 'LLM_NOT_RETAINED'
    frame['selected'] = frame.selected & frame.symbol.isin(selected_symbols)
    receipt = dict(enabled=True, run_id=llm_id, requested=len(candidates), selected=sorted(selected_symbols),
        input_sha256=run['input_sha256'], batch_id=batch, trade_date=str(day), horizon=horizon,
        provider=cfg.provider_label, analysis_mode=cfg.analysis_mode,
        long_score_threshold=cfg.long_score_threshold, short_score_threshold=cfg.short_score_threshold)
    return frame, receipt


def validate(engine, report, ranked, day):
    """Revalidate archived answers before each risk/execution, without API calls."""
    receipt = report.get('llm_filter')
    if not receipt:
        return
    if receipt.get('enabled') is not True or 'selected_before_llm' not in ranked:
        raise ValueError('Liaison du filtre LLM Q051 invalide')
    prior = set(ranked.loc[ranked.selected_before_llm, 'symbol'])
    current = set(ranked.loc[ranked.selected, 'symbol'])
    if not prior:
        if receipt.get('run_id') is not None or current or receipt.get('requested') != 0:
            raise ValueError('Filtre LLM vide incohérent')
        return
    run, selected = qualified_selection(engine, receipt['run_id'], day, 'default')
    snapshot = json.loads(run['input_json'])
    cfg = json.loads(run['config_json'])
    if (run['input_sha256'] != receipt['input_sha256'] or run['batch_id'] != report['batch_id']
            or snapshot['symbol_source'] != 'q051-selection:' + report['run_id']
            or {c['symbol'] for c in snapshot['candidates']} != prior
            or any(c.get('parent_q051_run_id') != report['run_id'] for c in snapshot['candidates'])
            or cfg['horizon'] != receipt['horizon'] or cfg['horizon'] != report['profile']['winner']['horizon_sessions']
            or cfg['allow_short'] is not False
            or current != {item['symbol'] for item in selected}
            or current != set(receipt['selected']) or not current.issubset(prior)):
        raise ValueError('Liaison ou sélection LLM Q051 altérée')
