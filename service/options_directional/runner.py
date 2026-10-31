import logging
from datetime import datetime, timezone, date
import pandas as pd
from sqlalchemy import bindparam, text

from .config import load_options_filter_config
from .features import select_top
from .store import seal, validate_window

LOGGER = logging.getLogger(__name__)


class OracleCoverageError(ValueError):
    """A genuine incomplete prediction set; never publish an options selection."""
    def __init__(self, *, rows, symbols, batch_id, trade_date, required_ratio):
        scored = {r['symbol'] for r in rows}
        self.diagnostics = dict(batch_id=batch_id, trade_date=str(trade_date),
            requested_count=len(symbols), prediction_count=len(rows),
            coverage_ratio=len(scored)/len(symbols) if symbols else 0.,
            required_ratio=required_ratio, missing_symbols=sorted(set(symbols)-scored))
        d = self.diagnostics
        super().__init__(f"Couverture Oracle insuffisante : {len(scored)}/{len(symbols)} "
            f"({d['coverage_ratio']:.2%}, minimum {required_ratio:.2%}) ; "
            f"séance {trade_date}, modèle {batch_id}. "
            f"Titres sans prédiction : {', '.join(d['missing_symbols'][:12])}"
            + ('…' if len(d['missing_symbols']) > 12 else ''))


def _load_oracle_rows(conn, *, dialect, batch_id, day, symbols, cutoff):
    if cutoff.tzinfo is None:
        raise ValueError('Cutoff Oracle explicitement horodaté requis')
    # MySQL TIMESTAMP is rendered in the SQL session zone (often SYSTEM/Paris).
    # Compare physical instants, not a local SQL timestamp to a naive UTC bind.
    # No global/session timezone change and no assumption of a fixed DST offset.
    mysql = dialect == 'mysql'
    projection = 'UNIX_TIMESTAMP(p.created_at) AS created_at_epoch' if mysql else 'p.created_at'
    p_cutoff = 'UNIX_TIMESTAMP(p.created_at)<=:cutoff_epoch' if mysql else 'p.created_at<=:cutoff'
    l_cutoff = 'UNIX_TIMESTAMP(l.created_at)<=:cutoff_epoch' if mysql else 'l.created_at<=:cutoff'
    query = text(f'''SELECT p.symbol,p.proba_extreme,p.fold_start,{projection},
        l.fold_start lineage_fold_start,l.model_available_date,l.target_name,l.target_horizon,
        l.model_sha256,l.feature_profile_sha256 FROM oracle_extreme_predictions p
        LEFT JOIN oracle_path_prediction_lineage l ON l.prediction_date=p.prediction_date
          AND l.symbol=p.symbol AND l.batch_id=p.batch_id AND {l_cutoff}
        WHERE p.batch_id=:batch AND p.prediction_date=:day AND p.symbol IN :symbols AND {p_cutoff}
        ORDER BY p.proba_extreme DESC,p.symbol ASC''').bindparams(bindparam('symbols', expanding=True))
    utc = cutoff.astimezone(timezone.utc)
    rows = [dict(r) for r in conn.execute(query, dict(batch=batch_id, day=day, symbols=symbols,
        cutoff=utc.replace(tzinfo=None), cutoff_epoch=utc.timestamp())).mappings()]
    if mysql:
        for row in rows:
            row['created_at'] = datetime.fromtimestamp(float(row.pop('created_at_epoch')), timezone.utc)
    return rows


def validate_oracle_lineage(rows, day, profile_hash, folds, *, horizon=20):
    from modelFactory.oracle_path import target_name
    target = target_name(horizon)
    for row in rows:
        fold_name = str(pd.Timestamp(row['fold_start']).date())
        fold = folds.get(fold_name)
        if fold is None:
            raise ValueError('Fold Oracle absent du contrat')
        available = max(pd.Timestamp(fold['metrics'][k]) for k in ('train_available_max', 'val_available_max'))
        if (row['target_name'] != target or row['target_horizon'] != horizon
                or pd.Timestamp(row['lineage_fold_start']) != pd.Timestamp(row['fold_start'])
                or not available < pd.Timestamp(day)
                or pd.Timestamp(fold_name) > pd.Timestamp(day)
                or pd.Timestamp(row['model_available_date']) != available.normalize()
                or row['feature_profile_sha256'] != profile_hash
                or row['model_sha256'] != fold['model_sha256']):
            raise ValueError('Lineage Oracle manquante, incohérente ou non causale')


