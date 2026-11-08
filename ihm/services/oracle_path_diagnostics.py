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
        isinstance(data,dict) and data.get('oracle_path_model_only') is True) or meta.get('mode') in (
            'oracle_path_h10','oracle_path_h15',MODE)
    batch=str(batch_id)
    if not batch or Path(batch).name!=batch or '/' in batch or '\\' in batch:return False
    root=Path(artifacts_root)
    folder=root if root.name==batch else root/batch
    return bool(declared or (folder/'oracle_path/protocol.json').is_file())


def artifact_signature(batch_id,artifacts_root):
    root=Path(artifacts_root)
    folder=(root if root.name==batch_id else root/batch_id)/'oracle_path'
    files=[folder/name for name in ('protocol.json','report.json','feature_profile.json','progress.json')]
    files.append(folder/'directional/manifest.json')
    files.append(folder/'directional/benchmark.parquet')
    files.extend((folder/'directional/diagnostics').glob('*'))
    files.extend((folder/'directional/oos').glob('*.parquet'))
    if (folder/'directional').is_dir():
        files.extend((folder/'directional').glob('*/*.joblib'))
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
            from pyarrow.parquet import read_schema
            if not {'date','symbol',protocol['target'],'proba_path_extreme','path_amplitude'}.issubset(read_schema(oof).names):
                raise ValueError('Schéma OOF différent de la cible parcours : '+name)
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
        if protocol.get('training_config',{}).get('oracle_path_directional_enabled'):
            # load_contract has already verified this manifest, every model hash
            # and their causal availability. Do not deserialize weights in UI.
            manifest=json.loads((verified_root/'directional/manifest.json').read_text(encoding='utf-8'))
            summary=directional_summary(protocol,manifest)
            if (summary['models']!=report.get('directional_models')
                    or summary['skipped']!=report.get('directional_skipped')):
                raise ValueError('Compteurs per-symbol différents du manifeste vérifié')
            summary['manifest_sha256']=digest(verified_root/'directional/manifest.json')
            supplemental=verified_root/'directional/diagnostics/report.json'
            metrics_records=manifest['models']
            oos_files=manifest.get('oos_files',[]);oos_root=verified_root
            if supplemental.is_file():
                evaluation=json.loads(supplemental.read_text(encoding='utf-8'))
                if (evaluation.get('status')!='COMPLETED'
                        or evaluation.get('manifest_sha256')!=summary['manifest_sha256']
                        or evaluation.get('oracle_protocol_sha256')!=digest(verified_root/'protocol.json')
                        or evaluation.get('source_hashes')!=manifest['source_hashes']):
                    raise ValueError('Diagnostics per-symbol absents/incompatibles avec les modèles')
                expected={(r['symbol'],r['year'],r['side']):r['sha256'] for r in manifest['models']}
                actual={(r['symbol'],r['year'],r['side']):r['model_sha256'] for r in evaluation['models']}
                if actual!=expected or len(actual)!=len(evaluation['models']):
                    raise ValueError('Couverture des diagnostics per-symbol incomplète')
                for file in [dict(path=evaluation['benchmark_file'],sha256=evaluation['benchmark_sha256']),*evaluation['oos_files']]:
                    path=(supplemental.parent/file['path']).resolve()
                    if not path.is_relative_to(supplemental.parent.resolve()) or digest(path)!=file['sha256']:
                        raise ValueError('Fichier de diagnostic per-symbol corrompu')
                metrics_records=evaluation['models']
                oos_files=evaluation['oos_files'];oos_root=supplemental.parent
                summary['benchmark_reconstructed_from_SQL']=evaluation.get('benchmark_reconstructed_from_SQL',False)
            summary['metrics_rows']=directional_metric_rows(metrics_records)
            summary['oos_coverage']=directional_oos_coverage(oos_root,oos_files)
            progress_file=verified_root/'directional/diagnostics/progress.json'
            if progress_file.is_file():
                summary['diagnostic_progress']=json.loads(progress_file.read_text(encoding='utf-8'))
            view['directional']=summary
    except (OSError,ValueError,KeyError,TypeError) as exc:
        view['ready']=False
        view['errors'].append(str(exc))
    return view


