"""Step 11 read-only view: exact LLM → risk link, never a SQL latest target."""
import math
import json

from sqlalchemy import MetaData, Table, inspect, or_, select

from database.run_business_summaries import _build_summary_table
from service.llm_directional.repository import runs
from ihm.services.llm_prediction_review import _day, _object, add_company_names, load_prediction_review


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _risk_rows(engine, name, run_id, day, account):
    # Some deployed schemas lack optional side/reason_code columns. Never
    # migrate or fabricate them just to display this view.
    table = Table(name, MetaData(), autoload_with=engine)
    columns = ('symbol', 'decision', 'reason', 'reason_code', 'side', 'entry_price',
        'price_asof_date', 'proposed_shares', 'approved_shares', 'shares',
        'target_notional', 'stop_price_initial', 'take_profit_price')
    query = select(*(table.c[c] for c in columns if c in table.c)).where(
        table.c.run_id == run_id, table.c.trade_date == day, table.c.account_id == account)
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(query).mappings()]
    if len({r['symbol'] for r in rows}) != len(rows):
        raise ValueError('Décisions/cibles risque ambiguës pour ce run')
    return rows


def _summary(engine, run_id, day, account):
    inspector = inspect(engine)
    for name in ('run_summaries', 'run_business_summaries'):
        if not inspector.has_table(name):
            continue
        table = _build_summary_table(name)
        with engine.connect() as conn:
            row = conn.execute(select(table.c.status, table.c.summary_json).where(
                table.c.step_key == 'risk_management', table.c.account_id == account,
                table.c.trade_date == day, or_(table.c.summary_run_id == run_id,
                table.c.entity_run_id == run_id)).order_by(
                    (table.c.summary_run_id == run_id).desc(), table.c.updated_at.desc())).mappings().first()
        if row:
            summary = _object(row['summary_json'])
            if (summary.get('run_id') != run_id or _day(summary.get('trade_date')) != day):
                raise ValueError('Résumé risque incompatible avec son identifiant/date')
            return summary, str(row['status']).upper()
    return {}, 'NON CONFIRMÉ'


def _universe_exclusions(engine, summary, day, symbols):
    """Only the exact archived universe may explain a pre-decision exclusion."""
    identifier = summary.get('universe_run_id')
    inspector = inspect(engine)
    if not identifier or not symbols or not all(inspector.has_table(t) for t in (
            'tradable_universe_runs', 'tradable_universe_history')):
        return {}
    history = Table('tradable_universe_history', MetaData(), autoload_with=engine)
    universe = Table('tradable_universe_runs', MetaData(), autoload_with=engine)
    with engine.connect() as conn:
        rows = conn.execute(select(history.c.symbol, history.c.tradability_reason_code).join(
            universe, universe.c.universe_run_id == history.c.universe_run_id).where(
                universe.c.universe_run_id == identifier, universe.c.snapshot_date == day,
                universe.c.status == 'completed', history.c.is_tradable == 0,
                history.c.symbol.in_(symbols))).mappings().all()
    labels = {'close_below_minimum': 'Cours inférieur au minimum autorisé',
        'spread_above_maximum': 'Spread supérieur au maximum autorisé',
        'quote_unavailable': 'Quote qualifiée indisponible',
        'market_cap_unavailable': 'Capitalisation indisponible',
        'market_cap_stale': 'Capitalisation trop ancienne',
        'market_cap_below_minimum': 'Capitalisation inférieure au minimum autorisé'}
    return {r['symbol']: 'Exclu de l’univers tradable utilisé : '
        + labels.get(r['tradability_reason_code'], str(r['tradability_reason_code']))
        + f" ({r['tradability_reason_code']})" for r in rows}


