"""Read-only step-10 view of one archived Oracle/LLM snapshot.

Never re-rank by LLM confidence, read future outcomes, call a provider, or
publish a selection. This view is not the risk/execution handoff.
"""
import json
import math
from datetime import date, datetime

from sqlalchemy import Column, MetaData, String, Table, select

from service.llm_directional.repository import assessments, runs


def add_company_names(engine, rows):
    """Current display labels only: no historical identity or selection change."""
    if not rows:
        return rows
    stock_metadata = Table('stock_metadata', MetaData(),
        Column('symbol', String), Column('company_name', String))
    symbols = sorted({r['Symbole'] for r in rows})
    with engine.connect() as conn:
        records = conn.execute(select(stock_metadata.c.symbol, stock_metadata.c.company_name)
            .where(stock_metadata.c.symbol.in_(symbols))).mappings().all()
    names = {r['symbol']: r['company_name'].strip()
             if isinstance(r['company_name'], str) and r['company_name'].strip() else None for r in records}
    enriched = []
    for row in rows:
        result = {}
        for key, value in row.items():
            if key == 'Nom de l’entreprise':
                continue
            result[key] = value
            if key == 'Symbole':
                result['Nom de l’entreprise'] = names.get(value)
        enriched.append(result)
    return enriched


def _object(value):
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError('Archive LLM illisible : objet attendu')
    return parsed


def _score(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) and 0 <= result <= 1 else None


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _last_archived_price(candidate, trade_date):
    """Last valid close supplied to this analysis, never a current/future quote."""
    cutoff = _day(trade_date) or _day(candidate.get('trade_date'))
    bars = candidate.get('prices_through_decision_date')
    if cutoff is None or not isinstance(bars, list):
        return None, None
    usable = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        day = _day(bar.get('date'))
        value = bar.get('close')
        if day is None or day > cutoff or isinstance(value, bool):
            continue
        try:
            price = float(value)
        except (ValueError, TypeError, OverflowError):
            continue
        if math.isfinite(price) and price > 0:
            usable.append((day, price))
    if not usable:
        return None, None
    day, price = max(usable, key=lambda row: row[0])
    return price, day


def _quota_exclusions(candidates, items, config, selected_symbols):
    """Explain a cap only when the archived selection matches the full ranking."""
    cap = config.get('max_selected')
    if type(cap) is not int or cap < 0 or not isinstance(selected_symbols, list):
        return set()
    ranks = {c['symbol']: int(c['oracle_rank']) for c in candidates}
    eligible = []
    for item in items:
        if item.get('status') != 'VALID' or item['symbol'] not in ranks:
            continue
        try:
            parsed = _object(item.get('assessment_json'))
        except (TypeError, ValueError):
            continue
        confidence = _score(parsed.get('confidence'))
        if (parsed.get('eligible') is True and not parsed.get('selection_blockers')
                and parsed.get('decision') in ('LONG', 'SHORT') and confidence is not None):
            eligible.append((item['symbol'], confidence))
    eligible.sort(key=lambda row: (-row[1], ranks[row[0]], row[0]))
    expected = [symbol for symbol, _ in eligible[:cap]]
    if selected_symbols != expected:
        return set()  # Never invent a cap explanation for an inconsistent archive.
    return {symbol for symbol, _ in eligible[cap:]}


def _non_selection_reason(*, selected, parsed, state, run_status, config, quota_excluded):
    if selected:
        return '—'
    reasons = []
    if run_status == 'RUNNING':
        reasons.append('Analyse globale en cours : aucune sélection publiée')
    elif run_status != 'COMPLETED':
        reasons.append('Analyse globale échouée ou interrompue : aucune sélection publiée')
    if state == 'VALID':
        if parsed.get('decision') == 'ABSTAIN':
            reasons.append('Abstention du LLM : aucune direction retenue')
        blockers = parsed.get('selection_blockers')
        for code in blockers if isinstance(blockers, list) else []:
            if code == 'excluded_untraceable_sources':
                reasons.append('Source(s) citée(s) non traçable(s) ou URL invalide(s)')
            elif code == 'confidence_below_threshold':
                confidence, threshold = _score(parsed.get('confidence')), _score(config.get('min_confidence'))
                detail = f' ({confidence*100:g} % < {threshold*100:g} %)' if confidence is not None and threshold is not None else ''
                reasons.append('Confiance sous le seuil requis' + detail)
            elif code == 'insufficient_fresh_sources':
                count, minimum = parsed.get('fresh_source_count'), config.get('min_sources')
                detail = f' ({count}/{minimum})' if type(count) is int and type(minimum) is int else ''
                reasons.append('Sources récentes qualifiées insuffisantes' + detail)
            elif code == 'short_not_allowed':
                reasons.append('SHORT non autorisé dans cette analyse')
            elif code == 'insufficient_qualified_local_sources':
                reasons.append('Preuves locales qualifiées insuffisantes ; consensus/news non qualifiés ne suffisent pas')
            elif code == 'excluded_untraceable_local_sources':
                reasons.append('Référence locale ou citation non traçable')
            elif code == 'identity_not_confirmed':
                reasons.append('Identité du titre non confirmée')
            else:
                reasons.append('Blocage archivé : ' + str(code)[:120])
        if not reasons:
            if quota_excluded:
                reasons.append('Sélection désactivée : nombre maximal de titres retenus fixé à 0'
                    if config['max_selected'] == 0 else
                    f"Admissible, mais hors des {config['max_selected']} titres retenus après classement par confiance LLM")
            elif parsed.get('eligible') is True:
                reasons.append('Admissible, mais non retenu : motif non renseigné dans l’archive')
            else:
                reasons.append('Évaluation non admissible : motif non renseigné dans l’archive')
    elif state == 'RECEIVED':
        reasons.append('Réponse reçue, validation en attente')
    elif state in ('Absent', 'En cours'):
        reasons.append('Évaluation non encore enregistrée' if run_status == 'RUNNING' else 'Évaluation absente de l’archive')
    elif state == 'Archive invalide':
        reasons.append('Réponse archivée illisible ou invalide')
    else:
        reasons.append('Erreur technique : aucune réponse validée')
    return ' ; '.join(reasons)