def directional_summary(protocol,manifest):
    """Describe trained artifacts, never present fit counts as predictive skill."""
    models=manifest['models'];skipped=manifest['skipped'];universe=set(protocol['universe'])
    years=sorted({int(r['year']) for r in [*models,*skipped]})
    details=[];coverage=[];omissions=[]
    for row in models:
        details.append({'Symbole':row['symbol'],'Année d’utilisation':int(row['year']),
            'Direction':row['side'].upper(),'Début entraînement':row['fit_start'],
            'Fin entraînement':row['fit_end'],'Début calibration':row['calibration_start'],
            'Fin calibration':row['calibration_end'],'Disponible après':row['available'],
            'Séances entraînement':row['fit_rows'],'Séances calibration':row['calibration_rows'],
            'Fichier':row['file'],'SHA-256':row['sha256']})
    for year in years:
        selected=[r for r in models if int(r['year'])==year]
        long={r['symbol'] for r in selected if r['side']=='long'}
        short={r['symbol'] for r in selected if r['side']=='short'}
        coverage.append({'Année d’utilisation':year,'Titres de l’univers':len(universe),
            'Titres avec LONG':len(long),'Titres avec SHORT':len(short),
            'Sans modèle LONG':len(universe-long),'Sans modèle SHORT':len(universe-short)})
    reasons={'INSUFFICIENT_HISTORY_OR_CLASSES':'Historique ou exemples de chaque classe insuffisants',
             'CONSTANT_CALIBRATION':'Prédictions constantes sur la calibration'}
    for row in skipped:
        omissions.append({'Symbole':row['symbol'],'Année d’utilisation':int(row['year']),
            'Direction':row['side'].upper(),'Motif':reasons.get(row['reason'],row['reason'])})
    return dict(models=len(models),long_models=sum(r['side']=='long' for r in models),
        short_models=sum(r['side']=='short' for r in models),skipped=len(skipped),
        universe_size=len(universe),features=len(manifest['features']),contract=manifest['contract'],
        serving_side=manifest['serving_side'],coverage=coverage,details=details,omissions=omissions)


def directional_metric_rows(records):
    rows=[]
    for record in records:
        for stage,metrics in record.get('metrics',{}).items():
            rows.append({'Symbole':record['symbol'],'Année d’utilisation':int(record['year']),
                'Direction':record['side'].upper(),'Échantillon':stage,
                'Observations':metrics['n'],'AUC':metrics.get('auc'),
                'Exactitude — seuil 0,5':metrics.get('accuracy'),
                'Exactitude équilibrée':metrics.get('balanced_accuracy'),
                'Précision des scores ≥ 0,5':metrics.get('precision_at_05'),
                'Scores ≥ 0,5':metrics.get('selected_at_05'),
                'Fréquence de gains dans les labels':metrics.get('positive_rate'),
                'Brier':metrics.get('brier')})
    return rows


def directional_oos_coverage(root,files):
    from modelFactory.oracle_path.train import digest
    root=Path(root).resolve();counts={side:dict(days=set(),symbols=set(),rows=0) for side in ('long','short')}
    for record in files:
        path=(root/record['path']).resolve()
        if not path.is_relative_to(root) or digest(path)!=record['sha256']:
            raise ValueError('Prédictions test per-symbol manquantes/corrompues')
        keys=pd.read_parquet(path,columns=['date','symbol','side'])
        if (len(keys)!=record['rows'] or keys.isna().any().any() or keys.duplicated().any()
                or not keys.side.isin(counts).all()):
            raise ValueError('Clés test per-symbol invalides')
        for side,part in keys.groupby('side'):
            counts[side]['days'].update(pd.to_datetime(part.date))
            counts[side]['symbols'].update(part.symbol);counts[side]['rows']+=len(part)
    return {side:dict(min_date=min(c['days']) if c['days'] else None,
        max_date=max(c['days']) if c['days'] else None,nb_dates=len(c['days']),
        nb_symbols=len(c['symbols']),n_rows=c['rows']) for side,c in counts.items()}


SQL_PERIODS='''SELECT MIN(prediction_date) AS min_date,MAX(prediction_date) AS max_date,
COUNT(DISTINCT prediction_date) AS nb_dates,COUNT(DISTINCT symbol) AS nb_symbols,
COUNT(*) AS n_rows FROM alpha_trade.oracle_extreme_predictions WHERE batch_id=:batch_id'''