def risk_review_rows(llm_rows, decisions, targets, *, status, summary=None, universe_exclusions=None,
                     selected_symbols=None):
    summary, exclusions = summary or {}, universe_exclusions or {}
    base = {r['Symbole']: dict(r) for r in llm_rows}
    dec, tgt = {r['symbol']: r for r in decisions}, {r['symbol']: r for r in targets}
    symbols = set(selected_symbols) if selected_symbols is not None else set(dec) | set(tgt)
    if selected_symbols is not None and not symbols.issubset(base):
        raise ValueError('Titre retenu à l’étape 10 absent du snapshot LLM')
    rows = []
    for symbol in sorted(symbols, key=lambda s: (base.get(s, {}).get('Rang Oracle') or 999999, s)):
        original = base.get(symbol, {})
        row = dict(original) if original else {'Rang Oracle': None, 'Symbole': symbol,
            'Dernier prix ($)': None, 'Date du prix': None, 'Score Oracle': None,
            'Avis LLM': 'Hors snapshot LLM' if llm_rows else 'Sans filtre LLM',
            'Confiance LLM (%)': None, 'Retenu par le filtre': None, 'Motif de non-sélection': '—'}
        d, t = dec.get(symbol), tgt.get(symbol)
        values = dict(d or {}, **{k:v for k,v in (t or {}).items() if v is not None})
        quantity = _number(t.get('shares')) if t else _number((d or {}).get('approved_shares'))
        published = status == 'COMPLETED' and t is not None and (quantity or 0) > 0
        decision = (d or {}).get('decision') or ('Cible enregistrée' if t else None)
        reason = (d or {}).get('reason') or (d or {}).get('reason_code')
        if d is None and t is None:
            if symbol in exclusions:
                decision, reason = 'Exclu avant sizing', exclusions[symbol]
            elif symbol in (summary.get('new_entry_data_rejections') or {}):
                decision, reason = 'Données d’entrée non qualifiées', str(summary['new_entry_data_rejections'][symbol])
            else:
                decision = 'En attente / non finalisé' if status != 'COMPLETED' else 'Aucune décision enregistrée'
                reason = 'Aucune décision ni cible publiée pour ce titre ; aucun motif individuel disponible'
        if status != 'COMPLETED' and (d or t):
            reason = 'Run non confirmé terminé : résultat partiel. ' + str(reason or '')
        side = str(values.get('side') or '').lower()
        row.update({'Décision risque': decision, 'Cible publiée': published,
            'Sens cible': {'buy':'LONG', 'long':'LONG', 'sell':'SHORT', 'short':'SHORT'}.get(side),
            'Quantité validée': quantity, 'Prix de référence risque ($)': _number(values.get('entry_price')),
            'Date du prix risque': _day(values.get('price_asof_date')),
            'Montant cible ($)': _number(values.get('target_notional')),
            'SL initial ($)': _number(values.get('stop_price_initial')),
            'TP prix ($)': _number(values.get('take_profit_price')), 'Motif risque': reason or 'Motif non renseigné'})
        row.pop('État de l’analyse', None)
        row.pop('Retenu par le filtre', None)
        row.pop('Motif de non-sélection', None)
        rows.append(row)
    return rows


def load_risk_prediction_review(engine, *, trade_date, account_id='default',
                               llm_run_id=None, risk_run_id=None):
    if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
        raise ValueError('Vue risque réservée au marché US')
    day = _day(trade_date)
    if day is None or not (llm_run_id or risk_run_id):
        raise ValueError('Date et identifiant risque/LLM exacts requis')
    llm, selected_symbols = None, None
    if llm_run_id:
        with engine.connect() as conn:
            record = conn.execute(select(runs.c.batch_id, runs.c.input_json, runs.c.risk_run_id,
                runs.c.selected_json, runs.c.status).where(
                runs.c.run_id == llm_run_id, runs.c.trade_date == day,
                runs.c.account_id == account_id)).mappings().one()
        snapshot = _object(record['input_json'])
        llm = load_prediction_review(engine, trade_date=day, batch_id=record['batch_id'],
            symbol_source=snapshot.get('symbol_source'), capital_preset_key=snapshot.get('capital_preset_key'),
            account_id=account_id, analysis_run_id=llm_run_id, limit=100)
        if llm is None or (risk_run_id and record['risk_run_id'] != risk_run_id):
            raise ValueError('Liaison exacte LLM → risque absente ou incompatible')
        selected_symbols = json.loads(record['selected_json'] or '[]') if record['status']=='COMPLETED' else []
        if (not isinstance(selected_symbols,list) or any(not isinstance(s,str) for s in selected_symbols)
                or len(set(selected_symbols)) != len(selected_symbols)):
            raise ValueError('Liste des titres retenus à l’étape 10 invalide')
        risk_run_id = record['risk_run_id']
    summary, status, decisions, targets, exclusions = {}, 'NON LIÉ', [], [], {}
    if risk_run_id:
        summary, status = _summary(engine, risk_run_id, day, account_id)
        if summary.get('llm_filter_run_id') and summary['llm_filter_run_id'] != llm_run_id:
            raise ValueError('Le résumé risque concerne une autre analyse LLM')
        decisions = _risk_rows(engine, 'risk_decisions', risk_run_id, day, account_id)
        targets = _risk_rows(engine, 'portfolio_targets', risk_run_id, day, account_id)
        if llm:
            exclusions = _universe_exclusions(engine, summary, day,
                selected_symbols)
    return dict(run_id=risk_run_id, llm_run_id=llm_run_id, trade_date=str(day), account_id=account_id,
        status=status, provider_label=llm['provider_label'] if llm else None,
        scoring_mode=llm.get('scoring_mode','legacy_confidence') if llm else 'legacy_confidence',
        separate_trend_evidence=llm.get('separate_trend_evidence',False) if llm else False,
        score_thresholds=llm.get('score_thresholds') if llm else None,
        finished_at=summary.get('finished_at'),
        rows=add_company_names(engine, risk_review_rows(llm['rows'] if llm else [], decisions, targets,
            status=status, summary=summary, universe_exclusions=exclusions,selected_symbols=selected_symbols)),
        target_count=len(targets), decision_count=len(decisions))
