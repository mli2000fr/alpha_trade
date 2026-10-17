"""Serve path-amplitude scores, strictly causal folds, no directional inference."""
from pathlib import Path
import json
import logging
from hashlib import sha256

import numpy as np
import pandas as pd
from sqlalchemy import text

from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle_path import MODE, TARGET, HORIZON
from modelFactory.oracle_path.train import digest, restore_ranks, model_probabilities, select_champion
from modelFactory.oracle_path.backend import CHOICES, NAMES, DECLARATIONS, candidates_for, selection_policy

LOGGER = logging.getLogger(__name__)


def model_root(artifacts_dir, batch_id):
    batch = str(batch_id or '').strip()
    if not batch or Path(batch).name != batch or '/' in batch or '\\' in batch:
        raise ValueError('Batch Oracle parcours invalide')
    root = Path(artifacts_dir)
    return (root if root.name == batch else root/batch)/'oracle_path'


def load_contract(artifacts_dir, batch_id):
    root = model_root(artifacts_dir, batch_id)
    protocol, profile, report = [json.loads((root/n).read_text(encoding='utf-8'))
        for n in ('protocol.json', 'feature_profile.json', 'report.json')]
    frozen = {k: v for k, v in protocol.items() if k != 'fingerprint'}
    if protocol.get('fingerprint') != sha256(json.dumps(frozen, sort_keys=True, default=str).encode()).hexdigest():
        raise ValueError('Empreinte du protocole Oracle parcours invalide')
    if (protocol.get('batch_id') != batch_id or protocol.get('mode') != MODE
            or protocol.get('target') != TARGET or protocol.get('horizon') != HORIZON
            or report.get('status') != 'completed' or report.get('batch_id') != batch_id
            or report.get('mode') != MODE or profile.get('mode') != MODE
            or any(p.get('serving_ready') is not True for p in (protocol, profile, report))):
        raise ValueError('Contrat Oracle parcours terminé H20 requis')
    columns = profile.get('feature_columns') or []
    if not columns or len(columns) != len(set(columns)) or profile.get('target') != TARGET:
        raise ValueError('Profil Oracle parcours invalide')
    if profile.get('generator_options') != protocol.get('generator_options'):
        raise ValueError('Générateur du profil différent du training')
    requested=protocol.get('training_backend')
    if requested is not None:
        if (requested not in CHOICES or protocol.get('backend')!=DECLARATIONS[requested]
                or profile.get('training_backend')!=requested or report.get('training_backend')!=requested
                or protocol.get('champion_selection')!=selection_policy(requested)):
            raise ValueError('Contrat de backend Oracle parcours incohérent')
    folds = {}
    for folder in sorted((root/'folds').iterdir()):
        if not (folder/'done.json').is_file():
            continue
        done = json.loads((folder/'done.json').read_text(encoding='utf-8'))
        champion = done.get('champion') or {'backend': 'lightgbm', 'model_file': 'path_model.txt'}
        backend, name = champion.get('backend'), champion.get('model_file')
        if {'lightgbm': 'path_model.txt', 'catboost': 'catboost_model.cbm'}.get(backend) != name:
            raise ValueError('Backend/poids Oracle parcours invalide')
        if requested is not None:
            required=candidates_for(requested)
            validation=done.get('validation_candidates',{})
            if (set(validation)!=set(required) or champion.get('selection')!=selection_policy(requested)
                    or (requested!='auto' and backend!=requested)):
                raise ValueError('Backend du fold différent du choix explicite Oracle parcours')
            if requested=='auto' and select_champion(validation)!=backend:
                raise ValueError('Sélection automatique Oracle parcours invalide')
            for candidate_backend in required:
                candidate=NAMES[candidate_backend]
                checksum=done.get('files',{}).get(candidate)
                if not checksum or not (folder/candidate).is_file() or digest(folder/candidate)!=checksum:
                    raise ValueError('Poids du backend Oracle parcours absents/corrompus')
        if protocol.get('backend') == 'lightgbm_catboost_cpu':
            validation = done.get('validation_candidates', {})
            if (set(validation) != {'lightgbm', 'catboost'} or select_champion(validation) != backend
                    or champion.get('selection') != 'validation_auc; exact_tie_lightgbm'):
                raise ValueError('Sélection de champion Oracle parcours invalide')
            for candidate in ('path_model.txt', 'catboost_model.cbm'):
                checksum = done.get('files', {}).get(candidate)
                if not checksum or not (folder/candidate).is_file() or digest(folder/candidate) != checksum:
                    raise ValueError('Comparaison Oracle parcours incomplète/corrompue')
        expected = done.get('files', {}).get(name)
        if not expected or not (folder/name).is_file() or digest(folder/name) != expected:
            raise ValueError(f'Poids Oracle parcours corrompus : {folder.name}')
        metrics = done['metrics']
        if metrics.get('fold_start') != folder.name:
            raise ValueError('Fold Oracle parcours ambigu')
        folds[folder.name] = dict(metrics=metrics, model_file=str(folder/name), model_sha256=expected, backend=backend)
    if not folds or len(folds) != int(report.get('n_folds', -1)):
        raise ValueError('Folds Oracle parcours incomplets')
    return root, protocol, profile, folds