def read_sql_periods(engine,batch_id,view):
    result=dict(coverage={},matching_lineage_rows=None,errors=[],directional={})
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
        if hasattr(conn,'execution_options'):
            # Scores and lineage are committed together by predict. Keep the two
            # aggregates in one stable read snapshot while collection continues.
            conn=conn.execution_options(isolation_level='REPEATABLE READ')
        try:result['coverage']=dict(conn.execute(text(SQL_PERIODS),{'batch_id':batch_id}).mappings().one())
        except Exception as exc:
            result['errors'].append('Lecture des prédictions SQL impossible ('+type(exc).__name__+').')
            return result
        if view.get('directional'):
            for side in ('long','short'):
                # Count actual scores, not placeholder rows with NULL probability.
                query=f'''SELECT MIN(prediction_date) AS min_date,MAX(prediction_date) AS max_date,
COUNT(DISTINCT prediction_date) AS nb_dates,COUNT(DISTINCT symbol) AS nb_symbols,COUNT(*) AS n_rows,
SUM(CASE WHEN manifest_sha256=:manifest AND {side}_probability BETWEEN 0 AND 1
AND {side}_model_sha256 IS NOT NULL THEN 1 ELSE 0 END) AS matching_manifest_rows
FROM alpha_trade.oracle_path_directional_predictions
WHERE batch_id=:batch_id AND {side}_probability IS NOT NULL'''
                try:
                    coverage=dict(conn.execute(text(query),dict(batch_id=batch_id,
                        manifest=view['directional']['manifest_sha256'])).mappings().one())
                    result['directional'][side]=coverage
                    if coverage['n_rows'] and coverage['matching_manifest_rows']!=coverage['n_rows']:
                        result['errors'].append(f'Scores per-symbol {side.upper()} : manifeste/probabilités non qualifiés.')
                except Exception as exc:
                    result['errors'].append(f'Lecture des périodes per-symbol {side.upper()} impossible ({type(exc).__name__}).')
        if not result['coverage']['n_rows'] or not view.get('ready'):return result
        protocol=view.get('protocol') or {}
        conditions=[];params=dict(batch_id=batch_id,profile=view['profile_sha256'],
            target=protocol.get('target',TARGET),horizon=protocol.get('horizon',20))
        for i,(name,fold) in enumerate(view['folds'].items()):
            conditions.append(f'(l.fold_start=:fold{i} AND l.model_sha256=:hash{i} AND l.model_available_date=:available{i})')
            params.update({f'fold{i}':name,f'hash{i}':fold['model_sha256'],f'available{i}':str(max(
                pd.Timestamp(fold['metrics'][key]) for key in ('train_available_max','val_available_max')).date())})
        sql='''SELECT COUNT(*) FROM alpha_trade.oracle_extreme_predictions p
JOIN alpha_trade.oracle_path_prediction_lineage l ON l.batch_id=p.batch_id
AND l.prediction_date=p.prediction_date AND l.symbol=p.symbol
WHERE p.batch_id=:batch_id AND p.fold_start=l.fold_start
AND p.future_return IS NULL AND p.oracle_extreme10 IS NULL
AND p.proba_extreme BETWEEN 0 AND 1 AND l.target_name=:target AND l.target_horizon=:horizon
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
    if view.get('directional'):
        for side in ('long','short'):
            coverage=(sql.get('directional') or {}).get(side)
            if coverage is None:
                detail='Période SQL non vérifiable ; consulter les erreurs.'
            elif not coverage.get('n_rows'):
                detail=f'Modèles entraînés ; aucune prédiction {side.upper()} enregistrée en SQL pour ce batch.'
            else:
                detail='oracle_path_directional_predictions — scores non NULL, distincts des tests Oracle OOF'
            first,last=(coverage or {}).get('min_date'),(coverage or {}).get('max_date')
            period=(f'{pd.Timestamp(first).date()} → {pd.Timestamp(last).date()}'
                    if first is not None and last is not None else '—')
            rows.append({'Source':f'Per-symbol {side.upper()} — SQL','Période':period,
                'Séances':int((coverage or {}).get('nb_dates') or 0),
                'Symboles':int((coverage or {}).get('nb_symbols') or 0),
                'Lignes':int((coverage or {}).get('n_rows') or 0),'Détail':detail})
            oos=(view['directional'].get('oos_coverage') or {}).get(side) or {}
            if oos.get('n_rows'):
                rows.append({'Source':f'Tests OOS per-symbol {side.upper()}',
                    'Période':f"{pd.Timestamp(oos['min_date']).date()} → {pd.Timestamp(oos['max_date']).date()}",
                    'Séances':int(oos['nb_dates']),'Symboles':int(oos['nb_symbols']),'Lignes':int(oos['n_rows']),
                    'Détail':'Fichiers de test par titre, vérifiés ; distincts des prédictions SQL et de l’OOF Oracle'})
    return rows


def top_k_rows(report):
    overall=report.get('overall') or {}
    return [{'Sélection':f'{count} premiers titres','Précision véritable TOP20 %':overall.get(f'precision_top_{count}_titles'),
        'Amplitude maximale moyenne (%)':overall.get(f'mean_path_amplitude_top_{count}_titles_pct'),
        'Séances évaluées':overall.get(f'dates_top_{count}_titles')} for count in (10,20,50)]
