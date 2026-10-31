"""Read-only compatibility and session freshness for the amplitude Oracle.

The per-symbol ternary champion registry is not this model's publication
contract. Never manufacture that registry or interpret its rank as P(LONG).
"""
from datetime import date, datetime, timezone
import math

import pandas as pd
from sqlalchemy import bindparam, text


def build_entries(builder, candidates, prices, sector_map, trade_date, return_matrix):
    """Explicit LONG amplitude strategy, with native risk and real account state.

    Oracle ranks and options activity are not probabilities or expected edges.
    The existing oracle_pure_long contract preserves sizing, held/pending
    exposure, correlation, factor and account limits without an edge optimizer.
    """
    from risk_management.models import SelectionScore
    from service.market.new_entry_data_guard import validate_entry_prices
    if any(c.side != 'long' or c.trade_date != trade_date or
           c.lineage.get('score_semantics') != 'amplitude_rank_not_directional_probability'
           for c in candidates):
        raise ValueError('Candidat hors contrat Oracle amplitude LONG/date')
    rejected = validate_entry_prices(prices, [c.symbol for c in candidates], trade_date)
    if rejected:
        raise ValueError(f'Prix/ATR/ADV J non qualifié: {rejected}')
    selections = [SelectionScore(symbol=c.symbol,sector=sector_map.get(c.symbol,'Unknown'),
        score_used=c.p_side,score_source='oracle_amplitude_rank',snapshot_date=trade_date,
        selection_rank=c.side_rank,side='buy',selector_signal_mode='oracle_pure_long',
        universe_run_id=c.universe_run_id,
        selection_explanation='Oracle amplitude LONG strategy; not a directional probability or expected edge')
        for c in candidates]
    return builder.build(selections,prices,return_matrix=return_matrix,trade_date=trade_date,
                         selection_policy='oracle_pure_long')


def check_compatibility(engine, predictions, *, batch_id, trade_date,
                        artifacts_dir='artifacts/models', now=None):
    result = dict(compatible=False, issues=[], champion_count=0, model_versions={},
                  source='oracle_path_signed_contract', batch_id=batch_id)
    try:
        from modelFactory.oracle_path.predict import load_contract, select_fold
        from modelFactory.oracle_path.train import digest
        from service.options_directional.runner import _load_oracle_rows, validate_oracle_lineage
        from service.options_directional.store import validate_window
        from service.market.new_entry_data_guard import entry_sessions
        from modelFactory.synthesize_oracle_predictions import _SYNTH_RUN_SUFFIX

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('Horloge Oracle sans fuseau explicite')
        now = now.astimezone(timezone.utc)
        day = date.fromisoformat(str(trade_date))
        if engine.url.database != 'alpha_trade':
            raise ValueError('Contrat Oracle risque réservé à alpha_trade US')
        # EOD freshness is a session contract, not the intraday five-minute
        # proxy formerly constructed as midnight of J. Fresh SIP quotes retain
        # their separate liquidity/executor/watcher checks.
        entry_sessions(day, now=now, min_sessions=21)
        validate_window(day, now=now)
        root, protocol, profile, folds = load_contract(artifacts_dir, batch_id)
        eligible_fold = select_fold(day, folds)
        symbols = sorted(predictions)
        if not symbols or set(symbols)-set(protocol['universe']):
            raise ValueError('Prédictions Oracle vides ou symboles hors contrat')
        run_id = batch_id + _SYNTH_RUN_SUFFIX
        for symbol, pred in predictions.items():
            if (pred.symbol != symbol or pred.run_id != run_id or pred.prediction_date != day
                    or pred.predicted_side not in ('long', 'flat') or pred.research_only):
                raise ValueError(f'Prédiction Oracle incompatible : {symbol}')
        mysql = engine.dialect.name == 'mysql'
        cutoff_sql = ('UNIX_TIMESTAMP(created_at)<=:cutoff_epoch' if mysql else 'created_at<=:cutoff')
        query = text(f'''SELECT symbol,source,predicted_side FROM model_predictions
            WHERE prediction_date=:day AND run_id=:run AND symbol IN :symbols AND {cutoff_sql}''')
        query = query.bindparams(bindparam('symbols', expanding=True))
        with engine.connect() as conn:
            rows = _load_oracle_rows(conn, dialect=engine.dialect.name, batch_id=batch_id,
                                    day=day, symbols=symbols, cutoff=now)
            policies = [dict(r) for r in conn.execute(query, dict(day=day, run=run_id, symbols=symbols,
                cutoff=now.replace(tzinfo=None), cutoff_epoch=now.timestamp())).mappings()]
        if (len(rows) != len(symbols) or {r['symbol'] for r in rows} != set(symbols)
                or len(policies) != len(symbols) or {r['symbol'] for r in policies} != set(symbols)):
            raise ValueError('Scores/lineage/politique Oracle manquants, dupliqués ou futurs')
        validate_oracle_lineage(rows, day, digest(root/'feature_profile.json'), folds, horizon=protocol['horizon'])
        for row in rows:
            if (str(pd.Timestamp(row['fold_start']).date()) != eligible_fold
                    or not math.isfinite(float(row['proba_extreme']))
                    or not 0 <= float(row['proba_extreme']) <= 1):
                raise ValueError('Fold ou score Oracle différent du contrat causal')
        for row in policies:
            if row['source'] != 'oracle_path_policy' or row['predicted_side'] != predictions[row['symbol']].predicted_side:
                raise ValueError('Origine ou direction de la politique Oracle incompatible')
        result.update(compatible=True, champion_count=1, validated_fold_count=len(folds), fold_start=eligible_fold,
                      protocol_sha256=protocol['fingerprint'], horizon=protocol['horizon'],
                      score_semantics='amplitude_rank_not_directional_probability',
                      session_freshness=dict(allowed=True, signal_date=str(day),
                                             checked_at_utc=now.isoformat(),
                                             policy='closed_session_J_before_next_open'))
    except Exception as exc:
        result['issues'] = [f'oracle_path_contract_invalid: {exc}']
    return result