def discover_path_batches(artifacts_dir='artifacts/models'):
    """List completed technically connected models; inference still validates hashes."""
    result = []
    for p in Path(artifacts_dir).glob('*/oracle_path/report.json'):
        try:
            report = json.loads(p.read_text(encoding='utf-8'))
            if report.get('status') == 'completed' and report.get('serving_ready') is True:
                result.append(p.parent.parent.name)
        except (OSError, ValueError, TypeError):
            continue
    return sorted(result)


def select_fold(day, folds):
    day = pd.Timestamp(day)
    eligible = []
    for name, fold in folds.items():
        metrics = fold['metrics']
        if pd.Timestamp(metrics['fold_start']) <= day and all(
            pd.notna(pd.Timestamp(metrics.get(k))) and pd.Timestamp(metrics[k]) < day
            for k in ('train_available_max', 'val_available_max')):
            eligible.append(name)
    if not eligible:
        raise ValueError(f'Aucun fold causal avant {day.date()}; avancer le début du backtest')
    return max(eligible, key=pd.Timestamp)


def build_inference_features(engine, universe, start, end, options):
    # Build XS ranks on the TRAINING population, not on the selected/scored
    # subset or on chunks. Never load any future path or target to predict.
    parts = []
    for offset in range(0, len(universe), 25):
        frame = build_feature_matrix(engine, universe[offset:offset+25], start_date=start,
            end_date=end, generator_options={**options, 'enable_cross_sectional_ranks': False})
        if not frame.empty:
            parts.append(frame.loc[pd.to_datetime(frame.date).between(pd.Timestamp(start), pd.Timestamp(end))])
    if not parts:
        return pd.DataFrame()
    return restore_ranks(pd.concat(parts, ignore_index=True), options)


