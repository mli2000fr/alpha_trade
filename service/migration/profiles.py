"""Explicit backup scopes; portable module, no application imports or SQL writes."""
import json
from pathlib import Path
import re

import yaml

FULL = 'full'
US_DAILY = 'us_daily'
US_DATABASES = ('alpha_trade',)
DATABASES = ('alpha_trade', 'alpha_trade_fr', 'alpha_trade_cn')
STATE_DIRS = {'q051_paper', 'options_directional', 'llm_directional', 'market_regime',
              'protection_states', 'config_vault', 'ihm_preferences', 'risk_decision_audit'}


def scope(profile):
    if profile not in (FULL, US_DAILY):
        raise ValueError('Profil de sauvegarde inconnu')
    return US_DATABASES if profile == US_DAILY else DATABASES


def payload_scope(payload):
    names = scope(payload.get('backup_profile', FULL))
    if set(payload.get('databases', {})) != set(names):
        raise ValueError('Bases du manifeste incompatibles avec le profil de sauvegarde')
    return names


def model_folder(root, batch):
    if not isinstance(batch, str) or not re.fullmatch(r'model-factory-[A-Za-z0-9_-]+', batch):
        raise ValueError('Sélectionner un modèle Oracle terminé')
    folder = Path(root)/'artifacts/models'/batch
    if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
        raise ValueError('Répertoire du modèle absent ou non portable')
    return folder


def model_info(root, batch):
    folder = model_folder(root, batch)
    protocol = json.loads((folder/'oracle_path/protocol.json').read_text(encoding='utf-8'))
    report = json.loads((folder/'oracle_path/report.json').read_text(encoding='utf-8'))
    if (protocol.get('batch_id') != batch or report.get('status') != 'completed'
            or report.get('serving_ready') is not True or protocol.get('serving_ready') is not True):
        raise ValueError('Modèle non terminé ou non utilisable en prédiction')
    universe = protocol.get('universe')
    if not isinstance(universe, list) or not universe or any(not isinstance(s, str) for s in universe):
        raise ValueError('Univers du modèle absent')
    training = protocol.get('training_config') or {}
    return dict(batch_id=batch, horizon=protocol.get('horizon'), universe=universe,
                directional=bool(training.get('oracle_path_directional_enabled')),
                feature_mode=(protocol.get('directional_contract') or {}).get('feature_mode'),
                anti_sl=bool(training.get('oracle_path_anti_sl_enabled')),
                comment=training.get('comment') or report.get('comment') or '')


def list_models(root):
    result = []
    for folder in sorted((Path(root)/'artifacts/models').glob('model-factory-*'), reverse=True):
        try:
            info = model_info(root, folder.name)
        except (OSError, ValueError, TypeError, KeyError):
            continue
        result.append(info)
    return result


def selected_config(root, batch):
    """Only the archived copy is changed; source trading settings stay intact."""
    info = model_info(root, batch)
    cfg = yaml.safe_load((Path(root)/'config.yaml').read_text(encoding='utf-8')) or {}
    pipeline = cfg.get('us_pipeline') or {}
    for name in ('q051_vol20_regime', 'b_anti_sl_reference'):
        policy = pipeline.get(name) or {}
        if policy.get('enabled'):
            if info['horizon'] != 10 or not info['directional']:
                raise ValueError('Le parcours quotidien actif exige Oracle H10 + modèles LONG par titre')
            if name == 'b_anti_sl_reference' and info['feature_mode'] != 'compact_volatility':
                raise ValueError('Le parcours B actif exige les variables compact_volatility')
            if name == 'b_anti_sl_reference' and policy.get('apply_anti_sl', True) and not info['anti_sl']:
                raise ValueError('Le filtre anti-SL actif exige un modèle anti-SL dans le batch choisi')
        if name in pipeline:
            pipeline[name]['model_batch_id'] = batch
            pipeline[name]['artifacts_dir'] = 'artifacts/models'
    for name in ('llm_directional_filter', 'options_directional_filter'):
        if isinstance(cfg.get(name), dict):
            cfg[name]['default_oracle_batch_id'] = batch
    if isinstance(cfg.get('batch_diagnostics'),dict):
        cfg['batch_diagnostics']['live_batch_id']=batch
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False).encode('utf-8')


def file_included(relative, batch):
    """Prune generated trees before walking, especially intraday raw archives."""
    p = relative.parts
    if not p:
        return True
    if p[0] in ('doc', 'docs', 'tests', 'notebooks', 'outputs', 'output', 'log', 'logs',
                'data', 'datasets', 'node_modules', 'work'):
        return False
    if p[0] == 'artifacts':
        if len(p) == 1:
            return True
        if p[1] == 'models':
            if len(p) == 2:
                return True
            if p[2] != batch:
                return False
            # Model contracts/weights/checksummed fold files are retained. Raw
            # training matrices and aggregate research panels are not served.
            if 'chunks' in p[3:] or 'oos' in p[3:]:
                return False
            if relative.name in ('labels.parquet', 'oof_predictions.parquet',
                                 'training-panel.parquet', 'oof-pool.parquet'):
                return False
            return True
        if p[1] in STATE_DIRS:
            return True
        return p[1] == 'operations' and (len(p) == 2 or p[2] == 'us_pipeline')
    # Python source in analyst_research is imported by some application modules;
    # data/results under it are excluded.
    if p[0] == 'analyst_research':
        return relative.suffix == '.py' or not relative.suffix
    return True


def news_context_days(root=None):
    cfg=(yaml.safe_load((Path(root)/'config.yaml').read_text(encoding='utf-8')) or {}) if root else {}
    recalc=(cfg.get('sentiment_news_ingestion') or {}).get('pipeline_feature_recalc_days',52)
    if type(recalc) is not int or not 1<=recalc<=365:
        raise ValueError('Fenêtre de recalcul sentiment non qualifiée pour la sauvegarde')
    # The daily recalculation rereads 45 preceding calendar days of context.
    return max(90,recalc+45+3)


def evidence_windows(root=None):
    cfg=(yaml.safe_load((Path(root)/'config.yaml').read_text(encoding='utf-8')) or {}) if root else {}
    llm=cfg.get('llm_directional_filter') or {}
    consensus=llm.get('consensus_max_age_days',7)
    sec=llm.get('evidence_sec_max_age_days',14)
    if type(consensus) is not int or not 1<=consensus<=30 or type(sec) is not int or not 1<=sec<=60:
        raise ValueError('Fenêtres de fraîcheur des preuves non qualifiées')
    return dict(consensus_days=max(14,consensus+3),sec_days=max(30,sec+3))


def policy_summary(batch,root=None):
    return dict(profile=US_DAILY, selected_model=batch, databases=['alpha_trade'],
                daily_context_calendar_days=1120, recent_calendar_days=90,
                news_context_calendar_days=news_context_days(root),
                consensus_calendar_days=evidence_windows(root)['consensus_days'],
                sec_calendar_days=evidence_windows(root)['sec_days'],options_calendar_days=7,
                intraday_calendar_days=7, account_state='complete',
                excluded=['FR/CN', 'autres modèles', 'backtests', 'matrices d’entraînement',
                          'anciennes bougies intraday', 'anciennes archives fournisseur'],
                training_supported=False, historical_backtests_supported=False)