def load_inputs(engine, *, batch_id, trade_date, symbol_source, capital_preset_key, artifacts_dir,
                config, cutoff):
    from modelFactory.db_registry import load_symbols_for_source
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.train import digest as file_digest
    symbols = sorted(set(load_symbols_for_source(engine, symbol_source, trade_date=trade_date,
                                                 capital_preset_key=capital_preset_key)))
    if not symbols:
        raise ValueError('Univers Oracle vide')
    # Validate the serving contract without a historical loader that reads labels
    # or creates missing tables on read errors. This service issues SELECT only.
    root, protocol, _, folds = load_contract(artifacts_dir, batch_id)
    profile_hash = file_digest(root/'feature_profile.json')
    day = date.fromisoformat(str(trade_date))
    with engine.connect() as conn:
        oracle = _load_oracle_rows(conn, dialect=engine.dialect.name, batch_id=batch_id, day=day,
                                  symbols=symbols, cutoff=cutoff)
        LOGGER.info('Couverture Oracle séance=%s modèle=%s disponibles_au_cutoff_UTC=%d/%d minimum=%.2f%%',
            day, batch_id, len(oracle), len(symbols), 100*config.min_oracle_coverage_ratio)
        if len(oracle) / len(symbols) < config.min_oracle_coverage_ratio:
            raise OracleCoverageError(rows=oracle, symbols=symbols, batch_id=batch_id, trade_date=day,
                                      required_ratio=config.min_oracle_coverage_ratio)
        validate_oracle_lineage(oracle, day, profile_hash, folds, horizon=protocol['horizon'])
        # Validate the complete ranking before limiting, never backfill N+1 for missing options.
        select_top(oracle, {}, config)
        top = [r['symbol'] for r in oracle[:config.oracle_top_n]]
        from .history import read_options_evidence
        features,raw=read_options_evidence(conn,top,day,cutoff)
    return oracle, features, dict(universe=symbols, oracle=oracle, **raw)


def analyze(engine, *, run_id, batch_id, trade_date, symbol_source, capital_preset_key,
            artifacts_dir='artifacts/models', config=None, now=None, root=None,producer_account_id='default'):
    config = config or load_options_filter_config()
    if not config.enabled:
        raise ValueError('options_directional_filter.enabled=false')
    injected_clock = now is not None
    now = now or datetime.now(timezone.utc)
    validate_window(trade_date, now)
    oracle, features, inputs = load_inputs(engine, batch_id=batch_id, trade_date=trade_date,
        symbol_source=symbol_source, capital_preset_key=capital_preset_key, artifacts_dir=artifacts_dir,
        config=config, cutoff=now)
    rows = select_top(oracle, features, config)
    selected = [r['symbol'] for r in rows if r['selected']]
    validate_window(trade_date, now if injected_clock else datetime.now(timezone.utc))
    report = seal(run_id, dict(run_id=run_id, status='COMPLETED', trade_date=str(trade_date),
        batch_id=batch_id, account_id=producer_account_id, selection_scope='SHARED_MARKET',symbol_source=symbol_source,
        capital_preset_key=capital_preset_key, config=config.snapshot(), cutoff_utc=now.isoformat(),
        rows=rows, selected=selected, covered=sum(r['reason'] != 'MISSING_OR_STALE_OPTIONS' for r in rows),
        semantics='experimental_relative_options_activity_not_probability', side_policy='LONG_ONLY',
        zero_selection_is_valid=True), inputs, root=root)
    LOGGER.info('OPTIONS_FILTER run=%s TOP=%d couverts=%d retenus_LONG=%d exclus=%d %s',
                run_id, len(rows), report['covered'], len(selected), len(rows)-len(selected), ','.join(selected) or 'aucun')
    return report