_LINEAGE_DDL = """CREATE TABLE IF NOT EXISTS alpha_trade.oracle_path_prediction_lineage (
 prediction_date DATE NOT NULL, symbol VARCHAR(20) NOT NULL, batch_id VARCHAR(255) NOT NULL,
 fold_start DATE NOT NULL, model_available_date DATE NOT NULL,
 target_name VARCHAR(64) NOT NULL, target_horizon INT NOT NULL,
 model_sha256 CHAR(64) NOT NULL, feature_profile_sha256 CHAR(64) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(prediction_date,symbol,batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def write_path_predictions(engine, scores, batch_id):
    """Score and lineage commit atomically; terminal labels always NULL."""
    from modelFactory.oracle.predictions_store import ensure_oracle_predictions_table, _INSERT
    if scores.empty:
        return 0
    rows = []
    for r in scores.to_dict('records'):
        if not 0 <= float(r['proba_extreme']) <= 1 or pd.Timestamp(r['model_available_date']) >= pd.Timestamp(r['date']):
            raise ValueError('Score ou disponibilité Oracle parcours invalide')
        rows.append(dict(prediction_date=str(r['date'])[:10], symbol=r['symbol'], batch_id=batch_id,
            proba_extreme=float(r['proba_extreme']), future_return=None, oracle_extreme10=None,
            fold_start=r['fold_start'], model_available_date=r['model_available_date'],
            target_name=TARGET, target_horizon=HORIZON, model_sha256=r['model_sha256'],
            feature_profile_sha256=r['feature_profile_sha256']))
    ensure_oracle_predictions_table(engine)
    with engine.begin() as conn:
        conn.execute(text(_LINEAGE_DDL))
    insert = text("""INSERT INTO alpha_trade.oracle_path_prediction_lineage
        (prediction_date,symbol,batch_id,fold_start,model_available_date,target_name,target_horizon,
         model_sha256,feature_profile_sha256)
        VALUES (:prediction_date,:symbol,:batch_id,:fold_start,:model_available_date,:target_name,
          :target_horizon,:model_sha256,:feature_profile_sha256)
        ON DUPLICATE KEY UPDATE fold_start=VALUES(fold_start),model_available_date=VALUES(model_available_date),
         model_sha256=VALUES(model_sha256),feature_profile_sha256=VALUES(feature_profile_sha256)""")
    with engine.begin() as conn:
        conn.execute(_INSERT, rows)
        conn.execute(insert, rows)
    return len(rows)


def predict_oracle_path_history(engine, batch_id, start_date, end_date, *, artifacts_dir='artifacts/models',
                                symbols=None, horizon=None, persist_chunk_dates=20):
    root, protocol, profile, folds = load_contract(artifacts_dir, batch_id)
    if horizon not in (None, HORIZON):
        raise ValueError('Oracle parcours : horizon H20 fixe')
    if pd.Timestamp(start_date) > pd.Timestamp(end_date):
        raise ValueError('Plage Oracle parcours inversée')
    if getattr(getattr(engine, 'url', None), 'database', None) not in (None, 'alpha_trade'):
        raise ValueError('Oracle parcours US : base alpha_trade requise')
    universe = sorted(set(protocol['universe']))
    wanted = set(universe if symbols is None else [str(s).strip().upper() for s in symbols])
    if not wanted or wanted-set(universe):
        raise ValueError(f'Univers vide ou hors contrat du modèle : {sorted(wanted-set(universe))[:20]}')
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions = nyse_sessions(pd.Timestamp(start_date).date(), pd.Timestamp(end_date).date())
    if not len(sessions):
        raise ValueError('Aucune séance US demandée')
    # Preflight the entire range before writing: never use a future first fold.
    schedule = {day: select_fold(day, folds) for day in sessions}
    columns = profile['feature_columns']
    profile_hash = digest(root/'feature_profile.json')
    cache, persisted, observed = {}, 0, set()
    for offset in range(0, len(sessions), max(1, int(persist_chunk_dates))):
        chunk = sessions[offset:offset+max(1, int(persist_chunk_dates))]
        features = build_inference_features(engine, universe, str(chunk[0].date()), str(chunk[-1].date()),
            profile['generator_options'])
        if features.empty or set(columns)-set(features):
            raise ValueError('Features Oracle parcours absentes/incomplètes')
        features['date'] = pd.to_datetime(features.date).dt.normalize()
        features = features.loc[features.symbol.isin(wanted) & features.date.isin(chunk)].copy()
        if features.duplicated(['date', 'symbol']).any() or set(chunk)-set(features.date):
            raise ValueError('Séance absente ou clés de features dupliquées')
        features[columns] = features[columns].replace([np.inf, -np.inf], np.nan).astype(np.float32)
        if features[columns].isna().all(axis=1).any():
            raise ValueError('Ligne de features entièrement manquante')
        scores = features[['date', 'symbol']].copy()
        scores['fold_start'] = scores.date.map(schedule)
        for name, group in scores.groupby('fold_start'):
            if name not in cache:
                if folds[name]['backend'] == 'catboost':
                    from catboost import CatBoostClassifier
                    cache[name] = CatBoostClassifier().load_model(folds[name]['model_file'])
                    feature_names = cache[name].feature_names_
                else:
                    import lightgbm as lgb
                    cache[name] = lgb.Booster(model_file=folds[name]['model_file'])
                    feature_names = cache[name].feature_name()
                if feature_names != columns:
                    raise ValueError('Ordre des features différent du modèle')
            values = model_probabilities(cache[name], folds[name]['backend'], features.loc[group.index, columns])
            scores.loc[group.index, 'proba_extreme'] = values
            metrics = folds[name]['metrics']
            available = max(pd.Timestamp(metrics[k]) for k in ('train_available_max', 'val_available_max'))
            scores.loc[group.index, 'model_available_date'] = str(available.date())
            scores.loc[group.index, 'model_sha256'] = folds[name]['model_sha256']
        scores['feature_profile_sha256'] = profile_hash
        persisted += write_path_predictions(engine, scores, batch_id)
        observed.update(scores.symbol)
        LOGGER.info('Oracle parcours batch=%s dates=%s/%s persistés=%s', batch_id,
            min(offset+len(chunk), len(sessions)), len(sessions), persisted)
    return dict(status='completed', batch_id=batch_id, n_rows=persisted, n_dates=len(sessions),
        n_symbols=len(observed), target=TARGET, horizon=HORIZON, directional=False)
