"""Read-only diagnostic contract for path-amplitude models, never terminal labels."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

MODE='oracle_path_h20'
TARGET='oracle_path_extreme20'


def metadata_dict(value):
    if isinstance(value,dict):return value
    try:
        parsed=json.loads(value) if isinstance(value,str) and value.strip() else {}
        return parsed if isinstance(parsed,dict) else {}
    except (ValueError,TypeError):return {}


def is_path_model(batch_id,metadata,artifacts_root):
    meta=metadata_dict(metadata)
    cli=meta.get('cli_options') or {}
    training=meta.get('training_config') or {}
    data=(training.get('data') or {}) if isinstance(training,dict) else {}
    declared=(isinstance(cli,dict) and cli.get('oracle_path_model_only') is True) or (
        isinstance(data,dict) and data.get('oracle_path_model_only') is True) or meta.get('mode')==MODE
    batch=str(batch_id)
    if not batch or Path(batch).name!=batch or '/' in batch or '\\' in batch:return False
    root=Path(artifacts_root)
    folder=root if root.name==batch else root/batch
    return bool(declared or (folder/'oracle_path/protocol.json').is_file())


def artifact_signature(batch_id,artifacts_root):
    root=Path(artifacts_root)
    folder=(root if root.name==batch_id else root/batch_id)/'oracle_path'
    files=[folder/name for name in ('protocol.json','report.json','feature_profile.json','progress.json')]
    if (folder/'folds').is_dir():
        files.extend(p for p in (folder/'folds').glob('*/*')
            if p.name in ('done.json','path_model.txt','catboost_model.cbm','oof.parquet'))
    return tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in files if p.is_file())


def load_path_artifacts(batch_id,artifacts_root):
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.train import digest
    root=Path(artifacts_root)
    folder=(root if root.name==batch_id else root/batch_id)/'oracle_path'
    view=dict(batch_id=batch_id,root=str(folder),ready=False,errors=[],warnings=[],progress={},periods=[])
    try:
        if (folder/'progress.json').is_file():view['progress']=json.loads((folder/'progress.json').read_text(encoding='utf-8'))
        if not (folder/'report.json').is_file():
            view['warnings'].append("Rapport parcours absent : entraînement en cours ou artefacts incomplets.")
            return view
        verified_root,protocol,profile,folds=load_contract(artifacts_root,batch_id)
        report=json.loads((verified_root/'report.json').read_text(encoding='utf-8'))
        if int(report['n_features'])!=len(profile['feature_columns']):raise ValueError('Nombre de features incohérent')
        summaries={item['fold_start']:item for item in report['folds']}
        if len(summaries)!=len(report['folds']) or set(summaries)!=set(folds):
            raise ValueError('Folds du rapport incohérents')
        days,symbols=set(),set();rows=0;fold_rows=[]
        for name,fold in folds.items():
            metrics=fold['metrics']
            if summaries[name]!=metrics:raise ValueError('Métriques du rapport différentes du fold '+name)
            if not (pd.Timestamp(metrics['train_available_max'])<pd.Timestamp(metrics['val_start'])
                    and pd.Timestamp(metrics['val_available_max'])<pd.Timestamp(metrics['test_start'])):
                raise ValueError('Disponibilité non causale du fold '+name)
            done=json.loads((verified_root/'folds'/name/'done.json').read_text(encoding='utf-8'))
            oof=verified_root/'folds'/name/'oof.parquet'
            if done['files'].get('oof.parquet')!=digest(oof):raise ValueError('Prédictions OOF corrompues : '+name)
            keys=pd.read_parquet(oof,columns=['date','symbol'])
            keys['date']=pd.to_datetime(keys.date,errors='raise').dt.normalize()
            if keys.empty or keys.isna().any().any() or keys.duplicated(['date','symbol']).any():
                raise ValueError('Clés OOF invalides : '+name)
            dates=set(keys.date)
            if days & dates:raise ValueError('Dates de test réutilisées entre folds')
            if (len(keys)!=int(metrics['rows']) or len(dates)!=int(metrics['dates'])
                    or keys.date.min()<pd.Timestamp(metrics['test_start'])
                    or keys.date.max()>pd.Timestamp(metrics['test_end'])):
                raise ValueError('Couverture OOF différente du rapport : '+name)
            days.update(dates);symbols.update(keys.symbol);rows+=len(keys)
            fold_rows.append(dict(Fold=name,Algorithme=fold['backend'],Début=str(keys.date.min().date()),
                Fin=str(keys.date.max().date()),Séances=len(dates),Lignes=len(keys),
                AUC=metrics.get('auc'),**{'Précision 10 titres':metrics.get('precision_top_10_titles'),
                    'Précision 20 titres':metrics.get('precision_top_20_titles'),
                    'Précision 50 titres':metrics.get('precision_top_50_titles'),
                    'Amplitude 10 titres (%)':metrics.get('mean_path_amplitude_top_10_titles_pct')}))
        if rows!=int(report['overall']['rows']) or len(days)!=int(report['overall']['dates']):
            raise ValueError('Couverture OOF agrégée incohérente')
        view.update(ready=True,protocol=protocol,profile=profile,report=report,folds=folds,fold_rows=fold_rows,
            profile_sha256=digest(verified_root/'feature_profile.json'),
            oof_coverage=dict(min_date=min(days),max_date=max(days),nb_dates=len(days),nb_symbols=len(symbols),n_rows=rows))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        view['errors'].append(str(exc))
    return view


SQL_PERIODS='''SELECT MIN(prediction_date) AS min_date,MAX(prediction_date) AS max_date,
COUNT(DISTINCT prediction_date) AS nb_dates,COUNT(DISTINCT symbol) AS nb_symbols,
COUNT(*) AS n_rows FROM alpha_trade.oracle_extreme_predictions WHERE batch_id=:batch_id'''


def read_sql_periods(engine,batch_id,view):
    result=dict(coverage={},matching_lineage_rows=None,errors=[])
    if engine is None:
        result['errors'].append('Connexion SQL indisponible ; les périodes OOF locales restent distinctes.')
        return result
    if getattr(engine.url,'database',None)!='alpha_trade':
        result['errors'].append('La lecture des prédictions parcours exige la base US alpha_trade.')
        return result
    try:connection=engine.connect()
    except Exception as exc:
        result['errors'].append('Connexion SQL impossible ('+type(exc).__name__+').')
        return result
    with connection as conn:
        try:result['coverage']=dict(conn.execute(text(SQL_PERIODS),{'batch_id':batch_id}).mappings().one())
        except Exception as exc:
            result['errors'].append('Lecture des prédictions SQL impossible ('+type(exc).__name__+').')
            return result
        if not result['coverage']['n_rows'] or not view.get('ready'):return result
        conditions=[];params=dict(batch_id=batch_id,profile=view['profile_sha256'],target=TARGET)
        for i,(name,fold) in enumerate(view['folds'].items()):
            conditions.append(f'(l.fold_start=:fold{i} AND l.model_sha256=:hash{i} AND l.model_available_date=:available{i})')
            params.update({f'fold{i}':name,f'hash{i}':fold['model_sha256'],f'available{i}':str(max(
                pd.Timestamp(fold['metrics'][key]) for key in ('train_available_max','val_available_max')).date())})
        sql='''SELECT COUNT(*) FROM alpha_trade.oracle_extreme_predictions p
JOIN alpha_trade.oracle_path_prediction_lineage l ON l.batch_id=p.batch_id
AND l.prediction_date=p.prediction_date AND l.symbol=p.symbol
WHERE p.batch_id=:batch_id AND p.fold_start=l.fold_start
AND p.future_return IS NULL AND p.oracle_extreme10 IS NULL
AND p.proba_extreme BETWEEN 0 AND 1 AND l.target_name=:target AND l.target_horizon=20
AND l.feature_profile_sha256=:profile AND l.model_available_date<p.prediction_date
AND ('''+ ' OR '.join(conditions)+')'
        try:result['matching_lineage_rows']=int(conn.execute(text(sql),params).scalar_one())
        except Exception as exc:
            result['errors'].append('Filiation parcours non vérifiable ('+type(exc).__name__+').')
    return result


def period_rows(view,sql):
    rows=[]
    for label,coverage,source in (
        ('Prédictions SQL',sql.get('coverage') or {},'oracle_extreme_predictions + filiation parcours'),
        ('Tests OOF du training',view.get('oof_coverage') or {},'oracle_path/folds/*/oof.parquet, vérifiés')):
        first,last=coverage.get('min_date'),coverage.get('max_date')
        if not coverage.get('n_rows') or pd.isna(first) or pd.isna(last):continue
        rows.append({'Source':label,'Période':f'{pd.Timestamp(first).date()} → {pd.Timestamp(last).date()}',
            'Séances':int(coverage['nb_dates']),'Symboles':int(coverage['nb_symbols']),
            'Lignes':int(coverage['n_rows']),'Détail':source})
    return rows


def top_k_rows(report):
    overall=report.get('overall') or {}
    return [{'Sélection':f'{count} premiers titres','Précision véritable TOP20 %':overall.get(f'precision_top_{count}_titles'),
        'Amplitude maximale moyenne (%)':overall.get(f'mean_path_amplitude_top_{count}_titles_pct'),
        'Séances évaluées':overall.get(f'dates_top_{count}_titles')} for count in (10,20,50)]
