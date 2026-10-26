import logging
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
import pandas as pd
from sqlalchemy import bindparam, text

from .config import load_options_filter_config
from .features import build_features, select_top
from .store import seal, validate_window

LOGGER = logging.getLogger(__name__)


def validate_oracle_lineage(rows, day, profile_hash, folds):
    for row in rows:
        fold_name = str(pd.Timestamp(row['fold_start']).date())
        fold = folds.get(fold_name)
        if fold is None:
            raise ValueError('Fold Oracle absent du contrat')
        available = max(pd.Timestamp(fold['metrics'][k]) for k in ('train_available_max', 'val_available_max'))
        if (row['target_name'] != 'oracle_path_extreme20' or row['target_horizon'] != 20
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
    from common.daily_bar_sources import select_daily_bars
    symbols = sorted(set(load_symbols_for_source(engine, symbol_source, trade_date=trade_date,
                                                 capital_preset_key=capital_preset_key)))
    if not symbols:
        raise ValueError('Univers Oracle vide')
    # Validate the serving contract without a historical loader that reads labels
    # or creates missing tables on read errors. This service issues SELECT only.
    root, _, _, folds = load_contract(artifacts_dir, batch_id)
    profile_hash = file_digest(root/'feature_profile.json')
    query = text('''SELECT p.symbol,p.proba_extreme,p.fold_start,p.created_at,
        l.fold_start lineage_fold_start,l.model_available_date,l.target_name,l.target_horizon,
        l.model_sha256,l.feature_profile_sha256 FROM oracle_extreme_predictions p
        LEFT JOIN oracle_path_prediction_lineage l ON l.prediction_date=p.prediction_date
          AND l.symbol=p.symbol AND l.batch_id=p.batch_id AND l.created_at<=:cutoff
        WHERE p.batch_id=:batch AND p.prediction_date=:day AND p.symbol IN :symbols AND p.created_at<=:cutoff
        ORDER BY p.proba_extreme DESC,p.symbol ASC''').bindparams(bindparam('symbols', expanding=True))
    day = date.fromisoformat(str(trade_date))
    start = datetime.combine(day, datetime.min.time(), ZoneInfo('America/New_York')).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    with engine.connect() as conn:
        oracle = [dict(r) for r in conn.execute(query, dict(batch=batch_id, day=day, symbols=symbols,
                    cutoff=cutoff.replace(tzinfo=None))).mappings()]
        if len(oracle) / len(symbols) < config.min_oracle_coverage_ratio:
            raise ValueError(f'Couverture Oracle insuffisante : {len(oracle)}/{len(symbols)}')
        validate_oracle_lineage(oracle, day, profile_hash, folds)
        # Validate the complete ranking before limiting, never backfill N+1 for missing options.
        select_top(oracle, {}, config)
        top = [r['symbol'] for r in oracle[:config.oracle_top_n]]
        params = dict(symbols=top, start=start.replace(tzinfo=None), end=end.replace(tzinfo=None),
                      cutoff=cutoff.replace(tzinfo=None), day=day)
        queries = {
            'snapshots': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
                option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
                FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
                AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
                AND available_at<=:cutoff AND observed_at<=:cutoff''',
            'volumes': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
                FROM stock_option_bars_delayed WHERE provider='alpaca' AND timeframe='30Min'
                AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
                AND bar_timestamp>=:start AND bar_timestamp<:end AND available_at<=:cutoff AND observed_at<=:cutoff''',
            'prices': '''SELECT symbol,date,close,is_filled,data_source FROM stock_bars_daily
                WHERE symbol IN :symbols AND date=:day AND data_source IN ('eodhd_eod','alpaca_sip')''',
        }
        raw = {}
        for key, sql in queries.items():
            raw[key] = [dict(r) for r in conn.execute(text(sql).bindparams(
                bindparam('symbols', expanding=True)), params).mappings()]
    prices = select_daily_bars(pd.DataFrame(raw['prices'])) if raw['prices'] else pd.DataFrame()
    spots = {} if prices.empty else {r.symbol: float(r.close) for r in prices.itertuples()
                                      if not r.is_filled and pd.notna(r.close) and r.close > 0}
    features = build_features(pd.DataFrame(raw['snapshots']), pd.DataFrame(raw['volumes']), spots, day, pd.Timestamp(cutoff))
    return oracle, features, dict(universe=symbols, oracle=oracle, **raw)


def analyze(engine, *, run_id, batch_id, trade_date, symbol_source, capital_preset_key,
            artifacts_dir='artifacts/models', config=None, now=None, root=None):
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
        batch_id=batch_id, account_id='default', symbol_source=symbol_source,
        capital_preset_key=capital_preset_key, config=config.snapshot(), cutoff_utc=now.isoformat(),
        rows=rows, selected=selected, covered=sum(r['reason'] != 'MISSING_OR_STALE_OPTIONS' for r in rows),
        semantics='experimental_relative_options_activity_not_probability', side_policy='LONG_ONLY',
        zero_selection_is_valid=True), inputs, root=root)
    LOGGER.info('OPTIONS_FILTER run=%s TOP=%d couverts=%d retenus_LONG=%d exclus=%d %s',
                run_id, len(rows), report['covered'], len(selected), len(rows)-len(selected), ','.join(selected) or 'aucun')
    return report