def review_rows(candidates, items, *, run_status, limit=10, config=None, selected_symbols=None,
                trade_date=None):
    """Keep all top candidates, including pending, abstaining and rejected ones."""
    if not isinstance(candidates, list) or not 1 <= limit <= 100:
        raise ValueError('Snapshot ou limite de classement invalide')
    if len({c['symbol'] for c in candidates}) != len(candidates):
        raise ValueError('Symboles dupliqués dans le snapshot Oracle')
    for candidate in candidates:
        if _score(candidate.get('oracle_score')) is None:
            raise ValueError('Score Oracle archivé invalide')
    ordered = sorted(candidates, key=lambda c: (-float(c['oracle_score']),
        int(c['oracle_rank']), c['symbol']))[:limit]
    config = config or {}
    quota_excluded = _quota_exclusions(candidates, items, config, selected_symbols)
    by_symbol = {item['symbol']: item for item in items}
    rows = []
    for candidate in ordered:
        item = by_symbol.get(candidate['symbol'])
        decision, confidence, state = 'Non analysé', None, 'Absent'
        selected = False
        parsed = {}
        if item:
            state = str(item['status'])
            if state == 'VALID':
                try:
                    parsed = _object(item['assessment_json'])
                except (ValueError, TypeError):
                    parsed = {}
                raw_decision = parsed.get('decision')
                confidence = _score(parsed.get('confidence'))
                if raw_decision in ('LONG', 'SHORT', 'ABSTAIN') and confidence is not None:
                    decision = {'LONG': 'LONG', 'SHORT': 'SHORT', 'ABSTAIN': 'NEUTRE / ABSTENTION'}[raw_decision]
                    # A failed/unfinished run cannot publish even a valid individual answer.
                    selected = run_status == 'COMPLETED' and bool(item.get('selected'))
                else:
                    decision, confidence, state = 'Erreur technique', None, 'Archive invalide'
            elif state == 'RECEIVED':
                decision = 'En attente de validation'
            else:
                decision = 'Erreur technique'
        elif run_status == 'RUNNING':
            decision, state = 'En attente', 'En cours'
        last_price, price_date = _last_archived_price(candidate, trade_date)
        rows.append({'Rang Oracle': int(candidate['oracle_rank']),
            'Symbole': candidate['symbol'], 'Dernier prix ($)': last_price, 'Date du prix': price_date,
            'Score Oracle': float(candidate['oracle_score']),
            'Avis LLM': decision,
            'Confiance LLM (%)': round(confidence * 100, 2) if confidence is not None else None,
            'Retenu par le filtre': selected,
            'Motif de non-sélection': _non_selection_reason(selected=selected, parsed=parsed,
                state=state, run_status=run_status, config=config,
                quota_excluded=candidate['symbol'] in quota_excluded),
            'État de l’analyse': state})
    return rows


def load_prediction_review(engine, *, trade_date, batch_id, symbol_source,
                          account_id='default', capital_preset_key='capital_2001_5000', limit=10,
                          analysis_run_id=None):
    """Latest attempt for this exact scope, never latest successful/other scope.

    Scope comes from the archived input, not the mutable current Oracle table.
    Research retries are excluded. No raw responses or API requests are loaded.
    """
    if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
        raise ValueError('Vue Oracle/LLM réservée au marché US')
    with engine.connect() as conn:
        query = select(runs.c.run_id, runs.c.trade_date, runs.c.batch_id, runs.c.status,
            runs.c.account_id, runs.c.started_at, runs.c.completed_at,
            runs.c.config_json, runs.c.input_json, runs.c.selected_json,
            runs.c.risk_run_id, runs.c.risk_started_at).where(
                runs.c.trade_date == trade_date, runs.c.batch_id == batch_id,
                runs.c.account_id == account_id).order_by(runs.c.started_at.desc(), runs.c.run_id.desc())
        if analysis_run_id is not None:
            query = query.where(runs.c.run_id == analysis_run_id)
        run = snapshot = None
        for record in conn.execute(query).mappings():
            archived = _object(record['input_json'])
            if archived.get('research_only'):
                continue
            if (archived.get('symbol_source') == symbol_source
                    and archived.get('capital_preset_key') == capital_preset_key):
                run, snapshot = dict(record), archived
                break
        if run is None:
            return None
        items = [dict(row) for row in conn.execute(select(assessments.c.symbol,
            assessments.c.status, assessments.c.assessment_json, assessments.c.selected)
            .where(assessments.c.run_id == run['run_id'])).mappings()]
    config = _object(run.pop('config_json'))
    run.pop('input_json')
    provider = config.get('provider', 'openai')
    run['provider_label'] = 'DeepSeek' if provider == 'deepseek' else 'GPT' if provider == 'openai' else str(provider)
    run['model'] = config.get('deepseek_model') if provider == 'deepseek' else config.get('model')
    selected_symbols = json.loads(run.pop('selected_json') or 'null')
    run['rows'] = review_rows(snapshot.get('candidates'), items, run_status=run['status'], limit=limit,
        config=config, selected_symbols=selected_symbols, trade_date=run['trade_date'])
    run['rows'] = add_company_names(engine, run['rows'])
    run['candidate_count'] = len(snapshot['candidates'])
    return run
